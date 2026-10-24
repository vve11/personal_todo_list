import json
import logging
import os
from typing import Optional

_logger = logging.getLogger(__name__)
_client = None
_unavailable = False

DEFAULT_TTL_SECONDS = 60


def _redis():
    global _client, _unavailable
    if _unavailable:
        return None
    if _client is not None:
        return _client

    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        _unavailable = True
        return None

    try:
        import redis
    except ImportError:
        _logger.warning("REDIS_URL is set but the redis package is not installed")
        _unavailable = True
        return None

    try:
        client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
    except Exception:
        _logger.exception("Redis is unavailable; requests will use the database")
        _unavailable = True
        return None

    _client = client
    return _client


def tasks_key(user_id: int) -> str:
    return f"tasks:{user_id}"


def inbox_key(user_id: int) -> str:
    return f"inbox:{user_id}"


def due_key(user_id: int) -> str:
    return f"due:{user_id}"


def get_json(key: str):
    client = _redis()
    if client is None:
        return None
    try:
        raw = client.get(key)
    except Exception:
        _logger.exception("Redis get failed for %s", key)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def set_json(key: str, value, ttl_seconds: Optional[int] = None) -> None:
    client = _redis()
    if client is None:
        return
    ttl = DEFAULT_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    try:
        client.set(key, json.dumps(value), ex=ttl)
    except Exception:
        _logger.exception("Redis set failed for %s", key)


def delete(*keys: str) -> None:
    client = _redis()
    if client is None or not keys:
        return
    try:
        client.delete(*keys)
    except Exception:
        _logger.exception("Redis delete failed")


def invalidate_user(user_id: int) -> None:
    delete(tasks_key(user_id), inbox_key(user_id), due_key(user_id))
