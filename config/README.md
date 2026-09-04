# MCP Client Configuration Examples
#
# Copy-paste snippets for remote HTTP (hosted) and local stdio.
# Hosted endpoint: https://uml-mcp.vercel.app/mcp  (always use /mcp, not the site root)

## Choose your mode

| Mode | When to use | Env vars on client |
| --- | --- | --- |
| **Remote HTTP** (recommended) | Zero local Python; chat PNG via force-fetch tools | Client-side `KROKI_SERVER` / `MCP_OUTPUT_DIR` do **not** apply |
| **Local stdio** | File output (`output_dir`), offline Kroki, full control | Set `KROKI_SERVER`, `MCP_OUTPUT_DIR`, `MCP_DIAGRAM_FALLBACK` |

Remote snippet shape (Cursor / many JSON clients):

```json
"uml-mcp": {
  "transport": "http",
  "url": "https://uml-mcp.vercel.app/mcp"
}
```

## Client matrix

| Client | Hosted HTTP | Local stdio | Guide |
| --- | --- | --- | --- |
| Cursor | [cursor_http.json](cursor_http.json) · [`.cursor/mcp.json`](../.cursor/mcp.json) | [cursor_config.json](cursor_config.json) | [docs/integrations/cursor.md](../docs/integrations/cursor.md) |
| Claude Desktop | [claude_desktop_http.json](claude_desktop_http.json) | [claude_desktop_config.json](claude_desktop_config.json) | [docs/integrations/claude_desktop.md](../docs/integrations/claude_desktop.md) |
| VS Code / GitHub Copilot | [vscode_mcp.json](vscode_mcp.json) · [`.vscode/mcp.json`](../.vscode/mcp.json) | [vscode_mcp_stdio.json](vscode_mcp_stdio.json) | [docs/integrations/vscode_copilot.md](../docs/integrations/vscode_copilot.md) |
| OpenAI Codex | [codex_config.toml](codex_config.toml) · [`.codex/config.toml`](../.codex/config.toml) | [codex_stdio.toml](codex_stdio.toml) | [docs/integrations/openai_codex.md](../docs/integrations/openai_codex.md) |
| Open WebUI + Ollama | [openwebui_mcp.json](openwebui_mcp.json) | Optional via [mcpo](../docs/integrations/ollama.md#local-stdio-via-mcpo) | [docs/integrations/ollama.md](../docs/integrations/ollama.md) |
| Continue + Ollama | [continue_config.yaml](continue_config.yaml) | See comments in that file | [docs/integrations/ollama.md](../docs/integrations/ollama.md) |

## Config locations

### Cursor

- Windows: `%APPDATA%\Cursor\User\globalStorage\cursor.mcp\mcp.json` (or **Cursor Settings → MCP**)
- macOS: `~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp/mcp.json`
- Linux: `~/.config/Cursor/User/globalStorage/cursor.mcp/mcp.json`

### Claude Desktop

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

### VS Code / GitHub Copilot

- Workspace (recommended): `.vscode/mcp.json` — root key is **`servers`**, not `mcpServers`
- User profile: Command Palette → **MCP: Open User Configuration**
- Copilot Chat must be in **Agent** mode for tools to run

### OpenAI Codex (CLI + IDE)

- User: `~/.codex/config.toml`
- Project: `.codex/config.toml` (loads only when the project is **trusted**)
- Verify: `codex mcp list` or `/mcp` in a session

### Open WebUI (Ollama models)

- Admin → Settings → Integrations → External Tool Servers
- Type: **MCP (Streamable HTTP)**; URL: `https://uml-mcp.vercel.app/mcp`
- On the model: **Function Calling = Native**, enable the UML-MCP tools

## Local stdio notes

- `cwd` must be the repo root (folder containing `server.py`)
- Prefer `uv run python -u server.py` or a venv Python for `command`
- `args: ["-u", "server.py"]` runs unbuffered Python when using a bare interpreter
- Set `MCP_READ_ONLY=true` to block file writes on shared hosts
- Full env reference: [docs/configuration.md](../docs/configuration.md)
