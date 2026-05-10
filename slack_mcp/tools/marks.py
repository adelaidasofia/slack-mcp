"""Channel marking: mark_read."""

from __future__ import annotations

import time
from typing import Any

from ..audit import audit
from ..client import SlackClient, safe_call
from ..workspaces import REGISTRY
from .channels import _resolve_channel


def register(mcp) -> None:
    @mcp.tool()
    def mark_read(channel: str, ts: str, workspace: str | None = None) -> dict[str, Any]:
        """Mark a channel read up to a given message ts.

        Affects unread state across all your linked devices. Use the ts
        of the most recent message you've read.
        """
        start = time.time()
        client = SlackClient(REGISTRY.get(workspace))
        channel_id, channel_name = _resolve_channel(client, channel)
        safe_call(client.web.conversations_mark, channel=channel_id, ts=ts)
        audit("mark_read", {"workspace": workspace, "channel": channel, "ts": ts},
              "ok", int((time.time() - start) * 1000))
        return {"ok": True, "workspace": client.alias,
                "channel": {"id": channel_id, "name": channel_name}, "ts": ts}
