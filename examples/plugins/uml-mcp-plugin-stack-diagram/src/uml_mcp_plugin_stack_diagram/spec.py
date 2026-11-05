"""Parse and validate the JSON source shared by the auto-layout architecture diagrams."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .images import validate_icon

MAX_NODES = 100
MAX_GROUPS = 40
MAX_EDGES = 240
MAX_TEXT = 60

DIRECTIONS = ("LR", "RL", "TB", "BT")
THEMES = ("dark", "light", "auto")  # auto: dark when static, system preference in HTML
TONES = ("blue", "orange", "green", "purple", "red", "teal", "yellow", "gray")
EDGE_TONES = (*TONES, "accent", "neutral")

_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,48}$")
_ICON = re.compile(r"^[a-z0-9_-]{1,32}$")


class SpecError(ValueError):
    """A source error that says how to fix the diagram."""


@dataclass(frozen=True)
class Node:
    id: str
    name: str
    role: str
    icon: str
    group: str | None
    tone: str | None
    tag: str = ""  # a short third line, e.g. an owning team


@dataclass(frozen=True)
class Group:
    id: str
    name: str
    parent: str | None
    style: str
    tone: str | None
    icon: str


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    label: str
    dashed: bool
    tone: str


@dataclass(frozen=True)
class Spec:
    title: str
    direction: str
    theme: str
    nodes: tuple[Node, ...]
    groups: tuple[Group, ...]
    edges: tuple[Edge, ...]
    subtitle: str = ""
    preset: str = ""


def _text(value: Any, field: str, *, default: str = "", maximum: int = MAX_TEXT) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise SpecError(f"{field} must be a string")
    value = value.strip()
    if len(value) > maximum:
        raise SpecError(f"{field} must be at most {maximum} characters")
    return value


def _ident(value: Any, field: str) -> str:
    text = _text(value, field, maximum=48)
    if not _ID.fullmatch(text):
        raise SpecError(f"{field} must use 1-48 letters, numbers, '.', '_', ':' or '-'")
    return text


def _icon(value: Any, field: str) -> str:
    text = _text(value, field, maximum=1_400_000)
    if not text or _ICON.fullmatch(text):
        return text
    try:
        validate_icon(text)
    except ValueError as exc:
        raise SpecError(
            f"{field} must be a glyph name or a base64 image data URI: {exc}"
        ) from exc
    return text


def _tone(value: Any, field: str, allowed: tuple[str, ...]) -> str | None:
    if value is None:
        return None
    if value not in allowed:
        raise SpecError(f"{field} must be one of: {', '.join(allowed)}")
    return value


def _strip_fence(source: str) -> str:
    source = source.strip()
    match = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```", source, re.DOTALL)
    return match.group(1).strip() if match else source


def _list(root: dict[str, Any], key: str, limit: int) -> list[dict[str, Any]]:
    items = root.get(key, [])
    if not isinstance(items, list):
        raise SpecError(f"{key} must be an array")
    if len(items) > limit:
        raise SpecError(f"{key} has {len(items)} items; the limit is {limit}")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise SpecError(f"{key}[{index}] must be an object")
    return items


def parse(
    source: str,
    *,
    group_styles: tuple[str, ...],
    default_direction: str = "LR",
    max_nodes: int = MAX_NODES,
    presets: tuple[str, ...] = (),
) -> Spec:
    """Parse one source document; ``group_styles`` and ``presets`` come from the skin."""
    try:
        root = json.loads(_strip_fence(source))
    except json.JSONDecodeError as exc:
        raise SpecError(
            f"source must be JSON: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(root, dict):
        raise SpecError("source must be an object")

    title = _text(root.get("title"), "title", default="Architecture")
    direction = _text(
        root.get("direction"), "direction", default=default_direction, maximum=2
    )
    if direction not in DIRECTIONS:
        raise SpecError("direction must be LR (left to right), RL, TB (top down) or BT")
    subtitle = _text(root.get("subtitle"), "subtitle", maximum=160)
    preset = ""
    if presets:
        preset = _text(root.get("preset"), "preset", default=presets[0], maximum=12)
        if preset not in presets:
            raise SpecError(f"preset must be one of: {', '.join(presets)}")
    theme = _text(root.get("theme"), "theme", default="auto", maximum=5)
    if theme not in THEMES:
        raise SpecError("theme must be 'dark', 'light' or 'auto'")

    raw_groups = _list(root, "groups", MAX_GROUPS)
    groups: list[Group] = []
    group_ids: set[str] = set()
    for i, item in enumerate(raw_groups):
        gid = _ident(item.get("id"), f"groups[{i}].id")
        if gid in group_ids:
            raise SpecError(f"duplicate group id: {gid}")
        group_ids.add(gid)
        style = _text(item.get("style"), f"groups[{i}].style", default=group_styles[0])
        if style not in group_styles:
            raise SpecError(
                f"groups[{i}].style must be one of: {', '.join(group_styles)}"
            )
        parent = item.get("parent")
        groups.append(
            Group(
                gid,
                _text(item.get("name"), f"groups[{i}].name", default=gid),
                None if parent is None else _ident(parent, f"groups[{i}].parent"),
                style,
                _tone(item.get("tone"), f"groups[{i}].tone", TONES),
                _icon(item.get("icon"), f"groups[{i}].icon"),
            )
        )
    for group in groups:
        if group.parent is not None and group.parent not in group_ids:
            raise SpecError(f"group {group.id!r} has unknown parent {group.parent!r}")
    by_id = {g.id: g for g in groups}
    for group in groups:
        seen: set[str] = set()
        cursor: Group | None = group
        while cursor is not None:
            if cursor.id in seen:
                raise SpecError(f"group {group.id!r} is nested inside itself")
            seen.add(cursor.id)
            cursor = by_id.get(cursor.parent) if cursor.parent else None

    raw_nodes = _list(root, "nodes", max_nodes)
    if not raw_nodes:
        raise SpecError("nodes must be a non-empty array")
    nodes: list[Node] = []
    node_ids: set[str] = set()
    for i, item in enumerate(raw_nodes):
        nid = _ident(item.get("id"), f"nodes[{i}].id")
        if nid in node_ids:
            raise SpecError(f"duplicate node id: {nid}")
        node_ids.add(nid)
        group = item.get("group")
        if group is not None:
            group = _ident(group, f"nodes[{i}].group")
            if group not in group_ids:
                raise SpecError(f"nodes[{i}].group references unknown group {group!r}")
        nodes.append(
            Node(
                nid,
                _text(item.get("name"), f"nodes[{i}].name", default=nid),
                _text(item.get("role"), f"nodes[{i}].role", maximum=40),
                _icon(item.get("icon"), f"nodes[{i}].icon"),
                group,
                _tone(item.get("tone"), f"nodes[{i}].tone", TONES),
                _text(item.get("tag"), f"nodes[{i}].tag", maximum=24),
            )
        )

    edges: list[Edge] = []
    for i, item in enumerate(_list(root, "edges", MAX_EDGES)):
        source_id = item.get("from", item.get("source"))
        target_id = item.get("to", item.get("target"))
        source_id = _ident(source_id, f"edges[{i}].from")
        target_id = _ident(target_id, f"edges[{i}].to")
        for end, value in (("from", source_id), ("to", target_id)):
            if value not in node_ids:
                raise SpecError(f"edges[{i}].{end} references unknown node {value!r}")
        if source_id == target_id:
            raise SpecError(f"edges[{i}] cannot connect a node to itself")
        style = _text(
            item.get("style"), f"edges[{i}].style", default="solid", maximum=6
        )
        if style not in {"solid", "dashed"}:
            raise SpecError(f"edges[{i}].style must be 'solid' or 'dashed'")
        tone = _tone(item.get("tone"), f"edges[{i}].tone", EDGE_TONES)
        edges.append(
            Edge(
                source_id,
                target_id,
                _text(item.get("label"), f"edges[{i}].label", maximum=32),
                style == "dashed",
                tone or ("neutral" if style == "dashed" else "accent"),
            )
        )
    return Spec(
        title,
        direction,
        theme,
        tuple(nodes),
        tuple(groups),
        tuple(edges),
        subtitle,
        preset,
    )
