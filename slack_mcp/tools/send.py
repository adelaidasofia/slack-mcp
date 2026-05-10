"""Send tools with draft+confirm pattern.

Every send produces a draft_id; nothing hits Slack until confirm_send is
called. cancel_draft cleans up unconfirmed drafts. Drafts expire after 1h.

Tools: send_message, send_reply_quote, confirm_send, cancel_draft.
"""

from __future__ import annotations

import time
from typing import Any

from ..audit import audit
from ..client import SlackClient, safe_call
from ..drafts import STORE
from ..workspaces import REGISTRY
from .channels import _resolve_channel


def register(mcp) -> None:
    @mcp.tool()
    def send_message(channel: str, text: str,
                     workspace: str | None = None,
                     thread_ts: str | None = None) -> dict[str, Any]:
        """Stage a message send. Does NOT post until confirm_send is called.

        Returns a draft_id, the resolved workspace + channel, the text
        preview, and an expires_at unix timestamp. Drafts expire after
        1 hour and can only be confirmed once.

        For thread replies, set thread_ts to the parent message's ts.
        For replies that quote (reply with quote-block in Slack UI), use
        send_reply_quote instead.
        """
        start = time.time()
        ws = REGISTRY.get(workspace)
        client = SlackClient(ws)
        channel_id, channel_name = _resolve_channel(client, channel)
        if not text.strip():
            raise ValueError("text cannot be empty")
        draft = STORE.create(
            workspace=ws.alias, channel=channel_id, channel_name=channel_name,
            text=text, kind="send_message", thread_ts=thread_ts,
        )
        audit("send_message",
              {"workspace": workspace, "channel": channel,
               "thread_ts": thread_ts, "text_len": len(text)},
              f"draft={draft.draft_id[:8]}...", int((time.time() - start) * 1000))
        return {
            "draft_id": draft.draft_id,
            "workspace": ws.alias,
            "channel": {"id": channel_id, "name": channel_name},
            "preview": text[:200] + ("..." if len(text) > 200 else ""),
            "thread_ts": thread_ts,
            "expires_at": draft.expires_at(),
            "expires_in_seconds": int(draft.expires_at() - time.time()),
        }

    @mcp.tool()
    def send_reply_quote(channel: str, target_ts: str, text: str,
                         workspace: str | None = None) -> dict[str, Any]:
        """Stage a reply that threads under target_ts.

        Same draft+confirm semantics as send_message. The recipient sees
        the reply nested under the target message in their Slack UI.
        """
        start = time.time()
        ws = REGISTRY.get(workspace)
        client = SlackClient(ws)
        channel_id, channel_name = _resolve_channel(client, channel)
        if not text.strip():
            raise ValueError("text cannot be empty")
        draft = STORE.create(
            workspace=ws.alias, channel=channel_id, channel_name=channel_name,
            text=text, kind="send_reply_quote",
            thread_ts=target_ts, target_ts=target_ts,
        )
        audit("send_reply_quote",
              {"workspace": workspace, "channel": channel,
               "target_ts": target_ts, "text_len": len(text)},
              f"draft={draft.draft_id[:8]}...", int((time.time() - start) * 1000))
        return {
            "draft_id": draft.draft_id,
            "workspace": ws.alias,
            "channel": {"id": channel_id, "name": channel_name},
            "target_ts": target_ts,
            "preview": text[:200] + ("..." if len(text) > 200 else ""),
            "expires_at": draft.expires_at(),
            "expires_in_seconds": int(draft.expires_at() - time.time()),
        }

    @mcp.tool()
    def confirm_send(draft_id: str) -> dict[str, Any]:
        """Commit a previously-drafted send. Dispatches by draft.kind:

        - send_message / send_reply_quote -> chat.postMessage (new message)
        - update_message -> chat.update (in-place edit of target_ts)
        """
        start = time.time()
        draft = STORE.confirm(draft_id)
        ws = REGISTRY.get(draft.workspace)
        client = SlackClient(ws)
        try:
            if draft.kind == "update_message":
                if not draft.target_ts:
                    raise ValueError("update_message draft missing target_ts")
                response = safe_call(
                    client.web.chat_update,
                    channel=draft.channel, ts=draft.target_ts, text=draft.text,
                )
                result_ts = response.get("ts") or draft.target_ts
            else:
                kwargs: dict[str, Any] = {"channel": draft.channel, "text": draft.text}
                if draft.thread_ts:
                    kwargs["thread_ts"] = draft.thread_ts
                response = safe_call(client.web.chat_postMessage, **kwargs)
                result_ts = response.get("ts")
        except Exception as e:
            audit("confirm_send", {"draft_id": draft_id[:8], "kind": draft.kind},
                  "error", int((time.time() - start) * 1000), str(e))
            raise
        audit("confirm_send",
              {"draft_id": draft_id[:8], "workspace": draft.workspace,
               "channel": draft.channel_name, "kind": draft.kind},
              f"{'edited' if draft.kind == 'update_message' else 'posted'} ts={result_ts}",
              int((time.time() - start) * 1000))
        return {
            "ok": True,
            "workspace": draft.workspace,
            "channel": {"id": draft.channel, "name": draft.channel_name},
            "ts": result_ts,
            "kind": draft.kind,
            "permalink": _try_permalink(client, draft.channel, result_ts),
        }

    @mcp.tool()
    def cancel_draft(draft_id: str) -> dict[str, Any]:
        """Cancel an unconfirmed draft. Idempotent."""
        start = time.time()
        draft = STORE.cancel(draft_id)
        audit("cancel_draft", {"draft_id": draft_id[:8]}, "cancelled",
              int((time.time() - start) * 1000))
        return {
            "ok": True,
            "draft_id": draft.draft_id,
            "workspace": draft.workspace,
            "channel": draft.channel_name,
        }


def _try_permalink(client: SlackClient, channel: str, ts: str | None) -> str | None:
    if not ts:
        return None
    try:
        result = safe_call(client.web.chat_getPermalink, channel=channel, message_ts=ts)
        return result.get("permalink")
    except Exception:
        return None
