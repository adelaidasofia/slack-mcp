"""Multi-workspace registry with triple-mode auth.

Each workspace is identified by a short alias (`onde`, `mycelium`) and
backed by ONE of three auth modes:

  - xoxc: browser-session token from Slack web cookies (highest capability)
            requires both SLACK_WORKSPACE_<ALIAS>_TOKEN (xoxc-...) and
            SLACK_WORKSPACE_<ALIAS>_COOKIE (xoxd-... d cookie value)
  - xoxp: user OAuth token (permanent, slightly less capable on free plans)
            requires SLACK_WORKSPACE_<ALIAS>_TOKEN (xoxp-...)
  - xoxb: bot token (least capable, invited channels only)
            requires SLACK_WORKSPACE_<ALIAS>_TOKEN (xoxb-...)

Config is read from `~/.claude/slack-mcp/.env` at process start (and from
the surrounding env). Envs are evaluated lazily so adding a workspace mid-
session is picked up on next list_workspaces call after a server reload.

Format (in .env):

    SLACK_WORKSPACES=onde,mycelium
    SLACK_PRIMARY_WORKSPACE=onde

    SLACK_WORKSPACE_ONDE_TYPE=xoxc
    SLACK_WORKSPACE_ONDE_TOKEN=xoxc-...
    SLACK_WORKSPACE_ONDE_COOKIE=xoxd-...
    SLACK_WORKSPACE_ONDE_TEAM_ID=T0123456

    SLACK_WORKSPACE_MYCELIUM_TYPE=xoxp
    SLACK_WORKSPACE_MYCELIUM_TOKEN=xoxp-...
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

ENV_FILE = Path.home() / ".claude" / "slack-mcp" / ".env"


def _load_env_file() -> None:
    """Lightweight .env loader. No python-dotenv dependency."""
    if not ENV_FILE.exists():
        return
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Don't overwrite real env if already set
            if key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass


@dataclass
class Workspace:
    alias: str
    auth_type: str  # "xoxc" | "xoxp" | "xoxb"
    token: str
    cookie: str | None = None  # xoxc only (the d cookie value)
    team_id: str | None = None
    label: str | None = None

    def is_browser_session(self) -> bool:
        return self.auth_type == "xoxc"

    def has_search(self) -> bool:
        # xoxb tokens cannot use search.messages
        return self.auth_type in ("xoxc", "xoxp")

    def redacted(self) -> dict:
        return {
            "alias": self.alias,
            "auth_type": self.auth_type,
            "token_prefix": self.token[:8] + "..." if self.token else "",
            "has_cookie": bool(self.cookie),
            "team_id": self.team_id,
            "label": self.label,
        }


@dataclass
class WorkspaceRegistry:
    workspaces: dict[str, Workspace] = field(default_factory=dict)
    primary: str | None = None
    errors: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "WorkspaceRegistry":
        _load_env_file()
        registry = cls()
        aliases_csv = os.environ.get("SLACK_WORKSPACES", "").strip()
        if not aliases_csv:
            registry.errors.append(
                "SLACK_WORKSPACES not set. Edit ~/.claude/slack-mcp/.env "
                "(see SETUP.md for cookie extraction)."
            )
            return registry
        primary = os.environ.get("SLACK_PRIMARY_WORKSPACE", "").strip().lower() or None
        for alias_raw in aliases_csv.split(","):
            alias = alias_raw.strip().lower()
            if not alias:
                continue
            ws = cls._load_one(alias)
            if isinstance(ws, Workspace):
                registry.workspaces[alias] = ws
            else:
                registry.errors.append(ws)
        if primary and primary in registry.workspaces:
            registry.primary = primary
        elif registry.workspaces:
            # Fall back to first listed workspace
            registry.primary = next(iter(registry.workspaces))
        return registry

    @staticmethod
    def _load_one(alias: str) -> Workspace | str:
        upper = alias.upper().replace("-", "_")
        prefix = f"SLACK_WORKSPACE_{upper}_"
        auth_type = os.environ.get(prefix + "TYPE", "").strip().lower()
        if auth_type not in ("xoxc", "xoxp", "xoxb"):
            return f"workspace '{alias}': missing or invalid {prefix}TYPE (need xoxc|xoxp|xoxb)"
        token = os.environ.get(prefix + "TOKEN", "").strip()
        if not token:
            return f"workspace '{alias}': missing {prefix}TOKEN"
        if auth_type == "xoxc" and not token.startswith("xoxc-"):
            return f"workspace '{alias}': xoxc TYPE requires token starting xoxc-"
        if auth_type == "xoxp" and not token.startswith("xoxp-"):
            return f"workspace '{alias}': xoxp TYPE requires token starting xoxp-"
        if auth_type == "xoxb" and not token.startswith("xoxb-"):
            return f"workspace '{alias}': xoxb TYPE requires token starting xoxb-"
        cookie = None
        if auth_type == "xoxc":
            cookie = os.environ.get(prefix + "COOKIE", "").strip()
            if not cookie:
                return f"workspace '{alias}': xoxc TYPE requires {prefix}COOKIE (xoxd-...)"
            if not cookie.startswith("xoxd-"):
                return f"workspace '{alias}': cookie must start xoxd-"
        return Workspace(
            alias=alias,
            auth_type=auth_type,
            token=token,
            cookie=cookie,
            team_id=os.environ.get(prefix + "TEAM_ID", "").strip() or None,
            label=os.environ.get(prefix + "LABEL", "").strip() or None,
        )

    def get(self, alias: str | None) -> Workspace:
        target = (alias or self.primary or "").strip().lower()
        if not target:
            raise ValueError("no workspace specified and no primary configured")
        if target not in self.workspaces:
            available = ", ".join(self.workspaces) or "(none configured)"
            raise KeyError(f"unknown workspace '{target}'. available: {available}")
        return self.workspaces[target]

    def aliases(self) -> Iterable[str]:
        return list(self.workspaces.keys())


# Loaded once per server process. Server.py rebuilds via lifespan.
REGISTRY = WorkspaceRegistry.from_env()
