# MCP 2026-07-28 conformance gaps

- **Priority:** P1   **Size:** L
- **Blocked on:** FastMCP support for draft features (input-required results, v2 routing headers). 43/84 pass; identical on `main`.
- **Unblock:** fastmcp-slim release implementing SEP input-required results; then re-run `.github/workflows/mcp-2026-conformance.yml` and `mcp-tester conformance --dual-run`.
