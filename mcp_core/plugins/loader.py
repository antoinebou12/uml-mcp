"""Discover, allow-list and load plugins; route plugin diagram types to renderers."""

from __future__ import annotations

import base64
import importlib.metadata as md
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from .api import RENDERERS_GROUP, TOOLS_GROUP, PluginContext, Renderer

logger = logging.getLogger(__name__)


@dataclass
class PluginStatus:
    name: str
    group: str  # tools | renderers
    target: str
    distribution: str | None
    version: str | None
    enabled: bool
    loaded: bool = False
    error: str | None = None
    tools: list[str] = field(default_factory=list)
    diagram_types: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


#: Loaded renderers by diagram type, and the status of every discovered plugin.
RENDERERS: dict[str, Renderer] = {}
STATUS: list[PluginStatus] = []


def entry_points(group: str) -> list[md.EntryPoint]:
    return list(md.entry_points(group=group))


def discover() -> list[PluginStatus]:
    """Installed plugins (not loaded), for listings and lint."""
    from ..core.settings_file import get_app_config

    enabled = set(get_app_config().plugins.enabled)
    out = []
    for group, label in ((TOOLS_GROUP, "tools"), (RENDERERS_GROUP, "renderers")):
        for ep in entry_points(group):
            dist = getattr(ep, "dist", None)
            out.append(
                PluginStatus(
                    name=ep.name,
                    group=label,
                    target=ep.value,
                    distribution=getattr(dist, "name", None),
                    version=getattr(dist, "version", None),
                    enabled=ep.name in enabled,
                )
            )
    return out


def _load_renderer(obj: Any) -> Renderer:
    renderer = obj() if isinstance(obj, type) else obj
    if not isinstance(renderer, Renderer):
        raise TypeError("renderer must define name, diagram_types and render()")
    return renderer


def load_plugins() -> list[PluginStatus]:
    """Load allow-listed plugins; failures are recorded, never raised."""
    from ..core.config import MCP_SETTINGS, DiagramType
    from ..core.settings_file import get_app_config

    catalog = MCP_SETTINGS.diagram_types  # read by tools, resources and validation

    cfg = get_app_config().plugins
    STATUS.clear()
    for status in discover():
        STATUS.append(status)
        if not status.enabled:
            continue
        group = TOOLS_GROUP if status.group == "tools" else RENDERERS_GROUP
        ep = next(e for e in entry_points(group) if e.name == status.name)
        try:
            obj = ep.load()
            if status.group == "tools":
                ctx = PluginContext(
                    status.name, dict(cfg.settings.get(status.name) or {})
                )
                obj(ctx)
                status.tools = list(ctx.registered)
            else:
                renderer = _load_renderer(obj)
                for dtype, spec in renderer.diagram_types.items():
                    if dtype in catalog and dtype not in RENDERERS:
                        raise ValueError(f"diagram type {dtype!r} is already built in")
                    RENDERERS[dtype] = renderer
                    catalog[dtype] = DiagramType(
                        backend=f"plugin:{renderer.name}",
                        description=spec.description,
                        formats=list(spec.formats),
                    )
                    status.diagram_types.append(dtype)
            status.loaded = True
            logger.info("Loaded plugin %s (%s)", status.name, status.group)
        except Exception as exc:  # noqa: BLE001 - a broken plugin must not stop the server
            status.error = f"{type(exc).__name__}: {exc}"
            logger.error("Plugin %s failed to load: %s", status.name, status.error)
    missing = set(cfg.enabled) - {s.name for s in STATUS}
    for name in sorted(missing):
        STATUS.append(
            PluginStatus(
                name=name,
                group="?",
                target="",
                distribution=None,
                version=None,
                enabled=True,
                error="not installed",
            )
        )
    return STATUS


def render_with_plugin(
    diagram_type: str, code: str, output_format: str
) -> dict[str, Any]:
    """Render through a plugin renderer; returns the standard result dict."""
    renderer = RENDERERS[diagram_type]
    try:
        out = renderer.render(diagram_type, code, output_format)
    except Exception as exc:  # noqa: BLE001 - surface as a tool error result
        return {
            "code": code,
            "url": None,
            "playground": None,
            "local_path": None,
            "error": f"plugin renderer {renderer.name} failed: {exc}",
        }
    return {
        "code": code,
        "url": out.url,
        "playground": None,
        "local_path": None,
        "source": f"plugin:{renderer.name}",
        "content_base64": base64.b64encode(out.content).decode("ascii"),
        "mime_type": out.mime_type,
    }


__all__ = [
    "RENDERERS",
    "STATUS",
    "PluginStatus",
    "discover",
    "load_plugins",
    "render_with_plugin",
]
