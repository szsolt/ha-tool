from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone


_RELATIVE_RE = re.compile(r"^(\d+)\s*([smhdw])$", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse_duration_seconds(value: str) -> int | None:
    """Parse a relative duration like '7d', '30m', '2w' into seconds.

    Returns None if the value isn't a relative duration.
    """
    if not isinstance(value, str):
        return None
    m = _RELATIVE_RE.match(value.strip().lower())
    if not m:
        return None
    return int(m.group(1)) * _UNIT_SECONDS[m.group(2).lower()]


def parse_time(value: str, *, now: datetime | None = None) -> datetime:
    """Parse a time spec into a timezone-aware UTC datetime.

    Accepts:
      - Relative: "1h", "30m", "5d", "2w" (subtracted from now)
      - Keywords: "now", "today", "yesterday"
      - ISO 8601 absolute (e.g. "2026-04-30T12:00:00Z")
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Empty time value")

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    s = value.strip().lower()

    if s == "now":
        return now
    if s == "today":
        local = now.astimezone()
        midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight.astimezone(timezone.utc)
    if s == "yesterday":
        local = now.astimezone()
        midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
        return (midnight - timedelta(days=1)).astimezone(timezone.utc)

    m = _RELATIVE_RE.match(s)
    if m:
        amount = int(m.group(1))
        unit = m.group(2).lower()
        return now - timedelta(seconds=amount * _UNIT_SECONDS[unit])

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError(f"Cannot parse time: {value!r}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
