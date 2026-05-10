"""Render Slack messages and threads to vault-flavored markdown.

Output shape matches the existing ingest-slack skill's convention so the
vault stays internally consistent: one `##` heading per parent message,
threads as `###` sub-sections, ts as a stable anchor.
"""

from __future__ import annotations

from typing import Any

from .slack_ts import ts_to_human, ts_to_iso


def render_message(msg: dict[str, Any], user_lookup: dict[str, str] | None = None) -> str:
    """Render a single Slack message dict to a markdown block.

    user_lookup maps user_id -> display name. Pass None to render raw IDs.
    """
    ts = msg.get("ts", "")
    user_id = msg.get("user") or msg.get("bot_id") or "unknown"
    user_name = (user_lookup or {}).get(user_id, user_id)
    text = msg.get("text", "")
    when = ts_to_human(ts) if ts else ""
    iso = ts_to_iso(ts) if ts else ""

    out = [f"## {user_name} — {when}", f"<!-- ts: {ts} | iso: {iso} -->", "", text]
    files = msg.get("files") or []
    if files:
        out.append("")
        for f in files:
            name = f.get("name", "file")
            url = f.get("url_private", "")
            out.append(f"- 📎 [{name}]({url})")
    return "\n".join(out)


def render_thread(parent: dict[str, Any], replies: list[dict[str, Any]],
                  user_lookup: dict[str, str] | None = None) -> str:
    """Render a parent message + its thread replies as nested markdown."""
    sections = [render_message(parent, user_lookup)]
    if replies:
        sections.append("\n### Thread\n")
        for reply in replies:
            ts = reply.get("ts", "")
            user_id = reply.get("user") or "unknown"
            user_name = (user_lookup or {}).get(user_id, user_id)
            when = ts_to_human(ts) if ts else ""
            text = reply.get("text", "")
            sections.append(f"\n**{user_name}** — {when}\n\n{text}")
    return "\n".join(sections)


def channel_to_markdown(workspace: str, channel_name: str, channel_id: str,
                         messages: list[dict[str, Any]],
                         user_lookup: dict[str, str] | None = None) -> str:
    """Full channel-day file format: frontmatter + message blocks."""
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fm = [
        "---",
        f"workspace: {workspace}",
        f"channel: {channel_name}",
        f"channel_id: {channel_id}",
        f"exported: {today}",
        "type: slack-export",
        "---",
        "",
        f"# #{channel_name} — {today}",
        "",
    ]
    blocks = [render_message(m, user_lookup) for m in messages]
    return "\n".join(fm) + "\n\n---\n\n".join(blocks) + "\n"
