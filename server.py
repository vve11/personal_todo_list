import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps
from typing import Optional

from flask import Flask, request, jsonify, send_from_directory, abort, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, inspect, text
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-todo-secret-change-me")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "http://127.0.0.1:5173",
                "http://localhost:5173",
                "http://127.0.0.1:5050",
                "http://localhost:5050",
            ],
            "supports_credentials": True,
        }
    },
)

_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "todos.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{_db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

NOTIFY_BEFORE_HOURS = int(os.environ.get("NOTIFY_BEFORE_HOURS", "24"))
NOTIFY_COOLDOWN_HOURS = int(os.environ.get("NOTIFY_COOLDOWN_HOURS", "6"))


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, default="You")
    email = db.Column(db.String(255), nullable=False, unique=True, default="")
    password_hash = db.Column(db.String(255), nullable=True)
    notifications_enabled = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    tasks = db.relationship("Task", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password: str):
        # pbkdf2: Apple CLT Python builds often lack hashlib.scrypt
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "notifications_enabled": self.notifications_enabled,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }


class Task(db.Model):
    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    due_at = db.Column(db.DateTime, nullable=True)
    last_notified_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "completed": self.completed,
            "sort_order": self.sort_order,
            "due_at": self.due_at.isoformat() + "Z" if self.due_at else None,
            "last_notified_at": self.last_notified_at.isoformat() + "Z"
            if self.last_notified_at
            else None,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }


def _next_sort_order(user_id: int):
    m = (
        db.session.query(func.max(Task.sort_order))
        .filter(Task.user_id == user_id)
        .scalar()
    )
    return (m or -1) + 1


def _renumber_tasks(user_id: int):
    tasks = (
        Task.query.filter_by(user_id=user_id)
        .order_by(Task.sort_order, Task.id)
        .all()
    )
    for i, t in enumerate(tasks):
        t.sort_order = i
    db.session.commit()


def _ensure_schema():
    db.create_all()
    insp = inspect(db.engine)
    user_cols = {c["name"] for c in insp.get_columns("users")}
    task_cols = {c["name"] for c in insp.get_columns("tasks")}

    if "notifications_enabled" not in user_cols:
        db.session.execute(
            text(
                "ALTER TABLE users ADD COLUMN notifications_enabled BOOLEAN NOT NULL DEFAULT 1"
            )
        )
    if "password_hash" not in user_cols:
        db.session.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))

    if "due_at" not in task_cols:
        db.session.execute(text("ALTER TABLE tasks ADD COLUMN due_at DATETIME"))
    if "last_notified_at" not in task_cols:
        db.session.execute(text("ALTER TABLE tasks ADD COLUMN last_notified_at DATETIME"))
    if "user_id" not in task_cols:
        db.session.execute(text("ALTER TABLE tasks ADD COLUMN user_id INTEGER"))
        # Attach orphan tasks to the first user, or create a placeholder owner.
        first = db.session.execute(text("SELECT id FROM users ORDER BY id LIMIT 1")).fetchone()
        if first is None:
            db.session.execute(
                text(
                    "INSERT INTO users (name, email, notifications_enabled, created_at, updated_at) "
                    "VALUES ('You', 'legacy@local', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            first = db.session.execute(text("SELECT id FROM users ORDER BY id LIMIT 1")).fetchone()
        owner_id = first[0]
        db.session.execute(
            text("UPDATE tasks SET user_id = :uid WHERE user_id IS NULL"),
            {"uid": owner_id},
        )

    # Ensure any remaining null user_id rows are owned.
    db.session.execute(
        text(
            "UPDATE tasks SET user_id = (SELECT id FROM users ORDER BY id LIMIT 1) "
            "WHERE user_id IS NULL"
        )
    )
    db.session.commit()


def _parse_due_at(value):
    if value is None or value == "":
        return None, None
    if not isinstance(value, str):
        return None, "due_at must be an ISO datetime string"
    s = value.strip()
    if not s:
        return None, None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None, "due_at is invalid"
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt, None


def _task_urgency(task: Task, now: Optional[datetime] = None):
    if task.completed or task.due_at is None:
        return None
    now = now or datetime.utcnow()
    seconds_left = (task.due_at - now).total_seconds()
    if seconds_left < 0:
        return "overdue"
    if seconds_left <= NOTIFY_BEFORE_HOURS * 3600:
        return "due_soon"
    return None


def _deadline_message(task: Task, urgency: str) -> str:
    when = task.due_at.strftime("%Y-%m-%d %H:%M UTC")
    if urgency == "overdue":
        return f'Task "{task.title}" is overdue (deadline was {when}).'
    return f'Task "{task.title}" is due soon (deadline: {when}).'


def _should_send_notification(task: Task, now: datetime) -> bool:
    urgency = _task_urgency(task, now)
    if urgency is None:
        return False
    if task.last_notified_at is None:
        return True
    cooldown = timedelta(hours=NOTIFY_COOLDOWN_HOURS)
    return now - task.last_notified_at >= cooldown


def _send_email(to_addr: str, subject: str, body: str):
    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        return False, "SMTP not configured (set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS)"
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASS", "").strip()
    from_addr = os.environ.get("SMTP_FROM", user or "todo@localhost").strip()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.ehlo()
            if os.environ.get("SMTP_TLS", "1") != "0":
                smtp.starttls()
                smtp.ehlo()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
    except OSError as exc:
        return False, f"Email failed: {exc}"
    return True, "sent"


def _notification_payload(task: Task, urgency: str):
    return {
        "task_id": task.id,
        "title": task.title,
        "due_at": task.due_at.isoformat() + "Z" if task.due_at else None,
        "urgency": urgency,
        "message": _deadline_message(task, urgency),
    }


with app.app_context():
    _ensure_schema()


def _current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return db.session.get(User, uid)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = _current_user()
        if user is None:
            return jsonify({"error": "Login required"}), 401
        return fn(user, *args, **kwargs)

    return wrapper


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _get_task_for_user_or_404(user: User, tid: int):
    t = Task.query.filter_by(id=tid, user_id=user.id).first()
    if t is None:
        return None, (jsonify({"error": "Task not found"}), 404)
    return t, None


@app.post("/api/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = _normalize_email(data.get("email"))
    password = data.get("password") or ""

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "valid email is required"}), 400
    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email is already registered"}), 409

    user = User(name=name[:120], email=email[:255], notifications_enabled=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    return jsonify(user.to_dict()), 201


@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = _normalize_email(data.get("email"))
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        return jsonify({"error": "invalid email or password"}), 401

    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    return jsonify(user.to_dict())


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/auth/me")
def auth_me():
    user = _current_user()
    if user is None:
        return jsonify({"user": None})
    return jsonify({"user": user.to_dict()})


@app.get("/api/user")
@login_required
def get_user(user: User):
    return jsonify(user.to_dict())


@app.patch("/api/user")
@login_required
def update_user(user: User):
    data = request.get_json(silent=True) or {}
    if "name" in data:
        s = (data.get("name") or "").strip()
        if not s:
            return jsonify({"error": "name must not be empty"}), 400
        user.name = s[:120]
    if "email" in data:
        email = _normalize_email(data.get("email"))
        if not email or "@" not in email:
            return jsonify({"error": "email is invalid"}), 400
        other = User.query.filter(User.email == email, User.id != user.id).first()
        if other:
            return jsonify({"error": "email is already registered"}), 409
        user.email = email[:255]
    if "notifications_enabled" in data:
        user.notifications_enabled = bool(data["notifications_enabled"])
    if "password" in data and data.get("password"):
        password = data.get("password") or ""
        if len(password) < 6:
            return jsonify({"error": "password must be at least 6 characters"}), 400
        user.set_password(password)
    user.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(user.to_dict())


@app.get("/api/tasks")
@login_required
def list_tasks(user: User):
    items = (
        Task.query.filter_by(user_id=user.id)
        .order_by(Task.sort_order, Task.id)
        .all()
    )
    return jsonify([t.to_dict() for t in items])


@app.post("/api/tasks")
@login_required
def create_task(user: User):
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    due_at, due_err = _parse_due_at(data.get("due_at"))
    if due_err:
        return jsonify({"error": due_err}), 400
    task = Task(
        user_id=user.id,
        title=title[:500],
        completed=bool(data.get("completed", False)),
        sort_order=_next_sort_order(user.id),
        due_at=due_at,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@app.patch("/api/tasks/<int:task_id>")
@login_required
def update_task(user: User, task_id: int):
    t, err = _get_task_for_user_or_404(user, task_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    if "title" in data:
        s = (data.get("title") or "").strip()
        if not s:
            return jsonify({"error": "title must not be empty"}), 400
        t.title = s[:500]
    if "completed" in data:
        t.completed = bool(data["completed"])
    if "due_at" in data:
        due_at, due_err = _parse_due_at(data.get("due_at"))
        if due_err:
            return jsonify({"error": due_err}), 400
        t.due_at = due_at
        t.last_notified_at = None
    if "sort_order" in data and isinstance(data["sort_order"], int) and data["sort_order"] >= 0:
        t.sort_order = data["sort_order"]
    t.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(t.to_dict())


@app.put("/api/tasks/reorder")
@login_required
def reorder_tasks(user: User):
    data = request.get_json(silent=True) or {}
    ordered_ids = data.get("task_ids")
    if not isinstance(ordered_ids, list) or not ordered_ids:
        return jsonify({"error": "task_ids must be a non-empty array of task ids"}), 400
    all_ids = {r.id for r in Task.query.filter_by(user_id=user.id).all()}
    if not all(isinstance(tid, int) for tid in ordered_ids):
        return jsonify({"error": "task_ids must be integers"}), 400
    if set(ordered_ids) != all_ids or len(ordered_ids) != len(all_ids):
        return jsonify(
            {"error": "task_ids must list every task id exactly once in the desired order"}
        ), 400
    for i, tid in enumerate(ordered_ids):
        Task.query.filter_by(id=tid, user_id=user.id).update(
            {"sort_order": i, "updated_at": datetime.utcnow()}
        )
    db.session.commit()
    items = (
        Task.query.filter_by(user_id=user.id)
        .order_by(Task.sort_order, Task.id)
        .all()
    )
    return jsonify([t.to_dict() for t in items])


@app.delete("/api/tasks/<int:task_id>")
@login_required
def delete_task(user: User, task_id: int):
    t, err = _get_task_for_user_or_404(user, task_id)
    if err:
        return err
    db.session.delete(t)
    db.session.commit()
    _renumber_tasks(user.id)
    return "", 204


@app.get("/api/notifications/due")
@login_required
def list_due_notifications(user: User):
    now = datetime.utcnow()
    items = []
    for task in (
        Task.query.filter_by(user_id=user.id)
        .order_by(Task.sort_order, Task.id)
        .all()
    ):
        urgency = _task_urgency(task, now)
        if urgency:
            items.append(_notification_payload(task, urgency))
    return jsonify(
        {
            "notifications_enabled": user.notifications_enabled,
            "notify_before_hours": NOTIFY_BEFORE_HOURS,
            "items": items,
        }
    )


@app.post("/api/notifications/send")
@login_required
def send_notifications(user: User):
    if not user.notifications_enabled:
        return jsonify({"error": "Notifications are disabled in your profile"}), 400

    now = datetime.utcnow()
    due_tasks = []
    for task in (
        Task.query.filter_by(user_id=user.id).order_by(Task.due_at, Task.id).all()
    ):
        if _should_send_notification(task, now):
            due_tasks.append(task)

    if not due_tasks:
        return jsonify(
            {
                "sent": [],
                "skipped": [],
                "message": "No tasks need a reminder right now.",
            }
        )

    messages = []
    email_results = []
    for task in due_tasks:
        urgency = _task_urgency(task, now)
        msg = _deadline_message(task, urgency)
        messages.append(_notification_payload(task, urgency))
        task.last_notified_at = now

        if user.email:
            subject = (
                f"[Todo] Overdue: {task.title}"
                if urgency == "overdue"
                else f"[Todo] Due soon: {task.title}"
            )
            body = (
                f"Hi {user.name},\n\n"
                f"{msg}\n\n"
                "Open your todo list to mark it done or update the deadline.\n"
            )
            ok, detail = _send_email(user.email, subject, body)
            email_results.append(
                {"task_id": task.id, "email": user.email, "ok": ok, "detail": detail}
            )
        else:
            email_results.append(
                {
                    "task_id": task.id,
                    "email": None,
                    "ok": False,
                    "detail": "No email on profile — in-app notification only",
                }
            )

    db.session.commit()
    return jsonify(
        {
            "sent": messages,
            "email_results": email_results,
            "message": f"Notified about {len(messages)} task(s).",
        }
    )


def _client_dist() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "client", "dist")


def _html_help_no_build():
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Todo API</title>
  <style>body{font-family:system-ui,sans-serif;max-width:36rem;margin:2rem auto;padding:0 1rem;}
  code{background:#eee;padding:0 .25rem;}</style>
</head>
<body>
  <h1>API is running</h1>
  <p>The task UI is a separate <strong>React</strong> app. Use one of these:</p>
  <ol>
    <li><strong>Dev (recommended):</strong> in <code>client</code> run
      <code>npm run dev</code>, then open
      <a href="http://127.0.0.1:5173">http://127.0.0.1:5173</a> — Vite proxies <code>/api</code> to this server (default port 5050).</li>
    <li><strong>One port (API+UI):</strong> run <code>npm run build</code> in <code>client</code>, restart this app, and open the URL shown in the terminal (default <code>http://127.0.0.1:5050/</code>).</li>
  </ol>
  <p>API example: <code>GET <a href="/api/tasks">/api/tasks</a></code> (requires login)</p>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/")
def home():
    d = _client_dist()
    index = os.path.join(d, "index.html")
    if os.path.isfile(index):
        return send_from_directory(d, "index.html")
    return _html_help_no_build()


@app.get("/<path:path>")
def dist_files_or_spa(path: str):
    if path.startswith("api/") or path == "api":
        return jsonify({"error": "Not found"}), 404
    d = _client_dist()
    if ".." in path or path.startswith("\\"):
        abort(404)
    rel = path.replace("\\", "/").lstrip("/")
    full = os.path.normpath(os.path.join(d, rel))
    dist_n = os.path.normpath(d)
    if not full.startswith(dist_n + os.sep) and full != dist_n:
        abort(404)
    if rel and os.path.isfile(full):
        return send_from_directory(d, rel)
    index = os.path.join(d, "index.html")
    if os.path.isfile(index):
        return send_from_directory(d, "index.html")
    return _html_help_no_build()


if __name__ == "__main__":
    # use_reloader=False: debug mode with reloader spawns a second process and
    # often causes "Address already in use" / conflicts when restarting the server.
    # Default 5050: port 5000 is often already taken (other tools / stuck processes) and then URLs fail.
    port = int(os.environ.get("PORT", "5050"))
    # 0.0.0.0: listen on all interfaces; in the browser use http://127.0.0.1:<port>/
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Todo API: open http://127.0.0.1:{port}/  (API: /api/tasks, /api/auth/login)")
    app.run(debug=True, host=host, port=port, use_reloader=False, threaded=True)
