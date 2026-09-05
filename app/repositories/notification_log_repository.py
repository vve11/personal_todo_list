from datetime import datetime
from typing import Optional

from app.extensions import db
from app.models import NotificationLog


class NotificationLogRepository:
    def exists(self, task_id: int, milestone: str) -> bool:
        return (
            NotificationLog.query.filter_by(task_id=task_id, milestone=milestone).first()
            is not None
        )

    def add(self, log: NotificationLog) -> NotificationLog:
        db.session.add(log)
        db.session.commit()
        return log

    def list_inbox_for_user(self, user_id: int, limit: int = 50) -> list[NotificationLog]:
        return (
            NotificationLog.query.filter_by(user_id=user_id)
            .order_by(NotificationLog.sent_at.desc(), NotificationLog.id.desc())
            .limit(limit)
            .all()
        )

    def count_unread_for_user(self, user_id: int) -> int:
        return NotificationLog.query.filter_by(user_id=user_id, read_at=None).count()

    def get_for_user(self, user_id: int, log_id: int) -> Optional[NotificationLog]:
        return NotificationLog.query.filter_by(id=log_id, user_id=user_id).first()

    def mark_read(self, log: NotificationLog) -> NotificationLog:
        if log.read_at is None:
            log.read_at = datetime.utcnow()
            db.session.commit()
        return log

    def mark_all_read(self, user_id: int) -> int:
        now = datetime.utcnow()
        updated = (
            NotificationLog.query.filter_by(user_id=user_id, read_at=None)
            .update({"read_at": now}, synchronize_session=False)
        )
        db.session.commit()
        return updated
