"""UML-MCP plugin: agent traces as a waterfall and a flow.

One diagram type, ``agent_trace``: the steps of an agent run (user turns, LLM calls, tool
calls, retrievals, sub-agents, guardrails, memory, replies, errors) on a time axis, nested
under their parent, with durations, tokens and cost. ``svg`` is a static waterfall with a
summary header; ``html`` is an interactive page with a waterfall and a flow view, folding
sub-agents, a detail card per step, the critical path, themes and exports.

The source is the native ``steps`` JSON or a minimal OpenTelemetry span list using the
GenAI semantic conventions; see ``uml://examples``.
"""

from __future__ import annotations

from typing import Any

from mcp_core.plugins import DiagramTypeSpec, RenderOutput

from . import html
from .samples import EXAMPLE, OTEL_EXAMPLE, TEMPLATE
from .spec import MAX_STEPS, SpecError, Trace, parse
from .svg import waterfall_svg

__all__ = ["OTEL_EXAMPLE", "TraceRenderer"]

DESCRIPTION = (
    "Agent run trace: steps (user, llm, tool, retrieval, subagent, guardrail, memory, reply, "
    "error) as a waterfall on a time axis with tokens, cost, errors and retries; the html page "
    "adds a flow view, folding, step details and the critical path. JSON steps or "
    "OpenTelemetry GenAI spans; html or svg"
)
FEATURES = ("zoom", "pan", "fit", "theme", "inspect", "trace")


class TraceRenderer:
    """Render ``agent_trace`` sources locally, without network access."""

    name = "trace"

    def __init__(self) -> None:
        self.max_steps = MAX_STEPS
        self.diagram_types = {
            "agent_trace": DiagramTypeSpec(
                DESCRIPTION,
                ("html", "svg"),
                example=EXAMPLE,
                template=TEMPLATE,
                version="0.1.0",
                source_schema="urn:uml-mcp:agent-trace:1",
                interaction_features=FEATURES,
                security_profile="sandboxed",
                renderer_capabilities_version=2,
            )
        }

    def configure(self, settings: dict[str, Any]) -> None:
        """``plugins.settings.trace``: ``max_steps`` (1 to 400)."""
        value = settings.get("max_steps", MAX_STEPS)
        if type(value) is not int or not 1 <= value <= MAX_STEPS:
            raise ValueError(f"max_steps must be an integer from 1 to {MAX_STEPS}")
        self.max_steps = value

    def _parse(self, diagram_type: str, code: str) -> Trace:
        if diagram_type not in self.diagram_types:
            raise SpecError([f"unknown trace type: {diagram_type}"])
        return parse(code, max_steps=self.max_steps)

    def validate(self, diagram_type: str, code: str) -> list[str]:
        try:
            self._parse(diagram_type, code)
        except SpecError as exc:
            return exc.problems
        return []

    def render(self, diagram_type: str, code: str, output_format: str) -> RenderOutput:
        if output_format not in ("html", "svg"):
            raise ValueError("agent_trace renders html or svg")
        try:
            trace = self._parse(diagram_type, code)
        except SpecError as exc:
            raise ValueError(
                f"invalid {diagram_type} source: " + "; ".join(exc.problems)
            ) from exc
        if output_format == "html":
            return RenderOutput(
                html.page(trace).encode("utf-8"), "text/html; charset=utf-8"
            )
        theme = "light" if trace.theme == "light" else "dark"
        return RenderOutput(
            waterfall_svg(trace, theme=theme).encode("utf-8"), "image/svg+xml"
        )
