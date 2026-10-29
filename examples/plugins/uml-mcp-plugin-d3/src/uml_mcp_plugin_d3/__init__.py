"""UML-MCP plugin: interactive D3.js diagrams.

* ``d3_force``: a force-directed graph (drag, pin, zoom, pan).
* ``d3_architecture``: boxes in nested groups with cloud-service icons (AWS, Azure, Google
  Cloud, Kubernetes, on premises), input and output ports, and arrows routed around the
  boxes with A*. Boxes can be dragged and the arrows re-route.
* ``d3_topology``: the same engine, flowing top to bottom, for deployments and networks.

Each renders to ``html`` (a standalone interactive page) or ``svg`` (a static picture).
The source is JSON; call ``d3_catalog`` or read ``uml://examples`` for the format.
"""

from __future__ import annotations

from typing import Any

from mcp_core.plugins import DiagramTypeSpec, PluginContext, RenderOutput

from . import force, html, layout
from .icons import PROVIDERS, catalog
from .samples import SAMPLES
from .spec import DEFAULT_DIRECTION, MAX_NODES, ArchSpec, ForceSpec, SpecError, parse
from .svg import architecture_svg

__all__ = ["D3Renderer", "register"]

_DESCRIPTIONS = {
    "d3_force": (
        "Interactive force-directed graph (D3): drag and pin nodes, zoom, pan, hover to "
        "highlight. JSON nodes and links; html or svg"
    ),
    "d3_architecture": (
        "System or cloud architecture (D3): boxes in nested groups with AWS, Azure, GCP and "
        "Kubernetes style icons, input/output ports, A*-routed straight arrows and draggable boxes. "
        "JSON; html or svg"
    ),
    "d3_topology": (
        "Deployment or network topology (D3), flowing top to bottom, with zones, tiers and "
        "device icons; same engine and JSON as d3_architecture; html or svg"
    ),
}


class D3Renderer:
    """Render the three D3 diagram types, locally and without network access."""

    name = "d3"

    #: Interaction modes available for D3 diagram types in the unified viewer.
    _D3_FEATURES: tuple[str, ...] = (
        "zoom",
        "pan",
        "fit",
        "reset",
        "drag",
        "inspect",
        "story",
        "overlays",
    )
    _ARCH_FEATURES: tuple[str, ...] = _D3_FEATURES + ("drilldown", "trace")

    def __init__(self) -> None:
        self.d3_source = "cdn"
        self.max_nodes = MAX_NODES
        self.diagram_types = {
            dtype: DiagramTypeSpec(
                _DESCRIPTIONS[dtype],
                ("html", "svg"),
                example=example,
                template=template,
                version="1.0.0",
                interaction_features=(
                    self._D3_FEATURES if dtype == "d3_force" else self._ARCH_FEATURES
                ),
                security_profile="sandboxed",
                renderer_capabilities_version=2,
            )
            for dtype, (example, template) in SAMPLES.items()
        }

    def configure(self, settings: dict[str, Any]) -> None:
        """``plugins.settings.d3``: ``d3_source`` (cdn or inline) and ``max_nodes``."""
        source = str(settings.get("d3_source", "cdn"))
        if source not in ("cdn", "inline"):
            raise ValueError(f"d3_source must be 'cdn' or 'inline', not {source!r}")
        limit = int(settings.get("max_nodes", MAX_NODES))
        if not 1 <= limit <= MAX_NODES:
            raise ValueError(f"max_nodes must be between 1 and {MAX_NODES}")
        self.d3_source, self.max_nodes = source, limit

    def validate(self, diagram_type: str, code: str) -> list[str]:
        try:
            parse(diagram_type, code, max_nodes=self.max_nodes)
        except SpecError as exc:
            return exc.problems
        return []

    def render(self, diagram_type: str, code: str, output_format: str) -> RenderOutput:
        if output_format not in ("html", "svg"):
            raise ValueError("the d3 diagram types render html or svg")
        try:
            spec = parse(diagram_type, code, max_nodes=self.max_nodes)
        except SpecError as exc:
            raise ValueError(
                f"invalid {diagram_type} source: " + "; ".join(exc.problems)
            ) from exc

        if isinstance(spec, ForceSpec):
            model = force.build(spec)
            if output_format == "svg":
                text = force.force_svg(model, spec)
            else:
                text = html.force_page(model, spec, d3_source=self.d3_source)
        else:
            assert isinstance(spec, ArchSpec)
            arranged = layout.build(spec, diagram_type, DEFAULT_DIRECTION[diagram_type])
            if output_format == "svg":
                text = architecture_svg(arranged, title=spec.title, theme=spec.theme)
            else:
                text = html.architecture_page(arranged, spec, d3_source=self.d3_source)
        mime = "image/svg+xml" if output_format == "svg" else "text/html; charset=utf-8"
        return RenderOutput(text.encode("utf-8"), mime)


def register(ctx: PluginContext) -> None:
    """The ``d3_catalog`` tool: what a model can put in an architecture diagram."""

    @ctx.tool(
        "catalog",
        "List the providers, cloud service names (provider:service, for example aws:s3) and "
        "icon kinds that d3_architecture and d3_topology diagrams accept, and the diagram "
        "types of the d3 plugin. Read it before writing a diagram source.",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "providers": {"type": "object"},
                "services": {"type": "object"},
                "kinds": {"type": "array", "items": {"type": "string"}},
                "categories": {"type": "object"},
                "diagram_types": {"type": "object"},
            },
            "required": [
                "providers",
                "services",
                "kinds",
                "categories",
                "diagram_types",
            ],
        },
        example="d3_catalog(provider='aws')",
        lint_ignore={"tool-no-required": "the only argument is an optional filter"},
    )
    def catalog_tool(provider: str = "") -> dict[str, Any]:
        """List what the D3 diagrams accept.

        Args:
            provider: only list the services of this provider (aws, azure, gcp,
                kubernetes, onprem); empty lists all of them
        """
        if provider and provider not in PROVIDERS:
            return {
                "error": f"unknown provider {provider!r}; use one of {', '.join(sorted(PROVIDERS))}"
            }
        return {
            **catalog(provider or None),
            "diagram_types": dict(_DESCRIPTIONS),
        }
