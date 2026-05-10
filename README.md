# slack-mcp

Multi-workspace Slack MCP server with draft+confirm safety, vault auto-export, and triple-mode auth.

One process, N workspaces, every write goes through draft → confirm. Built because the existing Slack MCP servers are single-workspace per instance and the Anthropic reference impl was deprecated.

## Why use this over the alternatives

| | This | Anthropic connector | korotovsky/slack-mcp-server |
|---|---|---|---|
| Multi-workspace per server | Yes | No | No |
| Draft + confirm on writes | Yes | No | No |
| Vault auto-export of reads | Yes | No | No |
| Prompt-injection scrubber | Yes | No | No |
| Audit log | Yes | No | No |
| xoxc / xoxp / xoxb auth | Yes | n/a | Yes |
| Status | Active | Active (limited) | Active |

## Install

```bash
git clone https://github.com/adelaidasofia/slack-mcp.git ~/.claude/slack-mcp
cd ~/.claude/slack-mcp
pip3 install --break-system-packages -r requirements.txt
cp .env.example .env
# fill in tokens — see SETUP.md for cookie extraction walkthrough
```

Register in your project `.mcp.json` (or via `claude mcp add -s user`):

```json
{
  "mcpServers": {
    "slack": {
      "command": "python3",
      "args": ["-m", "slack_mcp.server"],
      "cwd": "/Users/YOU/.claude/slack-mcp"
    }
  }
}
```

Restart Claude Code, then run `claude mcp list` to verify `slack` shows up.

## Tools (v0.1.1)

**Meta:** `list_workspaces`, `healthcheck`

**Read:** `list_channels`, `search_channels`, `read_channel`, `read_thread`, `list_users`, `search_users`, `get_user_profile`, `search_messages`

**Write (draft+confirm):** `send_message` → `confirm_send`, `send_reply_quote` → `confirm_send`, `update_own_message` → `confirm_send`, `cancel_draft`

**Write (low-consequence, immediate):** `add_reaction`, `mark_read`, `delete_own_message`

## Auth modes

| Mode | Token shape | Capability | When to use |
|---|---|---|---|
| `xoxc` | `xoxc-...` + `xoxd-...` cookie | Full (search, internal APIs) | Default. Best for personal use across multiple workspaces. |
| `xoxp` | `xoxp-...` | Permanent, OAuth, search restricted on free plans | If you don't want occasional cookie re-extraction. |
| `xoxb` | `xoxb-...` | Bot-only, no search, invited channels only | Rare. Use only when you want bot semantics. |

Cookie extraction takes ~3 minutes per workspace. See SETUP.md.

## Vault auto-export

Every `read_channel` call mirrors the channel to `<vault>/🤖 AI Chats/Slack/<workspace>/<channel>.md`. Idempotent (same channel + day overwrites cleanly). Disable via `SLACK_MCP_VAULT_EXPORT=false`.

## Configuration

All config via env vars (loaded from `.env` at process start):

- `SLACK_WORKSPACES` — comma-separated list of aliases (e.g. `onde,mycelium`)
- `SLACK_PRIMARY_WORKSPACE` — default workspace when tool calls omit `workspace`
- Per-workspace: `SLACK_WORKSPACE_<ALIAS>_TYPE`, `_TOKEN`, `_COOKIE` (xoxc only), `_TEAM_ID`, `_LABEL`
- `SLACK_MCP_VAULT_PATH` — vault root for the auto-export mirror (default `~/Documents/Vault`)
- `SLACK_MCP_VAULT_EXPORT` — `true`/`false` (default `true`)
- `SLACK_MCP_AUDIT_LOG_PATH` — JSONL audit log path
- `SLACK_MCP_DRAFT_TTL_SECONDS` — draft expiration (default 3600)
- `SLACK_MCP_SCRUB_PROMPT_INJECTION` — `true`/`false` (default `true`)

## Safety patterns

- **Draft + confirm.** Every send (`send_message`, `send_reply_quote`, `update_own_message`) returns a `draft_id`. Nothing posts until `confirm_send(draft_id)` is called. Drafts expire after 1 hour. One-time confirm. `update_own_message` drafts include a before/after preview so the operator can diff before confirming the edit.
- **Workspace required on writes.** No global default for sends — every write tool requires `workspace` to prevent wrong-workspace posts when channel names collide.
- **Audit log.** Every tool call appends a JSONL record. Tokens are redacted.
- **Prompt-injection scrubber.** Incoming message text is sanitized for known prompt-injection patterns (zalgo, role-spoof headers, fake fences). Hits are wrapped not deleted so the operator sees the attempt.
- **Token redaction.** `list_workspaces` returns redacted profiles only. Tokens never appear in tool responses.

## Related MCPs

Same author, same architecture pattern (FastMCP, draft+confirm on writes where applicable, vault auto-export, MIT):

- [imessage-mcp](https://github.com/adelaidasofia/imessage-mcp) - macOS iMessage
- [whatsapp-mcp](https://github.com/adelaidasofia/whatsapp-mcp) - WhatsApp via whatsmeow
- [google-workspace-mcp](https://github.com/adelaidasofia/google-workspace-mcp) - Gmail / Calendar / Drive / Docs / Sheets
- [apollo-mcp](https://github.com/adelaidasofia/apollo-mcp) - Apollo.io CRM + sequences
- [substack-mcp](https://github.com/adelaidasofia/substack-mcp) - Substack writing + analytics
- [luma-mcp](https://github.com/adelaidasofia/luma-mcp) - lu.ma events
- [parse-mcp](https://github.com/adelaidasofia/parse-mcp) - markitdown / Docling / LlamaParse router
- [rescuetime-mcp](https://github.com/adelaidasofia/rescuetime-mcp) - RescueTime productivity data
- [graph-query-mcp](https://github.com/adelaidasofia/graph-query-mcp) - vault knowledge graph queries
- [investor-relations-mcp](https://github.com/adelaidasofia/investor-relations-mcp) - seed-raise pipeline tracker
- [vault-sync-mcp](https://github.com/adelaidasofia/vault-sync-mcp) - bidirectional vault sync

## License

MIT — see [LICENSE](LICENSE).

---

Built by Adelaida Diaz-Roa. Full install or team version at diazroa.com.
