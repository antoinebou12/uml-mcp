"""
MCP resources for diagram information
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional, TypeVar, cast

from tools.kroki.kroki_templates import DiagramExamples, DiagramTemplates

from ..core.config import MCP_SETTINGS
from ..core.diagram_catalog import get_diagram_types_dict

logger = logging.getLogger(__name__)

# Store for registered resources when using decorator pattern
_registered_resources: Dict[str, Dict[str, Any]] = {}

F = TypeVar("F", bound=Callable[..., Any])


def mcp_resource(
    uri: str, description: Optional[str] = None, category: str = "default"
) -> Callable[[F], F]:
    """
    Decorator for registering a function as an MCP resource.

    Args:
        uri: Resource URI
        description: Resource description (defaults to function docstring if not provided)
        category: Resource category for organization

    Returns:
        Decorated function

    Example:
        @mcp_resource("uml://types", description="Get available diagram types")
        def get_diagram_types():
            # Implementation
            return {"class": {...}, "sequence": {...}}
    """

    def decorator(func: F) -> F:
        func_doc = func.__doc__ or ""
        func_description = description or func_doc.split("\n")[0] if func_doc else ""

        # Store resource metadata
        _registered_resources[uri] = {
            "function": func,
            "uri": uri,
            "description": func_description,
            "category": category,
        }

        # Return function unchanged
        return cast(F, func)

    return decorator


# Define resources using decorators
@mcp_resource(
    "uml://types",
    description="Returns available diagram types with backend, description, and supported formats (e.g. class, sequence, mermaid, d2). Use before generating to verify diagram_type.",
)
def get_diagram_types() -> str:
    """Get available diagram types"""
    return json.dumps(get_diagram_types_dict(), indent=2)


@mcp_resource(
    "uml://templates",
    description="Returns starter templates (PlantUML, Mermaid, D2, etc.) for each diagram type. Use to get minimal valid code to customize.",
)
def get_diagram_templates() -> str:
    """Get diagram templates for different diagram types"""
    templates = {}
    for name in MCP_SETTINGS.diagram_types:
        templates[name] = DiagramTemplates.get_template(name)
    return json.dumps(templates, indent=2)


@mcp_resource(
    "uml://examples",
    description="Returns example diagrams for each type (class, sequence, activity, etc.). Use as reference for syntax and structure.",
)
def get_diagram_examples() -> str:
    """Get diagram examples for different diagram types"""
    examples = {}
    for name in MCP_SETTINGS.diagram_types:
        examples[name] = DiagramExamples.get_example(name)
    return json.dumps(examples, indent=2)


@mcp_resource(
    "uml://formats",
    description="Returns supported output formats (svg, png, pdf) per diagram type. Use to choose valid output_format for generate_uml.",
)
def get_output_formats() -> str:
    """Get supported output formats for each diagram type"""
    formats = {}
    for name, config in MCP_SETTINGS.diagram_types.items():
        formats[name] = config.formats
    return json.dumps(formats, indent=2)


@mcp_resource(
    "uml://capabilities",
    description=(
        "Matrix of diagram_type -> backend engine and supported output_format values. "
        "Same data the server uses for validation before render."
    ),
)
def get_capabilities() -> str:
    """Type → backend → formats matrix for tooling and clients."""
    caps: Dict[str, Dict[str, Any]] = {}
    for name, config in MCP_SETTINGS.diagram_types.items():
        caps[name] = {
            "backend": config.backend,
            "formats": list(config.formats),
            "description": config.description,
        }
    return json.dumps(caps, indent=2)


@mcp_resource(
    "uml://server-info",
    description="Returns server metadata: name, version, tools, prompts, Kroki URL. Use for discovery and health checks.",
)
def get_server_info() -> str:
    """Get MCP server information"""
    return json.dumps(
        {
            "server_name": MCP_SETTINGS.server_name,
            "version": MCP_SETTINGS.version,
            "description": MCP_SETTINGS.description,
            "tools": MCP_SETTINGS.tools,
            "prompts": MCP_SETTINGS.prompts,
            "kroki_server": MCP_SETTINGS.kroki_server,
            "plantuml_server": MCP_SETTINGS.plantuml_server,
        },
        indent=2,
    )


@mcp_resource(
    "uml://recipes",
    description=(
        "Named recipe templates that span multiple diagram_types (e.g. algorithm_flowchart, "
        "paper_concept). Each entry pairs a recipe key with a starter source body and the "
        "diagram_type to pass to generate_uml. Use after the algorithm_explainer or "
        "paper_concept_diagram prompts."
    ),
)
def get_diagram_recipes() -> str:
    """Return curated starter recipes that map a use case to a ready-to-edit source body."""
    recipes = {
        "algorithm_flowchart": {
            "diagram_type": "mermaid",
            "output_format": "svg",
            "description": (
                "Mermaid flowchart for explaining an algorithm. Each step is labelled "
                "with its time complexity and the aggregate complexity is noted at the "
                "bottom."
            ),
            "prompt": "algorithm_explainer",
            "template": DiagramTemplates.get_template("algorithm_flowchart"),
        },
        "paper_concept": {
            "diagram_type": "mermaid",
            "output_format": "svg",
            "description": (
                "Mermaid flowchart visualising a paper concept (e.g. transformer block) "
                "with clickable arXiv links on the cited nodes. Render as SVG so the "
                "links remain clickable."
            ),
            "prompt": "paper_concept_diagram",
            "template": DiagramTemplates.get_template("paper_concept"),
        },
    }
    return json.dumps(recipes, indent=2)


@mcp_resource(
    "uml://workflow",
    description="Recommended workflow: plan first (diagram type, elements, relationships), then call generate_uml with the final code. Use uml_diagram or uml_diagram_with_thinking prompt.",
)
def get_recommended_workflow() -> str:
    """Return the recommended workflow: plan first, then call generate_uml."""
    return json.dumps(
        {
            "workflow": (
                "Plan first: decide diagram type, purpose (communication, design, documentation, etc.), "
                "and key elements (actors, messages, classes, states, etc.) and relationships. "
                "Then output the diagram code and call generate_uml with the chosen diagram_type and the final code."
            ),
            "prompt": "Use the uml_diagram or uml_diagram_with_thinking prompt for plan-then-generate instructions.",
        },
        indent=2,
    )


def register_resources_with_server(server: Any) -> List[str]:
    """
    Register all decorated resources with the MCP server

    Args:
        server: The MCP server instance

    Returns:
        List of registered resource URIs
    """
    logger.info(
        f"Registering {len(_registered_resources)} resources with the MCP server"
    )

    registered_resource_uris = []

    for uri, resource_info in _registered_resources.items():
        func = resource_info["function"]

        # Register with server using resource decorator
        resource_decorator = server.resource(uri)
        resource_decorator(func)

        registered_resource_uris.append(uri)
        logger.debug(f"Registered resource: {uri}")

    return registered_resource_uris


def register_diagram_resources(server: Any) -> List[str]:
    """
    Register diagram resources with the MCP server

    Args:
        server: The MCP server instance

    Returns:
        List of registered resource names
    """
    logger.info("Registering diagram resources")

    # Register all resources that were decorated with @mcp_resource
    registered_resources = register_resources_with_server(server)

    # Store registered resources in MCP_SETTINGS
    MCP_SETTINGS.resources = registered_resources

    logger.info("Diagram resources registered successfully")

    return registered_resources


def get_resource_registry() -> Dict[str, Dict[str, Any]]:
    """
    Get the registry of all resources registered with the decorator

    Returns:
        Dictionary of resource metadata
    """
    return _registered_resources
