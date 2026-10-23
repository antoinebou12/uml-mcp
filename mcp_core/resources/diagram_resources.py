"""
MCP resources for diagram information
"""

import json
import logging
from collections.abc import Callable
from typing import Any, TypeVar, cast

from tools.kroki.kroki_templates import DiagramExamples, DiagramTemplates

from ..core.config import MCP_SETTINGS
from ..core.diagram_catalog import get_diagram_types_dict

logger = logging.getLogger(__name__)

# Store for registered resources when using decorator pattern
_registered_resources: dict[str, dict[str, Any]] = {}

F = TypeVar("F", bound=Callable[..., Any])


def mcp_resource(
    uri: str, description: str | None = None, category: str = "default"
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
    from ..plugins.loader import plugin_sample

    templates = {}
    for name in MCP_SETTINGS.diagram_types:
        templates[name] = plugin_sample(name, "template") or (
            DiagramTemplates.get_template(name)
        )
    return json.dumps(templates, indent=2)


@mcp_resource(
    "uml://examples",
    description="Returns example diagrams for each type (class, sequence, activity, etc.). Use as reference for syntax and structure.",
)
def get_diagram_examples() -> str:
    """Get diagram examples for different diagram types"""
    from ..plugins.loader import plugin_sample

    examples = {}
    for name in MCP_SETTINGS.diagram_types:
        examples[name] = plugin_sample(name, "example") or (
            DiagramExamples.get_example(name)
        )
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
    caps: dict[str, dict[str, Any]] = {}
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
            "mermaid_ink_server": MCP_SETTINGS.mermaid_ink_server,
        },
        indent=2,
    )


@mcp_resource(
    "uml://recipes",
    description="Starter recipes (algorithm_flowchart, paper_concept) with diagram_type + template for generate_uml.",
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
    description="Plan-then-generate workflow; pairs with uml_diagram / skill://uml-mcp-diagrams/SKILL.md.",
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
            "prompt": "Use the uml_diagram prompt or skill://uml-mcp-diagrams/SKILL.md for plan-then-generate.",
        },
        indent=2,
    )


def _normalize_diagram_type(diagram_type: str) -> str:
    return (diagram_type or "").strip().lower()


def _unknown_diagram_type_payload(diagram_type: str) -> str:
    return json.dumps(
        {
            "error": f"Unknown diagram_type: {diagram_type!r}",
            "hint": "Use uml://types or completion/complete on diagram_type",
        },
        indent=2,
    )


def get_template_for_type(diagram_type: str) -> str:
    """Single-type starter template (resource template ``uml://templates/{diagram_type}``)."""
    from ..plugins.loader import plugin_sample

    key = _normalize_diagram_type(diagram_type)
    if key not in MCP_SETTINGS.diagram_types:
        return _unknown_diagram_type_payload(diagram_type)
    body = plugin_sample(key, "template") or DiagramTemplates.get_template(key)
    return json.dumps({"diagram_type": key, "template": body}, indent=2)


def get_example_for_type(diagram_type: str) -> str:
    """Single-type example (resource template ``uml://examples/{diagram_type}``)."""
    from ..plugins.loader import plugin_sample

    key = _normalize_diagram_type(diagram_type)
    if key not in MCP_SETTINGS.diagram_types:
        return _unknown_diagram_type_payload(diagram_type)
    body = plugin_sample(key, "example") or DiagramExamples.get_example(key)
    return json.dumps({"diagram_type": key, "example": body}, indent=2)


def get_formats_for_type(diagram_type: str) -> str:
    """Formats for one type (resource template ``uml://formats/{diagram_type}``)."""
    key = _normalize_diagram_type(diagram_type)
    cfg = MCP_SETTINGS.diagram_types.get(key)
    if cfg is None:
        return _unknown_diagram_type_payload(diagram_type)
    return json.dumps(
        {"diagram_type": key, "formats": list(cfg.formats)},
        indent=2,
    )


def get_recipe_for_id(recipe_id: str) -> str:
    """Single recipe (resource template ``uml://recipes/{recipe_id}``)."""
    recipes = json.loads(get_diagram_recipes())
    key = (recipe_id or "").strip().lower()
    if key not in recipes:
        return json.dumps(
            {
                "error": f"Unknown recipe_id: {recipe_id!r}",
                "hint": "Known ids: algorithm_flowchart, paper_concept",
            },
            indent=2,
        )
    return json.dumps({"recipe_id": key, **recipes[key]}, indent=2)


#: URI templates registered alongside the aggregate ``uml://`` resources.
RESOURCE_TEMPLATES: tuple[tuple[str, str, Callable[..., str]], ...] = (
    (
        "uml://templates/{diagram_type}",
        "Starter template for one diagram_type (JSON: diagram_type + template).",
        get_template_for_type,
    ),
    (
        "uml://examples/{diagram_type}",
        "Example diagram for one diagram_type (JSON: diagram_type + example).",
        get_example_for_type,
    ),
    (
        "uml://formats/{diagram_type}",
        "Supported output_format values for one diagram_type.",
        get_formats_for_type,
    ),
    (
        "uml://recipes/{recipe_id}",
        "One starter recipe (algorithm_flowchart or paper_concept).",
        get_recipe_for_id,
    ),
)


def register_resources_with_server(server: Any) -> list[str]:
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

    from ..observability.audit import instrument

    for uri, resource_info in _registered_resources.items():
        func = instrument(resource_info["function"], "resource", uri)

        # Register with server using resource decorator
        resource_decorator = server.resource(uri)
        resource_decorator(func)

        registered_resource_uris.append(uri)
        logger.debug(f"Registered resource: {uri}")

    return registered_resource_uris


def register_resource_templates_with_server(server: Any) -> list[str]:
    """Register parameterized ``uml://`` resource templates (SEP resource templates)."""
    from ..observability.audit import instrument

    uris: list[str] = []
    for uri, description, func in RESOURCE_TEMPLATES:
        wrapped = instrument(func, "resource", uri)
        try:
            server.resource(uri, description=description)(wrapped)
        except TypeError:
            server.resource(uri)(wrapped)
        uris.append(uri)
        logger.debug("Registered resource template: %s", uri)
    return uris


def register_diagram_resources(server: Any) -> list[str]:
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
    registered_resources += register_resource_templates_with_server(server)

    from .completions import register_completions

    register_completions(server)

    # Store registered resources in MCP_SETTINGS
    MCP_SETTINGS.resources = registered_resources

    logger.info("Diagram resources registered successfully")

    return registered_resources


def get_resource_registry() -> dict[str, dict[str, Any]]:
    """
    Get the registry of all resources registered with the decorator

    Returns:
        Dictionary of resource metadata
    """
    return _registered_resources
