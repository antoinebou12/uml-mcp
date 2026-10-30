# Backlog (prioritized)

Priorities: **P1** next release · **P2** soon · **P3** nice to have. Size: S < 1 day, M 1–3 days, L > 3 days.

| # | Item | Pri | Size | Status |
| --- | --- | --- | --- | --- |
| 1 | [MCP 2026-07-28 conformance gaps (41 failing scenarios)](blocked/P1-mcp-2026-conformance.md) | P1 | L | blocked |
| 2 | [Linter: mcpx rule set, score, grade, token budget](done/2026-09-lint-score-grade.md) | P1 | M | done |
| 3 | [OpenTelemetry traces (optional)](done/2026-09-opentelemetry.md) | P1 | M | done |
| 4 | [Playwright e2e for the admin dashboard and /mcp](done/2026-09-playwright-e2e.md) | P1 | S | done |
| 5 | [Dead code and duplication cleanup](done/2026-09-dead-code-cleanup.md) | P2 | M | done (first pass) |
| 6 | [Publish the container image to GHCR](blocked/P1-ghcr-image.md) | P1 | S | blocked |
| 7 | [Shared state for multi-replica (Redis): rate limits, audit buffer, AG-UI runs](backlog/P2-shared-state-redis.md) | P2 | L | backlog |
| 8 | [Filter `tools/list` by the caller's permissions](done/P2-tools-list-filtering.md) | P2 | S | done |
| 9 | [OAuth follow-ups: CIMD, RFC 7662 introspection, Entra OBO, admin PKCE in jwt mode](backlog/P3-oauth-followups.md) | P3 | L | backlog |
| 11 | [Admin console, setup wizard, installer, plugins v1](done/2026-09-admin-console-setup-plugins.md) | P1 | L | done |
| 10 | [Stale docs: `FASTMCP_STATELESS_HTTP` default, Vercel keys](backlog/P3-stale-docs.md) | P3 | S | backlog |
| 12 | [MRTR elicitation for diagram tools (SEP-2322)](done/2026-10-mcp-mrtr-elicitation.md) | P2 | M | done |
| 13 | [Argument completions for diagram_type / theme](done/2026-10-mcp-completions.md) | P2 | S | done |
| 14 | [Resource templates for uml://examples and templates](done/2026-10-mcp-resource-templates.md) | P2 | S | done |
| 15 | [Tasks extension for long batch / architecture_report](backlog/P3-mcp-tasks-extension.md) | P3 | L | backlog |
| 16 | [MCP Apps interactive viewer (zoom / links)](done/2026-10-mcp-apps-interactive.md) | P3 | M | done (first pass) |
| 17 | [Partial / streaming tool results (SEP-2998 watch)](backlog/P3-mcp-partial-tool-results.md) | P3 | M | backlog |
| 18 | [Skills resources/directory/read](done/2026-10-mcp-skills-directory-read.md) | P3 | S | done |
| 19 | [Structured progress (JSON trailer / SEP-2632)](done/2026-10-mcp-structured-progress.md) | P3 | S | done (interim) |
| 20 | [ChatGPT app submission (bundle, domain challenge, viewer)](in-progress/P1-chatgpt-app-submission.md) | P1 | M | in progress |

| 21 | [Diagram platform roadmap](backlog/P2-diagram-platform.md) | P2 | L | backlog; implementation requires audit |

Shipped: see [`done/`](done/).

### MCP protocol notes (2026-07-28 + draft SEPs)

| Status | Feature |
| --- | --- |
| **Done** | Skills (+ `directoryRead`), MCP Apps viewer (zoom/links), server card, completions, resource templates, MRTR elicitation, structured progress trailers, Streamable HTTP, OTEL |
| **P3 backlog** | [Tasks](backlog/P3-mcp-tasks-extension.md) (SEP-2663), [partial/streaming results](backlog/P3-mcp-partial-tool-results.md) (SEP-2998 watch) |
| **Blocked** | Full [2026 conformance](blocked/P1-mcp-2026-conformance.md) (FastMCP routing headers / suite gaps) |
| **Skip** | Roots, Sampling, Logging ([SEP-2577](https://modelcontextprotocol.io/specification/2026-07-28/changelog) deprecated) |
| **Auth** | CIMD / hardening under [OAuth follow-ups](backlog/P3-oauth-followups.md) |
