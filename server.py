import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5050"))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Todo API: open http://127.0.0.1:{port}/  (API: /api/tasks, /api/auth/login)")
    app.run(debug=True, host=host, port=port, use_reloader=False, threaded=True)
