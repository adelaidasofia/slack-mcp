"""Channel read tools: list_channels, search_channels, read_channel."""

from __future__ import annotations

import time
from typing import Any

from .._shared.ids import is_channel_id, strip_channel_prefix
from ..audit import audit
from ..client import SlackClient, safe_call
from ..scrubber import scrub_message
from ..vault_export import export_channel
from ..workspaces import REGISTRY


def _resolve_channel(client: SlackClient, channel: str) -> tuple[str, str]:
    """Return (channel_id, channel_name). Accepts ID or #name."""
    bare = strip_channel_prefix(channel)
    if is_channel_id(bare):
        info = safe_call(client.web.conversations_info, channel=bare)
        chan = info.get("channel", {})
        return bare, chan.get("name", bare)
    # Name lookup via paginated conversations.list
    cursor = None
    types = "public_channel,private_channel,mpim,im"
    while True:
        page = safe_call(client.web.conversations_list, types=types, limit=200, cursor=cursor)
        for chan in page.get("channels", []):
            if chan.get("name") == bare:
                return chan["id"], bare
        cursor = page.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    raise ValueError(f"channel '{channel}' not found in workspace")


def _build_user_lookup(client: SlackClient, user_ids: set[str]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    if not user_ids:
        return lookup
    cursor = None
    while True:
        page = safe_call(client.web.users_list, limit=200, cursor=cursor)
        for u in page.get("members", []):
            if u.get("id") in user_ids:
                profile = u.get("profile", {})
                lookup[u["id"]] = (
                    profile.get("display_name")
                    or profile.get("real_name")
                    or u.get("name")
                    or u["id"]
                )
        cursor = page.get("response_metadata", {}).get("next_cursor")
        if not cursor or len(lookup) >= len(user_ids):
            break
    return lookup


def register(mcp) -> None:
    @mcp.tool()
    def list_channels(workspace: str | None = None,
                      types: str = "public_channel,private_channel",
                      limit: int = 100) -> dict[str, Any]:
        """List channels in the workspace.

        types: comma-separated subset of public_channel, private_channel,
        mpim, im. Default omits DMs to keep responses short.
        limit caps results at the API page size.
        """
        start = time.time()
        client = SlackClient(REGISTRY.get(workspace))
        page = safe_call(client.web.conversations_list, types=types, limit=min(limit, 200))
        channels = [
            {
                "id": c["id"],
                "name": c.get("name"),
                "is_private": c.get("is_private", False),
                "is_archived": c.get("is_archived", False),
                "topic": (c.get("topic") or {}).get("value", ""),
                "num_members": c.get("num_members"),
            }
            for c in page.get("channels", [])
        ]
        audit("list_channels", {"workspace": workspace, "types": types},
              f"{len(channels)} channels", int((time.time() - start) * 1000))
        return {"workspace": client.alias, "channels": channels,
                "next_cursor": page.get("response_metadata", {}).get("next_cursor", "")}

    @mcp.tool()
    def search_channels(workspace: str | None = None, query: str = "",
                        types: str = "public_channel,private_channel") -> dict[str, Any]:
        """Substring match against channel names + topics. Case-insensitive."""
        start = time.time()
        client = SlackClient(REGISTRY.get(workspace))
        q = query.lower().strip()
        if not q:
            raise ValueError("query is required")
        results = []
        cursor = None
        while True:
            page = safe_call(client.web.conversations_list,
                             types=types, limit=200, cursor=cursor)
            for c in page.get("channels", []):
                name = (c.get("name") or "").lower()
                topic = (c.get("topic") or {}).get("value", "").lower()
                purpose = (c.get("purpose") or {}).get("value", "").lower()
                if q in name or q in topic or q in purpose:
                    results.append({
                        "id": c["id"], "name": c.get("name"),
                        "topic": (c.get("topic") or {}).get("value", ""),
                        "purpose": (c.get("purpose") or {}).get("value", ""),
                        "is_private": c.get("is_private", False),
                    })
            cursor = page.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        audit("search_channels", {"workspace": workspace, "query": query},
              f"{len(results)} matches", int((time.time() - start) * 1000))
        return {"workspace": client.alias, "query": query, "channels": results}

    @mcp.tool()
    def read_channel(channel: str, workspace: str | None = None,
                     limit: int = 50, oldest: str | None = None,
                     latest: str | None = None) -> dict[str, Any]:
        """Read recent messages from a channel.

        channel accepts ID (C12345) or name (#general). Newest first.
        Auto-exports the result to the vault at
        🤖 AI Chats/Slack/<workspace>/<channel>.md (best-effort).
        """
        start = time.time()
        client = SlackClient(REGISTRY.get(workspace))
        channel_id, channel_name = _resolve_channel(client, channel)
        kwargs = {"channel": channel_id, "limit": min(limit, 200)}
        if oldest:
            kwargs["oldest"] = oldest
        if latest:
            kwargs["latest"] = latest
        page = safe_call(client.web.conversations_history, **kwargs)
        raw_messages = page.get("messages", [])
        messages = [scrub_message(m) for m in raw_messages]
        # Build user lookup for vault export rendering
        user_ids = {m.get("user") for m in messages if m.get("user")}
        try:
            user_lookup = _build_user_lookup(client, user_ids)  # type: ignore[arg-type]
        except Exception:
            user_lookup = {}
        export_path = export_channel(client.alias, channel_name, channel_id,
                                      messages, user_lookup)
        audit("read_channel",
              {"workspace": workspace, "channel": channel, "limit": limit},
              f"{len(messages)} msgs, vault={'yes' if export_path else 'no'}",
              int((time.time() - start) * 1000))
        return {
            "workspace": client.alias,
            "channel": {"id": channel_id, "name": channel_name},
            "messages": messages,
            "has_more": page.get("has_more", False),
            "next_cursor": page.get("response_metadata", {}).get("next_cursor", ""),
            "vault_export": export_path,
        }
