# Repository layout (maintainer note)

This file used to hold a long refactor roadmap; it drifted as the tree changed. The **current** layout is summarized in the [README](https://github.com/antoinebou12/uml-mcp/blob/main/README.md) **Architecture** section.

| Area | Location | Role |
|------|-----------|------|
| MCP runtime | `mcp_core/` | Server, tools, resources, prompts, config |
| Kroki / diagram clients | `tools/kroki/` | Rendering and encoding helpers |
| HTTP / Vercel | `app.py`, `api/app.py` | FastAPI + MCP HTTP |
| Stdio / CLI | `server.py` → `mcp_core.core.server` | Documented entrypoint |

For contribution setup and commands, see [CONTRIBUTING.md](https://github.com/antoinebou12/uml-mcp/blob/main/CONTRIBUTING.md).
