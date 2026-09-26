# Testing

How the test suite is laid out and how to run it locally.

## How the suite is organized

This repo uses **pytest** for all tests. Shared fixtures and hooks live in [tests/conftest.py](https://github.com/antoinebou12/uml-mcp/blob/main/tests/conftest.py). Tests under `tests/` exercise the MCP server, Kroki clients, and HTTP surfaces with mocks where I/O or external services would otherwise make runs slow or flaky.

## Running tests

From the repo root, after `uv sync --all-groups`:

```bash
uv run pytest
```

Verbose output or a subset of paths:

```bash
uv run pytest tests/ -v
uv run pytest tests/test_server.py -q
```

Coverage is enabled by default via `pyproject.toml` (`addopts`); CI runs the same command with HTML reports uploaded as artifacts.

## Browser e2e (Playwright)

`tests/test_e2e_playwright.py` starts the real app on a free port. It then drives
the admin dashboard in Chromium, checking that every tab renders without JS
errors, and calls `/mcp` (`initialize`, `tools/list`, `tools/call`) through
Playwright's request API.

```bash
uv sync --all-groups                   # includes the e2e group (playwright)
uv run playwright install chromium     # once, unless a browser is already present
uv run pytest tests/test_e2e_playwright.py
```

The tests skip automatically when no Chromium build is available. Set
`PLAYWRIGHT_CHROMIUM=/path/to/chrome` to use a specific binary.

## External MCP testers (local only)

```bash
uv run uvicorn app:app --port 8765 &
mcp-tester conformance http://127.0.0.1:8765/mcp   # 18/20: GET SSE 405 (stateless) and foreign-Origin CORS are by design
uv run uml-mcp lint http://127.0.0.1:8765/mcp --min-grade A
```

## Real journeys (agent use and computer use)

`tests/test_real_journeys.py` runs the real `app.py` with real FastMCP, with
`KROKI_SERVER` pointed at one of three **Kroki tiers** (`tests/fixtures_real.py`):

| Tier | Kroki | Runs when |
| --- | --- | --- |
| `fake` | An in-test fake: real HTTP, no internet | Always |
| `local` | A real Kroki in Docker | `UML_MCP_TEST_KROKI_URL` is set (CI: service containers) |
| `public` | `https://kroki.io` | `UML_MCP_TEST_PUBLIC_KROKI=1` (CI: the non-blocking `public-kroki` job, marker `public_kroki`) |

These tests check the **rendered output**, not just that bytes came back
(`mcp_core/quality/render_check.py`):

- an SVG must parse, have an `<svg>` root and show the diagram's labels;
- a PNG must decode, at a real size (not a 1×1 placeholder).

| Test | What it proves |
| --- | --- |
| `test_agent_uses_the_server_end_to_end[tier]` | An MCP client behaves like an agent. It reads the `initialize` instructions, checks the catalog, resources and prompts, then validates, self-corrects and renders. The Mermaid SVG shows `Alice` and `Bob`, the inline PNG decodes, and the Mermaid, D2 and PlantUML batch results show their labels. A Graphviz syntax error becomes an MCP tool error. It checks every call against the audit trail, and that diagram code is never stored raw. |
| `test_every_example_and_template_renders[tier]` | Every `uml://examples` and `uml://templates` source (2 × 37 types) renders. |
| `test_every_diagram_in_the_docs_renders[tier]` | Every fenced diagram in `docs/` (for example `mermaid` or `d2` blocks) renders. |
| `test_mcp_over_raw_http_like_any_client` | Plain JSON-RPC over HTTP: no redirect, instructions in `initialize`, malformed bodies rejected, lenient `Accept` handling |
| `test_getting_started_journey_and_accessibility[light/dark]` | Chromium takes a first-run user through the Setup wizard, then sees the agent's calls in Activity and 100/100 on Quality. It runs an **axe-core WCAG 2 AA** scan of every console page (no serious or critical violations). |
| `test_keyboard_only_navigation` | The console works without a mouse |

`tests/test_chatgpt_mcp_smoke_prompt.py` also runs the
[smoke-test prompt](https://github.com/antoinebou12/uml-mcp/blob/main/tests/prompts/chatgpt_mcp_smoke_test.md)
(`scripts/run_mcp_smoke.py`) and the 37-type catalog stress prompt
(`scripts/run_vercel_kroki_stress.py`) against each tier.

```bash
uv sync --all-groups
# fake tier only
uv run pytest tests/test_real_journeys.py -v
# plus a real local Kroki (all 37 types with the kroki-extra companions)
docker compose --profile kroki-extra up -d kroki mermaid blockdiag bpmn excalidraw
uv run python scripts/wait_for_kroki.py http://127.0.0.1:8001   # companions start later than /health
UML_MCP_TEST_KROKI_URL=http://127.0.0.1:8001 uv run pytest -m "not public_kroki" \
  tests/test_real_journeys.py tests/test_chatgpt_mcp_smoke_prompt.py
# plus the public kroki.io (needs internet)
UML_MCP_TEST_PUBLIC_KROKI=1 uv run pytest -m public_kroki --no-cov tests/test_real_journeys.py
```

In CI, the test job runs Kroki and its companions as service containers. It also installs
Chromium and Helm, so the local-tier, browser and chart tests run instead of being
skipped.

