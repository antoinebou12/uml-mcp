# MCP Apps compatibility and deployment

The viewer resource uses `ui://uml-mcp/diagram-viewer` with MIME type
`text/html;profile=mcp-app`. All three viewer tools advertise the
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

## Resource descriptions and policy review

The resource has a standard MCP Apps description. The reported checker reads
`_meta.ui.widgetDescription` or `_meta["openai/widgetDescription"]` instead of
`resource.description`. That warning is a checker compatibility gap; unsupported
v1 metadata is not added to silence it. A complete policy review remains a
platform action. No SOC 2 or ISO 27001 certification is claimed for this project.

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
