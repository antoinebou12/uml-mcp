# UML-MCP: Diagram Generation via MCP

[![Run Tests](https://github.com/antoinebou12/uml-mcp/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/antoinebou12/uml-mcp/actions/workflows/test.yml)
[![Build Package](https://github.com/antoinebou12/uml-mcp/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/antoinebou12/uml-mcp/actions/workflows/build.yml)
[![Deploy docs](https://github.com/antoinebou12/uml-mcp/actions/workflows/docs.yml/badge.svg?branch=main)](https://github.com/antoinebou12/uml-mcp/actions/workflows/docs.yml)
[![GitHub stars](https://img.shields.io/github/stars/antoinebou12/uml-mcp)](https://github.com/antoinebou12/uml-mcp/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python >=3.12,<3.15](https://img.shields.io/badge/python-%3E%3D3.12%2C%3C3.15-blue.svg)](https://www.python.org/downloads/)
[![MseeP.ai Security Assessment](https://img.shields.io/badge/MseeP.ai-Security%20Assessment-green)](https://mseep.ai/app/antoinebou12-uml-mcp)
[![MCP status](https://mcpvitals.com/badge/6cfb821be2.svg)](https://mcpvitals.com/status/6cfb821be2)
[![Lulu MCPs](https://getlulu.dev/api/mcps/badge/uml-mcp)](https://getlulu.dev/mcps/uml-mcp)
[![smithery badge](https://smithery.ai/badge/antoinebou12/uml)](https://smithery.ai/servers/antoinebou12/uml)

Generate UML and other diagrams through the [Model Context Protocol](https://modelcontextprotocol.io/) — for Cursor, Claude, Copilot, ChatGPT, and any MCP client.

### At a glance

| Topic | What you get |
| --- | --- |
| **Diagrams** | **~37 types** via [Kroki](https://kroki.io/): UML, Mermaid, D2, Graphviz, TikZ, BPMN, C4, GoAT, UMLet, and more |
| **MCP tools** | `generate_uml`, `generate_uml_image` (chat PNG), `validate_uml`, `list_diagram_types`, `generate_uml_batch` |
| **Chat output** | URL + **playground** + markdown image; PNG force-fetches inline bytes even on hosted URL-only mode |
| **Frontend** | AG-UI SSE (`/ag-ui/*`) for live web rendering — [guide](docs/integrations/frontend.md) |
| **Pipeline** | Kroki first, then [PlantUML](https://plantuml.com/) or [Mermaid.ink](https://mermaid.ink/) |
| **Deploy** | Local stdio/HTTP, Docker, [Vercel](https://vercel.com/), [Smithery](https://smithery.ai/) |

| Source | URL |
| --- | --- |
| Live MCP (HTTP) | [https://uml-mcp.vercel.app/mcp](https://uml-mcp.vercel.app/mcp) |
| Docs site | [antoinebou12.github.io/uml-mcp](https://antoinebou12.github.io/uml-mcp/) |
| Smithery catalog | [Add via Smithery](https://smithery.ai/server/antoinebou12/uml) |
| Lulu MCPs | [getlulu.dev/mcps/uml-mcp](https://getlulu.dev/mcps/uml-mcp) |

<img width="934" height="1148" alt="UML-MCP diagram generation in an MCP client" src="https://github.com/user-attachments/assets/2da4000c-2090-46c5-846c-1f3c834611e4" />

## Quick Start

### Remote (recommended) — Vercel HTTP MCP

```json
"uml-mcp": {
  "transport": "http",
  "url": "https://uml-mcp.vercel.app/mcp"
}
```

Clients must call **`/mcp`**, not the site root. This repo ships [`.cursor/mcp.json`](.cursor/mcp.json) with that endpoint.

### Local — stdio MCP

```bash
git clone https://github.com/antoinebou12/uml-mcp.git && cd uml-mcp
uv sync
uv run python server.py
```

Example client configs: [`config/cursor_config.json`](config/cursor_config.json), [`config/claude_desktop_config.json`](config/claude_desktop_config.json), [`config/README.md`](config/README.md).

### Claude Code plugin

```text
/plugin marketplace add https://github.com/antoinebou12/uml-mcp
/plugin install uml-mcp@uml-mcp-plugins
```

Details: [docs/integrations/claude_code.md](docs/integrations/claude_code.md). Cursor skill: [`.skill/skills/uml-mcp-diagrams/SKILL.md`](.skill/skills/uml-mcp-diagrams/SKILL.md).

## Remote vs local

| | Remote (Vercel) | Local |
| --- | --- | --- |
| Transport | HTTP MCP | stdio (default) or HTTP |
| File writes | No (`output_dir` ignored) | Yes, when configured |
| Chat images | `generate_uml_image` / `generate_uml` + `png` fetch bytes even with `MCP_URL_ONLY` | Same tools; optional disk save |
| Env | Server-side | Your shell / `.env` |

## Supported diagram types

| Category | Examples |
| --- | --- |
| UML (PlantUML) | Class, Sequence, Activity, Use Case, State, Component, Deployment, Object |
| General | Mermaid, D2, Graphviz, ERD, BlockDiag, BPMN, C4 |
| Specialized | TikZ, Excalidraw, **GoAT**, **UMLet**, Nomnoml, Pikchr, Structurizr, SVGBob, WaveDrom, WireViz, … |

Full catalog: `uml://types` / `uml://formats`, or `list_diagram_types`. See [docs/diagrams/index.md](docs/diagrams/index.md).

## MCP tools and resources

### Tools

| Tool | Purpose |
| --- | --- |
| `generate_uml` | Render one diagram; omit `output_dir` for URL/base64. Tool text includes `![diagram](url)`, **URL**, and **Playground** when available. Use `output_format: png` for chat ImageContent. |
| `generate_uml_image` | Inline MCP image block (default **png**) for Cursor / Copilot / Claude / ChatGPT chat |
| `validate_uml` | Local validation; `strict: true` for extra Mermaid/D2 checks (rejects semicolon-packed `sequenceDiagram`) |
| `list_diagram_types` | Catalog metadata (same idea as `uml://types`) |
| `generate_uml_batch` | Many diagrams in one call (`MCP_BATCH_MAX_ITEMS`, `MCP_BATCH_CONCURRENCY`) |

Manual client smoke prompts: [`tests/prompts/chatgpt_mcp_smoke_test.md`](tests/prompts/chatgpt_mcp_smoke_test.md).

### Resources (`uml://`)

| Resource | Description |
| --- | --- |
| `uml://types` | Types, backends, formats |
| `uml://templates` | Starter templates |
| `uml://examples` | Examples per type |
| `uml://formats` | Output formats per type |
| `uml://capabilities` | Type → backend → formats matrix |
| `uml://server-info` | Name, version, tools, Kroki/PlantUML URLs |
| `uml://workflow` | Plan-then-generate workflow |

### Frontend streaming (AG-UI)

`POST /ag-ui/generate` (SSE), plus `POST /ag-ui/start` and `GET /ag-ui/events/{run_id}` — [docs/integrations/frontend.md](docs/integrations/frontend.md).

## Deployment

### Vercel

1. Connect the repo to [Vercel](https://vercel.com)
2. Use `https://<project>.vercel.app/mcp`
3. Keep `/mcp` in every MCP client URL

### Smithery

Enter `https://<project>.vercel.app/mcp` at [smithery.ai/new](https://smithery.ai/new). Guide: [docs/integrations/vercel_smithery.md](docs/integrations/vercel_smithery.md).

### Docker

```bash
docker compose up -d                          # local Kroki stack
docker build -t uml-mcp . && docker run -p 8000:8000 uml-mcp
docker run -i uml-mcp python server.py --transport stdio
docker compose --profile plantuml up -d       # optional PlantUML on :8002
```

See [docs/deploy/docker.md](docs/deploy/docker.md).

## Configuration (local / self-hosted)

| Variable | Description | Default |
| --- | --- | --- |
| `KROKI_SERVER` | Kroki URL | `https://kroki.io` |
| `PLANTUML_SERVER` | PlantUML URL | `http://plantuml-server:8080` |
| `MCP_OUTPUT_DIR` | Diagram output directory | `./output` |
| `MCP_READ_ONLY` | Disable file writes | `false` |
| `MCP_URL_ONLY` | Skip byte fetch (Vercel default on); `generate_uml_image` / png still fetch | see [docs](docs/configuration.md) |
| `MCP_MAX_CODE_LENGTH` | Max diagram source length | `500000` |
| `MCP_BATCH_MAX_ITEMS` | Max `generate_uml_batch` items | `20` |
| `MCP_BATCH_CONCURRENCY` | Batch workers (1–16; Mermaid-majority capped at 2) | `4` |
| `MCP_RATE_LIMIT_PER_MINUTE` | HTTP rate limit per IP (`0` = off) | `0` |
| `USE_LOCAL_KROKI` | Prefer local Kroki | `false` |
| `USE_LOCAL_PLANTUML` | Prefer local PlantUML | `false` |

Full options: [docs/configuration.md](docs/configuration.md). Fallback behavior: [docs](docs/) (not duplicated here).

## Architecture

Typical flow: assistant calls `generate_uml` / `generate_uml_image` → server renders via Kroki (with fallbacks) → returns `url`, `playground`, and optional image bytes.

<p align="center">
  <img src="docs/assets/diagrams/mcp-request-flow.svg" width="100%" style="max-width: 1132px;" alt="Sequence diagram: User to AI Assistant to UML-MCP server to Kroki and back" />
</p>

```text
server.py              -- MCP entry (stdio / HTTP)
app.py                 -- FastAPI + MCP HTTP at /mcp
mcp_core/
  core/                -- config, CLI, diagram pipeline
  tools/               -- generate_uml, generate_uml_image, validate, batch
  prompts/             -- diagram prompts
  resources/           -- uml:// handlers
tools/kroki/           -- Kroki, PlantUML, Mermaid, D2 clients
```

## Development

```bash
uv sync --all-groups
uv run pytest tests/ -v
uv run ruff check . && uv run ruff format --check .
make ci
```

## Documentation

- **Online:** [antoinebou12.github.io/uml-mcp](https://antoinebou12.github.io/uml-mcp/)
- **Local:** `uv run mkdocs serve` → [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Integrations:** [Cursor](docs/integrations/cursor.md) · [Claude Code](docs/integrations/claude_code.md) · [Frontend](docs/integrations/frontend.md)

## Contributing

- [Contributing guide](CONTRIBUTING.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md)

## License

[MIT](LICENSE)

## Acknowledgements

Maintained by [Antoine Boucher](https://github.com/antoinebou12). Built on [PlantUML](https://plantuml.com/), [Kroki](https://kroki.io/), [Mermaid](https://mermaid.js.org/), and [D2](https://d2lang.com/).
