# Status

_Last updated: 2026-09-25 (branch `claude/lint-100-real-tests`)_

| Area | State |
| --- | --- |
| Version | 1.4.0 (`pyproject.toml`, Helm `appVersion`, server cards) |
| Python | 3.12 baseline, 3.14 in the CI matrix |
| Tests | 784 passed, 0 skipped with a local Kroki (helm, Chromium and Kroki services in CI) · agent, smoke and 37-type catalog runs checked on fake/local/public Kroki (public: non-blocking CI job) · 12 vitest tests |
| Lint | ruff, ty clean · `uml-mcp lint`: grade A, 100/100, ~5,045 tokens, 1 documented exception (gate: A, 100, ≤ 5,500) |
| mcp-tester 0.8.0 | conformance 18/20 (GET SSE 405 in stateless mode and foreign-Origin CORS are by design) |
| mcpx | cannot run here: sandbox blocks mcpplayground.tech; `uml-mcp lint` applies the same rules offline |
| Docs | `mkdocs build --strict` clean |
| Conformance (MCP 2026) | 43 passed / 41 failed, same as `main` (see blocked item) |
| Local CI (`act`) | lint ✅ · test ✅ 755 passed (browser/helm installs and artifact upload skipped under act) · frontend ✅ |
| Public endpoint | https://uml-mcp.vercel.app/mcp, auth off by design |

## Known issues

- kroki.io is unreachable from the sandbox proxy (403), so the `public` Kroki tier skips there; a local Kroki in Docker (`docker compose --profile kroki-extra up -d`) covers every type.
- `actions/upload-artifact@v7` can't run under `act` (no compatible artifact server); the step is skipped with `!env.ACT`.
