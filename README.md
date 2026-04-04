[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/antoinebou12-uml-mcp-badge.png)](https://mseep.ai/app/antoinebou12-uml-mcp)

# UML-MCP: Diagram Generation via MCP

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![smithery badge](https://smithery.ai/badge/antoinebou12/uml)](https://smithery.ai/server/antoinebou12/uml)
[![MseeP.ai Security Assessment](https://img.shields.io/badge/MseeP.ai-Security%20Assessment-green)](https://mseep.ai/app/antoinebou12-uml-mcp)

Generate UML and other diagrams from AI assistants via the [Model Context Protocol](https://modelcontextprotocol.io/). Supports 30+ diagram types through [Kroki](https://kroki.io/), [PlantUML](https://plantuml.com/), [Mermaid](https://mermaid.js.org/), and [D2](https://d2lang.com/).

**Live:** [MCP endpoint](https://umlmcp.vercel.app/mcp) | [Add via Smithery](https://smithery.ai/server/antoinebou12/uml)

## Features

- **30+ diagram types** -- UML (Class, Sequence, Activity, Use Case, State, Component, Deployment, Object), Mermaid, D2, Graphviz, TikZ, ERD, BlockDiag, BPMN, C4, and more via Kroki
- **MCP integration** -- works with Cursor, Claude Desktop, and any MCP client
- **Multiple output formats** -- SVG, PNG, PDF, JPEG, base64 (varies by diagram type)
- **Automatic fallback** -- Kroki first, then PlantUML server or Mermaid.ink if unavailable
- **Read-only mode** -- `MCP_READ_ONLY=true` disables file writes (URL + base64 only)
- **Flexible deployment** -- stdio, HTTP, Vercel serverless, Docker, or Smithery

## Quick start

### Install

```bash
# Via Smithery (one command)
npx -y @smithery/cli install antoinebou12/uml --client claude

# Or manually
git clone https://github.com/antoinebou12/uml-mcp.git && cd uml-mcp
uv sync            # recommended
# poetry install   # alternative
# pip install -e . # alternative
```

### Run

```bash
# MCP stdio transport (default)
uv run python server.py

# HTTP transport
uv run python server.py --transport http --port 8000

# List tools and exit
uv run python server.py --list-tools
```

### MCP client config

Copy the appropriate snippet from `config/` into your client:

- **Cursor**: `config/cursor_config.json`
- **Claude Desktop**: `config/claude_desktop_config.json`

Replace `/path/to/uml-mcp` with the actual path. See `config/README.md` for config file locations.

## Supported diagram types

| Category | Types |
|----------|-------|
| **UML (PlantUML)** | Class, Sequence, Activity, Use Case, State, Component, Deployment, Object |
| **General** | Mermaid, D2, Graphviz, ERD, BlockDiag, BPMN, C4 |
| **Specialized** | TikZ, Excalidraw, Nomnoml, Pikchr, Structurizr, SVGBob, WaveDrom, WireViz, and more |

Full list with supported output formats: run `python server.py --list-tools` or query `uml://formats`.

## MCP tools and resources

**Tools:**
- `generate_uml` -- generate a diagram and optionally save to disk
- `generate_diagram_url` -- return diagram URL + base64 without file writes

**Resources** (via `uml://` URIs):
`types`, `templates`, `examples`, `formats`, `server-info`, `mermaid-examples`, `bpmn-guide`, `workflow`

## Deployment

### Vercel

The repo includes `vercel.json` pre-configured for serverless deployment:

1. Connect this repo to [Vercel](https://vercel.com)
2. Your MCP URL: `https://<project>.vercel.app/mcp` (use `/mcp` path, not root)
3. Vercel uses read-only filesystem -- diagrams are returned as URLs/base64

### Smithery

After deploying to Vercel:

1. Go to [smithery.ai/new](https://smithery.ai/new), choose **URL**
2. Enter `https://<project>.vercel.app/mcp`
3. Set display name, description, and homepage in Settings

See [docs/integrations/vercel_smithery.md](docs/integrations/vercel_smithery.md) for detailed instructions and troubleshooting.

### Docker

```bash
docker compose up -d          # full stack with Kroki + PlantUML
# or standalone:
docker build -t uml-mcp . && docker run -p 8000:8000 uml-mcp
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `KROKI_SERVER` | Kroki server URL | `https://kroki.io` |
| `PLANTUML_SERVER` | PlantUML server URL | `http://plantuml-server:8080` |
| `MCP_OUTPUT_DIR` | Diagram output directory | `./output` |
| `MCP_READ_ONLY` | Disable file writes | `false` |
| `MCP_MAX_CODE_LENGTH` | Max diagram code length | `500000` |
| `USE_LOCAL_KROKI` | Use local Kroki instance | `false` |
| `USE_LOCAL_PLANTUML` | Use local PlantUML instance | `false` |

Full options: [docs/configuration.md](docs/configuration.md)

## Architecture

```
server.py              -- MCP entry point (stdio/HTTP)
app.py                 -- FastAPI REST API + MCP HTTP at /mcp
api/app.py             -- Vercel serverless wrapper
mcp_core/
  core/                -- config, server, CLI, utilities
  tools/               -- generate_uml, generate_diagram_url
  prompts/             -- diagram generation prompts
  resources/           -- uml:// resource handlers
tools/kroki/           -- Kroki, PlantUML, Mermaid, D2 clients
```

**Fallback strategy:** Kroki (primary) -> PlantUML server (UML types) / Mermaid.ink (Mermaid) -> error with details.

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
- **Local**: `uv run mkdocs serve` then open http://127.0.0.1:8000

## Contributing

- [Contributing guide](CONTRIBUTING.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md)

## License

[MIT](LICENSE)

## Acknowledgements

[PlantUML](https://plantuml.com/) | [Kroki](https://kroki.io/) | [Mermaid](https://mermaid.js.org/) | [D2](https://d2lang.com/)
