"""
FastAPI application for UML diagram generation service on Vercel.
Provides REST API and MCP (Model Context Protocol) at /mcp for Smithery and clients.
"""

import asyncio
import json
import logging
import os
import time
import warnings
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    Response,
    StreamingResponse,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mcp_core.core.agent_discovery import (
    approximate_markdown_token_count,
    build_robots_txt,
    build_sitemap_xml,
    homepage_html,
    homepage_markdown,
    link_header_values,
    negotiate_root_format,
    status_html,
)

# Suppress deprecation warnings from Vercel's vendored websockets/uvicorn (not from this app).
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    module="websockets.legacy",
)
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=r".*WebSocketServerProtocol.*deprecated.*",
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional MCP HTTP app for /mcp (used on Vercel / Smithery). Requires fastmcp>=2.3.1 for http_app().
_mcp_http_app = None
try:
    from mcp_core.core.server import get_mcp_server

    _mcp = get_mcp_server()
    if hasattr(_mcp, "http_app"):
        _mcp_http_app = _mcp.http_app(path="/")
        logger.info("MCP HTTP app configured at /mcp")
    else:
        logger.warning(
            "FastMCP instance has no http_app (need fastmcp>=2.3.1); MCP at /mcp will be unavailable."
        )
except Exception as e:
    logger.warning("MCP HTTP not available: %s", e, exc_info=True)

# OpenAPI tag groups for Swagger UI / ReDoc
TAG_REST = "rest"
TAG_WELL_KNOWN = "well-known"
TAG_OPENAPI_META = "openapi"
TAG_AGUI = "agui"

_OPENAPI_TAGS = [
    {
        "name": TAG_REST,
        "description": "Diagram generation, encoding, and health endpoints.",
    },
    {
        "name": TAG_AGUI,
        "description": (
            "AG-UI (Agent-User Interaction Protocol) event streaming endpoints. "
            "Emit RUN_STARTED/TOOL_CALL_*/RUN_FINISHED events over SSE for inline, "
            "live diagram rendering in chat frontends."
        ),
    },
    {
        "name": TAG_WELL_KNOWN,
        "description": "Machine-readable manifests, MCP server card, and plugin metadata.",
    },
    {
        "name": TAG_OPENAPI_META,
        "description": "OpenAPI specification exports (JSON is also served by FastAPI at /openapi.json).",
    },
]

# Initialize FastAPI (use MCP lifespan when mounted so session manager initializes)
# Swagger UI at /docs, ReDoc at /redoc for API exploration (custom HTML so tab favicon matches branding)
app = FastAPI(
    title="UML Diagram Generator",
    description=(
        "API for generating UML and other diagrams; MCP at /mcp (Streamable HTTP — use an MCP client). "
        "[Swagger UI](/docs) · [ReDoc](/redoc) · [OpenAPI JSON](/openapi.json)"
    ),
    version="1.3.0",
    docs_url=None,
    redoc_url=None,
    swagger_ui_oauth2_redirect_url=None,
    openapi_url="/openapi.json",
    openapi_tags=_OPENAPI_TAGS,
    lifespan=_mcp_http_app.lifespan if _mcp_http_app else None,
)

_FAVICON_SVG = Path(__file__).resolve().parent / "favicon.svg"


@app.get("/favicon.svg", include_in_schema=False)
async def favicon_svg():
    """Brand favicon for /docs and /redoc (and direct requests)."""
    if not _FAVICON_SVG.is_file():
        raise HTTPException(status_code=404, detail="Favicon not found")
    return FileResponse(_FAVICON_SVG, media_type="image/svg+xml")


@app.get("/docs", include_in_schema=False)
async def swagger_ui_docs(request: Request) -> HTMLResponse:
    """Swagger UI with project favicon (default FastAPI docs use the FastAPI icon)."""
    root_path = request.scope.get("root_path", "").rstrip("/")
    openapi_url = f"{root_path}{app.openapi_url}"
    return get_swagger_ui_html(
        openapi_url=openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_favicon_url=f"{root_path}/favicon.svg",
        init_oauth=app.swagger_ui_init_oauth,
        swagger_ui_parameters=app.swagger_ui_parameters,
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_docs(request: Request) -> HTMLResponse:
    """ReDoc with project favicon."""
    root_path = request.scope.get("root_path", "").rstrip("/")
    openapi_url = f"{root_path}{app.openapi_url}"
    return get_redoc_html(
        openapi_url=openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_favicon_url=f"{root_path}/favicon.svg",
    )


# MCP Streamable HTTP requires Accept: application/json, text/event-stream.
# Some clients/proxies (e.g. Smithery) omit it; normalize for /mcp so the MCP layer accepts the request.
MCP_ACCEPT = "application/json, text/event-stream"


class _MCPAcceptHeaderMiddleware:
    """Set Accept: application/json, text/event-stream for /mcp when missing."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path.startswith("/mcp"):
                headers = list(scope.get("headers", []))
                accept_val = None
                for k, v in headers:
                    if k.lower() == b"accept":
                        accept_val = v
                        break
                if accept_val is None or b"text/event-stream" not in accept_val:
                    headers = [(k, v) for k, v in headers if k.lower() != b"accept"]
                    headers.append((b"accept", MCP_ACCEPT.encode("utf-8")))
                    scope = {**scope, "headers": headers}
        await self.app(scope, receive, send)


class _MCPOriginValidationMiddleware:
    """Validate Origin for Streamable HTTP MCP requests per MCP security requirements."""

    def __init__(self, app):
        self.app = app
        allowed_origins_env = os.environ.get("MCP_ALLOWED_ORIGINS", "").strip()
        self.allowed_origins = (
            {o.strip() for o in allowed_origins_env.split(",") if o.strip()}
            if allowed_origins_env
            else set()
        )
        allowed_hosts_env = os.environ.get("MCP_ALLOWED_HOSTS", "").strip()
        self.allowed_hosts = (
            {h.strip().lower() for h in allowed_hosts_env.split(",") if h.strip()}
            if allowed_hosts_env
            else set()
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path.startswith("/mcp"):
                origin = None
                for k, v in scope.get("headers", []):
                    if k.lower() == b"origin":
                        origin = v.decode("utf-8")
                        break
                # Non-browser MCP clients may omit Origin; allow if no origin present
                if (
                    origin
                    and self.allowed_origins
                    and origin not in self.allowed_origins
                ):
                    # Reject invalid origin
                    from starlette.responses import JSONResponse

                    resp = JSONResponse(
                        {"detail": "Origin not allowed"}, status_code=403
                    )
                    await resp(scope, receive, send)
                    return
                # Continue
        await self.app(scope, receive, send)


# Configure CORS (cast: Starlette stubs expect a factory type; classes work at runtime)
# Secure default: do not allow wildcard with credentials. Allow origins via MCP_ALLOWED_ORIGINS env var (comma-separated) or default to empty.
_allowed_origins_env = os.environ.get("MCP_ALLOWED_ORIGINS", "").strip()
if _allowed_origins_env:
    allow_origins = [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
else:
    allow_origins = []

app.add_middleware(
    cast(Any, CORSMiddleware),
    allow_origins=allow_origins,
    allow_credentials=bool(allow_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)
# Origin validation for MCP Streamable HTTP
app.add_middleware(cast(Any, _MCPOriginValidationMiddleware))
# Run first (outermost): normalize Accept for /mcp so MCP Streamable HTTP accepts the request.
app.add_middleware(cast(Any, _MCPAcceptHeaderMiddleware))

try:
    from mcp_core.core.http_observability import RequestIdAndRateLimitMiddleware

    app.add_middleware(cast(Any, RequestIdAndRateLimitMiddleware))
except Exception as e:  # noqa: BLE001
    logger.warning("RequestIdAndRateLimitMiddleware not loaded: %s", e)

# Import local modules
try:
    from mcp_core.core.config import MCP_SETTINGS
    from mcp_core.core.utils import generate_diagram
    from tools.kroki.kroki import LANGUAGE_OUTPUT_SUPPORT

    HAS_MODULES = True
except ImportError:
    logger.warning(
        "Some UML-MCP modules could not be imported. Limited functionality available."
    )
    HAS_MODULES = False

# AG-UI event streaming (imported separately: failure here only disables /ag-ui routes)
try:
    from mcp_core.core.agui import (
        diagram_generation_events,
        new_run_id,
        sse_frame,
    )

    HAS_AGUI = True
except ImportError as _agui_exc:
    HAS_AGUI = False
    logger.warning("AG-UI endpoint unavailable: %s", _agui_exc)


# Models
class DiagramRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "lang": "plantuml",
                "type": "class",
                "code": "@startuml\nclass Demo {\n  +name : String\n}\n@enduml",
                "theme": "",
                "output_format": "svg",
            }
        }
    )

    lang: str = Field(
        description="The language of the diagram like plantuml, mermaid, etc."
    )
    type: str = Field(description="The type of the diagram like class, sequence, etc.")
    code: str = Field(description="The code of the diagram.", min_length=1)
    theme: str = Field(default="", description="Optional theme for the diagram.")
    output_format: str | None = Field(
        default="svg", description="Output format for the diagram (svg, png, etc.)"
    )

    @field_validator("code")
    @classmethod
    def validate_code_length(cls, v: str) -> str:
        try:
            from mcp_core.core.config import MCP_SETTINGS

            max_len = MCP_SETTINGS.max_code_length
        except ImportError:
            max_len = int(os.environ.get("MCP_MAX_CODE_LENGTH", "500000"))

        if len(v) > max_len:
            raise ValueError(
                f"Diagram code exceeds maximum length of {max_len} characters"
            )
        return v


class DiagramResponse(BaseModel):
    url: str = Field(description="URL to the generated diagram.")
    message: str | None = Field(
        default=None, description="A message about the diagram generation."
    )
    playground: str | None = Field(
        default=None, description="URL to an interactive playground."
    )
    local_path: str | None = Field(
        default=None, description="Local path to the diagram file."
    )


@app.get("/", tags=[TAG_REST])
async def root(request: Request):
    """Root: JSON by default; ``Accept: text/html`` or ``text/markdown`` for agents."""
    base = str(request.base_url).rstrip("/")
    link_h = link_header_values(base)
    headers = {"Link": link_h, "Vary": "Accept"}
    accept = request.headers.get("accept")
    fmt = negotiate_root_format(accept)
    if fmt == "markdown":
        md = homepage_markdown()
        tokens = approximate_markdown_token_count(md)
        return Response(
            content=md,
            media_type="text/markdown; charset=utf-8",
            headers={**headers, "x-markdown-tokens": str(tokens)},
        )
    if fmt == "html":
        return HTMLResponse(content=homepage_html(), headers=headers)
    return JSONResponse(
        content={
            "message": "Welcome to the UML-MCP API",
            "version": "1.3.0",
            "status": "operational",
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi_json": "/openapi.json",
            "openapi_yaml": "/openapi.yaml",
            "mcp": "/mcp",
            "kroki_encode": "/kroki_encode",
            "status_page": "/status",
        },
        headers=headers,
    )


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt(request: Request):
    """Robots exclusion / allow rules and sitemap reference (RFC 9309)."""
    body = build_robots_txt(str(request.base_url))
    return Response(content=body, media_type="text/plain; charset=utf-8")


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml(request: Request):
    """XML sitemap for discovery."""
    body = build_sitemap_xml(str(request.base_url))
    return Response(content=body, media_type="application/xml; charset=utf-8")


def _health_payload() -> dict[str, Any]:
    """Shared body for ``/health`` and ``/status``."""
    return {"status": "healthy", "modules_available": HAS_MODULES}


@app.get("/health", tags=[TAG_REST])
async def health_check():
    """Health check endpoint"""
    return _health_payload()


@app.get("/status", include_in_schema=False)
async def service_status_page():
    """Human-readable status page (same payload as ``/health``)."""
    return HTMLResponse(content=status_html(_health_payload()))


@app.post("/generate_diagram", response_model=DiagramResponse, tags=[TAG_REST])
async def generate_diagram_endpoint(request: DiagramRequest):
    """Generate a diagram from text"""
    if not HAS_MODULES:
        raise HTTPException(
            status_code=503, detail="Diagram generation modules not available"
        )

    try:
        # Map request fields to diagram type
        diagram_type = request.type.lower()
        if diagram_type == "":
            diagram_type = request.lang.lower()

        output_format = request.output_format or "svg"

        # Apply theme if provided - store original code for testing purposes
        original_code = request.code
        code = original_code
        if (
            request.theme
            and "plantuml" in request.lang.lower()
            and "@startuml" in code
            and "!theme" not in code
        ):
            code = code.replace("@startuml", f"@startuml\n!theme {request.theme}")

        # No disk writes in read-only or memory-only mode (default on Vercel via memory_only).
        if MCP_SETTINGS.read_only or MCP_SETTINGS.memory_only:
            output_dir = None
        else:
            output_dir = MCP_SETTINGS.output_dir
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Generate the diagram
        result = generate_diagram(
            diagram_type=diagram_type,
            code=(
                original_code
                if os.environ.get("TESTING", "").lower() == "true"
                else code
            ),
            output_format=output_format,
            output_dir=output_dir,
        )

        # If error occurred during generation
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])

        # Prepare response
        response = {
            "url": result["url"],
            "message": "Diagram generated successfully",
            "playground": result.get("playground"),
            "local_path": result.get("local_path"),
        }

        return response

    except HTTPException:
        # Re-raise HTTP exceptions as they already have status codes
        raise
    except Exception as e:
        logger.exception("Error generating diagram")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate diagram: {e!s}"
        )


class KrokiEncodeRequest(BaseModel):
    """Request body for /kroki_encode: returns Kroki URL without writing to disk."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "class",
                "code": "@startuml\nclass A\n@enduml",
                "output_format": "svg",
                "theme": None,
            }
        }
    )

    type: str = Field(description="Diagram type (class, sequence, mermaid, d2, etc.).")
    code: str = Field(description="Diagram source code.")
    output_format: str = Field(
        default="svg", description="Output format: svg, png, or pdf."
    )
    theme: str | None = Field(
        default=None,
        description="PlantUML theme (e.g. cerulean). Ignored for non-PlantUML backends.",
    )


class KrokiEncodeResponse(BaseModel):
    url: str = Field(description="Kroki URL for the rendered diagram.")
    playground: str | None = Field(
        default=None,
        description="Optional URL to an interactive editor when available.",
    )


@app.post("/kroki_encode", response_model=KrokiEncodeResponse, tags=[TAG_REST])
async def kroki_encode_endpoint(request: KrokiEncodeRequest):
    """Return the Kroki-encoded URL for a diagram (no file write). Use when running on a read-only filesystem (e.g. serverless)."""
    try:
        from mcp_core.core.config import MCP_SETTINGS
        from mcp_core.core.diagram_rendering import prepare_diagram_code
        from tools.kroki.kroki import Kroki
    except ImportError as e:
        logger.warning("kroki_encode dependencies unavailable: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Kroki encode not available; required modules could not be imported.",
        ) from e

    diagram_type = request.type.lower()
    diagram_config = MCP_SETTINGS.diagram_types.get(diagram_type)
    if not diagram_config:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported diagram type: {diagram_type}. Use /supported_formats for valid types.",
        )
    if request.output_format not in diagram_config.formats:
        raise HTTPException(
            status_code=400,
            detail=f"Format {request.output_format} not supported for {diagram_type}. Supported: {diagram_config.formats}",
        )

    backend = diagram_config.backend
    code = prepare_diagram_code(request.code.strip(), backend, request.theme)

    kroki = Kroki(base_url=os.environ.get("KROKI_SERVER", "https://kroki.io"))
    url = kroki.get_url(backend, code, request.output_format)
    playground = kroki.get_playground_url(backend, code)
    return {"url": url, "playground": playground}


# ---------------------------------------------------------------------------
# AG-UI (Agent-User Interaction Protocol) event streaming
# ---------------------------------------------------------------------------
# These endpoints either stream AG-UI events for one render in a single request
# (POST /ag-ui/generate — stateless, recommended on serverless) or use the canonical
# start-then-subscribe pattern (POST /ag-ui/start -> GET /ag-ui/events/{run_id}).
# The run store is intentionally per-process; ``POST /ag-ui/generate`` avoids it.
_AGUI_RUNS: dict[str, list[dict[str, Any]]] = {}
_AGUI_RUN_DONE: dict[str, asyncio.Event] = {}


class AguiRunRequest(BaseModel):
    """Input for an AG-UI diagram run (mirrors the ``generate_uml`` tool arguments)."""

    diagram_type: str = Field(
        ..., min_length=1, description="Diagram type (class, sequence, mermaid, …)."
    )
    code: str = Field(..., min_length=1, description="Diagram source code.")
    output_format: str = Field(
        default="svg", description="Output format: svg, png, etc."
    )
    theme: str | None = Field(default=None, description="Optional PlantUML theme.")
    scale: float = Field(default=1.0, ge=0.1, description="SVG scale factor.")
    run_id: str | None = Field(
        default=None,
        description="Optional caller-supplied run id (auto-generated if omitted).",
    )

    @field_validator("output_format")
    @classmethod
    def _normalize_format(cls, v: str) -> str:
        return (v or "svg").strip().lower() or "svg"


class AguiRunResponse(BaseModel):
    """Response from POST /ag-ui/start: where to subscribe for events."""

    run_id: str
    endpoint: str
    events_url: str
    status: str


def _build_agui_diagram_request(req: AguiRunRequest):
    """Convert the AG-UI run request into the shared render pipeline request."""
    from mcp_core.core.diagram_service import DiagramRequest

    return DiagramRequest(
        diagram_type=req.diagram_type,
        code=req.code,
        output_format=req.output_format,
        theme=req.theme,
        scale=req.scale,
    )


async def _agui_worker(run_id: str, req: AguiRunRequest) -> None:
    """Background worker: run the render and append AG-UI events to the run store."""
    store = _AGUI_RUNS.get(run_id, [])
    try:
        async for ev in diagram_generation_events(
            _build_agui_diagram_request(req), run_id=run_id
        ):
            store.append(ev)
    except Exception:
        logger.exception("AG-UI worker crashed for run %s", run_id)
        store.append(
            {
                "type": "RUN_ERROR",
                "run_id": run_id,
                "timestamp": int(time.time() * 1000),
                "error": {
                    "code": "RENDER_FAILED",
                    "message": "Unexpected AG-UI worker failure.",
                    "retryable": False,
                },
            }
        )
    finally:
        _AGUI_RUN_DONE.get(run_id, asyncio.Event()).set()


async def _agui_events_stream(run_id: str):
    """Incrementally drain the run store as SSE frames until the run settles."""
    store = _AGUI_RUNS.get(run_id)
    done = _AGUI_RUN_DONE.get(run_id)
    index = 0
    try:
        while store is not None and done is not None:
            while index < len(store):
                yield sse_frame(store[index])
                index += 1
            if done.is_set():
                break
            try:
                await asyncio.wait_for(done.wait(), timeout=0.5)
            except TimeoutError:
                pass
    finally:
        _AGUI_RUN_DONE.pop(run_id, None)
        _AGUI_RUNS.pop(run_id, None)


@app.post("/ag-ui/start", response_model=AguiRunResponse, tags=[TAG_AGUI])
async def agui_start(request: Request, body: AguiRunRequest):
    """Start an AG-UI diagram run and return the SSE events URL (start-then-subscribe).

    Generation runs in the background; subscribe to ``GET /ag-ui/events/{run_id}`` to
    stream RUN_STARTED/TOOL_CALL_*/RUN_FINISHED events and render the diagram inline.
    """
    if not HAS_AGUI:
        raise HTTPException(status_code=503, detail="AG-UI streaming not available")
    run_id = body.run_id or new_run_id()
    if run_id in _AGUI_RUNS:
        raise HTTPException(
            status_code=409, detail=f"run_id {run_id} is already in progress"
        )
    _AGUI_RUNS[run_id] = []
    _AGUI_RUN_DONE[run_id] = asyncio.Event()
    asyncio.create_task(_agui_worker(run_id, body))
    base = str(request.base_url).rstrip("/")
    return AguiRunResponse(
        run_id=run_id,
        endpoint="/ag-ui/start",
        events_url=f"{base}/ag-ui/events/{run_id}",
        status="started",
    )


@app.get("/ag-ui/events/{run_id}", tags=[TAG_AGUI])
async def agui_events(run_id: str):
    """Stream the AG-UI events for a started run as Server-Sent Events."""
    if run_id not in _AGUI_RUNS:
        raise HTTPException(status_code=404, detail="Unknown run_id")
    return StreamingResponse(
        _agui_events_stream(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/ag-ui/generate", tags=[TAG_AGUI])
async def agui_generate(body: AguiRunRequest):
    """Render a diagram and stream the full AG-UI event sequence over SSE in one request.

    Stateless (no run store) — the recommended path on serverless deployments such as
    Vercel. The terminal CUSTOM event carries the generative-UI payload (base64 image,
    URL, editable source) so frontends render the diagram inline.
    """
    if not HAS_AGUI:
        raise HTTPException(status_code=503, detail="AG-UI streaming not available")
    run_id = body.run_id or new_run_id()
    render_req = _build_agui_diagram_request(body)

    async def event_source():
        async for ev in diagram_generation_events(render_req, run_id=run_id):
            yield sse_frame(ev)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "X-Run-Id": run_id,
        },
    )


@app.get(
    "/logo.png",
    tags=[TAG_WELL_KNOWN],
    responses={
        200: {
            "content": {
                "image/x-icon": {"schema": {"type": "string", "format": "binary"}}
            },
            "description": "Plugin logo (ICO format, used by Smithery and AI plugin manifests).",
        }
    },
)
async def get_logo():
    """Return the logo for the plugin (used by Smithery and AI plugin manifests)."""
    logo_path = os.path.join(os.path.dirname(__file__), "favicon.ico")
    if os.path.exists(logo_path):
        return FileResponse(logo_path, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="Logo not found")


@app.get("/.well-known/ai-plugin.json", tags=[TAG_WELL_KNOWN])
def get_plugin_manifest(request: Request):
    """Return the plugin manifest for OpenAI plugins and Smithery (base URL from request)."""
    try:
        with open(
            os.path.join(os.path.dirname(__file__), ".well-known/ai-plugin.json"), "r"
        ) as f:
            manifest = json.load(f)
        base = str(request.base_url).rstrip("/")
        manifest["api"] = {"type": "openapi", "url": f"{base}/openapi.json"}
        manifest["logo_url"] = f"{base}/logo.png"
        return JSONResponse(content=manifest)
    except Exception:
        logger.exception("Error loading plugin manifest")
        raise HTTPException(status_code=500, detail="Failed to load plugin manifest")


def _build_server_card():
    """Build MCP server card from live tool and resource registries (same data as static card build)."""
    try:
        from mcp_core.core.server_card import build_server_card

        return build_server_card()
    except Exception as e:  # noqa: BLE001 - best-effort card build; fall back to a static card
        logger.warning("Could not build dynamic server card: %s", e)
        return {
            "serverInfo": {"name": "UML Diagram Generator", "version": "1.3.0"},
            "tools": [],
            "resources": [],
            "prompts": [],
        }


@app.get("/.well-known/mcp/server-card.json", tags=[TAG_WELL_KNOWN])
async def get_mcp_server_card():
    """MCP server metadata for Smithery and other registries (SEP-1649 server card)."""
    return JSONResponse(content=_build_server_card())


@app.get("/.well-known/privacy.txt", tags=[TAG_WELL_KNOWN])
async def get_privacy_policy():
    """Return the privacy policy for the plugin"""
    try:
        privacy_path = os.path.join(
            os.path.dirname(__file__), ".well-known/privacy.txt"
        )
        if os.path.exists(privacy_path):
            return FileResponse(privacy_path, media_type="text/plain")
        else:
            raise HTTPException(status_code=404, detail="Privacy policy not found")
    except Exception:
        logger.exception("Error loading privacy policy")
        raise HTTPException(status_code=500, detail="Failed to load privacy policy")


@app.get("/supported_formats", tags=[TAG_REST])
async def get_supported_formats():
    """Return the supported diagram formats"""
    if HAS_MODULES:
        return {"formats": LANGUAGE_OUTPUT_SUPPORT}
    else:
        return {"formats": {}}


@app.get("/openapi.yaml", tags=[TAG_OPENAPI_META])
async def get_openapi_yaml():
    """Return the OpenAPI specification in YAML format (for AI tools and ReDoc)."""
    try:
        import yaml

        openapi_spec = app.openapi()
        yaml_content = yaml.dump(
            openapi_spec, default_flow_style=False, allow_unicode=True, sort_keys=False
        )
        return Response(content=yaml_content, media_type="application/x-yaml")
    except ImportError:
        return JSONResponse(
            content={
                "error": "YAML conversion not available, use /openapi.json instead"
            },
            status_code=501,
        )


# Mount MCP server at /mcp for Smithery and Streamable HTTP clients; fallback when unavailable
if _mcp_http_app is not None:
    logger.info("MCP HTTP app mounted at /mcp")
    app.mount("/mcp", _mcp_http_app)
else:
    logger.info(
        "MCP HTTP fallback: GET/POST /mcp return 503 (MCP HTTP transport not available)."
    )
    _mcp_unavailable_detail = {"detail": "MCP HTTP transport is not available."}

    @app.get("/mcp", tags=[TAG_REST])
    async def mcp_unavailable_get():
        """Return 503 when MCP HTTP transport is not available (e.g. fastmcp missing or init failed)."""
        return JSONResponse(status_code=503, content=_mcp_unavailable_detail)

    @app.post("/mcp", tags=[TAG_REST])
    async def mcp_unavailable_post():
        """Return 503 when MCP HTTP transport is not available (Streamable HTTP uses POST)."""
        return JSONResponse(status_code=503, content=_mcp_unavailable_detail)

    @app.options("/mcp", tags=[TAG_REST])
    async def mcp_unavailable_options():
        """Allow CORS preflight for /mcp when MCP is unavailable."""
        return Response(status_code=204)


# Main entry point for local development
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
