# Agent instructions for UML-MCP

Use this file to guide AI agents (Cursor, etc.) when working in this repository.

## Project overview

- **UML-MCP** is a diagram generation server that implements the Model Context Protocol (MCP).
- It exposes tools so AI assistants and MCP clients can create diagrams (UML, Mermaid, D2, PlantUML, and all [Kroki](https://kroki.io/) types) and get SVG/PNG/PDF (and optionally jpeg, txt, base64) output. Use resource `uml://types` for supported `diagram_type` values.
- Main entry points: `server.py`, `mcp_core.core.server`, `app.py` (FastAPI).

## Tech stack

- **Python 3.10+**
- **Dependency management**: Poetry and/or uv (prefer uv for commands when possible: `uv run pytest`, `uv sync`).
- **Server**: FastAPI, Starlette; MCP via FastMCP.
- **Packages**: `mcp_core` (MCP server, tools, config), `tools` (Kroki / PlantUML / Mermaid / D2 clients under `tools/kroki/`).

## Conventions

1. **Modern Python**: Follow the project skill in `.skill/skills/modern-python/SKILL.md` for tooling (uv, ruff, pytest, type checking).
2. **MCP Python**: When adding or changing MCP tools, resources, or server behavior, follow `.skill/skills/mcp-python/SKILL.md` (FastMCP, STDIO logging, contracts, best practices).
3. **Sequential thinking**: For complex or multi-step tasks, use step-by-step reasoning; when the sequential-thinking MCP tool is available, use it for hard problems (see `.skill/skills/sequential-thinking/SKILL.md`).
4. **Tests**: Add/update tests in `tests/`; run with `uv run pytest` or `poetry run pytest`. Keep coverage for `mcp_core` and `tools` (e.g. `uv run pytest --cov=mcp_core --cov=tools`).
5. **Linting/formatting**: Use ruff (or existing black/isort/flake8 per `pyproject.toml`). Run before committing.
6. **MCP tools**: New diagram tools or resources belong in `mcp_core/tools/` and `mcp_core/resources/`; follow existing patterns and docstrings for MCP discovery.

## Where to look

- **MCP server and tools**: `mcp_core/core/server.py`, `mcp_core/tools/diagram_tools.py`, `mcp_core/server/fastmcp_wrapper.py`
- **Diagram backends**: `tools/kroki/` (PlantUML, Mermaid, D2, TikZ, etc.)
- **Config**: `mcp_core/core/config.py`, `config/`
- **Docs**: `docs/`, `mkdocs.yml`

## Before submitting changes

- Run tests: `uv run pytest` or `poetry run pytest`
- Run lint/format as configured (e.g. `uv run ruff check .` and `uv run ruff format .` if ruff is used)
- Ensure new MCP tools have clear names and descriptions for AI clients
