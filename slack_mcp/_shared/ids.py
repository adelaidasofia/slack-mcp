"""Channel and user ID resolution helpers.

Slack accepts either a channel ID (C12345) or a name (#general). Tool
arguments accept both; this module normalizes inputs to IDs.
"""

from __future__ import annotations

import re

CHANNEL_ID_RE = re.compile(r"^[CDG][A-Z0-9]{8,}$")
USER_ID_RE = re.compile(r"^[UW][A-Z0-9]{8,}$")


def is_channel_id(value: str) -> bool:
    return bool(CHANNEL_ID_RE.match(value))


def is_user_id(value: str) -> bool:
    return bool(USER_ID_RE.match(value))


def strip_channel_prefix(value: str) -> str:
    """Remove leading # or @ from a name-form identifier."""
    return value.lstrip("#@").strip()
