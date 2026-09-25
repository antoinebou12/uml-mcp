## Learned User Preferences

- In documentation and attributions, spell the maintainer name as Antoine Boucher; do not abbreviate it to "Antoine Bou".
- Pin `astral-sh/setup-uv` in GitHub Actions to a full release tag (for example `v8.1.0`) or an explicit commit SHA; do not use a bare `@v8` ref, because that action is not published as a floating major tag and Actions fails to resolve it.
- For the root `README.md`, prefer compact markdown tables for reference-style blocks (for example environment variables with defaults, deployment URLs, MCP tools and `uml://` resources) when improving scanability; keep deeper topics such as the diagram fallback pipeline in `docs/` rather than duplicating them in the README unless asked.

## Learned Workspace Facts

- Python dependencies and the lockfile are driven by `uv` (`pyproject.toml`, `uv.lock`); after constraint changes, expect `uv lock` / `uv sync` and CI parity with `uv lock --check` where applicable; when the checked-in `requirements.txt` / `requirements-dev.txt` pins are maintained, regenerate them with `uv export` so they match the lockfile.
- Diagram skills: canonical copy in `.skill/skills/uml-mcp-diagrams/SKILL.md`; Claude Code plugin copy in `plugins/uml-mcp/skills/uml-diagrams/SKILL.md`; GitHub Copilot mirror in `.github/skills/uml-mcp-diagrams/SKILL.md` (byte-identical to the canonical copy, enforced by tests) used by the custom agent `.github/agents/uml-mcp.agent.md`. Cursor uses `.cursor/mcp.json` (hosted MCP) plus the `.skill` skill path—see `docs/integrations/cursor.md`.
- Multi-version Python work in this repo has treated 3.12 as the primary baseline while also exercising 3.14 in CI matrices when supported; widening `requires-python` and regenerating the lock goes with that pattern.
- Agent persona and principles live in `SOUL.md`; optional enterprise SSO (`MCP_AUTH_MODE`) lives in `mcp_core/auth/` and `docs/enterprise/`. Never enable auth on Vercel; never forward client tokens downstream.

## Navigation and planning

- Repository map (feature → code → tests → docs) and verification commands: `.skill/skills/uml-mcp-navigation/SKILL.md`.
- Planning lives in `.plan/`: `BACKLOG.md` (prioritized roadmap), `STATUS.md` (health), `DECISIONS.md`, and one file per item in `backlog/`, `in-progress/`, `blocked/`, `done/` (the folder is the status). Move items with `git mv` and update `BACKLOG.md` when their status changes.
- One configuration file, `uml-mcp.yaml` (`mcp_core/core/settings_file.py`): defaults < file < env vars. New settings should get a YAML key, a `uml-mcp lint` rule when misuse is risky, and a row in `docs/configuration/uml-mcp-yaml.md`.
- Quality gates before pushing: ruff check/format, `ty check`, pytest (coverage ≥ 82%), `uml-mcp lint --strict`, `mkdocs build --strict`; run `act` for `.github/workflows/ci.yml` when workflows change.
