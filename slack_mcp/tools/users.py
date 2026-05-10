"""User read tools: list_users, search_users, get_user_profile."""

from __future__ import annotations

import time
from typing import Any

from ..audit import audit
from ..client import SlackClient, safe_call
from ..workspaces import REGISTRY


def _condense(member: dict) -> dict:
    profile = member.get("profile", {})
    return {
        "id": member.get("id"),
        "name": member.get("name"),
        "real_name": profile.get("real_name"),
        "display_name": profile.get("display_name"),
        "email": profile.get("email"),
        "title": profile.get("title"),
        "is_bot": member.get("is_bot", False),
        "deleted": member.get("deleted", False),
    }


def register(mcp) -> None:
    @mcp.tool()
    def list_users(workspace: str | None = None, limit: int = 100,
                   include_deleted: bool = False) -> dict[str, Any]:
        """List users in the workspace. Excludes deleted by default."""
        start = time.time()
        client = SlackClient(REGISTRY.get(workspace))
        page = safe_call(client.web.users_list, limit=min(limit, 200))
        members = [_condense(m) for m in page.get("members", [])
                   if include_deleted or not m.get("deleted", False)]
        audit("list_users", {"workspace": workspace, "limit": limit},
              f"{len(members)} users", int((time.time() - start) * 1000))
        return {"workspace": client.alias, "users": members,
                "next_cursor": page.get("response_metadata", {}).get("next_cursor", "")}

    @mcp.tool()
    def search_users(workspace: str | None = None, query: str = "") -> dict[str, Any]:
        """Substring match against user real_name/display_name/email/name."""
        start = time.time()
        client = SlackClient(REGISTRY.get(workspace))
        q = query.lower().strip()
        if not q:
            raise ValueError("query is required")
        matches = []
        cursor = None
        while True:
            page = safe_call(client.web.users_list, limit=200, cursor=cursor)
            for m in page.get("members", []):
                if m.get("deleted"):
                    continue
                profile = m.get("profile", {})
                blob = " ".join([
                    m.get("name", ""),
                    profile.get("real_name", ""),
                    profile.get("display_name", ""),
                    profile.get("email", ""),
                ]).lower()
                if q in blob:
                    matches.append(_condense(m))
            cursor = page.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        audit("search_users", {"workspace": workspace, "query": query},
              f"{len(matches)} matches", int((time.time() - start) * 1000))
        return {"workspace": client.alias, "query": query, "users": matches}

    @mcp.tool()
    def get_user_profile(user_id: str, workspace: str | None = None) -> dict[str, Any]:
        """Get full profile for a user_id (U... or W...)."""
        start = time.time()
        client = SlackClient(REGISTRY.get(workspace))
        info = safe_call(client.web.users_info, user=user_id)
        audit("get_user_profile", {"workspace": workspace, "user_id": user_id},
              "ok", int((time.time() - start) * 1000))
        return {"workspace": client.alias, "user": info.get("user")}
