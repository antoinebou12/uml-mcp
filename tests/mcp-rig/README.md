# MCP Rig suites

Black-box tests for the UML-MCP server, written as YAML and run with
[MCP Rig](https://github.com/gorkemgul/mcp-rig). MCP Rig launches `server.py` over stdio
exactly like an MCP client would, calls the tools, and checks the responses. These suites
complement the in-process pytest tests in `tests/`: they exercise the real transport, the
real FastMCP wiring and the JSON schemas clients actually see.

| Suite | Tool(s) | What it covers |
| --- | --- | --- |
| `discovery.yaml` | `list_diagram_types` | Catalog contents, `backend` / `query` / `output_format` filters, `limit` clamping, bad arguments |
| `validate.yaml` | `validate_uml` | PlantUML normalization, strict Mermaid / D2 diagnostics, unsupported types and formats. Full-payload snapshots in `validate.snap.yaml` |
| `generate.yaml` | `generate_uml`, `generate_uml_image`, `generate_uml_batch` | URL rendering, input validation errors, memory-only file-output refusal, batch ordering and per-item failure isolation |
| `limits.yaml` | `validate_uml`, `generate_uml`, `generate_uml_batch` | `MCP_MAX_CODE_LENGTH` and `MCP_BATCH_MAX_ITEMS` enforcement |

CI additionally runs `mcp-rig check --strict --probe-invalid-args`, which verifies protocol
behavior, lints tool definitions, and confirms every tool with required parameters rejects an
empty call.

## Running

The suites start the server with `uv run --frozen python server.py`, so sync the project
first (`uv sync --all-groups`). MCP Rig is run as an isolated tool rather than a project
dependency: it needs `mcp>=2.2`, while `uv.lock` pins the server's own `mcp`, and keeping
them separate means the server is tested with exactly the versions it ships with.

```bash
make mcp-rig
```

or directly:

```bash
uvx mcp-rig@0.1.0 run tests/mcp-rig/
uvx mcp-rig@0.1.0 run tests/mcp-rig/ --tag smoke
uvx mcp-rig@0.1.0 run tests/mcp-rig/generate.yaml --case "batch*"
uvx mcp-rig@0.1.0 run tests/mcp-rig/ --server-logs   # show server stderr when debugging
```

Tags: `smoke`, `strict`, `errors`, `security`, `batch`, plus one per suite
(`discovery`, `validate`, `generate`, `limits`).

On Windows, set `PYTHONUTF8=1` so MCP Rig can print its check marks in a cp1252 console.

## Why the suites are hermetic

Every suite sets `MCP_URL_ONLY=true`, `MCP_MEMORY_ONLY=true` and
`KROKI_SERVER=http://kroki.invalid`, so results never depend on kroki.io, mermaid.ink or
the network being up:

- PlantUML SVG URLs are computed locally, so `generate_uml` is fully testable offline. The
  unroutable Kroki host also proves the configured server is used in the returned URL, and
  turns any accidental network fetch into a loud failure.
- Mermaid rendering and raster output (`png`, `jpeg`) need a live renderer, so they are
  covered only through validation (`validate_uml`, and `generate_uml` rejecting unsupported
  formats). Live rendering belongs in a separate, network-tolerant smoke job.
- The server caches renders per process, so no case asserts `cache_hit`.

## Snapshots

`validate.snap.yaml` pins the complete `validate_uml` payload for a few cases. An ordinary
run never writes files and fails with a diff when the payload changes. After an intentional
change, refresh and review the diff before committing:

```bash
uvx mcp-rig@0.1.0 run tests/mcp-rig/validate.yaml --update-snapshots
git diff tests/mcp-rig/validate.snap.yaml
```

Only cases whose whole payload is unambiguously correct are snapshotted; a snapshot of a
questionable payload would lock the bug in.

## Adding a case

Copy a neighboring case and keep the server block unchanged. Use `json_path` / `schema` for
structured results (they read structured content), and `contains` / `matches` for the
human-readable text and for error messages. Prefer asserting stable fields (codes, `success`,
ordering) over exact wording from third-party libraries.
