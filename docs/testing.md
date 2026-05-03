# Testing

Where tests live, why integration tests skip by default, and how to run them.

## Why integration tests show as SKIPPED

The integration tests in [tests/integration/test_mcp_client.py](https://github.com/antoinebou12/uml-mcp/blob/main/tests/integration/test_mcp_client.py) stay skipped unless you set an environment variable.

- Skip condition (lines 14 to 18): a module-level `pytestmark` skips the entire module unless `USE_REAL_FASTMCP` is set to `"1"`, `"true"`, or `"yes"` (case-insensitive).
- If you run `uv run pytest` or `uv run pytest tests/` without that variable, every test in this file is skipped with the reason: *"Integration tests require USE_REAL_FASTMCP=1"*.

### How to run integration tests locally

**Bash / WSL:**

```bash
USE_REAL_FASTMCP=1 uv run pytest tests/integration -v
```

**Windows PowerShell:**

```powershell
$env:USE_REAL_FASTMCP="1"; uv run pytest tests/integration -v
```

**CI:** In [.github/workflows/test.yml](https://github.com/antoinebou12/uml-mcp/blob/main/.github/workflows/test.yml) (lines 36 to 38), integration tests run in a separate step with `USE_REAL_FASTMCP=1` and `continue-on-error: true`, so the main test run stays fast and non-flaky even if the integration step fails.

## How the suite is organized

This repo follows a typical pytest layout:

- **pytest** for all tests; **conftest.py** for shared fixtures (see [tests/conftest.py](https://github.com/antoinebou12/uml-mcp/blob/main/tests/conftest.py) and [tests/integration/conftest.py](https://github.com/antoinebou12/uml-mcp/blob/main/tests/integration/conftest.py)).
- **Fast tests by default**; use mocks for I/O or external services when appropriate.

This project does that by:

- Keeping the default test run fast and stable (unit tests only; no real MCP client/server).
- Making integration tests opt-in via `USE_REAL_FASTMCP=1`, so they run only when you or CI set the variable.
- Using a conftest in [tests/integration/conftest.py](https://github.com/antoinebou12/uml-mcp/blob/main/tests/integration/conftest.py) with a `require_integration_env` fixture that skips if the env is not set or if the FastMCP `Client` is not importable.

That skip behavior is deliberate: the default run stays fast, mocks cover I/O where it helps, and heavier tests run when you opt in.

## Integration tests and tools

The server exposes `generate_uml` (omit `output_dir` for URL/base64 only), `validate_uml`, `list_diagram_types` (same payload as `uml://types` when resources are unavailable), and `generate_uml_batch` (see [mcp_core/tools/diagram_tools.py](https://github.com/antoinebou12/uml-mcp/blob/main/mcp_core/tools/diagram_tools.py)). The default prompts (`uml_diagram`, `uml_diagram_with_thinking`) ask the model to pick diagram type, elements, and relationships before calling `generate_uml` with the final code.

With `USE_REAL_FASTMCP=1`, integration tests check that `generate_uml` is discoverable and callable via the real FastMCP client (for example `TestDiscoveryViaClient::test_list_tools_via_client` and `TestDiagramToolsViaClient`).

## MCP evaluation

The repo includes a small harness for checking LLM-facing behavior against the MCP server:

- [evaluations/uml_mcp_eval.xml](https://github.com/antoinebou12/uml-mcp/blob/main/evaluations/uml_mcp_eval.xml): 10 read-only Q&A pairs answerable from `uml://` resources.
- [scripts/evaluation.py](https://github.com/antoinebou12/uml-mcp/blob/main/scripts/evaluation.py): verifies server connection and tools/resources discovery.

To run the connectivity check:

```bash
python scripts/evaluation.py -t stdio -c python -a server.py evaluations/uml_mcp_eval.xml
```

For full evaluation with Claude (requires `anthropic`), use the evaluation harness from the MCP Development Guide.

## At a glance

| Topic | Detail |
| --- | --- |
| Why skipped | `USE_REAL_FASTMCP` is not set. |
| Run integration tests | `USE_REAL_FASTMCP=1 uv run pytest tests/integration -v` (or set the env in PowerShell first). |
| Default suite | Stays fast; integration tests are opt-in and use conftest/fixtures. |
| Diagram tools | `generate_uml`, `validate_uml`, `list_diagram_types`, `generate_uml_batch`; integration tests check they are listed and callable. |

You do not need to “fix” the skips; that is the intended behavior. To run those tests, set the environment variable above.
