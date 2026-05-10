Notable changes per release. Latest first.

## 0.1.1 — 2026-05-10

Added — edit-own-message surfaces (the two write tools that were missing from v0.1.0):

- `delete_own_message(workspace, channel, ts)` — one-shot `chat.delete`. Soft-success on `message_not_found` (already-deleted or wrong ts). xoxc user tokens can delete their own messages without special scopes. Audit-logged.
- `update_own_message(workspace, channel, ts, text)` — draft + confirm via the existing `confirm_send` gate. The draft fetches the current message text up front so the preview shows a before/after diff. Confirm dispatches `chat.update` instead of `chat.postMessage`.

Changed:

- `confirm_send` now dispatches by `draft.kind`: `update_message` routes to `chat.update`, everything else routes to `chat.postMessage`. Existing send/reply-quote behavior unchanged.
- `Draft` model gained `before_text` field (optional, for update drafts).
- Default `SLACK_MCP_VAULT_PATH` changed from a personal-specific path to a generic `~/Documents/Vault`. Local installs that need a different vault root should set the env var.

Why: today's session generated four reposts of a team broadcast because of voice corrections (channel routing, cross-contamination, first-person singular, self-referential tail). Each correction left an undeletable artifact in Slack that had to be cleaned manually. The MCP gap was hurting real work. Edit + delete close the loop so corrections happen in place.

## 0.1.0 — 2026-05-08

Initial public release. 16 tools:

- Meta: `list_workspaces`, `healthcheck`
- Read: `list_channels`, `search_channels`, `read_channel`, `read_thread`, `list_users`, `search_users`, `get_user_profile`, `search_messages`
- Write (draft+confirm): `send_message` → `confirm_send`, `send_reply_quote` → `confirm_send`, `cancel_draft`
- Write (low-consequence, immediate): `add_reaction`, `mark_read`

Built because the existing Slack MCP servers are single-workspace per instance and the Anthropic reference implementation was deprecated.

Differentiators: native multi-workspace (`xoxc/xoxd`, `xoxp`, `xoxb` per workspace), draft+confirm on every write, vault auto-export of every channel read, prompt-injection scrubber, JSONL audit log with token redaction.
