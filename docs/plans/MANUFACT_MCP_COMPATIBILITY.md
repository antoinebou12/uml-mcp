# Manufact MCP Apps compatibility & lean deployments

This document records the five platform findings for the diagram viewer at
`https://fast-steel-xf470.run.mcp-use.com/mcp`. It is a remediation ledger, not a
claim that the remote compatibility checker was rerun.

## Remediation

| Finding | Implementation | Verification |
| --- | --- | --- |
| `view-domain-present` | FastMCP resource `AppConfig(domain=...)` at `ui://uml-mcp/diagram-viewer`, with an exact HTTPS origin and `MCP_APP_DOMAIN` override. | `test_app_view_domain_validation` and `test_viewer_resource_read_has_apps_mime` |
| `tool-invocation-metadata-present` | Adds an object `_meta["openai/toolInvocation"]` with `invoking` and `invoked` plus the two official flat OpenAI compatibility keys to the three viewer tools. | `test_render_invocation_labels` |
| `tool-resource-metadata-complete` | Keeps MCP Apps `ui://`, `text/html;profile=mcp-app`, standard resource `description`, and `_meta.ui.csp` on the resource. | `test_viewer_resource_read_has_apps_mime` |
| `policy-review-summary` | Inspect all tools and review evidence, not a code defect; request a new full review after preview deployment. | Manual platform review required |
| `policy-review-4226dd8ec2db` | Limits first-response base64 to 48,000 chars and echoed source to 12,000 chars. Large images omit **whole** base64 rather than cutting it; links remain when present. | `TestBoundedMcpAppResults`; check live client thresholds |

### Tool resource metadata: checker limitation

MCP Apps v2 puts a view's description in the normal resource `description`.
The reported checker currently looks only for v1
`_meta["openai/widgetDescription"]` or `_meta.ui.widgetDescription`.
Do not insert a fabricated v1-only key into v2 resource metadata merely to
silence that warning. Report it as a checker compatibility gap.

### Bounded first response

Rendered assets are not truncated byte-by-byte. The server returns an inline image
only when its base64 representation fits the budget; a larger image is replaced
by a short explanation and existing render/playground link if supplied.
Large source code is omitted from the result (the viewer cannot re-render that
source). The `content_base64` field has an explicit JSON Schema `maxLength`
to give automated policy reviews evidence of this bound.

This is a small initial-result solution, not a persistent image-store API:
offline plugin output that exceeds the limit must be rendered at a smaller size
until a separately designed authenticated, chunked asset resource exists.
Do not describe large inline images as available when omitted.

### Exact iframe origin

Default production view origin: `https://fast-steel-xf470.run.mcp-use.com`.
Set `MCP_APP_DOMAIN=https://uml-mcp.vercel.app` for the Vercel deployment.
The setting accepts only a single HTTPS origin (no credentials, path,
fragment or query). Use the same value for all views served by one app.
For each host, verify whether it accepts the proposed stable origin before
claiming compatibility.

## Lean Manufact builds

The previous hosted build used `uv sync || pip install .`. That installs dev
groups by default, including `pytest`, `ruff`, `ty`, `mypy`, `mkdocs` and
browser/coverage dependencies which are unnecessary at runtime.
The previous build log listed **145 installed packages**.

Set Manufact build command to:

```bash
uv sync --frozen --no-dev
```

Retain the existing launch command:

```bash
uv run --no-sync uvicorn app:app --host 0.0.0.0 --port 8000
```

This installs locked production dependencies only and does not resolve or
synchronize again at process startup. This override applies to **future**
deployments, including previews and future production builds; it does not
replace a running deployment. Do not claim an exact speedup or resulting
package count without comparing new build logs.

Do not run `npm install` or build the React frontend on Manufact for the
Python MCP app: the repository already ships frontend build assets.
Run the frontend typecheck/build and Python test suite in GitHub CI.

## Validation commands

```bash
uv sync --all-groups
uv run pytest tests/test_mcp_apps_viewer.py tests/test_mcp_apps_browser.py tests/test_tool_decorator.py -q
uv run ruff check mcp_core/apps/diagram_viewer.py mcp_core/tools/tool_decorator.py mcp_core/tools/schemas.py tests/
uv run ty check
cd frontend && npm ci && npm run build && npm run test -- --run
```

Then use an MCP-capable host on a **preview** to verify initialize, tools/list,
resources/list/read, input validation, small image renders, a large render,
and the viewer toolbar. Check build/runtime logs and rerun the Manufact
publishing checklist; the checker gap may remain. Promotion to production
is separate and requires passing gates.
