---
title: Developers
description: "Developer reference: testing strategy, architecture, and contribution workflow."
---

# Developers

Build, test, and extend UML-MCP. Pick the page that matches what you're trying to do.

<div class="grid cards" markdown>

-   :material-test-tube:{ .lg .middle } **Testing**

    ---

    Test layout and how to run the suite.

    [:octicons-arrow-right-24: Testing guide](../testing.md)

-   :material-graph:{ .lg .middle } **Architecture**

    ---

    Repository layout: MCP runtime, Kroki clients, HTTP / Vercel entry points, stdio CLI.

    [:octicons-arrow-right-24: Architecture](../refactor-architecture-plan.md)

-   :material-account-multiple-plus:{ .lg .middle } **Contributing**

    ---

    Local setup, conventions, code of conduct, security policy.

    [:octicons-arrow-right-24: Contributing](contributing.md)

-   :material-language-python:{ .lg .middle } **Python API**

    ---

    Auto-generated reference for embedding the server or extending the rendering pipeline.

    [:octicons-arrow-right-24: Python API](../reference/python/index.md)

</div>

## Local development cheatsheet

```bash
# Install dev dependencies
uv sync --all-groups

# Run unit tests
uv run pytest tests/ -v

# Lint
uv run ruff check .
uv run ruff format --check .

# Local CI (mirrors GitHub Actions)
make ci

# Serve docs locally
uv run mkdocs serve
```

## Repository layout

```text
server.py              MCP entry point (stdio/HTTP)
app.py                 FastAPI REST API + MCP HTTP at /mcp
api/app.py             legacy re-export of app for older Vercel preset
mcp_core/
  core/                config, server, CLI, utilities, diagram pipeline
  tools/               generate_uml, validate_uml, batch, schemas
  prompts/             diagram generation prompts
  resources/           uml:// resource handlers
  server/              FastMCP wrapper
tools/kroki/           Kroki, PlantUML, Mermaid, D2, TikZ clients
tests/                 pytest suite
docs/                  this MkDocs site
```

!!! note "Source of truth"

    Source layout drifts faster than narrative docs. Confirm against the [GitHub tree](https://github.com/antoinebou12/uml-mcp/tree/main) when in doubt.
