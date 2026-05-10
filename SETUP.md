# slack-mcp setup

## 1. Install

```bash
git clone https://github.com/adelaidasofia/slack-mcp.git ~/.claude/slack-mcp
cd ~/.claude/slack-mcp
pip3 install --break-system-packages -r requirements.txt
cp .env.example .env
```

## 2. Extract Slack browser-session tokens (xoxc + xoxd)

The default and most-capable auth path. Repeat for each workspace.

1. Open Slack in your browser. Log into the workspace you want to add.
2. Open DevTools (Cmd+Option+I on Mac, Ctrl+Shift+I elsewhere).
3. **Get the `xoxc` token:**
   - Go to the **Network** tab.
   - Filter for `client.boot` or `users.info`.
   - Click any matching request → the **Headers** panel.
   - Scroll to `Form Data` (or look at the request payload).
   - Find the `token` field — value starts with `xoxc-...`. Copy it.
   - Alternative: open the **Sources** tab → `(no domain)` → `app.slack.com` → search the source for `xoxc-`. The first match is your token.
4. **Get the `xoxd` cookie:**
   - Go to the **Application** tab (Chrome) or **Storage** tab (Firefox).
   - Expand **Cookies** → `https://app.slack.com` (or `https://<workspace>.slack.com`).
   - Find the cookie named `d` — value starts with `xoxd-...`. Copy it.
5. Paste both into `~/.claude/slack-mcp/.env`:
   ```
   SLACK_WORKSPACE_ONDE_TYPE=xoxc
   SLACK_WORKSPACE_ONDE_TOKEN=xoxc-...   # the token from step 3
   SLACK_WORKSPACE_ONDE_COOKIE=xoxd-...  # the d cookie from step 4
   ```

## 3. Configure aliases

In `.env`, list every workspace you've configured under `SLACK_WORKSPACES`:

```
SLACK_WORKSPACES=onde,mycelium
SLACK_PRIMARY_WORKSPACE=onde
```

The alias is what you pass to tools as the `workspace` param. Lowercase, no spaces. Examples: `onde`, `mycelium`, `personal`, `clientx`.

## 4. Verify

```bash
cd ~/.claude/slack-mcp
python3 -c "from slack_mcp import server; print('OK')"
```

If that prints `OK` and shows your workspaces in the startup log, the config parses cleanly.

## 5. Register in Claude Code

Add to your project `.mcp.json` (or run `claude mcp add -s user slack ...`):

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

Validate the JSON parses (Lesson #14):

```bash
python3 -c "import json; json.load(open('.mcp.json'))" && echo OK
```

Restart Claude Code. Run `claude mcp list` and confirm `slack` shows as connected.

## 6. Smoke test

In a Claude Code session:

```
list workspaces                  # should return your aliases + primary
healthcheck                       # auth.test per workspace, returns user/team
list channels in onde             # paginated channel list
read channel #general in onde     # newest 50 messages, vault-exported
```

## Alternative auth: xoxp (User OAuth)

If you don't want occasional re-extraction:

1. Go to https://api.slack.com/apps → **Create New App** → From scratch.
2. Name your app, pick the workspace.
3. **OAuth & Permissions** → add user-token scopes:
   - `channels:history`, `channels:read`, `channels:write`
   - `groups:history`, `groups:read`, `groups:write`
   - `im:history`, `im:read`, `im:write`
   - `mpim:history`, `mpim:read`, `mpim:write`
   - `chat:write`, `reactions:write`
   - `search:read` (paid Slack plans only)
   - `users:read`, `users:read.email`
4. **Install to Workspace** → approve.
5. Copy the **User OAuth Token** (starts with `xoxp-`).
6. In `.env`:
   ```
   SLACK_WORKSPACE_ONDE_TYPE=xoxp
   SLACK_WORKSPACE_ONDE_TOKEN=xoxp-...
   ```
   No cookie needed for xoxp.

## Troubleshooting

- **`invalid_auth` on healthcheck.** The cookie or token has been invalidated (logged out, password change, or session expiry). Re-extract per step 2.
- **`missing_scope` on a tool.** xoxp only — install scope is missing. Re-add scopes to your app and re-install.
- **Channel not found.** Channel names are case-sensitive in Slack. Try `search_channels` to find the right name.
- **`search.messages` errors with auth_type bot.** xoxb tokens cannot search. Switch the workspace to xoxc or xoxp.
- **Vault export not appearing.** Check `SLACK_MCP_VAULT_PATH` matches your vault root. Default is `~/Documents/Vault`; override in `.env` if your vault lives elsewhere.
