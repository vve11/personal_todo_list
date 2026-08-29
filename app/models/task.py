from datetime import datetime

from app.extensions import db
from app.models.base import TimestampMixin, utc_iso


class Task(db.Model, TimestampMixin):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    due_at = db.Column(db.DateTime, nullable=True)
    last_notified_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "completed": self.completed,
            "sort_order": self.sort_order,
            "due_at": utc_iso(self.due_at),
            "last_notified_at": utc_iso(self.last_notified_at),
            "created_at": utc_iso(self.created_at),
            "updated_at": utc_iso(self.updated_at),
        }
