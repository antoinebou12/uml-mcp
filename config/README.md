# MCP client configuration examples

This folder holds **example** MCP server config snippets for UML-MCP. Copy the relevant block into your client’s config file and replace the paths with your actual `uml-mcp` install path.

## Cursor

- **File**:  
  - Windows: `%APPDATA%\Cursor\User\globalStorage\cursor.mcp\mcp.json` or Cursor Settings → MCP  
  - macOS: `~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp/mcp.json`  
  - Linux: `~/.config/Cursor/User/globalStorage/cursor.mcp/mcp.json`  

- **Example**: `cursor_config.json`  
  - Server key: **`uml-mcp`**. Set **`cwd`** to your repo root; the sample uses **`${workspaceFolder}`** if your Cursor build expands it in MCP config—otherwise substitute the absolute path.  
  - **`args`**: `["-u", "server.py"]` runs unbuffered Python with `server.py` relative to `cwd`.  
  - **`env`**: `KROKI_SERVER`, `MCP_OUTPUT_DIR` (`output` is relative to `cwd`), and `MCP_DIAGRAM_FALLBACK` (`true` for local Kroki fallbacks). See [Configuration](../docs/configuration.md).

## Claude Desktop

- **File**:  
  - Windows: `%APPDATA%\Claude\claude_desktop_config.json`  
  - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`  

- **Example**: `claude_desktop_config.json`  
  - Replace **`cwd`** (`C:\\Users\\YOU\\uml-mcp`) with your real project root (macOS/Linux: use `/path/to/uml-mcp`).  
  - Same `args` and `env` as Cursor (see above).

## Notes

- **`cwd`** must be the project root (the folder that contains `server.py`).
- If you use a virtualenv or Poetry, set **`command`** to that interpreter, e.g. `"C:\\path\\to\\uml-mcp\\.venv\\Scripts\\python.exe"` (Windows) or `"/path/to/uml-mcp/.venv/bin/python"` (macOS/Linux).
