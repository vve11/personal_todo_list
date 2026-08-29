from datetime import datetime, timezone


def parse_due_at(value):
    if value is None or value == "":
        return None, None
    if not isinstance(value, str):
        return None, "due_at must be an ISO datetime string"
    s = value.strip()
    if not s:
        return None, None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None, "due_at is invalid"
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt, None


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()
