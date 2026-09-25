"""Example UML-MCP plugin.

* ``hello_echo``: a read-only MCP tool (audit, rate limits, lint and auth apply).
* ``ascii`` diagram type: renders plain text / ASCII art into an SVG, locally.
"""

from __future__ import annotations

from html import escape

from mcp_core.plugins import DiagramTypeSpec, PluginContext, RenderOutput


def register(ctx: PluginContext) -> None:
    greeting = str(ctx.settings.get("greeting", "Hello"))

    @ctx.tool(
        "echo",
        "Echo a message back with the configured greeting. Useful to verify that "
        "plugins are installed and enabled.",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        output_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        example="hello_echo(text='world')",
    )
    def echo(text: str) -> dict[str, str]:
        """Echo text.

        Args:
            text: what to echo back
        """
        return {"message": f"{greeting}, {text}!"}


class AsciiRenderer:
    """Render text as monospace SVG (no network, no dependencies)."""

    name = "ascii"

    def __init__(self) -> None:
        self.diagram_types = {
            "ascii": DiagramTypeSpec(
                "Plain text / ASCII art rendered as SVG", ("svg",)
            ),
        }

    def render(self, diagram_type: str, code: str, output_format: str) -> RenderOutput:
        if output_format != "svg":
            raise ValueError("ascii renders svg only")
        lines = code.splitlines() or [""]
        width = max(len(line) for line in lines) * 8 + 24
        height = len(lines) * 18 + 24
        body = "".join(
            f'<text x="12" y="{24 + i * 18}" xml:space="preserve">{escape(line)}</text>'
            for i, line in enumerate(lines)
        )
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'font-family="monospace" font-size="14"><rect width="100%" height="100%" '
            f'fill="white"/>{body}</svg>'
        )
        return RenderOutput(svg.encode("utf-8"), "image/svg+xml")
