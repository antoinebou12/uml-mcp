
# UML-MCP: Diagram Generation via MCP

[![Run Tests](https://github.com/antoinebou12/uml-mcp/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/antoinebou12/uml-mcp/actions/workflows/test.yml)
[![Build Package](https://github.com/antoinebou12/uml-mcp/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/antoinebou12/uml-mcp/actions/workflows/build.yml)
[![Deploy docs](https://github.com/antoinebou12/uml-mcp/actions/workflows/docs.yml/badge.svg?branch=main)](https://github.com/antoinebou12/uml-mcp/actions/workflows/docs.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python >=3.12,<3.13](https://img.shields.io/badge/python-%3E%3D3.12%2C%3C3.13-blue.svg)](https://www.python.org/downloads/)
[![MseeP.ai Security Assessment](https://img.shields.io/badge/MseeP.ai-Security%20Assessment-green)](https://mseep.ai/app/antoinebou12-uml-mcp)

Generate UML and other diagrams through the [Model Context Protocol](https://modelcontextprotocol.io/). Supports 30+ diagram types through [Kroki](https://kroki.io/), [PlantUML](https://plantuml.com/), [Mermaid](https://mermaid.js.org/), and [D2](https://d2lang.com/).

**Live endpoint:** [https://uml-mcp.vercel.app/mcp](https://uml-mcp.vercel.app/mcp)  
**Smithery:** [Add via Smithery](https://smithery.ai/server/antoinebou12/uml)

<img width="934" height="1148" alt="577497880-464b5b44-710c-4688-bfdc-432036b59cd1" src="https://github.com/user-attachments/assets/2da4000c-2090-46c5-846c-1f3c834611e4" />


## Quick Start

### Choose your mode

- **Remote (recommended):** Fast setup over HTTP MCP with Vercel serverless runtime
- **Local:** stdio process for file output and local debugging

### Remote quick start (Vercel HTTP MCP)

Use this when you want the deployed endpoint from this repo:

```json
"uml-mcp": {
  "transport": "http",
  "url": "https://uml-mcp.vercel.app/mcp"
}
```

### Local quick start (stdio MCP)

```bash
git clone https://github.com/antoinebou12/uml-mcp.git && cd uml-mcp
uv sync
uv run python server.py
```

For client config snippets, use:

- `config/cursor_config.json`
- `config/claude_desktop_config.json`
- `config/README.md` for exact config file locations

## Remote vs Local

- **Transport:** Remote uses HTTP MCP, local uses stdio by default
- **Runtime:** Remote runs on Vercel, local runs in your Python environment
- **File writes:** Remote is read-only (no `output_dir`), local supports `output_dir`
- **Returned data:** Both return URL + base64; local can also save files
- **Environment variables:** Remote is managed server-side; local reads your env config

**Important:** The MCP route is `/mcp`, not the domain root.

## Features

- **30+ diagram types** -- UML (Class, Sequence, Activity, Use Case, State, Component, Deployment, Object), Mermaid, D2, Graphviz, TikZ, ERD, BlockDiag, BPMN, C4, and more via Kroki
- **MCP-native tools** -- `generate_uml`, `validate_uml` (optional `strict`), `list_diagram_types`, `generate_uml_batch`
- **Multiple outputs** -- SVG, PNG, PDF, JPEG, and base64 (varies by diagram type)
- **Fallback pipeline** -- Kroki first, then PlantUML or Mermaid.ink
- **Flexible deployment** -- local stdio, local HTTP, Docker, Vercel, Smithery

## Supported Diagram Types

- **UML (PlantUML):** Class, Sequence, Activity, Use Case, State, Component, Deployment, Object
- **General:** Mermaid, D2, Graphviz, ERD, BlockDiag, BPMN, C4
- **Specialized:** TikZ, Excalidraw, Nomnoml, Pikchr, Structurizr, SVGBob, WaveDrom, WireViz, and more

Full list with supported formats: run `python server.py --list-tools` or query `uml://formats`.

## MCP Tools and Resources

### Tools

- `generate_uml` -- render a diagram; omit `output_dir` for URL/base64 only
- `validate_uml` -- structural validation before render (`strict` for extra Mermaid/D2 checks)
- `list_diagram_types` -- same metadata as `uml://types` when resources are awkward
- `generate_uml_batch` -- multiple diagrams in one call (cap: `MCP_BATCH_MAX_ITEMS`)

### Resources (`uml://`)

`types`, `templates`, `examples`, `formats`, `capabilities`, `server-info`, `mermaid-examples`, `bpmn-guide`, `workflow`

## Deployment

### Vercel

This repo includes `vercel.json` for serverless deployment.

1. Connect the repo to [Vercel](https://vercel.com)
2. Use `https://<project>.vercel.app/mcp`
3. Keep `/mcp` in all MCP client URLs

### Smithery

1. Open [smithery.ai/new](https://smithery.ai/new), choose **URL**
2. Enter `https://<project>.vercel.app/mcp`
3. Configure display name, description, and homepage

Detailed guide: [docs/integrations/vercel_smithery.md](docs/integrations/vercel_smithery.md)

### Docker

Default image serves FastAPI on port 8000 with MCP HTTP at `http://127.0.0.1:8000/mcp`.

```bash
# Full local stack (local Kroki + mermaid + blockdiag)
docker compose up -d

# API + MCP only (public Kroki)
docker build -t uml-mcp . && docker run -p 8000:8000 uml-mcp

# stdio MCP subprocess mode
docker run -i uml-mcp python server.py --transport stdio
```

## Configuration (Local runtime)

These variables apply to local/self-hosted runs. Remote Vercel endpoint settings are managed server-side.

- `KROKI_SERVER` -- Kroki server URL (default: `https://kroki.io`)
- `PLANTUML_SERVER` -- PlantUML server URL (default: `http://plantuml-server:8080`)
- `MCP_OUTPUT_DIR` -- diagram output directory (default: `./output`)
- `MCP_READ_ONLY` -- disable file writes (default: `false`)
- `MCP_MAX_CODE_LENGTH` -- max diagram code length (default: `500000`)
- `MCP_BATCH_MAX_ITEMS` -- max items per `generate_uml_batch` (default: `20`)
- `MCP_RATE_LIMIT_PER_MINUTE` -- HTTP rate limit per IP for diagram/MCP routes; `0` = off (default: `0`)
- `USE_LOCAL_KROKI` -- use local Kroki instance (default: `false`)
- `USE_LOCAL_PLANTUML` -- use local PlantUML instance (default: `false`)

Full options: [docs/configuration.md](docs/configuration.md)

## Architecture

```text
server.py              -- MCP entry point (stdio/HTTP)
app.py                 -- FastAPI REST API + MCP HTTP at /mcp
api/app.py             -- legacy re-export of root app (Vercel FastAPI preset uses root app.py)
mcp_core/
  core/                -- config, server, CLI, utilities, diagram pipeline
  tools/               -- generate_uml, validate_uml
  prompts/             -- diagram generation prompts
  resources/           -- uml:// resource handlers
tools/kroki/           -- Kroki, PlantUML, Mermaid, D2 clients
```

Fallback strategy: Kroki (primary) -> PlantUML server (UML types) / Mermaid.ink (Mermaid) -> error with details.

## Development

```bash
# Install dev dependencies
uv sync --all-groups

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check . && uv run ruff format --check .

# Integration tests (requires real FastMCP)
USE_REAL_FASTMCP=1 uv run pytest tests/integration -v

# Local CI
make ci
```

## Documentation

Built with [MkDocs](https://www.mkdocs.org/) + [Material](https://squidfunk.github.io/mkdocs-material/):

- **Online**: [antoinebou12.github.io/uml-mcp](https://antoinebou12.github.io/uml-mcp/)
- **Local**: `uv run mkdocs serve` then open [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Contributing

- [Contributing guide](CONTRIBUTING.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md)

## License

[MIT](LICENSE)

## Acknowledgements

[PlantUML](https://plantuml.com/) | [Kroki](https://kroki.io/) | [Mermaid](https://mermaid.js.org/) | [D2](https://d2lang.com/)
