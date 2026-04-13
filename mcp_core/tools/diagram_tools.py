"""
MCP tools for diagram generation using the decorator pattern
"""

import logging
from typing import Any, Dict, List, Optional

from mcp_core.server.fastmcp_wrapper import FastMCP

from ..core.config import MCP_SETTINGS
from ..core.diagram_service import DiagramRequest, generate_from_request
from ..core.diagram_validation import validate_uml_inputs

# Import the tool decorator system
from .tool_decorator import get_tool_registry, mcp_tool, register_tools_with_server

logger = logging.getLogger(__name__)

# MCP tool annotations per best practices (diagram tools call Kroki, may write files)
ANNOTATIONS_DIAGRAM = {
    "readOnlyHint": False,  # May write files when output_dir provided
    "destructiveHint": False,
    "idempotentHint": True,  # Same inputs produce same diagram via Kroki
    "openWorldHint": True,  # Calls external Kroki service for rendering
}

ANNOTATIONS_VALIDATE = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


# Main UML generation tool
@mcp_tool(
    description="Generate any UML or diagram by type (class, sequence, mermaid, d2, etc.)",
    category="uml",
    example=(
        "generate_uml('mermaid', 'graph TD; A-->B;')  # URL/base64 only; "
        "or generate_uml('class', code, './output') to save"
    ),
    annotations=ANNOTATIONS_DIAGRAM,
)
def generate_uml(
    diagram_type: str,
    code: str,
    output_dir: Optional[str] = None,
    output_format: str = "svg",
    theme: Optional[str] = None,
    scale: float = 1.0,
) -> Dict[str, Any]:
    """Generate a diagram using the specified diagram type.

    Use when you need a diagram of any supported type. For complex diagrams the
    default prompt guides planning first (type, elements, relationships), then
    you call this tool with the final code.

    Args:
        diagram_type: Type of diagram (class, sequence, activity, mermaid, d2, etc.)
        code: Diagram code in the syntax for the chosen type
        output_dir: Directory to save the image. Omit or None for URL, playground,
            and content_base64 only (no file write; use in serverless / read-only).
        output_format: svg, png, pdf, jpeg, txt, or base64 (default: svg). See uml://formats per type.
        theme: PlantUML theme for UML diagrams (e.g. cerulean)
        scale: Scale factor for SVG only (default 1.0, min 0.1). Ignored for other formats.

    Returns:
        Dict with code, url, playground; local_path when output_dir set; content_base64 when not saving; or error.
    """
    logger.info(
        "Called generate_uml tool: type=%s, code length=%s",
        diagram_type,
        len(code),
    )
    return generate_from_request(
        DiagramRequest(
            diagram_type=diagram_type,
            code=code,
            output_dir=output_dir,
            output_format=output_format,
            theme=theme,
            scale=scale,
        )
    )


@mcp_tool(
    description=(
        "Validate diagram type, format, code length, and basic syntax locally before render "
        "(no Kroki call). Returns errors and suggestions."
    ),
    category="uml",
    example="validate_uml('class', '@startuml\\nclass A\\n@enduml', 'svg')",
    annotations=ANNOTATIONS_VALIDATE,
)
def validate_uml(
    diagram_type: str,
    code: str,
    output_format: str = "svg",
) -> Dict[str, Any]:
    """Check inputs and light structure without rendering.

    Use to catch unsupported types, bad output_format for the type, empty code, or obvious
    PlantUML/Mermaid/D2 issues before calling generate_uml.

    Args:
        diagram_type: Same as generate_uml (see uml://types).
        code: Diagram source text.
        output_format: Intended output format (default svg); must be allowed for the type.

    Returns:
        Dict with valid (bool), errors, suggestions, backend, diagram_type, prepared_code,
        and optional corrected_code when only trivial wrapping changed the text.
    """
    logger.info(
        "Called validate_uml tool: type=%s, code length=%s",
        diagram_type,
        len(code or ""),
    )
    return validate_uml_inputs(diagram_type, code, output_format)


def register_diagram_tools(server: FastMCP) -> List[str]:
    """
    Register all diagram generation tools with the MCP server

    Args:
        server: The MCP server instance

    Returns:
        List of registered tool names
    """
    logger.info("Registering diagram tools")

    # Register all tools that were decorated with @mcp_tool
    registered_tools = register_tools_with_server(server)

    # Store registered tools in MCP_SETTINGS.tools (which is a standard attribute)
    MCP_SETTINGS.tools = registered_tools

    logger.info("Registered %s diagram tools successfully", len(registered_tools))
    logger.debug("Registered tools: %s", registered_tools)

    return registered_tools


def get_tool_info() -> Dict[str, Dict[str, Any]]:
    """
    Get information about all registered tools

    Returns:
        Dictionary mapping tool names to their information
    """
    return get_tool_registry()
