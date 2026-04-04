# Experimental: `ai_uml` package

The `ai_uml/` directory contains **research and training code** (diagram-oriented models, evaluation utilities, and optional image-generation scripts). It is **not part of the published wheel or sdist**: `[tool.poetry] packages` in `pyproject.toml` lists only `mcp_core` and `tools`. It is **not wired into the MCP runtime**: `mcp_core`, `server.py`, and `app.py` do not import `ai_uml`. All client-facing diagram generation goes through **`mcp_core`** and **`tools.kroki`** (Kroki, PlantUML, Mermaid, D2, etc.).

## What lives here

| Area | Path |
|------|------|
| Model training and inference | `ai_uml/src/model_training/` |
| Diagram / latent blocks | `ai_uml/src/diagram/` |
| Evaluation | `ai_uml/src/evaluation/` |
| Image generation from text (SDXL, etc.) | `ai_uml/image_generation/` |
| JSON schema for diagrams | `ai_uml/json_schemas/` |

## Tooling

- **Ruff** and **ty** exclude `ai_uml` in `pyproject.toml` (see `[tool.ruff] exclude` and `[tool.ty.src] exclude`).
- Default **pytest coverage** is configured for `mcp_core` and `tools`, not `ai_uml`.
- **CI** path filters include `ai_uml/**` so changes there still trigger workflows.

## If you need MCP integration later

Add explicit calls from new or existing tools under `mcp_core/tools/`, register them with the server, and cover them with tests under `tests/`. Until then, treat `ai_uml` as an optional subtree for experiments, not part of the MCP tool surface.
