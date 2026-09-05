from typing import Optional

from datetime import datetime

from app.config import Config
from app.exceptions import NotFoundError
from app.models import User
from app.repositories import NotificationLogRepository, TaskRepository


class NotificationService:
    def __init__(
        self,
        task_repo: Optional[TaskRepository] = None,
        log_repo: Optional[NotificationLogRepository] = None,
    ):
        self.task_repo = task_repo or TaskRepository()
        self.log_repo = log_repo or NotificationLogRepository()

    def list_due(self, user: User) -> dict:
        """Preview upcoming reminders (before cron fires)."""
        now = datetime.utcnow()
        items = []
        for task in self.task_repo.list_by_user(user.id):
            milestone = self._preview_milestone(task, now)
            if milestone:
                items.append(self._preview_payload(task, milestone))
        return {
            "notifications_enabled": user.notifications_enabled,
            "milestones": list(Config.REMINDER_MILESTONES),
            "items": items,
        }

    def inbox(self, user: User) -> dict:
        logs = self.log_repo.list_inbox_for_user(user.id)
        unread = self.log_repo.count_unread_for_user(user.id)
        return {
            "unread_count": unread,
            "items": [log.to_dict() for log in logs],
        }

    def mark_read(self, user: User, log_id: int) -> dict:
        log = self.log_repo.get_for_user(user.id, log_id)
        if log is None:
            raise NotFoundError("Notification not found")
        self.log_repo.mark_read(log)
        return log.to_dict()

    def mark_all_read(self, user: User) -> dict:
        count = self.log_repo.mark_all_read(user.id)
        return {"marked_read": count}

    def _preview_milestone(self, task, now: datetime):
        if task.completed or task.due_at is None:
            return None
        seconds_left = (task.due_at - now).total_seconds()
        if seconds_left < 0:
            return "overdue"
        if seconds_left <= 3600:
            return "1h"
        if seconds_left <= 6 * 3600:
            return "6h"
        if seconds_left <= 24 * 3600:
            return "24h"
        return None

    def _preview_payload(self, task, milestone: str) -> dict:
        when = task.due_at.strftime("%Y-%m-%d %H:%M UTC")
        labels = {
            "24h": f'"{task.title}" due in ~24h ({when})',
            "6h": f'"{task.title}" due in ~6h ({when})',
            "1h": f'"{task.title}" due in ~1h ({when})',
            "overdue": f'"{task.title}" is overdue ({when})',
        }
        return {
            "task_id": task.id,
            "title": task.title,
            "due_at": task.due_at.isoformat() + "Z",
            "milestone": milestone,
            "message": labels.get(milestone, task.title),
        }
