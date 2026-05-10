"""SlackClient — thin wrapper around slack_sdk.WebClient.

Per-workspace client construction with the right cookie header for xoxc
mode. Centralizes error handling so tools just call methods and trust the
SlackApiError -> string conversion.

slack_sdk handles retries, rate-limit backoff, and pagination cursors out
of the box. We don't reinvent.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .workspaces import Workspace

log = logging.getLogger("slack-mcp.client")


@lru_cache(maxsize=16)
def _client_for(token: str, cookie: str | None) -> WebClient:
    """Cache one WebClient per (token, cookie) pair."""
    headers = {}
    if cookie:
        # xoxc tokens need the xoxd= cookie alongside Authorization.
        # slack_sdk lets us pass arbitrary headers via the client.
        headers["Cookie"] = f"d={cookie}"
    return WebClient(token=token, headers=headers if headers else None)


class SlackClient:
    """Per-workspace client. Construct once, call many."""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.web = _client_for(workspace.token, workspace.cookie)

    def auth_test(self) -> dict:
        """Verify the token is valid. Returns user_id, team_id, etc.

        Raises SlackApiError on invalid_auth or network errors.
        """
        return self.web.auth_test().data  # type: ignore[no-any-return]

    @property
    def alias(self) -> str:
        return self.workspace.alias


def safe_call(fn, *args, **kwargs) -> dict:
    """Call a slack_sdk method and return .data, normalizing errors.

    Use this from tool modules so we never leak raw SlackApiError objects.
    """
    try:
        result = fn(*args, **kwargs)
        return result.data  # type: ignore[no-any-return]
    except SlackApiError as e:
        err = e.response.get("error", "unknown_error")
        raise RuntimeError(f"slack api error: {err}") from e
