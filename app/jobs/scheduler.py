import logging
import threading
import time

from app.config import Config
from app.services.reminder_service import ReminderService

_logger = logging.getLogger(__name__)
_scheduler_started = False
_scheduler_lock = threading.Lock()


def _poll_once(app) -> None:
    with app.app_context():
        result = ReminderService().run_scheduled_reminders()
        _logger.info(
            "Reminder poll finished: sent=%s skipped=%s failed=%s",
            result["sent"],
            result["skipped"],
            result["failed"],
        )


def _poll_loop(app, interval_seconds: int) -> None:
    while True:
        try:
            _poll_once(app)
        except Exception:
            _logger.exception("Reminder poll failed")
        time.sleep(interval_seconds)


def start_reminder_scheduler(app) -> None:
    global _scheduler_started
    if not Config.REMINDER_SCHEDULER_ENABLED:
        return

    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True

    interval = Config.REMINDER_POLL_INTERVAL_SECONDS
    thread = threading.Thread(
        target=_poll_loop,
        args=(app, interval),
        name="reminder-scheduler",
        daemon=True,
    )
    thread.start()
    _logger.info("Reminder scheduler started (every %ss)", interval)

    # Run once at startup so the user does not wait for the first interval.
    startup = threading.Thread(
        target=_poll_once,
        args=(app,),
        name="reminder-startup",
        daemon=True,
    )
    startup.start()
