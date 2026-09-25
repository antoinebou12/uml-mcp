# Status

_Last updated: 2026-09-25 (branch `claude/admin-console-setup-plugins`, PR [#337](https://github.com/antoinebou12/uml-mcp/pull/337))_

| Area | State |
| --- | --- |
| Version | 1.4.0 (`pyproject.toml`, Helm `appVersion`, server cards) |
| Python | 3.12 baseline, 3.14 in the CI matrix |
| Tests | 756 passed, 1 skipped · Playwright e2e on desktop and mobile · 12 vitest tests |
| Lint | ruff, ty clean · `uml-mcp lint`: grade A, 99/100, ~5,045 tokens (gate: A, ≤ 5,500) |
| mcp-tester 0.8.0 | conformance 18/20 (GET SSE 405 in stateless mode and foreign-Origin CORS are by design) |
| mcpx | cannot run here: sandbox blocks mcpplayground.tech; `uml-mcp lint` applies the same rules offline |
| Docs | `mkdocs build --strict` clean |
| Conformance (MCP 2026) | 43 passed / 41 failed, same as `main` (see blocked item) |
| Local CI (`act`) | lint ✅ · test ✅ (artifact upload unsupported by act) · helm via `alpine/helm` ✅ |
| Public endpoint | https://uml-mcp.vercel.app/mcp, auth off by design |

## Known issues

- Kroki is unreachable from the sandbox proxy (403), so render steps of the smoke runner fail there; they pass with network access.
- `actions/upload-artifact@v7` can't run under `act` (no compatible artifact server).
