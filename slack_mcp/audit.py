"""JSONL audit log. Same pattern as whatsapp-mcp.

Every tool call appends one line. Records params, result_summary,
duration_ms, error. Path overridable via SLACK_MCP_AUDIT_LOG_PATH env.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path.home() / ".claude" / "slack-mcp" / "audit.log"
AUDIT_PATH = Path(os.environ.get("SLACK_MCP_AUDIT_LOG_PATH", str(DEFAULT_PATH)))
AUDIT_ENABLED = os.environ.get("SLACK_MCP_AUDIT_LOG", "true").lower() in ("1", "true", "yes", "on")


def audit(tool: str, params: dict[str, Any], result_summary: str,
          duration_ms: int, error: str | None = None) -> None:
    """Append one structured audit record."""
    if not AUDIT_ENABLED:
        return
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.time(),
            "tool": tool,
            "params": _redact(params),
            "result_summary": result_summary,
            "duration_ms": duration_ms,
            "error": error,
        }
        with open(AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _redact(params: dict[str, Any]) -> dict[str, Any]:
    """Strip token-like values from audit records."""
    redacted = {}
    for k, v in params.items():
        if isinstance(v, str) and (v.startswith("xox") or k.lower() in ("token", "cookie", "secret")):
            redacted[k] = "[REDACTED]"
        else:
            redacted[k] = v
    return redacted
