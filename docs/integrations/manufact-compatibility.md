# MCP Apps compatibility and deployment

The viewer resource uses `ui://uml-mcp/diagram-viewer` with MIME type
`text/html;profile=mcp-app`. All four viewer tools (including batch generation) advertise the
`openai/toolInvocation` object and the flat OpenAI invocation labels.

The default HTTPS viewer origin is `https://uml-mcp.antoineboucher.info`.
Set `MCP_APP_DOMAIN=https://fast-steel-xf470.run.mcp-use.com` for Manufact.
The value must be one HTTPS origin without credentials, paths, queries or fragments.

## Initial results

Inline image previews are limited to 48,000 base64 characters. Large PNG, JPEG
and SVG images use a complete resized PNG when possible. The viewer labels these
as compact previews, and original render links remain available when supplied.
Invalid or unsupported assets have an explanatory fallback. Source over 12,000
characters is omitted from the initial result. Oversized interactive HTML still
requires a separate asset transport; it cannot be displayed as a raster image.

Tests cover valid large images, malformed input, SVG thumbnails, metadata and
viewer interaction. These checks do not establish a new platform review score.

The app-only `rerender_diagram` helper is declared read-only and can be used by
bounded platform probes. Generation tools allow optional file export and retain
their write-capable annotations. The image schema limits base64 to 48,000
characters; the transport also bounds escaped source, links and diagnostics.

If a hosted report still lists missing invocation labels or domain metadata,
check its deployed Git revision. A failed build leaves the previous version
running. The D3 package is required during installation, so build contexts must
include `examples/plugins/uml-mcp-plugin-d3/src/uml_mcp_plugin_d3` and its assets.

## Resource descriptions and policy review

The resource has a standard MCP Apps description. The reported checker reads
`_meta.ui.widgetDescription` or `_meta["openai/widgetDescription"]` instead of
`resource.description`. That warning is a checker compatibility gap; unsupported
v1 metadata is not added to silence it. A complete policy review remains a
platform action. No SOC 2 or ISO 27001 certification is claimed for this project.

The saved production review completed on October 30, 2026 with a score of 95/100,
30 passing checks and two warnings. It marked both ChatGPT and Claude ready.
Domain and invocation metadata passed. The partial policy review supplied no
details identifying inaccessible evidence, so it cannot be resolved by changing
server metadata or treated as a completed review.

## Unsolicited HTTP probes

The shared FastAPI app rejects common credential-file, PHP and repository-file
probe paths with an empty HTTP 403 before application dispatch. This applies on
both Vercel and Manufact. MCP, health, documentation, admin and `.well-known`
verification endpoints remain accessible under their normal access rules.

Gateway request logs still record these rejections. Application middleware cannot
stop traffic reaching the hosting provider; edge firewall rules are required for
that. The guard does not ban peer addresses because a hosting gateway can share
one address across unrelated clients. Ordinary unknown paths still return 404.

## Manufact builds

Automatic deployments are restricted to `main`. Do not start Manufact PR or
branch preview builds. The saved build command installs locked runtime dependencies:

```bash
uv sync --frozen --no-dev
```

The launch command uses the existing environment and the root ASGI application:

```bash
uv run --no-sync uvicorn app:app --host 0.0.0.0 --port 8000
```

Frontend compilation belongs in CI; checked-in frontend assets are served by
Python. Changing saved build settings does not replace a running deployment.
No exact speed improvement is claimed without comparable build logs.
