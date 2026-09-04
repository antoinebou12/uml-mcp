# VS Code / GitHub Copilot Integration

Connect UML-MCP to **VS Code** so **GitHub Copilot Chat** (Agent mode) can generate diagrams.

## Overview

VS Code uses a different MCP JSON shape than Cursor or Claude Desktop:

- Root key is **`servers`**, not `mcpServers`
- Remote entries need **`"type": "http"`**
- Tools run only when Copilot Chat is in **Agent** mode

## Quick setup (hosted MCP)

This repository ships [`.vscode/mcp.json`](https://github.com/antoinebou12/uml-mcp/blob/main/.vscode/mcp.json):

```json
{
  "servers": {
    "uml-mcp": {
      "type": "http",
      "url": "https://uml-mcp.vercel.app/mcp"
    }
  }
}
```

1. Open this repo in VS Code (or copy the block into your user MCP config).
2. Command Palette → **MCP: List Servers** and confirm **uml-mcp** is running.
3. Open **GitHub Copilot Chat**, switch the mode dropdown to **Agent**.
4. Ask for a diagram (for example: “Show a Mermaid sequence Client → Server as a PNG in chat”).

No local Python install is required for the hosted endpoint. The MCP route is **`/mcp`**, not the site root.

Copy-paste template: [`config/vscode_mcp.json`](https://github.com/antoinebou12/uml-mcp/blob/main/config/vscode_mcp.json).

### User-wide config

Command Palette → **MCP: Open User Configuration** and merge the same `servers.uml-mcp` entry. User config applies across workspaces and can sync via Settings Sync.

## Showing diagrams in chat

Prefer **`generate_uml_image`** with `output_format: png` for a native inline image. See the shared chat notes in [Cursor integration](cursor.md#showing-diagrams-in-chat-cursor--copilot--claude).

## Local stdio MCP (optional)

For local file output, merge [`config/vscode_mcp_stdio.json`](https://github.com/antoinebou12/uml-mcp/blob/main/config/vscode_mcp_stdio.json):

```json
{
  "servers": {
    "uml-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "python", "-u", "server.py"],
      "cwd": "${workspaceFolder}",
      "env": {
        "KROKI_SERVER": "https://kroki.io",
        "MCP_OUTPUT_DIR": "output",
        "MCP_DIAGRAM_FALLBACK": "true"
      }
    }
  }
}
```

Adjust env per [Configuration](../configuration.md).

## Test the integration

```
Create a Mermaid sequence diagram for Client calling Server and show it as a PNG in chat.
```

You should see tools from **uml-mcp** (`list_diagram_types`, `generate_uml`, `generate_uml_image`, …) and a chat image or markdown `![diagram](url)` plus **Playground**.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| No tools appear | Confirm root key is `servers` (not `mcpServers`). Copied Cursor JSON is silently ignored. |
| Server listed but unused | Switch Copilot Chat to **Agent** mode. |
| HTTP type missing | Add `"type": "http"` for the hosted URL. |
| Timeout on Mermaid | Hosted fallback uses mermaid.ink; retry, or use local stdio with `MCP_DIAGRAM_FALLBACK=true`. |
| Wrong URL | Use `https://uml-mcp.vercel.app/mcp`, not the site root. |

More client snippets: [`config/README.md`](https://github.com/antoinebou12/uml-mcp/blob/main/config/README.md).
