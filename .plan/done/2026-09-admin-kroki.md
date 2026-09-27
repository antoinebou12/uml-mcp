# Kroki in the admin console

- **Status:** done (branch `claude/lint-100-real-tests`)
- **Backend:** `mcp_core/kroki` (health with a real render per companion; generated
  compose stack: kroki + mermaid, blockdiag, bpmn, excalidraw on 127.0.0.1) and
  `/admin/api/kroki*` (status, catalog, render, use, docker up/down).
- **CLI:** `uml-mcp kroki up [--use] | down | status | logs`.
- **Console:** Kroki page with health, Docker controls (local) and a playground.
- **Tests:** unit + CLI, playground parity with MCP on `/admin` and `uml-mcp admin`,
  Playwright journey (desktop, dark, mobile, axe), real Docker `-m docker` (37/37).
- **Docs:** `docs/admin/install.md`, `docs/admin/user-guide.md`, tour, screenshots.
- **Fixes found:** Typer exit codes were dropped; mobile Stop button unlabeled.
