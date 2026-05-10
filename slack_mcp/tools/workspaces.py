"""Meta tools: list_workspaces, healthcheck."""

from __future__ import annotations

import time
from typing import Any

from ..audit import audit, AUDIT_PATH
from ..client import SlackClient
from ..drafts import STORE
from ..workspaces import REGISTRY


def register(mcp) -> None:
    @mcp.tool()
    def list_workspaces() -> dict[str, Any]:
        """List configured Slack workspaces with auth type and primary status.

        Returns a dict with `workspaces` (list of redacted profiles), `primary`
        (alias of the default workspace), and `errors` (config errors found at
        load time, e.g. malformed env values). Tokens never appear in the
        response.
        """
        start = time.time()
        try:
            payload = {
                "workspaces": [REGISTRY.workspaces[a].redacted() for a in REGISTRY.aliases()],
                "primary": REGISTRY.primary,
                "errors": list(REGISTRY.errors),
            }
            audit("list_workspaces", {}, f"{len(payload['workspaces'])} workspaces",
                  int((time.time() - start) * 1000))
            return payload
        except Exception as e:  # noqa: BLE001
            audit("list_workspaces", {}, "", int((time.time() - start) * 1000), str(e))
            raise

    @mcp.tool()
    def healthcheck() -> dict[str, Any]:
        """Verify token validity per workspace + report draft store + audit log path.

        For each workspace, calls auth.test. Returns user_id and team domain on
        success, or error code on failure. Does not retry. A failed auth.test
        means the token has been invalidated (logout, password change, app
        revoke) and needs re-extraction per SETUP.md.
        """
        start = time.time()
        results = {}
        for alias in REGISTRY.aliases():
            try:
                client = SlackClient(REGISTRY.get(alias))
                info = client.auth_test()
                results[alias] = {
                    "ok": True,
                    "user": info.get("user"),
                    "user_id": info.get("user_id"),
                    "team": info.get("team"),
                    "team_id": info.get("team_id"),
                    "url": info.get("url"),
                    "auth_type": REGISTRY.get(alias).auth_type,
                }
            except Exception as e:  # noqa: BLE001
                results[alias] = {"ok": False, "error": str(e)}
        payload = {
            "workspaces": results,
            "primary": REGISTRY.primary,
            "config_errors": list(REGISTRY.errors),
            "draft_store_size": STORE.size(),
            "audit_log_path": str(AUDIT_PATH),
        }
        audit("healthcheck", {}, f"{sum(1 for v in results.values() if v.get('ok'))}/{len(results)} ok",
              int((time.time() - start) * 1000))
        return payload
