import json
import logging

from app import cache
from app.queue import LOCK_KEY, _recover_processing, ack, claim, requeue
from app.services.reminder_service import ReminderService

_logger = logging.getLogger(__name__)


def drain_reminders(limit: int = 20) -> dict:
    redis = cache.client()
    if redis is None:
        result = ReminderService().run_scheduled_reminders()
        result["mode"] = "inline"
        return result

    try:
        locked = redis.set(LOCK_KEY, "1", nx=True, ex=120)
    except Exception:
        _logger.exception("Could not lock the reminder queue")
        result = ReminderService().run_scheduled_reminders()
        result["mode"] = "inline"
        return result
    if not locked:
        return {"mode": "busy", "enqueued": 0, "processed": 0, "failed": 0}

    processed = 0
    failed = 0
    try:
        recovered = _recover_processing(redis)
        enqueued = ReminderService().enqueue_due()
        for _ in range(limit):
            raw = claim(redis)
            if not raw:
                break
            try:
                message = json.loads(raw)
                ReminderService().handle_message(message)
                ack(redis, raw)
                processed += 1
            except Exception:
                _logger.exception("Reminder message failed")
                failed += 1
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    ack(redis, raw)
                    continue
                requeue(redis, raw, message)
        return {
            "mode": "queue",
            "recovered": recovered,
            "enqueued": enqueued,
            "processed": processed,
            "failed": failed,
        }
    finally:
        try:
            redis.delete(LOCK_KEY)
        except Exception:
            _logger.exception("Could not release the reminder queue lock")
