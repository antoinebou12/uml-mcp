"""
Configuration settings for MCP server.
"""

import os
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field

from tools.kroki.kroki import LANGUAGE_OUTPUT_SUPPORT


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name, "")
    if v == "":
        return default
    return v.lower() in ("true", "1", "yes")


def _env_use_local_kroki() -> bool:
    return os.environ.get("USE_LOCAL_KROKI", "false").lower() in (
        "true",
        "1",
        "yes",
    )


def _diagram_fallback_default() -> bool:
    """
    When False, a Kroki failure does not try PlantUML server or Mermaid.ink.

    MCP_DIAGRAM_FALLBACK overrides when set. Otherwise disabled on Vercel or when
    USE_LOCAL_KROKI=true (Docker / local Kroki stack). Enabled for typical desktop
    use with public Kroki.
    """
    explicit = os.environ.get("MCP_DIAGRAM_FALLBACK", "").strip().lower()
    if explicit in ("true", "1", "yes"):
        return True
    if explicit in ("false", "0", "no"):
        return False
    if _env_bool("VERCEL", False):
        return False
    if _env_use_local_kroki():
        return False
    return True


def _default_output_dir() -> str:
    """Default diagram output directory (current working directory / output)."""
    return str(Path.cwd() / "output")


def _memory_only_default() -> bool:
    """
    When True, diagram generation never writes to disk (URL + base64 only).

    On Vercel (VERCEL set), defaults to True so serverless stays within /tmp limits
    and avoids redundant file I/O. Set MCP_MEMORY_ONLY=false to allow writes to
    VERCEL_OUTPUT_DIR. Locally, default False unless MCP_MEMORY_ONLY=true.
    """
    explicit = os.environ.get("MCP_MEMORY_ONLY", "").strip().lower()
    if explicit in ("true", "1", "yes"):
        return True
    if explicit in ("false", "0", "no"):
        return False
    return _env_bool("VERCEL", False)


def _url_only_default() -> bool:
    """
    When True, diagram pipeline returns Kroki/playground URLs only: no HTTP fetch of
    rendered bytes, no content_base64, no image bytes in the serverless function.

    On Vercel (VERCEL set), defaults to True. Set MCP_URL_ONLY=false to fetch and
    return base64 when not saving to disk. Locally, default False unless
    MCP_URL_ONLY=true.
    """
    explicit = os.environ.get("MCP_URL_ONLY", "").strip().lower()
    if explicit in ("true", "1", "yes"):
        return True
    if explicit in ("false", "0", "no"):
        return False
    return _env_bool("VERCEL", False)


def _get_output_dir() -> str:
    """Output dir: on Vercel use writable /tmp; else MCP env or cwd/output."""
    if os.environ.get("VERCEL"):
        return os.environ.get("VERCEL_OUTPUT_DIR", "/tmp/diagrams")
    return (
        os.environ.get("MCP_OUTPUT_DIR")
        or os.environ.get("UML_MCP_OUTPUT_DIR")
        or _default_output_dir()
    )


class DiagramType(BaseModel):
    """Configuration for a diagram type."""

    backend: str
    description: str
    formats: List[str] = ["png", "svg"]


class MCPSettings(BaseModel):
    """Configuration settings for MCP server."""

    server_name: str = "uml_mcp"  # MCP naming: {service}_mcp (protocol)
    display_name: str = "UML Diagram Generator"  # Human-readable for UI
    version: str = "1.3.0"
    read_only: bool = Field(default_factory=lambda: _env_bool("MCP_READ_ONLY", False))
    memory_only: bool = Field(default_factory=_memory_only_default)
    url_only: bool = Field(default_factory=_url_only_default)
    diagram_fallback_enabled: bool = Field(default_factory=_diagram_fallback_default)
    lulu_ads_enabled: bool = Field(default_factory=lambda: _env_bool("LULU_ADS_ENABLED", _env_bool("VERCEL", False)))
    description: str = "Generate UML and other diagrams through MCP"
    config_schema_url: str = (
        ""  # Optional URL for session config schema (improves Configuration UX score)
    )
    max_code_length: int = Field(
        default_factory=lambda: int(os.environ.get("MCP_MAX_CODE_LENGTH", "500000"))
    )
    max_render_seconds: float = Field(
        default_factory=lambda: float(os.environ.get("MCP_MAX_RENDER_SECONDS", "30"))
    )
    batch_max_items: int = Field(
        default_factory=lambda: int(os.environ.get("MCP_BATCH_MAX_ITEMS", "20"))
    )
    rate_limit_per_minute: int = Field(
        default_factory=lambda: int(os.environ.get("MCP_RATE_LIMIT_PER_MINUTE", "0"))
    )
    output_dir: str = _get_output_dir()
    tools: List[str] = []
    prompts: List[str] = []
    resources: List[str] = []  # Added resources field
    diagram_types: Dict[str, DiagramType] = {}
    plantuml_server: str = os.environ.get(
        "PLANTUML_SERVER", "http://plantuml-server:8080"
    )
    kroki_server: str = os.environ.get("KROKI_SERVER", "https://kroki.io")

    @property
    def output_path(self) -> Path:
        """Output directory as a Path for file operations."""
        return Path(self.output_dir)


# Define supported diagram types with their backends. Formats from https://kroki.io/
DIAGRAM_TYPES = {
    # UML diagram types (PlantUML)
    "class": DiagramType(
        backend="plantuml",
        description="Shows classes, attributes, methods and relationships between classes",
        formats=LANGUAGE_OUTPUT_SUPPORT["plantuml"],
    ),
    "sequence": DiagramType(
        backend="plantuml",
        description="Shows object interactions arranged in time sequence",
        formats=LANGUAGE_OUTPUT_SUPPORT["plantuml"],
    ),
    "activity": DiagramType(
        backend="plantuml",
        description="Shows workflows or business processes",
        formats=LANGUAGE_OUTPUT_SUPPORT["plantuml"],
    ),
    "usecase": DiagramType(
        backend="plantuml",
        description="Shows system functionality and actors who interact with it",
        formats=LANGUAGE_OUTPUT_SUPPORT["plantuml"],
    ),
    "state": DiagramType(
        backend="plantuml",
        description="Shows states of an object during its lifecycle",
        formats=LANGUAGE_OUTPUT_SUPPORT["plantuml"],
    ),
    "component": DiagramType(
        backend="plantuml",
        description="Shows components and dependencies",
        formats=LANGUAGE_OUTPUT_SUPPORT["plantuml"],
    ),
    "deployment": DiagramType(
        backend="plantuml",
        description="Shows physical architecture of a system",
        formats=LANGUAGE_OUTPUT_SUPPORT["plantuml"],
    ),
    "object": DiagramType(
        backend="plantuml",
        description="Shows instances of classes and their relationships",
        formats=LANGUAGE_OUTPUT_SUPPORT["plantuml"],
    ),
    # Other diagram types
    "mermaid": DiagramType(
        backend="mermaid",
        description="A JavaScript based diagramming and charting tool",
        formats=LANGUAGE_OUTPUT_SUPPORT["mermaid"],
    ),
    "d2": DiagramType(
        backend="d2",
        description="A modern diagram scripting language",
        formats=LANGUAGE_OUTPUT_SUPPORT["d2"],
    ),
    "graphviz": DiagramType(
        backend="graphviz",
        description="Graph visualization software",
        formats=LANGUAGE_OUTPUT_SUPPORT["graphviz"],
    ),
    "erd": DiagramType(
        backend="erd",
        description="Entity-relationship diagrams",
        formats=LANGUAGE_OUTPUT_SUPPORT["erd"],
    ),
    "blockdiag": DiagramType(
        backend="blockdiag",
        description="Simple block diagram images",
        formats=LANGUAGE_OUTPUT_SUPPORT["blockdiag"],
    ),
    "packetdiag": DiagramType(
        backend="packetdiag",
        description="Network packet layout diagrams",
        formats=LANGUAGE_OUTPUT_SUPPORT["packetdiag"],
    ),
    "bpmn": DiagramType(
        backend="bpmn",
        description="Business Process Model and Notation",
        formats=LANGUAGE_OUTPUT_SUPPORT["bpmn"],
    ),
    "c4plantuml": DiagramType(
        backend="c4plantuml",
        description="C4 model diagrams using PlantUML",
        formats=LANGUAGE_OUTPUT_SUPPORT["c4plantuml"],
    ),
    # Kroki backend types (https://kroki.io/)
    "actdiag": DiagramType(
        backend="actdiag",
        description="Activity and workflow diagrams (blockdiag family)",
        formats=LANGUAGE_OUTPUT_SUPPORT["actdiag"],
    ),
    "bytefield": DiagramType(
        backend="bytefield",
        description="Binary protocol and byte layout diagrams",
        formats=LANGUAGE_OUTPUT_SUPPORT["bytefield"],
    ),
    "seqdiag": DiagramType(
        backend="seqdiag",
        description="Sequence diagrams (blockdiag family)",
        formats=LANGUAGE_OUTPUT_SUPPORT["seqdiag"],
    ),
    "nwdiag": DiagramType(
        backend="nwdiag",
        description="Network diagrams (blockdiag family)",
        formats=LANGUAGE_OUTPUT_SUPPORT["nwdiag"],
    ),
    "rackdiag": DiagramType(
        backend="rackdiag",
        description="Rack and server layout diagrams (blockdiag family)",
        formats=LANGUAGE_OUTPUT_SUPPORT["rackdiag"],
    ),
    "dbml": DiagramType(
        backend="dbml",
        description="Database Markup Language schema diagrams",
        formats=LANGUAGE_OUTPUT_SUPPORT["dbml"],
    ),
    "ditaa": DiagramType(
        backend="ditaa",
        description="Diagrams Through ASCII Art",
        formats=LANGUAGE_OUTPUT_SUPPORT["ditaa"],
    ),
    "excalidraw": DiagramType(
        backend="excalidraw",
        description="Excalidraw whiteboard-style diagrams",
        formats=LANGUAGE_OUTPUT_SUPPORT["excalidraw"],
    ),
    "nomnoml": DiagramType(
        backend="nomnoml",
        description="UML-style diagrams from shorthand syntax",
        formats=LANGUAGE_OUTPUT_SUPPORT["nomnoml"],
    ),
    "pikchr": DiagramType(
        backend="pikchr",
        description="Pikchr diagram scripting language",
        formats=LANGUAGE_OUTPUT_SUPPORT["pikchr"],
    ),
    "plantuml": DiagramType(
        backend="plantuml",
        description="PlantUML raw diagram source (all diagram kinds)",
        formats=LANGUAGE_OUTPUT_SUPPORT["plantuml"],
    ),
    "structurizr": DiagramType(
        backend="structurizr",
        description="Structurizr C4 and architecture DSL",
        formats=LANGUAGE_OUTPUT_SUPPORT["structurizr"],
    ),
    "svgbob": DiagramType(
        backend="svgbob",
        description="ASCII art to SVG diagrams",
        formats=LANGUAGE_OUTPUT_SUPPORT["svgbob"],
    ),
    "symbolator": DiagramType(
        backend="symbolator",
        description="Digital logic and schematic symbols",
        formats=LANGUAGE_OUTPUT_SUPPORT["symbolator"],
    ),
    "tikz": DiagramType(
        backend="tikz",
        description="TikZ/PGF graphics (LaTeX)",
        formats=LANGUAGE_OUTPUT_SUPPORT["tikz"],
    ),
    "vega": DiagramType(
        backend="vega",
        description="Vega visualization grammar",
        formats=LANGUAGE_OUTPUT_SUPPORT["vega"],
    ),
    "vegalite": DiagramType(
        backend="vegalite",
        description="Vega-Lite visualization grammar",
        formats=LANGUAGE_OUTPUT_SUPPORT["vegalite"],
    ),
    "wavedrom": DiagramType(
        backend="wavedrom",
        description="Waveform and digital timing diagrams",
        formats=LANGUAGE_OUTPUT_SUPPORT["wavedrom"],
    ),
    "wireviz": DiagramType(
        backend="wireviz",
        description="Cable and wiring diagrams",
        formats=LANGUAGE_OUTPUT_SUPPORT["wireviz"],
    ),
}

# Create MCP settings
MCP_SETTINGS = MCPSettings(diagram_types=DIAGRAM_TYPES)

# Override servers when local backends are requested
_use_local_kroki = _env_use_local_kroki()
_use_local_plantuml = os.environ.get("USE_LOCAL_PLANTUML", "false").lower() in (
    "true",
    "1",
    "yes",
)
if _use_local_kroki:
    MCP_SETTINGS.kroki_server = os.environ.get("KROKI_SERVER", "http://kroki:8000")
if _use_local_plantuml:
    MCP_SETTINGS.plantuml_server = os.environ.get(
        "PLANTUML_SERVER", "http://plantuml-server:8080"
    )
