import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


def _database_uri() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        return url

    db_path = os.environ.get(
        "SQLITE_PATH",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "todos.db"),
    )
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    return f"sqlite:///{db_path}"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-todo-secret-change-me")
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_HTTPONLY = True
    # Render sets RENDER=true. Vercel sets VERCEL=1. Local HTTP keeps this off.
    SESSION_COOKIE_SECURE = os.environ.get("RENDER") == "true" or os.environ.get("VERCEL") == "1"

    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CORS_ORIGINS = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5050",
        "http://localhost:5050",
    ]

    NOTIFY_BEFORE_HOURS = int(os.environ.get("NOTIFY_BEFORE_HOURS", "24"))
    NOTIFY_COOLDOWN_HOURS = int(os.environ.get("NOTIFY_COOLDOWN_HOURS", "6"))

    REMINDER_MILESTONES = tuple(
        m.strip()
        for m in os.environ.get("REMINDER_MILESTONES", "24h,6h,1h,overdue").split(",")
        if m.strip()
    )
    REMINDER_WINDOW_MINUTES = int(os.environ.get("REMINDER_WINDOW_MINUTES", "30"))
    # Default: check deadlines / reminder status every 30 seconds
    REMINDER_POLL_INTERVAL_SECONDS = int(os.environ.get("REMINDER_POLL_INTERVAL_SECONDS", "30"))
    # Vercel stops the process after each request, so the background reminder thread cannot stay running.
    REMINDER_SCHEDULER_ENABLED = (
        os.environ.get("VERCEL") != "1"
        and os.environ.get("REMINDER_SCHEDULER_ENABLED", "1") != "0"
    )

    SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "").strip()
    SMTP_PASS = os.environ.get("SMTP_PASS", "").strip()
    SMTP_FROM = os.environ.get("SMTP_FROM", "").strip()
    SMTP_TLS = os.environ.get("SMTP_TLS", "1") != "0"
