# MCP Client Configuration Examples

Use this folder for copy-paste MCP config snippets.

## Choose Your Mode

- **Remote HTTP MCP (recommended):** use deployed endpoint `https://uml-mcp.vercel.app/mcp`
- **Local stdio MCP:** run `server.py` from your machine

## Remote HTTP MCP

Use this when you want zero local Python setup.

```json
"uml-mcp": {
  "transport": "http",
  "url": "https://uml-mcp.vercel.app/mcp"
}
```

Notes:

- Use `/mcp` path (not root URL)
- Local env vars like `MCP_OUTPUT_DIR` and `KROKI_SERVER` do not apply here
- Remote endpoint is read-only (no local file writes via `output_dir`)

## Local stdio MCP

Use this when you want local execution and file output support.

- **Cursor example:** `cursor_config.json`
- **Claude Desktop example:** `claude_desktop_config.json`

### Cursor config location

- Windows: `%APPDATA%\Cursor\User\globalStorage\cursor.mcp\mcp.json` (or Cursor Settings -> MCP)
- macOS: `~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp/mcp.json`
- Linux: `~/.config/Cursor/User/globalStorage/cursor.mcp/mcp.json`

### Claude Desktop config location

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

### Local config notes

- `cwd` must be your project root (the folder containing `server.py`)
- `args: ["-u", "server.py"]` runs unbuffered Python
- `MCP_OUTPUT_DIR`, `KROKI_SERVER`, and related env vars are local/self-hosted settings
- If you use a virtualenv or Poetry, set `command` to that Python interpreter (for example `C:\\path\\to\\uml-mcp\\.venv\\Scripts\\python.exe` on Windows)

See [Configuration](../docs/configuration.md) for the full local environment variable reference.
