"""In-memory activity buffer for monitor — no FastAPI dependency."""

from collections import deque
from datetime import datetime, timezone

_utcnow = lambda: datetime.now(tz=timezone.utc)

_activity: deque = deque(maxlen=200)


def log_activity(event_type: str, data: dict):
    _activity.appendleft({
        "ts": _utcnow().isoformat(),
        "type": event_type,
        **data,
    })


def get_activity(limit: int = 50) -> list:
    return list(_activity)[:limit]
