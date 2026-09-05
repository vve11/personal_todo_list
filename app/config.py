import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-todo-secret-change-me")
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_HTTPONLY = True

    _db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "todos.db")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{_db_path}"
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
    REMINDER_SCHEDULER_ENABLED = os.environ.get("REMINDER_SCHEDULER_ENABLED", "1") != "0"

    SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "").strip()
    SMTP_PASS = os.environ.get("SMTP_PASS", "").strip()
    SMTP_FROM = os.environ.get("SMTP_FROM", "").strip()
    SMTP_TLS = os.environ.get("SMTP_TLS", "1") != "0"
