from sqlalchemy import inspect, text

from app.extensions import db


def ensure_schema() -> None:
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

    db.session.execute(
        text(
            "UPDATE tasks SET user_id = (SELECT id FROM users ORDER BY id LIMIT 1) "
            "WHERE user_id IS NULL"
        )
    )
    db.session.commit()
