"""Vault auto-export. When a read tool returns messages, we mirror the
channel to `<VAULT_ROOT>/🤖 AI Chats/Slack/<workspace>/<channel>.md`.

Idempotent: same channel + same day overwrites cleanly. Failures are
logged but never raised (vault export is best-effort, never blocks the
read tool that triggered it).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from ._shared.markdown import channel_to_markdown
from .scrubber import scrub_message

log = logging.getLogger("slack-mcp.vault_export")

VAULT_ROOT = Path(os.environ.get(
    "SLACK_MCP_VAULT_PATH",
    str(Path.home() / "Documents" / "Vault"),
))
EXPORT_DIR_NAME = "🤖 AI Chats"
SLACK_DIR_NAME = "Slack"
ENABLED = os.environ.get("SLACK_MCP_VAULT_EXPORT", "true").lower() in ("1", "true", "yes", "on")


def export_channel(workspace: str, channel_name: str, channel_id: str,
                   messages: list[dict[str, Any]],
                   user_lookup: dict[str, str] | None = None) -> str | None:
    """Write the channel to vault. Returns the path written, or None."""
    if not ENABLED or not messages:
        return None
    try:
        target_dir = VAULT_ROOT / EXPORT_DIR_NAME / SLACK_DIR_NAME / workspace
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{channel_name}.md"
        scrubbed = [scrub_message(m) for m in messages]
        markdown = channel_to_markdown(workspace, channel_name, channel_id, scrubbed, user_lookup)
        target.write_text(markdown, encoding="utf-8")
        return str(target)
    except Exception as e:  # noqa: BLE001
        log.warning("vault_export failed for %s/%s: %s", workspace, channel_name, e)
        return None
