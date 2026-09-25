# Lint 100/100 and real journey tests

- **Status:** done (branch `claude/lint-100-real-tests`)
- **Lint:** extended rules (SEP-986 names, titles, hints, outputSchema, closed schemas,
  tool size, server instructions, duplicates); documented exceptions via
  `mcp_tool(lint_ignore=...)` and `--ignore`; `--min-score` gate; CI requires 100/100.
- **Server:** FastMCP `instructions` describe the workflow.
- **Tests:** helm and Chromium installed in CI, so nothing skips; real agent journey
  (FastMCP client over Streamable HTTP against `app.py` + fake Kroki); Playwright
  getting-started and dashboard journeys with axe WCAG A/AA scans.
- **Fixes found by the new tests:** saving settings wiped Activity history; badge,
  tab and log contrast; unfocusable log region; loopback requests through HTTP(S)_PROXY.
