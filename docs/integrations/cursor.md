# Cursor Integration

Connect UML-MCP to Cursor to generate diagrams in the editor.

## Overview

Cursor connects to UML-MCP as an MCP server so you can generate and view UML and other supported diagram types in the editor.

## Quick setup (hosted MCP)

This repository ships a minimal project MCP config at **[`.cursor/mcp.json`](https://github.com/antoinebou12/uml-mcp/blob/main/.cursor/mcp.json)**:

```json
{
  "mcpServers": {
    "uml-mcp": {
      "transport": "http",
      "url": "https://uml-mcp.vercel.app/mcp"
    }
  }
}
```

1. Clone or open this repo in Cursor (or copy that `mcpServers` block into your user MCP settings).
2. Restart Cursor.
3. Confirm **uml-mcp** appears under **Cursor Settings → MCP**.

No local Python install is required for the hosted endpoint. The MCP route is **`/mcp`**, not the site root.

On every push to `main`, the CD pipeline ([`.github/workflows/deploy.yml`](https://github.com/antoinebou12/uml-mcp/blob/main/.github/workflows/deploy.yml)) smoke-tests the hosted MCP endpoint with JSON-RPC `tools/list` and `list_diagram_types` against the Vercel URL. CI validates [`.cursor/mcp.json`](https://github.com/antoinebou12/uml-mcp/blob/main/.cursor/mcp.json) on each PR.

## Diagram skill for Cursor

Use the canonical skill at **[`.skill/skills/uml-mcp-diagrams/SKILL.md`](https://github.com/antoinebou12/uml-mcp/blob/main/.skill/skills/uml-mcp-diagrams/SKILL.md)**:

- **Cursor Settings → Rules → Add skill** and point at that file, or
- Symlink/copy it into your user skills directory if your Cursor build expects skills outside the repo.

Claude Code users should install the **[Claude Code plugin](claude_code.md)** instead (`/uml-mcp:uml-diagrams`), which bundles the same workflow under `plugins/uml-mcp/skills/uml-diagrams/`.

## Showing diagrams in chat (Cursor / Copilot / Claude)

- Prefer **`generate_uml_image`** with `output_format: png` when you want a native inline image in the chat.
- **`generate_uml`** with `output_format: png` (or `jpeg`) also fetches image bytes for MCP `ImageContent`, even on hosted `MCP_URL_ONLY`.
- SVG responses include a markdown `![diagram](url)` in the tool text so clients can preview from the URL when bytes are omitted.
- Agents should not link local `output/*.png` paths in markdown; use the MCP tool result / public diagram URL instead.


## Local stdio MCP (optional)

To run the server from this clone with file output, merge **[`config/cursor_config.json`](https://github.com/antoinebou12/uml-mcp/blob/main/config/cursor_config.json)** into your MCP settings:

- **Windows:** `%APPDATA%\Cursor\User\globalStorage\cursor.mcp\mcp.json`
- **macOS:** `~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp/mcp.json`
- **Linux:** `~/.config/Cursor/User/globalStorage/cursor.mcp/mcp.json`

Set **`cwd`** to the repo root and adjust **`env`** (`KROKI_SERVER`, `MCP_OUTPUT_DIR`, `MCP_DIAGRAM_FALLBACK`) per [Configuration](../configuration.md).

## Smithery registry (alternative)

If you use the [Smithery CLI](https://smithery.ai/docs/concepts/cli) (Node.js 20+):

```bash
npm install -g @smithery/cli@latest
smithery auth login
smithery mcp add antoinebou12/uml --client cursor
```

Restart Cursor after the command finishes.

## Test the integration

Example prompt:

```
Create a UML class diagram for the current project structure.
```

## Troubleshooting

### Server connection issues

1. For hosted MCP, verify the URL ends with **`/mcp`**.
2. For local stdio, run `uv run python server.py` manually and check paths in `config/cursor_config.json`.
3. Review Cursor MCP logs for connection errors.

### Diagram generation problems

1. Call **`list_diagram_types`** or read **`uml://types`** when unsure of `diagram_type`.
2. Use **`validate_uml`** on pasted source before retrying **generate_uml**.
3. Prefer **`output_format` `svg`** for shareable URLs on the hosted server.

## Optional: Sequential Thinking MCP

UML-MCP does not bundle Sequential Thinking. For multi-step planning before **generate_uml**, add a second MCP server entry in Cursor if you use that tool, then call UML-MCP with the final diagram source.

## Related resources

- [Configuration Options](../configuration.md)
- [Claude Code plugin](claude_code.md)
- [UML Diagram Examples](../examples.md)
- [Supported Diagram Types](../diagrams/uml.md)
