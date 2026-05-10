"""Thread read: read_thread."""

from __future__ import annotations

import time
from typing import Any

from ..audit import audit
from ..client import SlackClient, safe_call
from ..scrubber import scrub_message
from ..workspaces import REGISTRY
from .channels import _resolve_channel


def register(mcp) -> None:
    @mcp.tool()
    def read_thread(channel: str, ts: str, workspace: str | None = None,
                    limit: int = 50) -> dict[str, Any]:
        """Read a thread's parent message and replies.

        ts is the parent message timestamp (Slack message ID). channel
        accepts ID or name. The returned messages list includes the parent
        as element 0.
        """
        start = time.time()
        client = SlackClient(REGISTRY.get(workspace))
        channel_id, channel_name = _resolve_channel(client, channel)
        page = safe_call(client.web.conversations_replies,
                         channel=channel_id, ts=ts, limit=min(limit, 200))
        raw = page.get("messages", [])
        messages = [scrub_message(m) for m in raw]
        audit("read_thread",
              {"workspace": workspace, "channel": channel, "ts": ts},
              f"{len(messages)} msgs", int((time.time() - start) * 1000))
        return {
            "workspace": client.alias,
            "channel": {"id": channel_id, "name": channel_name},
            "ts": ts,
            "messages": messages,
            "has_more": page.get("has_more", False),
        }
