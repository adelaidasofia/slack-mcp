"""Draft+confirm pattern for Slack writes.

Mirror of whatsapp-mcp drafts: send_*() returns a draft_id; nothing hits
Slack until confirm_send(draft_id). One-time confirm. 1-hour TTL.

Thread-safe via a single Lock; FastMCP runs tools concurrently.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

DRAFT_TTL_SECONDS = int(os.environ.get("SLACK_MCP_DRAFT_TTL_SECONDS", "3600"))
DRAFT_LOG_PATH = Path(os.environ.get(
    "SLACK_MCP_DRAFT_LOG_PATH",
    str(Path.home() / ".claude" / "slack-mcp" / "drafts.log"),
))


@dataclass
class Draft:
    draft_id: str
    workspace: str
    channel: str
    channel_name: str | None
    text: str
    thread_ts: str | None = None
    target_ts: str | None = None  # reply-quote drafts AND update drafts
    before_text: str | None = None  # update drafts: original text for diff preview
    kind: str = "send_message"     # send_message | send_reply_quote | update_message
    created_at: float = field(default_factory=time.time)
    confirmed: bool = False
    cancelled: bool = False

    def expires_at(self) -> float:
        return self.created_at + DRAFT_TTL_SECONDS

    def is_expired(self) -> bool:
        return time.time() > self.expires_at()


class DraftStore:
    """In-memory draft store + JSONL append for durability."""

    def __init__(self) -> None:
        self._drafts: dict[str, Draft] = {}
        self._lock = threading.Lock()

    def create(self, workspace: str, channel: str, channel_name: str | None,
               text: str, kind: str = "send_message",
               thread_ts: str | None = None, target_ts: str | None = None,
               before_text: str | None = None) -> Draft:
        with self._lock:
            draft = Draft(
                draft_id=uuid.uuid4().hex,
                workspace=workspace,
                channel=channel,
                channel_name=channel_name,
                text=text,
                thread_ts=thread_ts,
                target_ts=target_ts,
                before_text=before_text,
                kind=kind,
            )
            self._drafts[draft.draft_id] = draft
            self._append_log("create", draft)
            return draft

    def get(self, draft_id: str) -> Draft:
        with self._lock:
            draft = self._drafts.get(draft_id)
            if draft is None:
                raise KeyError(f"draft not found: {draft_id}")
            if draft.is_expired():
                raise ValueError(f"draft expired: {draft_id}")
            if draft.confirmed:
                raise ValueError(f"draft already confirmed: {draft_id}")
            if draft.cancelled:
                raise ValueError(f"draft cancelled: {draft_id}")
            return draft

    def confirm(self, draft_id: str) -> Draft:
        with self._lock:
            draft = self._drafts.get(draft_id)
            if draft is None:
                raise KeyError(f"draft not found: {draft_id}")
            if draft.is_expired():
                raise ValueError(f"draft expired: {draft_id}")
            if draft.confirmed:
                raise ValueError(f"draft already confirmed: {draft_id}")
            if draft.cancelled:
                raise ValueError(f"draft cancelled: {draft_id}")
            draft.confirmed = True
            self._append_log("confirm", draft)
            return draft

    def cancel(self, draft_id: str) -> Draft:
        with self._lock:
            draft = self._drafts.get(draft_id)
            if draft is None:
                raise KeyError(f"draft not found: {draft_id}")
            if draft.confirmed:
                raise ValueError(f"draft already confirmed: {draft_id}")
            draft.cancelled = True
            self._append_log("cancel", draft)
            return draft

    def list_pending(self) -> list[Draft]:
        with self._lock:
            return [
                d for d in self._drafts.values()
                if not d.confirmed and not d.cancelled and not d.is_expired()
            ]

    def size(self) -> int:
        with self._lock:
            return sum(
                1 for d in self._drafts.values()
                if not d.confirmed and not d.cancelled and not d.is_expired()
            )

    def _append_log(self, event: str, draft: Draft) -> None:
        try:
            DRAFT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            import json
            payload = {"event": event, "ts": time.time(), **asdict(draft)}
            with open(DRAFT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass


# Singleton
STORE = DraftStore()
