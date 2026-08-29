from typing import Optional

from datetime import datetime, timedelta

from app.config import Config
from app.extensions import db
from app.exceptions import ValidationError
from app.models import Task, User
from app.repositories import TaskRepository
from app.utils.email_sender import send_email


class NotificationService:
    def __init__(self, task_repo: Optional[TaskRepository] = None):
        self.task_repo = task_repo or TaskRepository()

    def list_due(self, user: User) -> dict:
        now = datetime.utcnow()
        items = []
        for task in self.task_repo.list_by_user(user.id):
            urgency = self._task_urgency(task, now)
            if urgency:
                items.append(self._notification_payload(task, urgency))
        return {
            "notifications_enabled": user.notifications_enabled,
            "notify_before_hours": Config.NOTIFY_BEFORE_HOURS,
            "items": items,
        }

    def send_reminders(self, user: User) -> dict:
        if not user.notifications_enabled:
            raise ValidationError("Notifications are disabled in your profile")

        now = datetime.utcnow()
        due_tasks = [
            task
            for task in self.task_repo.list_by_user_ordered_by_due(user.id)
            if self._should_send_notification(task, now)
        ]

        if not due_tasks:
            return {
                "sent": [],
                "skipped": [],
                "message": "No tasks need a reminder right now.",
            }

        messages = []
        email_results = []
        for task in due_tasks:
            urgency = self._task_urgency(task, now)
            msg = self._deadline_message(task, urgency)
            messages.append(self._notification_payload(task, urgency))
            task.last_notified_at = now

            if user.email:
                subject = (
                    f"[Todo] Overdue: {task.title}"
                    if urgency == "overdue"
                    else f"[Todo] Due soon: {task.title}"
                )
                body = (
                    f"Hi {user.name},\n\n"
                    f"{msg}\n\n"
                    "Open your todo list to mark it done or update the deadline.\n"
                )
                ok, detail = send_email(user.email, subject, body)
                email_results.append(
                    {"task_id": task.id, "email": user.email, "ok": ok, "detail": detail}
                )
            else:
                email_results.append(
                    {
                        "task_id": task.id,
                        "email": None,
                        "ok": False,
                        "detail": "No email on profile — in-app notification only",
                    }
                )

        db.session.commit()
        return {
            "sent": messages,
            "email_results": email_results,
            "message": f"Notified about {len(messages)} task(s).",
        }

    def _task_urgency(self, task: Task, now: Optional[datetime] = None):
        if task.completed or task.due_at is None:
            return None
        now = now or datetime.utcnow()
        seconds_left = (task.due_at - now).total_seconds()
        if seconds_left < 0:
            return "overdue"
        if seconds_left <= Config.NOTIFY_BEFORE_HOURS * 3600:
            return "due_soon"
        return None

    def _deadline_message(self, task: Task, urgency: str) -> str:
        when = task.due_at.strftime("%Y-%m-%d %H:%M UTC")
        if urgency == "overdue":
            return f'Task "{task.title}" is overdue (deadline was {when}).'
        return f'Task "{task.title}" is due soon (deadline: {when}).'

    def _should_send_notification(self, task: Task, now: datetime) -> bool:
        if self._task_urgency(task, now) is None:
            return False
        if task.last_notified_at is None:
            return True
        cooldown = timedelta(hours=Config.NOTIFY_COOLDOWN_HOURS)
        return now - task.last_notified_at >= cooldown

    def _notification_payload(self, task: Task, urgency: str) -> dict:
        return {
            "task_id": task.id,
            "title": task.title,
            "due_at": task.due_at.isoformat() + "Z" if task.due_at else None,
            "urgency": urgency,
            "message": self._deadline_message(task, urgency),
        }
