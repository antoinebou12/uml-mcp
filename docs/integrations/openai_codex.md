# OpenAI Codex Integration

Connect UML-MCP to **OpenAI Codex** (CLI, ChatGPT desktop Codex host, and the Codex IDE extension). They share MCP configuration in `config.toml`.

## Overview

Codex reads MCP servers from:

| Scope | Path | Notes |
| --- | --- | --- |
| User | `~/.codex/config.toml` | Available in every project |
| Project | `.codex/config.toml` | Loaded only when the directory is **trusted** |

Transport is implied by keys: **`url`** = Streamable HTTP; **`command`** = stdio. Do not set both.

## Quick setup (hosted MCP)

This repository ships [`.codex/config.toml`](https://github.com/antoinebou12/uml-mcp/blob/main/.codex/config.toml):

```toml
[mcp_servers.uml-mcp]
url = "https://uml-mcp.vercel.app/mcp"
enabled = true
startup_timeout_sec = 30
tool_timeout_sec = 120
```

1. Open or clone this repo and **trust** the project when Codex prompts (or merge the table into `~/.codex/config.toml`).
2. Verify: `codex mcp list` or start a session and run `/mcp`.
3. Ask Codex to render a diagram with UML-MCP tools.

CLI alternative:

```bash
codex mcp add uml-mcp --url https://uml-mcp.vercel.app/mcp
```

Copy-paste template: [`config/codex_config.toml`](https://github.com/antoinebou12/uml-mcp/blob/main/config/codex_config.toml).

### Why longer timeouts?

Diagram renders (especially Mermaid via Kroki then mermaid.ink) often exceed Codex’s default tool timeout. Keep `tool_timeout_sec` at **120** (or higher) for reliable chat images.

## Local stdio MCP (optional)

Use [`config/codex_stdio.toml`](https://github.com/antoinebou12/uml-mcp/blob/main/config/codex_stdio.toml):

```toml
[mcp_servers.uml-mcp]
command = "uv"
args = ["run", "python", "-u", "server.py"]
cwd = "/absolute/path/to/uml-mcp"
enabled = true
startup_timeout_sec = 30
tool_timeout_sec = 120

[mcp_servers.uml-mcp.env]
KROKI_SERVER = "https://kroki.io"
MCP_OUTPUT_DIR = "output"
MCP_DIAGRAM_FALLBACK = "true"
```

Set `cwd` to your clone. Env reference: [Configuration](../configuration.md).

## Showing diagrams in chat

Prefer **`generate_uml_image`** (`png`) when you want inline image content. Tool text also includes markdown `![diagram](url)`, **URL**, and **Playground**. Same guidance as [Cursor chat rendering](cursor.md#showing-diagrams-in-chat-cursor--copilot--claude).

## Test the integration

```
Use generate_uml_image to show a Mermaid sequence Client → Server as PNG, and include the playground link.
```

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Project config ignored | Trust the project directory, or put the server in `~/.codex/config.toml`. |
| Startup failures | Raise `startup_timeout_sec` (cold starts / `uv` sync). |
| Tool call timeouts | Raise `tool_timeout_sec` (Mermaid fallback can take tens of seconds). |
| Both `url` and `command` set | Invalid; keep only one transport. |
| Wrong path | Hosted URL must end with `/mcp`. |

Official reference: [Codex configuration](https://developers.openai.com/codex/config-reference). Snippets hub: [`config/README.md`](https://github.com/antoinebou12/uml-mcp/blob/main/config/README.md).
