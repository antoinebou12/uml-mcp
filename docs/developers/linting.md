---
title: Linting MCP definitions (uml-mcp lint)
description: "uml-mcp lint checks tool, prompt and resource definitions and the effective configuration, inspired by MXCP's linter."
---

# `uml-mcp lint`

LLMs choose and call tools from their descriptions, annotations and schemas.
Weak metadata leads to wrong tool choices, and a wrong `readOnlyHint` gives the wrong
auth scope. `uml-mcp lint` catches both, plus risky configuration, before
deployment. The rules are inspired by [MXCP's linter](https://mxcp.dev/quality/linting/).

```bash
uv run uml-mcp lint              # exit 1 on errors
uv run uml-mcp lint --strict     # exit 1 on errors or warnings (CI)
uv run uml-mcp lint --format json
```

CI runs `uml-mcp lint --strict` in the `lint` job. The same results appear in the
admin dashboard's **Lint** tab and at `GET /admin/api/lint`.

## Rules

| Code | Severity | Target | Check |
| --- | --- | --- | --- |
| TOOL001 | error | tool | Has a description |
| TOOL002 | warning | tool | Description is at least 40 characters (what it does, when to use it, what it returns) |
| TOOL003 | warning | tool | `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint` are set (read/write auth is derived from `readOnlyHint`) |
| TOOL004 | info | tool | `annotations.title` is set |
| TOOL005 | warning | tool | Declares an `output_schema` |
| TOOL006 | warning | tool | Every parameter has a type annotation |
| TOOL007 | warning | tool | Every parameter is described under `Args:` in the docstring |
| TOOL008 | info | tool | Has a usage example |
| PROM001 / RESO001 | warning | prompt / resource | Description is at least 15 characters |
| CFG000 | error | auth | Enterprise auth configuration fails to load |
| CFG001 | warning | auth | `resource_url` is not HTTPS |
| CFG002 | warning | audit | Auth is on but the audit trail is off |
| CFG003 | warning | rate_limit | Auth is on but rate limiting is off |
| CFG004 | warning | audit | `include_inputs: full` may store sensitive diagram content |
| CFG005 | error | audit | `file` sink without `audit.file` |
| CFG006 | info | admin | `allow_local_without_auth` is ignored while auth is on |
| CFG007 / CFG008 | error | tools / rate_limit.tools | Unknown tool name (typo would silently do nothing) |
| CFG009 | info | tools | Tool disabled by configuration |
| AUTH001 | warning | tool | No `readOnlyHint` and no `tool_permissions` entry, so it defaults to write |

## Adding a tool

`tests/test_lint.py::test_real_registry_is_strict_clean` fails when a new tool,
prompt or resource introduces an error or warning. Fix the definition rather than
relaxing the test. The fix is usually a longer description, the four annotations,
an `output_schema`, or an `Args:` entry.
