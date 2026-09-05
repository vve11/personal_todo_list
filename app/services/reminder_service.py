from datetime import datetime, timedelta
from typing import Optional

from app.config import Config
from app.models import NotificationLog, Task, User
from app.repositories import NotificationLogRepository, TaskRepository, UserRepository
from app.utils.email_sender import send_email

MILESTONE_OFFSETS = {
    "24h": timedelta(hours=24),
    "6h": timedelta(hours=6),
    "1h": timedelta(hours=1),
}


class ReminderService:
    def __init__(
        self,
        task_repo: Optional[TaskRepository] = None,
        user_repo: Optional[UserRepository] = None,
        log_repo: Optional[NotificationLogRepository] = None,
    ):
        self.task_repo = task_repo or TaskRepository()
        self.user_repo = user_repo or UserRepository()
        self.log_repo = log_repo or NotificationLogRepository()

    def run_scheduled_reminders(self) -> dict:
        now = datetime.utcnow()
        sent = 0
        skipped = 0
        failed = 0

        tasks = self.task_repo.list_reminder_candidates()
        for task in tasks:
            user = self.user_repo.get_by_id(task.user_id)
            if user is None or not user.notifications_enabled:
                skipped += 1
                continue

            milestone = self._matching_milestone(task, now)
            if milestone is None:
                continue
            if self.log_repo.exists(task.id, milestone):
                continue

            result = self._deliver(user, task, milestone, now)
            if result == "sent":
                sent += 1
            elif result == "failed":
                failed += 1
            else:
                skipped += 1

        return {"sent": sent, "skipped": skipped, "failed": failed, "checked_at": now.isoformat() + "Z"}

    def _matching_milestone(self, task: Task, now: datetime) -> Optional[str]:
        if task.due_at is None or task.completed:
            return None

        window = timedelta(minutes=Config.REMINDER_WINDOW_MINUTES)
        for milestone in Config.REMINDER_MILESTONES:
            if milestone == "overdue":
                if now > task.due_at:
                    return milestone
                continue

            offset = MILESTONE_OFFSETS.get(milestone)
            if offset is None:
                continue
            target = task.due_at - offset
            if target - window <= now <= target + window:
                return milestone
        return None

    def _deliver(self, user: User, task: Task, milestone: str, now: datetime) -> str:
        message = self._build_message(task, milestone)
        email_status = "skipped"
        email_detail = "SMTP not configured"

        if user.email and Config.SMTP_HOST:
            subject = self._email_subject(task, milestone)
            body = (
                f"Hi {user.name},\n\n"
                f"{message}\n\n"
                "Open your todo list to mark it done or update the deadline.\n"
            )
            ok, detail = send_email(user.email, subject, body)
            email_status = "sent" if ok else "failed"
            email_detail = detail
        elif user.email:
            email_detail = "SMTP not configured (set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS)"
        else:
            email_detail = "No email on profile"

        log = NotificationLog(
            user_id=user.id,
            task_id=task.id,
            milestone=milestone,
            message=message,
            email_status=email_status,
            email_detail=email_detail,
            sent_at=now,
        )
        self.log_repo.add(log)
        task.last_notified_at = now
        self.task_repo.save(task)
        return "sent"

    def _build_message(self, task: Task, milestone: str) -> str:
        when = task.due_at.strftime("%Y-%m-%d %H:%M UTC")
        labels = {
            "24h": f'Task "{task.title}" is due in about 24 hours (deadline: {when}).',
            "6h": f'Task "{task.title}" is due in about 6 hours (deadline: {when}).',
            "1h": f'Task "{task.title}" is due in about 1 hour (deadline: {when}).',
            "overdue": f'Task "{task.title}" is overdue (deadline was {when}).',
        }
        return labels.get(milestone, f'Task "{task.title}" reminder (deadline: {when}).')

    def _email_subject(self, task: Task, milestone: str) -> str:
        labels = {
            "24h": "Due in 24 hours",
            "6h": "Due in 6 hours",
            "1h": "Due in 1 hour",
            "overdue": "Overdue",
        }
        prefix = labels.get(milestone, "Reminder")
        return f"[Todo] {prefix}: {task.title}"
