---
title: Local install (single user)
description: "Install UML-MCP for one user on one machine: uv tool install, a local uml-mcp.yaml, and one-command registration in VS Code, Cursor, Claude Desktop or Claude Code."
---

# Local install (single user, stdio)

This is the local-only path: no server to host and no account. The MCP client
starts `uml-mcp` as a subprocess (stdio), and diagrams render through Kroki.

## 1. Install the command

```bash
uv tool install uml-mcp        # or: pipx install uml-mcp
uml-mcp --help
```

Upgrade later with `uv tool upgrade uml-mcp`.

## 2. Create your configuration (optional)

```bash
uml-mcp config init --profile local    # writes ~/.config/uml-mcp/config.yaml
uml-mcp config validate
```

The local profile keeps everything on your machine:

- the output directory is `~/uml-mcp/output`
- the rotating log is `~/.local/state/uml-mcp/server.log`
- an optional JSONL audit trail of your tool calls is in `~/.local/state/uml-mcp/audit.jsonl`

Edit the file to switch Kroki server, disable tools, or turn on the audit.
See the [uml-mcp.yaml reference](configuration/uml-mcp-yaml.md).

## 3. Register it in your client

```bash
uml-mcp client install --client vscode           # user settings (all workspaces)
uml-mcp client install --client vscode --scope workspace   # .vscode/mcp.json
uml-mcp client install --client cursor
uml-mcp client install --client claude-desktop
uml-mcp client install --client claude-code      # prints the `claude mcp add` command
```

- `--dry-run` prints the merged JSON without writing anything.
- The command merges one `uml-mcp` stdio entry into the client's existing file.
  Other servers are kept, a timestamped backup (`*.bak-<time>`) is written first,
  and running it twice changes nothing.
- It uses the installed `uml-mcp` executable, or `uvx uml-mcp` when that isn't on
  `PATH`.

Restart the client, then ask: *"Draw a sequence diagram of an OAuth login"*.

| Client | File written (user scope) |
| --- | --- |
| VS Code | `~/.config/Code/User/mcp.json` (macOS: `~/Library/Application Support/Code/User`, Windows: `%APPDATA%\Code\User`) |
| Cursor | `~/.cursor/mcp.json` |
| Claude Desktop | `claude_desktop_config.json` in the Claude app config folder |
| Claude Code | none: run the printed `claude mcp add --scope user uml-mcp -- uml-mcp --transport stdio` |

## 4. Optional: local dashboard

For a quick look at your own activity:

```yaml
# ~/.config/uml-mcp/config.yaml
audit: {enabled: true, sinks: [memory, file], file: {path: ~/.local/state/uml-mcp/audit.jsonl}}
metrics: {enabled: true}
admin: {allow_local_without_auth: true}
```

The dashboard is part of the full HTTP app (`app.py`), so run it from a clone:
`uv run uvicorn app:app --host 127.0.0.1 --port 8000`. Then open
<http://127.0.0.1:8000/admin>. Only loopback clients can reach it. The stdio
server installed above stays the one your client uses.

## Uninstall

```bash
uv tool uninstall uml-mcp
rm -rf ~/.config/uml-mcp ~/.local/state/uml-mcp
```

Then remove the `uml-mcp` entry from your client's MCP config. The backup next to
it holds your previous version.
