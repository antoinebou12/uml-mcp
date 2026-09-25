---
name: uml-mcp-navigation
description: Navigate the UML-MCP repository and its documentation quickly. Maps every feature (tools, rendering, auth, config file, audit, rate limits, lint, admin dashboard, Helm, docs) to its code, tests and docs, and lists the commands to verify a change. Use before editing UML-MCP code or docs, when answering "where is X", or when planning work from the .plan backlog.
---

# Navigating UML-MCP

## First steps

1. Read `AGENTS.md` (preferences, facts) and `SOUL.md` (principles).
2. Check `.plan/STATUS.md` and `.plan/BACKLOG.md` for current state and priorities.
3. Use the map below; open the test file next to the code you change.

## Feature map

| Feature | Code | Tests | Docs |
| --- | --- | --- | --- |
| MCP tools (`generate_uml`, `validate_uml`, …) | `mcp_core/tools/diagram_tools.py`, `tool_decorator.py` | `tests/test_diagram_tools.py`, `test_tool_decorator.py` | `docs/api/tools.md` |
| Resources / prompts | `mcp_core/resources/diagram_resources.py`, `mcp_core/prompts/diagram_prompts.py` | `tests/test_diagram_resources.py`, `test_diagram_prompts.py` | `docs/reference/` |
| Rendering (Kroki, PlantUML, fallback) | `tools/kroki/`, `mcp_core/core/utils.py` | `tests/test_kroki.py`, `test_fallback_mechanism.py` | `docs/fallback-mechanism.md` |
| HTTP app (REST, AG-UI, /mcp mount) | `app.py` | `tests/test_app.py`, `test_agui.py` | `docs/integrations/frontend.md` |
| Stdio / CLI / subcommands | `mcp_core/core/cli.py`, `commands.py`, `client_install.py` | `tests/test_cli.py`, `test_client_install.py` | `docs/installation-local.md` |
| Config file `uml-mcp.yaml` | `mcp_core/core/settings_file.py`, `mcp_core/config_templates/` | `tests/test_settings_file.py` | `docs/configuration/uml-mcp-yaml.md` |
| Env settings | `mcp_core/core/config.py` | `tests/test_config.py` | `docs/configuration.md` |
| Audit, metrics, rate limits, logging | `mcp_core/observability/`, `mcp_core/core/http_observability.py` | `tests/test_observability.py` | `docs/enterprise/operations.md` |
| Lint (`uml-mcp lint`) | `mcp_core/quality/lint.py` | `tests/test_lint.py` | `docs/developers/linting.md` |
| Enterprise auth (Entra / OAuth) | `mcp_core/auth/` | `tests/test_auth_*.py`, `tests/http/entra-auth.http` | `docs/enterprise/` |
| Admin dashboard | `mcp_core/auth/admin/`, `mcp_core/observability/admin_api.py` | `tests/test_auth_admin.py`, `test_admin_dashboard.py` | `docs/enterprise/admin-ui.md` |
| Helm / Docker | `deploy/helm/uml-mcp/`, `Dockerfile`, `docker-compose*.yml` | `tests/test_enterprise_packaging.py`, `test_compose_profiles.py` | `docs/enterprise/kubernetes.md`, `docs/deploy/docker.md` |
| Smoke tests | `scripts/run_mcp_smoke.py`, `tests/prompts/` | `tests/test_chatgpt_mcp_smoke_prompt.py` | `tests/prompts/chatgpt_mcp_smoke_test.md` |
| Diagram skills | `.skill/skills/uml-mcp-diagrams/SKILL.md` (canonical) | mirror test in `test_enterprise_packaging.py` | `docs/integrations/cursor.md` |

## Docs layout

`mkdocs.yml` `nav:` is the table of contents. Sections: Tutorials · Diagram types ·
Reference (tools, resources, prompts, configuration, `uml-mcp.yaml`) · Deploy
(installation, local install, Docker, clients) · Enterprise (guide, architecture,
Entra, config, clients, Helm, admin, operations, security, troubleshooting) ·
Developers (testing, linting, contributing). New pages must be added to `nav`.

## Verify a change

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
uv run pytest -q                      # coverage gate 82%
UML_MCP_CONFIG=none uv run uml-mcp lint --strict
MKDOCS_SOCIAL=false uv run mkdocs build --strict
uv run python scripts/run_mcp_smoke.py --offline
```

Local CI: `act pull_request -W .github/workflows/ci.yml -j lint` (see `.plan/STATUS.md`).

## Rules that bite

- Keep `.skill/skills/uml-mcp-diagrams/SKILL.md` and `.github/skills/uml-mcp-diagrams/SKILL.md` byte-identical.
- Version bumps touch many files: `tests/test_version_consistency.py` lists them.
- Never enable auth on Vercel; never forward client tokens; secrets never in YAML/JSON config.
- Stdio transport: log to stderr only.
