"""
Utility functions for MCP server.

Logging is configured only by the CLI entrypoint (mcp_core.core.cli).
Kroki client is lazy-loaded for testability.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .config import MCP_SETTINGS
from .diagram_rendering import (
    DiagramRenderContext,
    _handle_diagram_error,  # noqa: F401 — re-export for callers/tests
    prepare_diagram_code,
    run_diagram_pipeline,
)

# Module logger; do not configure root logger here (entrypoint does that)
logger = logging.getLogger(__name__)

# Lazy Kroki client (avoids side-effects at import; testable via get_kroki_client)
_kroki_client = None


def get_kroki_client():
    """Return the Kroki client singleton. Lazy-initialized for testability."""
    global _kroki_client
    if _kroki_client is None:
        import httpx
        from tools.kroki.kroki import Kroki

        timeout = httpx.Timeout(
            connect=3.0,
            read=float(MCP_SETTINGS.max_render_seconds),
            write=10.0,
            pool=5.0,
        )
        _kroki_client = Kroki(base_url=MCP_SETTINGS.kroki_server, timeout=timeout)
    return _kroki_client


# Optional override for tests: if set, generate_diagram calls this instead of real I/O
_diagram_generator: Optional[
    Callable[
        [str, str, str, Optional[str], Optional[str], float],
        Dict[str, Any],
    ]
] = None


def set_diagram_generator(
    fn: Optional[
        Callable[
            [str, str, str, Optional[str], Optional[str], float],
            Dict[str, Any],
        ]
    ],
) -> None:
    """Set an optional diagram generator (e.g. for tests). Pass None to use default."""
    global _diagram_generator
    _diagram_generator = fn


def generate_diagram(
    diagram_type: str,
    code: str,
    output_format: str = "png",
    output_dir: Optional[str] = None,
    theme: Optional[str] = None,
    scale: float = 1.0,
) -> Dict[str, Any]:
    """
    Generate a diagram using Kroki first, with fallback to alternative services.

    Strategy: Always try Kroki first. If Kroki fails, fall back to:
    - PlantUML diagrams -> local PlantUML server
    - Mermaid diagrams -> mermaid.ink
    - Other diagrams -> return error (no fallback available)

    Args:
        diagram_type: Type of diagram (class, sequence, mermaid, d2, etc.)
        code: The diagram code/description
        output_format: Output format (png, svg, etc.)
        output_dir: Directory to save the generated image (optional). When None, no file is written (memory-only).
        theme: PlantUML theme (e.g. cerulean) - only for PlantUML backends
        scale: Scale factor for SVG (only when output_format is svg); default 1.0, min 0.1.

    Returns:
        Dict containing code, url, playground, local_path, optional error; when not writing to file, content_base64 is included.
        On success via Kroki or a fallback, ``source`` may be ``kroki``, ``plantuml_server``, or ``mermaid_ink``.
    """
    if MCP_SETTINGS.read_only or MCP_SETTINGS.memory_only:
        output_dir = None

    if _diagram_generator is not None:
        return _diagram_generator(
            diagram_type, code, output_format, output_dir, theme, scale
        )

    logger.info("Generating %s diagram (Kroki first, fallback if needed)", diagram_type)

    if output_dir:
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            logger.debug("Using output directory: %s", output_dir)
        except OSError as e:
            logger.warning(
                "Could not create output directory %s (%s); returning URL only.",
                output_dir,
                e,
            )
            output_dir = None

    diagram_config = MCP_SETTINGS.diagram_types.get(diagram_type.lower())
    if not diagram_config:
        error_msg = (
            f"Unsupported diagram type: {diagram_type}. Use uml://types resource "
            "for valid types."
        )
        logger.error(error_msg)
        return {
            "code": code,
            "url": None,
            "playground": None,
            "local_path": None,
            "error": error_msg,
        }

    backend_type = diagram_config.backend
    prepared_code = prepare_diagram_code(code, backend_type, theme)

    ctx = DiagramRenderContext(
        diagram_type=diagram_type,
        backend_type=backend_type,
        prepared_code=prepared_code,
        output_format=output_format,
        output_dir=output_dir,
        theme=theme,
        scale=scale,
    )
    return run_diagram_pipeline(ctx)
