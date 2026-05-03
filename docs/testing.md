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
