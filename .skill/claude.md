# Claude instructions for UML-MCP

Use this when working with Claude (Claude Desktop, API, or other MCP clients) in this repository.

## What this project is

UML-MCP is an MCP (Model Context Protocol) server that generates diagrams. It provides tools so you can:

- Create UML diagrams (class, sequence, activity, use case, state, component, deployment, object)
- Create Mermaid, D2, Graphviz, ERD, BlockDiag, BPMN, and C4 diagrams
- Get output as SVG, PNG, or PDF (depending on backend and diagram type)

Backends: PlantUML (local or remote) and Kroki.

## How to work in this repo

1. **Python**: Use Python 3.12 (see `requires-python` in `pyproject.toml`). Prefer `uv` for running commands: `uv run pytest`, `uv sync`. Poetry is also supported (`poetry run pytest`, `poetry install`).
2. **Style**: Follow existing code style. The project uses black, isort, flake8, and mypy (see `pyproject.toml`). Modern tooling (ruff, ty) is described in `.skill/skills/modern-python/SKILL.md` if you are adding or refactoring tooling.
3. **MCP Python**: When adding or changing MCP tools or resources, follow `.skill/skills/mcp-python/SKILL.md` (FastMCP, STDIO logging, best practices).
4. **Sequential thinking**: For complex or multi-step tasks, use step-by-step reasoning; when the sequential-thinking MCP tool is available, use it for hard problems (see `.skill/skills/sequential-thinking/SKILL.md`).
5. **Tests**: Tests live in `tests/`. Run with `uv run pytest` or `poetry run pytest`. Add tests for new behavior and keep coverage for core packages.
6. **MCP**: When adding or changing MCP tools or resources, update `mcp_core/tools/diagram_tools.py` and related modules so tool names and descriptions stay clear for AI clients.

## Key paths

- MCP server and entry: `mcp_core/core/server.py`, `server.py`
- Diagram tools and FastMCP: `mcp_core/tools/diagram_tools.py`, `mcp_core/server/fastmcp_wrapper.py`
- Backends: `tools/kroki/` (PlantUML, Mermaid, D2, TikZ, etc.)
- Configuration: `mcp_core/core/config.py`, `config/`
- User-facing docs: `docs/`, `README.md`

## Before suggesting or making changes

- Run the test suite and fix any failures.
- Ensure new or modified MCP tools have descriptive names and help text so Claude and other clients can use them correctly.
