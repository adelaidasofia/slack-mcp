"""Edit-own-message tools.

delete_own_message: one-shot, immediate. Calls chat.delete. No draft needed
(idempotent + Slack returns message_not_found as a soft failure).

update_own_message: draft+confirm. Two-step: stage an "update_message" draft
with the BEFORE text fetched from conversations.history and the proposed
AFTER text in the same payload, then confirm to call chat.update. The diff
view gives the user one last visual review before the edit lands.

Tools: delete_own_message, update_own_message.
"""

from __future__ import annotations

import time
from typing import Any

from ..audit import audit
from ..client import SlackClient, safe_call
from ..drafts import STORE
from ..workspaces import REGISTRY
from .channels import _resolve_channel


def _fetch_message_text(client: SlackClient, channel_id: str, ts: str) -> str:
    """Return the text of a single message by ts. Empty string if not found."""
    try:
        page = safe_call(
            client.web.conversations_history,
            channel=channel_id, latest=ts, oldest=ts,
            inclusive=True, limit=1,
        )
        msgs = page.get("messages", [])
        if msgs:
            return msgs[0].get("text", "") or ""
    except Exception:
        pass
    return ""


def register(mcp) -> None:
    @mcp.tool()
    def delete_own_message(channel: str, ts: str,
                           workspace: str | None = None) -> dict[str, Any]:
        """Delete one of your own messages.

        Calls chat.delete with (channel, ts). xoxc user tokens can delete
        their OWN messages without special scopes. Returns ok=True on
        success. message_not_found is treated as a soft success
        (already-deleted or wrong ts).

        Low-consequence (only your own messages, no destructive cascade)
        so no draft+confirm. The audit log records every call.
        """
        start = time.time()
        client = SlackClient(REGISTRY.get(workspace))
        channel_id, channel_name = _resolve_channel(client, channel)
        try:
            safe_call(client.web.chat_delete, channel=channel_id, ts=ts)
            ok = True
            err = None
        except RuntimeError as e:
            if "message_not_found" in str(e):
                ok = True
                err = "message_not_found"
            else:
                audit("delete_own_message",
                      {"workspace": workspace, "channel": channel, "ts": ts},
                      "error", int((time.time() - start) * 1000), str(e))
                raise
        audit("delete_own_message",
              {"workspace": workspace, "channel": channel, "ts": ts},
              "ok" + (f" ({err})" if err else ""),
              int((time.time() - start) * 1000))
        return {
            "ok": ok,
            "workspace": client.alias,
            "channel": {"id": channel_id, "name": channel_name},
            "ts": ts,
            "note": err,
        }

    @mcp.tool()
    def update_own_message(channel: str, ts: str, text: str,
                           workspace: str | None = None) -> dict[str, Any]:
        """Stage an edit to one of your own messages. Does NOT update
        until confirm_send is called.

        Fetches the current message text up front so the draft preview
        shows BOTH the BEFORE and AFTER strings — a visual diff in plain
        Python. After confirm_send, the message is edited in place via
        chat.update.

        Returns a draft_id, the resolved workspace + channel + target_ts,
        and a preview dict with `before`, `after`, `target_ts`. Drafts
        expire after 1 hour and can only be confirmed once.
        """
        start = time.time()
        ws = REGISTRY.get(workspace)
        client = SlackClient(ws)
        channel_id, channel_name = _resolve_channel(client, channel)
        if not text.strip():
            raise ValueError("text cannot be empty")
        before_text = _fetch_message_text(client, channel_id, ts)
        draft = STORE.create(
            workspace=ws.alias, channel=channel_id, channel_name=channel_name,
            text=text, kind="update_message",
            target_ts=ts, before_text=before_text,
        )
        audit("update_own_message",
              {"workspace": workspace, "channel": channel,
               "ts": ts, "text_len": len(text)},
              f"draft={draft.draft_id[:8]}...",
              int((time.time() - start) * 1000))
        return {
            "draft_id": draft.draft_id,
            "workspace": ws.alias,
            "channel": {"id": channel_id, "name": channel_name},
            "target_ts": ts,
            "preview": {
                "before": before_text[:400] + ("..." if len(before_text) > 400 else ""),
                "after": text[:400] + ("..." if len(text) > 400 else ""),
            },
            "expires_at": draft.expires_at(),
            "expires_in_seconds": int(draft.expires_at() - time.time()),
        }
