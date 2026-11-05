"""Parse and validate the JSON source shared by the 2D and 3D renderers."""

from __future__ import annotations

import itertools
import json
import re
from dataclasses import dataclass
from typing import Any

MAX_LAYERS = 64
MAX_CONNECTIONS = 160
MAX_LABEL = 80
MAX_NOTE = 240
MAX_REPEAT = 256
MAX_GROUPS = 16

LAYER_KINDS = (
    "input",
    "embedding",
    "attention",
    "normalization",
    "feedforward",
    "residual",
    "router",
    "expert",
    "memory",
    "output",
    "encoder",
    "decoder",
    "bottleneck",
    "vector",
    "decision",
    "token",
    "generic",
)

#: Kinds drawn as dedicated shapes (trapezoids, bars, squares, circles, chips) in the
#: ``flow`` layout, following the usual autoencoder / GAN / VAE diagram conventions.
SHAPED_KINDS = ("encoder", "decoder", "bottleneck", "vector", "decision", "token")
LAYOUTS = ("grid", "flow")

KIND_COLORS = {
    "input": "#38bdf8",
    "embedding": "#818cf8",
    "attention": "#a78bfa",
    "normalization": "#2dd4bf",
    "feedforward": "#f59e0b",
    "residual": "#fb7185",
    "router": "#e879f9",
    "expert": "#f97316",
    "memory": "#22c55e",
    "output": "#60a5fa",
    "encoder": "#6aa84f",
    "decoder": "#3d85c6",
    "bottleneck": "#e06666",
    "vector": "#93c47d",
    "decision": "#8e7cc3",
    "token": "#ea9999",
    "generic": "#94a3b8",
}

_ID = re.compile(r"^[A-Za-z0-9_.-]{1,48}$")
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class SpecError(ValueError):
    """A source error that explains how to fix the diagram."""


@dataclass(frozen=True)
class Layer:
    id: str
    label: str
    kind: str
    shape: tuple[int, ...]
    repeat: int
    color: str
    note: str
    group: str | None = None


@dataclass(frozen=True)
class Group:
    """A labelled container around layers, e.g. a repeated transformer block."""

    id: str
    label: str
    repeat: int
    color: str


@dataclass(frozen=True)
class Connection:
    source: str
    target: str
    label: str
    style: str


@dataclass(frozen=True)
class LLMSpec:
    title: str
    subtitle: str
    theme: str
    layers: tuple[Layer, ...]
    connections: tuple[Connection, ...]
    layout: str = "grid"
    direction: str = "LR"
    groups: tuple[Group, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "layout": self.layout,
            "direction": self.direction,
            "groups": [
                {"id": g.id, "label": g.label, "repeat": g.repeat, "color": g.color}
                for g in self.groups
            ],
            "title": self.title,
            "subtitle": self.subtitle,
            "theme": self.theme,
            "layers": [
                {
                    "id": layer.id,
                    "label": layer.label,
                    "kind": layer.kind,
                    "shape": list(layer.shape),
                    "repeat": layer.repeat,
                    "color": layer.color,
                    "note": layer.note,
                    "group": layer.group,
                }
                for layer in self.layers
            ],
            "connections": [
                {
                    "from": edge.source,
                    "to": edge.target,
                    "label": edge.label,
                    "style": edge.style,
                }
                for edge in self.connections
            ],
        }


def _text(value: Any, field: str, maximum: int, *, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise SpecError(f"{field} must be a string")
    value = value.strip()
    if len(value) > maximum:
        raise SpecError(f"{field} must be at most {maximum} characters")
    return value


def _integer(value: Any, field: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise SpecError(f"{field} must be an integer from {low} to {high}")
    return value


def _strip_fence(source: str) -> str:
    source = source.strip()
    match = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```", source, re.DOTALL)
    return match.group(1).strip() if match else source


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SpecError(f"{field} must be an object")
    return value


def parse(source: str, *, max_layers: int = MAX_LAYERS) -> LLMSpec:
    """Parse one LLM visualizer source document."""
    try:
        raw = json.loads(_strip_fence(source))
    except json.JSONDecodeError as exc:
        raise SpecError(
            f"source must be JSON: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    root = _object(raw, "source")

    title = _text(root.get("title"), "title", MAX_LABEL, default="LLM architecture")
    subtitle = _text(root.get("subtitle"), "subtitle", MAX_NOTE)
    theme = _text(root.get("theme"), "theme", 5, default="dark")
    if theme not in {"light", "dark", "auto"}:
        raise SpecError("theme must be 'light', 'dark' or 'auto'")
    if theme == "auto":  # static output is dark; the viewer has its own toggle
        theme = "dark"
    layout = _text(root.get("layout"), "layout", 4, default="grid")
    if layout not in LAYOUTS:
        raise SpecError("layout must be 'grid' or 'flow'")
    direction = _text(root.get("direction"), "direction", 2, default="LR")
    if direction not in {"LR", "TB"}:
        raise SpecError("direction must be 'LR' (left to right) or 'TB' (top down)")

    raw_groups = root.get("groups", [])
    if not isinstance(raw_groups, list) or len(raw_groups) > MAX_GROUPS:
        raise SpecError(f"groups must be an array of at most {MAX_GROUPS} items")
    groups: list[Group] = []
    group_ids: set[str] = set()
    for index, item in enumerate(raw_groups):
        obj = _object(item, f"groups[{index}]")
        group_id = _text(obj.get("id"), f"groups[{index}].id", 48)
        if not _ID.fullmatch(group_id):
            raise SpecError(
                f"groups[{index}].id must use 1-48 letters, numbers, '.', '_' or '-'"
            )
        if group_id in group_ids:
            raise SpecError(f"duplicate group id: {group_id}")
        group_ids.add(group_id)
        gcolor = _text(obj.get("color"), f"groups[{index}].color", 7, default="#60a5fa")
        if not _COLOR.fullmatch(gcolor):
            raise SpecError(f"groups[{index}].color must be a six-digit hex color")
        groups.append(
            Group(
                group_id,
                _text(
                    obj.get("label"),
                    f"groups[{index}].label",
                    MAX_LABEL,
                    default=group_id,
                ),
                _integer(
                    obj.get("repeat", 1), f"groups[{index}].repeat", 1, MAX_REPEAT
                ),
                gcolor,
            )
        )

    raw_layers = root.get("layers")
    if not isinstance(raw_layers, list) or not raw_layers:
        raise SpecError("layers must be a non-empty array")
    if len(raw_layers) > max_layers:
        raise SpecError(
            f"layers has {len(raw_layers)} items; the limit is {max_layers}"
        )

    layers: list[Layer] = []
    ids: set[str] = set()
    for index, item in enumerate(raw_layers):
        obj = _object(item, f"layers[{index}]")
        layer_id = _text(obj.get("id"), f"layers[{index}].id", 48)
        if not _ID.fullmatch(layer_id):
            raise SpecError(
                f"layers[{index}].id must use 1-48 letters, numbers, '.', '_' or '-'"
            )
        if layer_id in ids:
            raise SpecError(f"duplicate layer id: {layer_id}")
        ids.add(layer_id)

        label = _text(
            obj.get("label"), f"layers[{index}].label", MAX_LABEL, default=layer_id
        )
        kind = _text(obj.get("kind"), f"layers[{index}].kind", 20, default="generic")
        if kind not in LAYER_KINDS:
            raise SpecError(
                f"layers[{index}].kind must be one of: {', '.join(LAYER_KINDS)}"
            )

        raw_shape = obj.get("shape", [])
        if not isinstance(raw_shape, list) or len(raw_shape) > 4:
            raise SpecError(
                f"layers[{index}].shape must be an array of up to 4 integers"
            )
        shape = tuple(
            _integer(value, f"layers[{index}].shape[{part}]", 1, 10_000_000)
            for part, value in enumerate(raw_shape)
        )
        repeat = _integer(
            obj.get("repeat", 1), f"layers[{index}].repeat", 1, MAX_REPEAT
        )
        color = _text(
            obj.get("color"),
            f"layers[{index}].color",
            7,
            default=KIND_COLORS[kind],
        )
        if not _COLOR.fullmatch(color):
            raise SpecError(f"layers[{index}].color must be a six-digit hex color")
        note = _text(obj.get("note"), f"layers[{index}].note", MAX_NOTE)
        group = obj.get("group")
        if group is not None and group not in group_ids:
            raise SpecError(
                f"layers[{index}].group references unknown group {group!r}; "
                "declare it in the top-level groups array"
            )
        layers.append(Layer(layer_id, label, kind, shape, repeat, color, note, group))

    raw_connections = root.get("connections")
    if raw_connections is None:
        raw_connections = [
            {"from": first.id, "to": second.id}
            for first, second in itertools.pairwise(layers)
        ]
    if not isinstance(raw_connections, list):
        raise SpecError("connections must be an array")
    if len(raw_connections) > MAX_CONNECTIONS:
        raise SpecError(
            f"connections has {len(raw_connections)} items; the limit is {MAX_CONNECTIONS}"
        )

    connections: list[Connection] = []
    for index, item in enumerate(raw_connections):
        obj = _object(item, f"connections[{index}]")
        source_id = _text(obj.get("from"), f"connections[{index}].from", 48)
        target_id = _text(obj.get("to"), f"connections[{index}].to", 48)
        if source_id not in ids:
            raise SpecError(
                f"connections[{index}].from references unknown layer {source_id!r}"
            )
        if target_id not in ids:
            raise SpecError(
                f"connections[{index}].to references unknown layer {target_id!r}"
            )
        if source_id == target_id:
            raise SpecError(f"connections[{index}] cannot connect a layer to itself")
        label = _text(obj.get("label"), f"connections[{index}].label", MAX_LABEL)
        style = _text(
            obj.get("style"), f"connections[{index}].style", 6, default="solid"
        )
        if style not in {"solid", "dashed"}:
            raise SpecError(f"connections[{index}].style must be 'solid' or 'dashed'")
        connections.append(Connection(source_id, target_id, label, style))

    return LLMSpec(
        title,
        subtitle,
        theme,
        tuple(layers),
        tuple(connections),
        layout,
        direction,
        tuple(groups),
    )
