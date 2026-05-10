"""Prompt-injection scrubber for incoming Slack message text.

Strips zalgo, suspicious code-fence overrides, role-spoof headers, and
leading-whitespace tricks. Conservative: removes patterns matching known
injection shapes; leaves normal prose untouched.

Mirror of whatsapp-mcp/scrubber pattern.
"""

from __future__ import annotations

import os
import re
import unicodedata

ENABLED = os.environ.get("SLACK_MCP_SCRUB_PROMPT_INJECTION", "true").lower() in ("1", "true", "yes", "on")

# Common injection prefixes attackers use to flip role context.
INJECTION_PREFIXES = re.compile(
    r"(?i)^\s*(system\s*[:\-]|assistant\s*[:\-]|ignore (all |the )?previous instructions|disregard "
    r"(your |the )?previous|new instructions:|you are now|act as if|pretend you are)",
    re.MULTILINE,
)

# Code-fence used to inject false-system blocks.
FAKE_FENCE = re.compile(r"```(?:system|sudo|root|admin)\b[^`]*```", re.IGNORECASE | re.DOTALL)

# Hidden zero-width and bidi-control characters.
INVISIBLE_CHARS = re.compile(
    r"[​‌‍‎‏‪‫‬‭‮⁦⁧⁨⁩﻿]"
)


def scrub(text: str) -> str:
    """Return text with injection patterns neutralized.

    Neutralization is wrap-in-backticks rather than delete: we want the
    operator to see the attempt, not silently strip it.
    """
    if not ENABLED or not text:
        return text
    out = INVISIBLE_CHARS.sub("", text)
    out = unicodedata.normalize("NFKC", out)
    out = FAKE_FENCE.sub(lambda m: f"`[scrubbed-fake-fence: {m.group(0)[:40]}...]`", out)
    out = INJECTION_PREFIXES.sub(lambda m: f"`[scrubbed-prefix: {m.group(0)}]`", out)
    return out


def scrub_message(msg: dict) -> dict:
    """Apply scrub() to a Slack message dict's text field. Returns new dict."""
    if "text" in msg and isinstance(msg["text"], str):
        return {**msg, "text": scrub(msg["text"])}
    return msg
