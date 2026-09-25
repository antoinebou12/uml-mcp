# Decisions

| Date | Decision | Why |
| --- | --- | --- |
| 2026-09 | Own pure-ASGI auth layer instead of FastMCP `JWTVerifier` | Missing `exp`/`nbf` checks, no 403 path, no JWKS throttling; see `docs/enterprise/architecture.md` |
| 2026-09 | `entra-proxy` facade is stateless (AES-GCM sealed state) | No Redis needed; Entra enforces single-use codes across replicas |
| 2026-09 | Auth is opt-in; Vercel stays open | Public demo must keep working for every client |
| 2026-09 | One `uml-mcp.yaml`, env vars always win | Easy path for new users without breaking existing deployments |
| 2026-09 | MXCP-style audit fields, no MXCP dependency | Adopt the proven record shape; keep the dependency tree small |
| 2026-09 | Rate limits and audit buffer are per process | Simple and fast; global limits belong in the ingress/API gateway |
| 2026-09 | External linters (mcpx, mcp-tester) run locally, not in CI | They need network/public URLs; our own `uml-mcp lint` is the CI gate |
| 2026-09 | Admin dashboard is read-only | Config changes go through reviewed files (GitOps) |
| 2026-09 | Admin console in React + Vite + shadcn, built assets committed | Polished UI while `pip`/`uvx` installs stay Node-free; CI checks the build is current |
| 2026-09 | Console writes: local = loopback + setup token + custom header; enterprise = `MCP.Admin` + opt-in `allow_write` / `allow_stop` | Easy first-run locally; enterprise stays read-only (GitOps) unless explicitly enabled |
| 2026-09 | Plugins via entry points, explicit allow-list, no override of built-in types | Extensible without forks; trusted code only loads when named in `plugins.enabled` |
| 2026-09 | Lint exceptions are declared in code (`lint_ignore`) with a reason, reported but not scored | 100/100 stays honest: every deviation is visible and justified, never silently dropped |
| 2026-09 | Real journey tests use a fake Kroki and a real MCP client/browser, not mocks | Catch wiring bugs (proxy, Accept, audit history, contrast) that unit tests miss, without network access |
