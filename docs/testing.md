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

