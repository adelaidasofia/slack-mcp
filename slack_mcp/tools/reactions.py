"""Reactions: add_reaction. Low-consequence write, no draft+confirm needed."""

from __future__ import annotations

import time
from typing import Any

from ..audit import audit
from ..client import SlackClient, safe_call
from ..workspaces import REGISTRY
from .channels import _resolve_channel


def register(mcp) -> None:
    @mcp.tool()
    def add_reaction(channel: str, ts: str, emoji: str,
                     workspace: str | None = None) -> dict[str, Any]:
        """Add an emoji reaction to a message.

        emoji is the colon-stripped name (e.g. "thumbsup", "fire", "white_check_mark").
        Low-consequence write — no draft+confirm. Idempotent (Slack returns
        already_reacted as a soft success).
        """
        start = time.time()
        client = SlackClient(REGISTRY.get(workspace))
        channel_id, channel_name = _resolve_channel(client, channel)
        clean_emoji = emoji.strip().strip(":")
        try:
            safe_call(client.web.reactions_add, channel=channel_id, timestamp=ts,
                      name=clean_emoji)
            ok = True
        except RuntimeError as e:
            if "already_reacted" in str(e):
                ok = True
            else:
                raise
        audit("add_reaction",
              {"workspace": workspace, "channel": channel, "ts": ts, "emoji": clean_emoji},
              "ok" if ok else "fail", int((time.time() - start) * 1000))
        return {"ok": ok, "workspace": client.alias,
                "channel": {"id": channel_id, "name": channel_name},
                "ts": ts, "emoji": clean_emoji}
