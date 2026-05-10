"""Message search: search_messages.

search.messages requires a user-scope token (xoxc or xoxp). xoxb tokens
do not have search permissions; the tool will raise on bot-only workspaces.
"""

from __future__ import annotations

import time
from typing import Any

from ..audit import audit
from ..client import SlackClient, safe_call
from ..scrubber import scrub_message
from ..workspaces import REGISTRY


def register(mcp) -> None:
    @mcp.tool()
    def search_messages(query: str, workspace: str | None = None,
                        channel: str | None = None,
                        sort: str = "timestamp",
                        sort_dir: str = "desc",
                        limit: int = 20) -> dict[str, Any]:
        """Search messages with Slack's full-text search.

        Slack search modifiers work in `query`: `in:#channel`, `from:@user`,
        `before:YYYY-MM-DD`, `after:YYYY-MM-DD`, `"exact phrase"`. The
        explicit `channel` param is sugar — when provided, prepends
        `in:<channel>` to the query.

        Requires xoxc or xoxp auth (xoxb cannot search). Errors loudly
        with the workspace's actual auth_type if search isn't available.
        """
        start = time.time()
        ws = REGISTRY.get(workspace)
        if not ws.has_search():
            raise RuntimeError(
                f"workspace '{ws.alias}' uses {ws.auth_type} auth, which cannot "
                "use search.messages. Use xoxc (browser session) or xoxp."
            )
        client = SlackClient(ws)
        full_q = query.strip()
        if channel:
            channel_token = channel if channel.startswith("#") else f"#{channel}"
            full_q = f"in:{channel_token} {full_q}"
        page = safe_call(client.web.search_messages,
                         query=full_q, sort=sort, sort_dir=sort_dir,
                         count=min(limit, 100))
        matches = page.get("messages", {}).get("matches", [])
        scrubbed = [scrub_message(m) for m in matches]
        audit("search_messages",
              {"workspace": workspace, "query": query, "channel": channel,
               "limit": limit},
              f"{len(scrubbed)} matches", int((time.time() - start) * 1000))
        return {
            "workspace": client.alias,
            "query": full_q,
            "matches": scrubbed,
            "total": page.get("messages", {}).get("total"),
        }
