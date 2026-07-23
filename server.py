import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional

from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, inspect, text

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

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
    email = db.Column(db.String(255), nullable=False, default="")
    notifications_enabled = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

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
    

def _next_sort_order():
    m = db.session.query(func.max(Task.sort_order)).scalar()
    return (m or -1) + 1


def _renumber_tasks():
    tasks = Task.query.order_by(Task.sort_order, Task.id).all()
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
            text("ALTER TABLE users ADD COLUMN notifications_enabled BOOLEAN NOT NULL DEFAULT 1")
        )
    if "due_at" not in task_cols:
        db.session.execute(text("ALTER TABLE tasks ADD COLUMN due_at DATETIME"))
    if "last_notified_at" not in task_cols:
        db.session.execute(text("ALTER TABLE tasks ADD COLUMN last_notified_at DATETIME"))
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


def _get_task_or_404(tid: int):
    t = db.session.get(Task, tid)
    if t is None:
        return None, (jsonify({"error": "Task not found"}), 404)
    return t, None


_PROFILE_ID = 1


def _get_profile():
    u = db.session.get(User, _PROFILE_ID)
    if u is None:
        u = User(id=_PROFILE_ID, name="You", email="", notifications_enabled=True)
        db.session.add(u)
        db.session.commit()
    return u


@app.get("/api/user")
def get_user():
    return jsonify(_get_profile().to_dict())


@app.patch("/api/user")
def update_user():
    u = _get_profile()
    data = request.get_json(silent=True) or {}
    if "name" in data:
        s = (data.get("name") or "").strip()
        if not s:
            return jsonify({"error": "name must not be empty"}), 400
        u.name = s[:120]
    if "email" in data:
        email = (data.get("email") or "").strip()
        if email and "@" not in email:
            return jsonify({"error": "email is invalid"}), 400
        u.email = email[:255]
    if "notifications_enabled" in data:
        u.notifications_enabled = bool(data["notifications_enabled"])
    u.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(u.to_dict())


@app.get("/api/tasks")
def list_tasks():
    items = Task.query.order_by(Task.sort_order, Task.id).all()
    return jsonify([t.to_dict() for t in items])


@app.post("/api/tasks")
def create_task():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    due_at, due_err = _parse_due_at(data.get("due_at"))
    if due_err:
        return jsonify({"error": due_err}), 400
    task = Task(
        title=title[:500],
        completed=bool(data.get("completed", False)),
        sort_order=_next_sort_order(),
        due_at=due_at,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201

@app.patch("/api/tasks/<int:task_id>")
def update_task(task_id: int):
    t, err = _get_task_or_404(task_id)
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
def reorder_tasks():
    data = request.get_json(silent=True) or {}
    ordered_ids = data.get("task_ids")
    if not isinstance(ordered_ids, list) or not ordered_ids:
        return jsonify({"error": "task_ids must be a non-empty array of task ids"}), 400
    all_ids = {r.id for r in Task.query.all()}
    if not all(isinstance(tid, int) for tid in ordered_ids):
        return jsonify({"error": "task_ids must be integers"}), 400
    if set(ordered_ids) != all_ids or len(ordered_ids) != len(all_ids):
        return jsonify(
            {"error": "task_ids must list every task id exactly once in the desired order"}
        ), 400
    for i, tid in enumerate(ordered_ids):
        Task.query.filter_by(id=tid).update(
            {"sort_order": i, "updated_at": datetime.utcnow()}
        )
    db.session.commit()
    return jsonify([t.to_dict() for t in Task.query.order_by(Task.sort_order, Task.id).all()])


@app.delete("/api/tasks/<int:task_id>")
def delete_task(task_id: int):
    t, err = _get_task_or_404(task_id)
    if err:
        return err
    db.session.delete(t)
    db.session.commit()
    _renumber_tasks()
    return "", 204


@app.get("/api/notifications/due")
def list_due_notifications():
    now = datetime.utcnow()
    items = []
    for task in Task.query.order_by(Task.sort_order, Task.id).all():
        urgency = _task_urgency(task, now)
        if urgency:
            items.append(_notification_payload(task, urgency))
    return jsonify(
        {
            "notifications_enabled": _get_profile().notifications_enabled,
            "notify_before_hours": NOTIFY_BEFORE_HOURS,
            "items": items,
        }
    )


@app.post("/api/notifications/send")
def send_notifications():
    user = _get_profile()
    if not user.notifications_enabled:
        return jsonify({"error": "Notifications are disabled in your profile"}), 400

    now = datetime.utcnow()
    due_tasks = []
    for task in Task.query.order_by(Task.due_at, Task.id).all():
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
  <p>API example: <code>GET <a href="/api/tasks">/api/tasks</a></code></p>
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
    print(f"Todo API: open http://127.0.0.1:{port}/  (API: /api/tasks, /api/user)")
    app.run(debug=True, host=host, port=port, use_reloader=False, threaded=True)
