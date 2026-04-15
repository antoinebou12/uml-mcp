"""
FastAPI application for UML diagram generation service on Vercel.
Provides REST API and MCP (Model Context Protocol) at /mcp for Smithery and clients.
"""

import json
import logging
import os
import warnings
from pathlib import Path
from typing import Any, Optional, cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

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
except Exception as e:  # noqa: BLE001
    logger.warning("MCP HTTP not available: %s", e, exc_info=True)

# OpenAPI tag groups for Swagger UI / ReDoc
TAG_REST = "rest"
TAG_WELL_KNOWN = "well-known"
TAG_OPENAPI_META = "openapi"

_OPENAPI_TAGS = [
    {
        "name": TAG_REST,
        "description": "Diagram generation, encoding, and health endpoints.",
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


# Configure CORS (cast: Starlette stubs expect a factory type; classes work at runtime)
app.add_middleware(
    cast(Any, CORSMiddleware),
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Run first (outermost): normalize Accept for /mcp so MCP Streamable HTTP accepts the request.
app.add_middleware(cast(Any, _MCPAcceptHeaderMiddleware))

try:
    from mcp_core.core.http_observability import RequestIdAndRateLimitMiddleware

    app.add_middleware(cast(Any, RequestIdAndRateLimitMiddleware))
except Exception as e:  # noqa: BLE001
    logger.warning("RequestIdAndRateLimitMiddleware not loaded: %s", e)

# Import local modules
try:
    from tools.kroki.kroki import LANGUAGE_OUTPUT_SUPPORT
    from mcp_core.core.config import MCP_SETTINGS
    from mcp_core.core.utils import generate_diagram

    HAS_MODULES = True
except ImportError:
    logger.warning(
        "Some UML-MCP modules could not be imported. Limited functionality available."
    )
    HAS_MODULES = False


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
    output_format: Optional[str] = Field(
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
    message: Optional[str] = Field(
        default=None, description="A message about the diagram generation."
    )
    playground: Optional[str] = Field(
        default=None, description="URL to an interactive playground."
    )
    local_path: Optional[str] = Field(
        default=None, description="Local path to the diagram file."
    )


@app.get("/", tags=[TAG_REST])
async def root():
    """Root endpoint with basic information about the API"""
    return {
        "message": "Welcome to the UML-MCP API",
        "version": "1.3.0",
        "status": "operational",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi_json": "/openapi.json",
        "openapi_yaml": "/openapi.yaml",
        "mcp": "/mcp",
        "kroki_encode": "/kroki_encode",
    }


@app.get("/health", tags=[TAG_REST])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "modules_available": HAS_MODULES}


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
        if request.theme and "plantuml" in request.lang.lower():
            if "@startuml" in code and "!theme" not in code:
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
        if "error" in result and result["error"]:
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
        logger.exception(f"Error generating diagram: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate diagram: {str(e)}"
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
    theme: Optional[str] = Field(
        default=None,
        description="PlantUML theme (e.g. cerulean). Ignored for non-PlantUML backends.",
    )


class KrokiEncodeResponse(BaseModel):
    url: str = Field(description="Kroki URL for the rendered diagram.")
    playground: Optional[str] = Field(
        default=None,
        description="Optional URL to an interactive editor when available.",
    )


@app.post("/kroki_encode", response_model=KrokiEncodeResponse, tags=[TAG_REST])
async def kroki_encode_endpoint(request: KrokiEncodeRequest):
    """Return the Kroki-encoded URL for a diagram (no file write). Use when running on a read-only filesystem (e.g. serverless)."""
    try:
        from tools.kroki.kroki import Kroki
        from mcp_core.core.config import MCP_SETTINGS
        from mcp_core.core.diagram_rendering import prepare_diagram_code
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
async def get_plugin_manifest(request: Request):
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
    except Exception as e:
        logger.exception(f"Error loading plugin manifest: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load plugin manifest")


def _build_server_card():
    """Build MCP server card from live tool and resource registries (same data as static card build)."""
    try:
        from mcp_core.core.server_card import build_server_card

        return build_server_card()
    except Exception as e:
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
    except Exception as e:
        logger.exception(f"Error loading privacy policy: {str(e)}")
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
