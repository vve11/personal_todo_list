from datetime import datetime

from app.extensions import db


def utc_iso(value):
    if value is None:
        return None
    return value.isoformat() + "Z"


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
