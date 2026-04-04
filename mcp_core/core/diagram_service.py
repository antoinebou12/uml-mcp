"""
Diagram generation entry for MCP tools: validate once, then render.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from pydantic import ValidationError

from mcp_core.tools.schemas import GenerateUMLInput

from .config import MCP_SETTINGS
from .utils import generate_diagram

logger = logging.getLogger(__name__)


@dataclass
class DiagramRequest:
    """Tool-level inputs for diagram generation."""

    diagram_type: str
    code: str
    output_dir: Optional[str] = None
    output_format: str = "svg"
    theme: Optional[str] = None
    scale: float = 1.0


def _validation_error_response(code: str, exc: ValidationError) -> Dict[str, Any]:
    parts = []
    for err in exc.errors():
        loc = err.get("loc", ())
        name = loc[0] if loc else "input"
        parts.append(f"{name}: {err['msg']}")
    err_msg = "; ".join(parts)
    return {
        "code": code,
        "url": None,
        "playground": None,
        "local_path": None,
        "error": f"Validation error: {err_msg}",
    }


def generate_from_request(req: DiagramRequest) -> Dict[str, Any]:
    """
    Validate with GenerateUMLInput, ensure diagram_type is configured, then generate_diagram.
    """
    try:
        validated = GenerateUMLInput(
            diagram_type=req.diagram_type,
            code=req.code,
            output_dir=req.output_dir,
            output_format=req.output_format,
            theme=req.theme,
            scale=req.scale,
        )
    except ValidationError as e:
        return _validation_error_response(req.code, e)

    dt_key = validated.diagram_type.lower()
    types_map = getattr(MCP_SETTINGS, "diagram_types", None) or {}
    if dt_key not in types_map:
        error_msg = (
            f"Unsupported diagram type: {validated.diagram_type}. Use uml://types resource "
            "for valid types."
        )
        logger.error(error_msg)
        return {
            "code": validated.code,
            "url": None,
            "playground": None,
            "local_path": None,
            "error": error_msg,
        }

    return generate_diagram(
        validated.diagram_type,
        validated.code,
        validated.output_format,
        validated.output_dir,
        validated.theme,
        validated.scale,
    )
