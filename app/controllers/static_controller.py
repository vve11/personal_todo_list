import os

from flask import Blueprint, abort, jsonify, send_from_directory

static_bp = Blueprint("static", __name__)


def _client_dist() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "client", "dist")


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


@static_bp.get("/")
def home():
    dist = _client_dist()
    index = os.path.join(dist, "index.html")
    if os.path.isfile(index):
        return send_from_directory(dist, "index.html")
    return _html_help_no_build()


@static_bp.get("/<path:path>")
def dist_files_or_spa(path: str):
    if path.startswith("api/") or path == "api":
        return jsonify({"error": "Not found"}), 404
    dist = _client_dist()
    if ".." in path or path.startswith("\\"):
        abort(404)
    rel = path.replace("\\", "/").lstrip("/")
    full = os.path.normpath(os.path.join(dist, rel))
    dist_norm = os.path.normpath(dist)
    if not full.startswith(dist_norm + os.sep) and full != dist_norm:
        abort(404)
    if rel and os.path.isfile(full):
        return send_from_directory(dist, rel)
    index = os.path.join(dist, "index.html")
    if os.path.isfile(index):
        return send_from_directory(dist, "index.html")
    return _html_help_no_build()
