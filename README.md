# slack-mcp


<!-- mycelium-badges:start -->

<p>
  <a href="https://github.com/adelaidasofia/slack-mcp/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/adelaidasofia/slack-mcp?color=blue"></a>
  <a href="https://github.com/adelaidasofia/slack-mcp/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/adelaidasofia/slack-mcp?color=eab308"></a>
  <a href="https://github.com/adelaidasofia/slack-mcp/commits/main"><img alt="Last commit" src="https://img.shields.io/github/last-commit/adelaidasofia/slack-mcp"></a>
  <a href="https://github.com/adelaidasofia/slack-mcp/issues"><img alt="Open issues" src="https://img.shields.io/github/issues/adelaidasofia/slack-mcp"></a>
  <a href="https://pypi.org/project/adelaidasofia-slack-mcp/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/adelaidasofia-slack-mcp?color=blue&label=pypi"></a>
  <a href="https://pypi.org/project/adelaidasofia-slack-mcp/"><img alt="PyPI downloads" src="https://img.shields.io/pypi/dm/adelaidasofia-slack-mcp?color=blue&label=downloads"></a>
  <a href="https://myceliumai.co"><img alt="Built by Mycelium AI" src="https://img.shields.io/badge/built_by-Mycelium_AI-15B89A"></a>
</p>

<!-- mycelium-badges:end -->

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

Open Claude Code, paste:

    /plugin marketplace add adelaidasofia/slack-mcp
    /plugin install slack-mcp@slack-mcp

Then fill in tokens in `.env` (see SETUP.md for cookie extraction walkthrough).

<details>
<summary>Legacy install</summary>

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

</details>

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


## Telemetry

This plugin sends a single anonymous install signal to `myceliumai.co` the first time it loads in a Claude Code session on a given machine.

**What is sent:**
- Plugin name (e.g. `slack-mcp`)
- Plugin version (e.g. `0.1.0`)

**What is NOT sent:**
- No user identifiers, names, emails, tokens, or API keys
- No file paths, message content, or anything from your work
- No IP address is stored after dedup processing

**Why:** Helps the maintainer know which plugins people actually install, so attention goes to the ones that get used.

**Opt out:** Set the environment variable `MYCELIUM_NO_PING=1` before launching Claude Code. The hook will skip the network call entirely. Already-pinged installs leave a sentinel at `~/.mycelium/onboarded-<plugin>` — delete it if you want to reset state.

## License

MIT — see [LICENSE](LICENSE).

---

Built by Adelaida Diaz-Roa. Full install or team version at diazroa.com.
