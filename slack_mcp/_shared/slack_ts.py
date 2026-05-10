"""Slack timestamp helpers.

Slack `ts` strings are unix seconds with microseconds in a single string
("1700000000.000123"). They're also the message ID — ts uniquely identifies
a message within a channel. Don't drop the suffix.
"""

from __future__ import annotations

import datetime as dt


def ts_to_iso(ts: str) -> str:
    """Convert a Slack ts string to ISO 8601 UTC. Preserves precision."""
    seconds = float(ts)
    return dt.datetime.fromtimestamp(seconds, tz=dt.timezone.utc).isoformat()


def ts_to_human(ts: str, tz: str = "UTC") -> str:
    """Render ts as human-readable local time. Pass tz (IANA name) for local rendering."""
    try:
        from zoneinfo import ZoneInfo
        zone = ZoneInfo(tz)
    except Exception:
        zone = dt.timezone.utc
    seconds = float(ts)
    return dt.datetime.fromtimestamp(seconds, tz=zone).strftime("%Y-%m-%d %H:%M:%S %Z")


def now_ts() -> str:
    """Generate a current Slack-style ts."""
    return f"{dt.datetime.now(tz=dt.timezone.utc).timestamp():.6f}"
