import json
import logging

from app import cache

_logger = logging.getLogger(__name__)

QUEUE_KEY = "queue:reminders"
PROCESSING_KEY = "queue:reminders:processing"
LOCK_KEY = "queue:reminders:lock"
MAX_ATTEMPTS = 3


def _dedup_key(task_id: int, milestone: str) -> str:
    return f"queued:reminder:{task_id}:{milestone}"


def enqueue_reminder(task_id: int, user_id: int, milestone: str) -> bool:
    redis = cache.client()
    if redis is None:
        return False
    dedup = _dedup_key(task_id, milestone)
    try:
        created = redis.set(dedup, "1", nx=True, ex=60 * 60 * 24)
        if not created:
            return False
        payload = json.dumps(
            {
                "type": "send_reminder",
                "task_id": task_id,
                "user_id": user_id,
                "milestone": milestone,
                "attempt": 0,
            }
        )
        redis.rpush(QUEUE_KEY, payload)
        return True
    except Exception:
        _logger.exception("Could not enqueue reminder task=%s milestone=%s", task_id, milestone)
        try:
            redis.delete(dedup)
        except Exception:
            _logger.exception("Could not release reminder dedup key")
        return False


def _recover_processing(redis, limit: int = 100) -> int:
    moved = 0
    while moved < limit:
        item = redis.lmove(PROCESSING_KEY, QUEUE_KEY, "RIGHT", "LEFT")
        if not item:
            break
        moved += 1
    return moved


def claim(redis):
    try:
        return redis.lmove(QUEUE_KEY, PROCESSING_KEY, "RIGHT", "LEFT")
    except Exception:
        _logger.exception("Could not claim a reminder message")
        return None


def ack(redis, raw: str) -> None:
    redis.lrem(PROCESSING_KEY, 1, raw)


def requeue(redis, raw: str, message: dict) -> None:
    redis.lrem(PROCESSING_KEY, 1, raw)
    if int(message.get("attempt", 0)) >= MAX_ATTEMPTS:
        _logger.error("Dropping reminder after %s attempts: %s", MAX_ATTEMPTS, message)
        return
    message["attempt"] = int(message.get("attempt", 0)) + 1
    redis.rpush(QUEUE_KEY, json.dumps(message))
