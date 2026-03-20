[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/antoinebou12-uml-mcp-badge.png)](https://mseep.ai/app/antoinebou12-uml-mcp)

# UML-MCP: Diagram Generation Server with MCP Interface

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![smithery badge](https://smithery.ai/badge/antoinebou12/uml)](https://smithery.ai/server/antoinebou12/uml)
[![MseeP.ai Security Assessment](https://img.shields.io/badge/MseeP.ai-Security%20Assessment-green)](https://mseep.ai/app/antoinebou12-uml-mcp)

UML-MCP is a diagram generation server that implements the Model Context Protocol (MCP), so you can create diagrams from AI assistants and other MCP clients. Improve your diagramming skills with PlantUML, Mermaid, and D2 by creating optimized diagrams for various purposes (communication, design, documentation, etc.) using Class, Sequence, Activity, Use Case, State, Component, Deployment, Object, and more.

**Live:** [MCP endpoint](https://umlmcp.vercel.app/mcp) · [Add via Smithery](https://smithery.ai/server/antoinebou12/uml)

## Features

- **Multiple diagram types**: UML (Class, Sequence, Activity, Use Case, State, Component, Deployment, Object), Mermaid, D2, Graphviz, TikZ, ERD, BlockDiag, BPMN, C4 with PlantUML
- **MCP integration**: Works with any client that supports MCP (Cursor, Claude Desktop, etc.)
- **Output formats**: SVG, PNG, PDF, JPEG (where supported by type), plus txt/base64 for some backends; optional scale for SVG
- **Configurable backends**: Local or remote PlantUML and Kroki
- **Automatic fallback**: Always tries Kroki first; if unavailable, falls back to alternative rendering services (PlantUML server for UML diagrams, Mermaid.ink for Mermaid diagrams)

## Supported diagram types

| Category | Diagram types |
|----------|----------------|
| UML      | Class, Sequence, Activity, Use Case, State, Component, Deployment, Object |
| Other    | Mermaid, D2, Graphviz, TikZ, ERD, BlockDiag, BPMN, C4 (PlantUML) |

## Getting started

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/), [Poetry](https://python-poetry.org/), or pip

### Installation

#### Installing via Smithery

To install UML Model Context Protocol for Claude Desktop automatically via [Smithery](https://smithery.ai/server/antoinebou12/uml):

```bash
npx -y @smithery/cli install antoinebou12/uml --client claude
```

#### Manual installation

**With uv (recommended, modern Python):**

```bash
git clone https://github.com/antoinebou12/uml-mcp.git
cd uml-mcp
uv sync
```

**With Poetry:**

```bash
git clone https://github.com/antoinebou12/uml-mcp.git
cd uml-mcp
poetry install
```

**With pip:**

```bash
git clone https://github.com/antoinebou12/uml-mcp.git
cd uml-mcp
pip install -e .
```

For development (tests, linting, type checking) you must install dev dependencies:

```bash
uv sync --all-groups
# or: poetry install --with dev
# or: pip install -e ".[dev]"
```

Without `--all-groups`, tools like black, flake8, isort are not installed and `uv run python -m black` will fail with "No module named black". Dev tools: ruff (lint + format), ty (type check), pytest, pytest-cov, black, flake8, isort, pre-commit.

### Running the server

**MCP server (single CLI entrypoint):** `server.py` is the official MCP server; the FastAPI app in `app.py` provides both the REST API and the **MCP over HTTP** endpoint at `/mcp` for Vercel and Smithery.

**Canonical entry point** (MCP server using mcp_core and Kroki):

From the project root:

```bash
python server.py
```

Or with uv / Poetry:

```bash
uv run python server.py
# or: poetry run python server.py
# or: poetry run uml-mcp
```

You can also use the [FastMCP CLI](https://gofastmcp.com/) when `fastmcp.json` is present: run `fastmcp run` or `fastmcp run fastmcp.json` to start the server using the config file (CLI options override the config). For the full local CLI with options like `--list-tools`, use `python server.py` instead.

The server uses stdio by default and keeps stdout reserved for MCP JSON-RPC traffic. Human-readable Rich output is suppressed in stdio mode unless you explicitly enable it with `UML_MCP_STDIO_UI=true`. For HTTP:

```bash
python server.py --transport http --host 127.0.0.1 --port 8000
```

List available tools and exit:

```bash
python server.py --list-tools
```

To show the Rich banner/tables while still using stdio, send that UI to stderr explicitly:

```bash
UML_MCP_STDIO_UI=true python server.py --list-tools
```

### Deploy to Vercel and publish on Smithery

To expose the server over HTTP so anyone can connect without installing (e.g. via [Smithery](https://smithery.ai)):

1. **Deploy to [Vercel](https://vercel.com)** (connect this repo; `vercel.json` is already configured).
2. Your **MCP URL** will be: `https://<your-project>.vercel.app/mcp`. Use the `/mcp` path—**not** the root URL (e.g. `https://...vercel.app/mcp`, not `https://...vercel.app`).
3. **Publish on Smithery**: go to [smithery.ai/new](https://smithery.ai/new), choose **URL** (bring your own hosting), enter your MCP Server URL `https://<your-project>.vercel.app/mcp`, and complete the flow (Namespace: e.g. `antoinebou12`, Server ID: `uml`).

See **[docs/integrations/vercel_smithery.md](docs/integrations/vercel_smithery.md)** for step-by-step instructions. If Smithery shows a 401 or "Invalid OAuth" error, your Vercel project likely has Deployment Protection on; see the [Troubleshooting section](docs/integrations/vercel_smithery.md#troubleshooting) there (disable protection or use a bypass token). On Vercel, if the MCP cannot write to disk, it still returns the Kroki URL; you can also use `POST /kroki_encode` to get a diagram URL without file write.

**Improve your Smithery listing:** After publishing, open **Settings → General** on your server’s Smithery page. Set **Display name**, **Description**, **Homepage** (e.g. this repo or `https://umlmcp.vercel.app`), and **Server icon** to improve discoverability and the Server Metadata score. For better Configuration UX, publish with a config schema: `[smithery.ai/new](https://smithery.ai/new) (web); add config from `smithery-config-schema.json` in the server's Settings` (see [vercel_smithery.md](docs/integrations/vercel_smithery.md)).

## Configuration

### MCP client setup

Example MCP server configs are in the **`config/`** folder:

- **`config/cursor_config.json`** — snippet for Cursor
- **`config/claude_desktop_config.json`** — snippet for Claude Desktop

Copy the relevant block into your client’s config and replace `/path/to/uml-mcp` with the real path to this repo. See **`config/README.md`** for where each app stores its config.

### Environment variables

| Variable            | Description                          | Default                    |
|---------------------|--------------------------------------|----------------------------|
| `MCP_OUTPUT_DIR`    | Directory for generated diagrams     | `./output`                 |
| `UML_MCP_OUTPUT_DIR`| Same as above (alternative name)     | —                          |
| `KROKI_SERVER`      | Kroki server URL                      | `https://kroki.io`         |
| `PLANTUML_SERVER`   | PlantUML server URL                  | `http://plantuml-server:8080` |
| `USE_LOCAL_KROKI`   | Use local Kroki (`true`/`false`)      | `false`                    |
| `USE_LOCAL_PLANTUML`| Use local PlantUML (`true`/`false`)   | `false`                    |
| `LOG_LEVEL`         | Logging level                         | —                          |
| `LIST_TOOLS`        | Set to `true` to list tools and exit | —                          |

Full options are documented in [docs/configuration.md](docs/configuration.md) and [docs/installation.md](docs/installation.md).

## Local development

Run PlantUML and/or Kroki locally (e.g. with Docker):

```bash
# PlantUML
docker run -d -p 8080:8080 plantuml/plantuml-server

# Kroki
docker run -d -p 8000:8000 yuzutech/kroki
```

Then:

```bash
export USE_LOCAL_PLANTUML=true
export PLANTUML_SERVER=http://localhost:8080
export USE_LOCAL_KROKI=true
export KROKI_SERVER=http://localhost:8000
python server.py
```

## Architecture

- **MCP server**: `server.py` (entry point), `mcp_core/` (server, config, tools, resources, prompts)
- **Diagram backends**: `plantuml/`, `kroki/`, `mermaid/`, `D2/`

### Diagram Generation Strategy

The system uses an intelligent fallback mechanism to ensure maximum reliability:

1. **Primary method (Kroki)**: All diagram generation requests first attempt to use [Kroki.io](https://kroki.io) - a unified API that supports 30+ diagram types
2. **Automatic fallback**: If Kroki is unavailable or fails (network issues, service downtime, etc.), the system automatically falls back to alternative rendering services:
   - **PlantUML diagrams** (Class, Sequence, Activity, etc.) → Falls back to the configured PlantUML server (default: `http://plantuml-server:8080`)
   - **Mermaid diagrams** → Falls back to [Mermaid.ink](https://mermaid.ink)
   - **Other diagram types** → Returns an error with details from both attempts

This ensures your diagrams are generated even if the primary service is temporarily unavailable. Configure fallback servers using the `PLANTUML_SERVER` environment variable.
- **Tools**: Diagram generation tools are registered in `mcp_core/tools/` and exposed via MCP
- **Resources**: Templates and examples under the `uml://` URI scheme

## MCP resources and tools

**Resources (e.g. `uml://types`, `uml://templates`, `uml://examples`, `uml://formats`, `uml://server-info`, `uml://workflow`)**
Provide diagram types, templates, examples, formats, server info, and the recommended workflow for complex diagrams.

**Tools:**

- `generate_uml` — Generate a diagram and optionally save it (params: `diagram_type`, `code`, `output_dir`, `output_format`, `theme`, `scale`). Omit `output_dir` to get URL and base64 only.
- `generate_diagram_url` — Return the diagram URL and base64 image without writing a file. Same diagram types; no `output_dir`.

See [docs/api/tools.md](docs/api/tools.md) for full parameters.

### Better results for complex diagrams

The default prompts (**uml_diagram**, **uml_diagram_with_thinking**) instruct the model to plan first (decide diagram type, purpose, elements, relationships), then output the diagram code and call `generate_uml` with the chosen `diagram_type` and final code. The resource `uml://workflow` describes this flow.

## Tests

See [Testing](docs/testing.md) for why integration tests are skipped by default and how to run them. Use the project’s venv so pytest-cov and options from `pyproject.toml` apply:

```bash
uv run pytest tests/ -v
# or: poetry run pytest tests/ -v
```

Do not run bare `pytest` (system Python); it may not have pytest-cov and will not see the project’s addopts.

**Integration tests (MCP Client)** use the real FastMCP package and an in-process client to test discovery and tools. They are skipped unless `USE_REAL_FASTMCP=1` is set. Run them with:

```bash
USE_REAL_FASTMCP=1 uv run pytest tests/integration -v
```

These tests require a fastmcp version that provides `fastmcp.client.Client` (e.g. FastMCP 2.x / 3.x). Diagram generation is mocked so no network call to Kroki is made.

### Lint and type check

```bash
uv run ruff check .
uv run ruff format --check .
# or: make lint

# Optional type checking (gradual adoption):
uv run ty check
# or: make typecheck
```

- If you see **No module named black** (or flake8/isort), run `uv sync --all-groups` so dev tools are installed.
- If you get **Permission denied** when running `uv run black` / `flake8` / `isort` (e.g. on WSL with project on `/mnt/c/`), use the module form: `uv run python -m black ...`, `uv run python -m flake8 ...`, `uv run python -m isort ...`, or fix execute bits: `chmod +x .venv/bin/black .venv/bin/flake8 .venv/bin/isort`.

### Testing the CI pipeline locally

**Option 1: Same steps as CI, no Docker**

```bash
make ci
```

Runs lint (ruff) and tests with coverage, matching the test job in `.github/workflows/ci.yml`.

**Option 2: act (GitHub Actions in Docker)**

You can run the full workflow locally with [act](https://github.com/nektos/act). Requires Docker. The main pipeline is in a single file (`.github/workflows/ci.yml`) so `act push` runs test and build jobs without reusable-workflow issues.

**Install act (Windows):** Chocolatey `choco install act-cli -y`, Scoop `scoop install act`, or download from [act releases](https://github.com/nektos/act/releases).

```bash
act -l
act push
```

## Documentation

The documentation is built with [MkDocs](https://www.mkdocs.org/) and the [Material theme](https://squidfunk.github.io/mkdocs-material/).

- **Online:** [https://antoinebou12.github.io/uml-mcp/](https://antoinebou12.github.io/uml-mcp/) (after enabling GitHub Pages)
- **Local:** Run `uv run mkdocs serve` or `make docs-serve` (from project root), then open http://127.0.0.1:8000

Key docs (also in the static site):

- **[User Manual](docs/user-manual.md)** — Install, configure, and use (quick start, client setup, troubleshooting)
- [Installation](docs/installation.md)
- [Configuration](docs/configuration.md)
- [API / tools](docs/api/tools.md)
- [Cursor integration](docs/integrations/cursor.md)
- [Claude Desktop integration](docs/integrations/claude_desktop.md)
- [Deploy to Vercel and Smithery](docs/integrations/vercel_smithery.md)

## Contributing and community

- [Contributing guide](CONTRIBUTING.md) — setup, tests, and how to send pull requests
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md) — how to report vulnerabilities

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

- [PlantUML](https://plantuml.com/)
- [Kroki](https://kroki.io/)
- [Mermaid](https://mermaid.js.org/)
- [D2](https://d2lang.com/)
