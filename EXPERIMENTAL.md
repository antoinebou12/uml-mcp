# Experimental code

The directory **`experimental/`** holds work that is **not part of the MCP server runtime**.

- **`experimental/ai_uml/`** (or, until moved, **`ai_uml/`** at repo root): research and training code, diagram-oriented experiments, and optional scripts. It is **not** imported by `server.py`, `app.py`, or `mcp_core` for normal diagram generation.
- Tooling: Ruff and ty typically **exclude** this tree; pytest coverage targets the main packages. See `pyproject.toml` for the current exclude patterns.

For a fuller description of the former `ai_uml` layout, see [docs/ai_uml.md](docs/ai_uml.md). For a phased layout and packaging cleanup, see [docs/refactor-architecture-plan.md](docs/refactor-architecture-plan.md).
