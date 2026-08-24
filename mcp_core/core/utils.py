"""
Utility functions for MCP server.

Logging is configured only by the CLI entrypoint (mcp_core.core.cli).
Kroki client is lazy-loaded for testability.
"""

import hashlib
import logging
import os
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

    fp12 = hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]
    logger.info(
        "Generating diagram diagram_type=%s format=%s code_len=%s code_sha256_12=%s",
        diagram_type,
        output_format,
        len(code),
        fp12,
    )

    def _sanitize_output_dir(output_dir: str) -> Optional[str]:
        """Enforce MCP_OUTPUT_ROOT sandbox and opt-in arbitrary output."""
        if not output_dir:
            return None
        # Hosted / read-only mode must not write
        if MCP_SETTINGS.read_only or MCP_SETTINGS.memory_only:
            return None
        # Resolve absolute path
        try:
            target_path = Path(output_dir).resolve()
        except Exception:
            logger.warning("Invalid output_dir path: %s", output_dir)
            return None
        # Check sandbox root
        root_env = os.environ.get("MCP_OUTPUT_ROOT", "").strip()
        allow_arbitrary = os.environ.get("MCP_ALLOW_ARBITRARY_OUTPUT_DIR", "false").lower() in ("true","1","yes")
        if root_env:
            try:
                root_path = Path(root_env).resolve()
                # Prevent escape via .. or symlink
                try:
                    target_path.relative_to(root_path)
                except ValueError:
                    logger.warning("output_dir %s escapes MCP_OUTPUT_ROOT %s", target_path, root_path)
                    if not allow_arbitrary:
                        return None
            except Exception:
                logger.warning("Could not resolve MCP_OUTPUT_ROOT")
                return None
        else:
            # No root configured; require explicit opt-in for absolute paths
            if target_path.is_absolute() and not allow_arbitrary:
                logger.warning("Absolute output_dir %s requires MCP_ALLOW_ARBITRARY_OUTPUT_DIR=true", target_path)
                return None
        return str(target_path)

    if output_dir:
        sanitized = _sanitize_output_dir(output_dir)
        if sanitized is None:
            logger.debug("Output dir rejected by sandbox policy, returning URL only")
            output_dir = None
        else:
            output_dir = sanitized
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
