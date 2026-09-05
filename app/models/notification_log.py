from datetime import datetime

from app.extensions import db
from app.models.base import utc_iso


class NotificationLog(db.Model):
    __tablename__ = "notification_logs"
    __table_args__ = (
        db.UniqueConstraint("task_id", "milestone", name="uq_notification_task_milestone"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    task_id = db.Column(
        db.Integer,
        db.ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    milestone = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)
    email_status = db.Column(db.String(20), nullable=False, default="skipped")
    email_detail = db.Column(db.Text, nullable=True)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)

    task = db.relationship(
        "Task",
        backref=db.backref("notification_logs", cascade="all, delete-orphan"),
    )
    user = db.relationship("User", backref="notification_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "milestone": self.milestone,
            "message": self.message,
            "email_status": self.email_status,
            "email_detail": self.email_detail,
            "sent_at": utc_iso(self.sent_at),
            "read_at": utc_iso(self.read_at),
            "is_read": self.read_at is not None,
        }
