import os
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "todos.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{_db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, default="You")
    email = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }


class Task(db.Model):
    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
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


with app.app_context():
    db.create_all()


def _get_task_or_404(tid: int):
    t = db.session.get(Task, tid)
    if t is None:
        return None, (jsonify({"error": "Task not found"}), 404)
    return t, None


_PROFILE_ID = 1


def _get_profile():
    u = db.session.get(User, _PROFILE_ID)
    if u is None:
        u = User(id=_PROFILE_ID, name="You", email="")
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
    task = Task(
        title=title[:500],
        completed=bool(data.get("completed", False)),
        sort_order=_next_sort_order(),
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
