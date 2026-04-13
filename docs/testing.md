# Testing

This page explains how tests are organized, why integration tests are skipped by default, and how to run them.

## Why integration tests show as SKIPPED

The integration tests in [tests/integration/test_mcp_client.py](https://github.com/antoinebou12/uml-mcp/blob/main/tests/integration/test_mcp_client.py) are **intentionally skipped** when you run the normal test command without a special environment variable.

- **Skip condition** (lines 14–18): A module-level `pytestmark` skips the entire module unless:
  - `USE_REAL_FASTMCP` is set to one of `"1"`, `"true"`, or `"yes"` (case-insensitive).
- So when you run e.g. `uv run pytest` or `uv run pytest tests/` **without** setting that variable, every test in this file is skipped with the reason: *"Integration tests require USE_REAL_FASTMCP=1"*.

### How to run integration tests locally

**Bash / WSL:**

```bash
USE_REAL_FASTMCP=1 uv run pytest tests/integration -v
```

**Windows PowerShell:**

```powershell
$env:USE_REAL_FASTMCP="1"; uv run pytest tests/integration -v
```

**CI:** In [.github/workflows/test.yml](https://github.com/antoinebou12/uml-mcp/blob/main/.github/workflows/test.yml) (lines 36–38), integration tests run in a separate step with `USE_REAL_FASTMCP=1` and `continue-on-error: true`, so the main test run stays fast and non-flaky even if the integration step fails.

## Relation to testing best practices

We follow common Python testing practices:

- **pytest** for all tests; **conftest.py** for shared fixtures (see [tests/conftest.py](https://github.com/antoinebou12/uml-mcp/blob/main/tests/conftest.py) and [tests/integration/conftest.py](https://github.com/antoinebou12/uml-mcp/blob/main/tests/integration/conftest.py)).
- **Fast tests by default**; use mocks for I/O or external services when appropriate.

This project does that by:

- Keeping the **default** test run fast and stable (unit tests only; no real MCP client/server).
- Making **integration tests opt-in** via `USE_REAL_FASTMCP=1`, so they only run when you or CI explicitly request them.
- Using a **conftest** in [tests/integration/conftest.py](https://github.com/antoinebou12/uml-mcp/blob/main/tests/integration/conftest.py) with a `require_integration_env` fixture that skips if the env is not set or if the FastMCP `Client` is not importable.

So the skip behavior is **by design** and consistent with “keep tests fast; use mocks where appropriate; heavier tests opt-in.”

## Integration tests and tools

The server exposes **generate_uml** (omit `output_dir` for URL/base64 only) and **validate_uml** (see [mcp_core/tools/diagram_tools.py](https://github.com/antoinebou12/uml-mcp/blob/main/mcp_core/tools/diagram_tools.py)). Planning (diagram type, elements, relationships) is built into the default prompts (**uml_diagram**, **uml_diagram_with_thinking**), so the model plans first then calls `generate_uml` with the final code.

When you run integration tests with `USE_REAL_FASTMCP=1`, they verify that `generate_uml` is discoverable and callable via the real FastMCP client (e.g. **TestDiscoveryViaClient::test_list_tools_via_client**, **TestDiagramToolsViaClient**).

## MCP Evaluation

An evaluation harness for testing LLM usability of the MCP server is provided:

- **Evaluation questions**: [evaluations/uml_mcp_eval.xml](https://github.com/antoinebou12/uml-mcp/blob/main/evaluations/uml_mcp_eval.xml) — 10 read-only Q&A pairs answerable from `uml://` resources.
- **Script**: [scripts/evaluation.py](https://github.com/antoinebou12/uml-mcp/blob/main/scripts/evaluation.py) — Verifies server connection and tools/resources discovery.

To run the connectivity check:

```bash
python scripts/evaluation.py -t stdio -c python -a server.py evaluations/uml_mcp_eval.xml
```

For full evaluation with Claude (requires `anthropic`), use the evaluation harness from the MCP Development Guide.

## Summary

| Topic                     | Detail                                                                                    |
| ------------------------- | ----------------------------------------------------------------------------------------- |
| **Why skipped**           | `USE_REAL_FASTMCP` is not set; skip is intentional.                                       |
| **Run integration tests** | `USE_REAL_FASTMCP=1 uv run pytest tests/integration -v` (or set env in PowerShell first). |
| **Testing approach**      | Default suite stays fast; integration tests are opt-in and use conftest/fixtures.          |
| **Diagram tools**         | `generate_uml` and `validate_uml`; integration tests check they are listed and callable. |

No code changes are required to “fix” the skips; they are the intended behavior. To see the integration tests execute, run them with the environment variable above.
