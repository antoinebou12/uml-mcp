# Status

_Last updated: 2026-09-25 (branch `claude/observability-config`, PR [#335](https://github.com/antoinebou12/uml-mcp/pull/335))_

| Area | State |
| --- | --- |
| Version | 1.4.0 (`pyproject.toml`, Helm `appVersion`, server cards) |
| Python | 3.12 baseline, 3.14 in the CI matrix |
| Tests | 701 passed, 1 skipped · coverage 91% (gate 82%) |
| Lint | `ruff check`, `ruff format --check`, `ty check`, `uml-mcp lint --strict` all clean |
| Docs | `mkdocs build --strict` clean |
| Conformance (MCP 2026) | 43 passed / 41 failed, same as `main` (see blocked item) |
| Local CI (`act`) | lint ✅ · test ✅ (artifact upload unsupported by act) · helm via `alpine/helm` ✅ |
| Public endpoint | https://uml-mcp.vercel.app/mcp, auth off by design |

## Known issues

- Kroki is unreachable from the sandbox proxy (403), so render steps of the smoke runner fail there; they pass with network access.
- `actions/upload-artifact@v7` can't run under `act` (no compatible artifact server).
