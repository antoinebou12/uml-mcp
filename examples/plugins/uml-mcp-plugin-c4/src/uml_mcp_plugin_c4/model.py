"""The C4 model: one JSON source covering the context, container and component levels.

``parse`` turns the source into a :class:`Model` or raises :class:`SpecError` with every
problem it found, each naming the field (``systems[0].containers[2].kind``) and, for a bad
reference, the ids that do exist.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

MAX_ELEMENTS = 300
MAX_RELATIONS = 600
LEVELS = ("context", "container", "component")
THEMES = ("light", "dark", "auto")
DIRECTIONS = ("auto", "TB", "LR")
CONTAINER_KINDS = ("app", "web", "db", "queue", "storage", "function")
_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,63}$")
_FENCE = re.compile(r"^\s*```[A-Za-z0-9_-]*\s*\n(.*)\n\s*```\s*$", re.DOTALL)


class SpecError(ValueError):
    """Every problem found in a source, in order."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Element:
    """A person, software system, container or component."""

    id: str
    name: str
    level: str  # person | system | container | component
    description: str = ""
    technology: str = ""
    external: bool = False
    kind: str = ""  # containers only: app, web, db, queue, storage, function
    service: str = ""
    docs: str = ""
    parent: str | None = None
    children: tuple[str, ...] = ()


@dataclass(frozen=True)
class Relation:
    source: str
    target: str
    label: str = ""
    technology: str = ""
    is_async: bool = False


@dataclass
class Model:
    title: str
    theme: str
    elements: dict[str, Element]
    relations: list[Relation]
    level: str = "context"
    focus: str | None = None
    direction: str = "auto"
    description: str = ""
    order: list[str] = field(default_factory=list)

    def ancestors(self, element_id: str) -> list[str]:
        """``element_id`` and its parents, innermost first."""
        chain: list[str] = []
        cursor: str | None = element_id
        while cursor is not None:
            chain.append(cursor)
            cursor = self.elements[cursor].parent
        return chain


class _Problems:
    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, message: str) -> None:
        if len(self.items) < 40:
            self.items.append(message)


def _text(raw: dict[str, Any], key: str, where: str, p: _Problems, limit=400) -> str:
    value = raw.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        p.add(f"{where}.{key} must be a string")
        return ""
    value = value.strip()
    if len(value) > limit:
        p.add(f"{where}.{key} is longer than {limit} characters")
    return value[:limit]


def _flag(raw: dict[str, Any], key: str, where: str, p: _Problems) -> bool:
    value = raw.get(key, False)
    if not isinstance(value, bool):
        p.add(f"{where}.{key} must be true or false")
        return False
    return value


def _items(raw: dict[str, Any], key: str, where: str, p: _Problems) -> list[Any]:
    value = raw.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        p.add(f"{where}{key} must be a list")
        return []
    return value


def _load(code: str) -> Any:
    text = code.strip()
    fenced = _FENCE.match(text)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except ValueError as exc:
        raise SpecError([f"source must be JSON: {exc}"]) from None


def _known(ids: list[str]) -> str:
    shown = ", ".join(ids[:20])
    return shown + (", ..." if len(ids) > 20 else "")


_TOP_KEYS = {
    "title",
    "description",
    "theme",
    "direction",
    "view",
    "people",
    "systems",
    "relations",
}
_UNKNOWN_KEYS = {
    "person": {"id", "name", "description", "external", "docs", "tags"},
    "system": {
        "id",
        "name",
        "description",
        "external",
        "containers",
        "docs",
        "tags",
    },
    "container": {
        "id",
        "name",
        "technology",
        "description",
        "kind",
        "service",
        "components",
        "docs",
        "tags",
    },
    "component": {"id", "name", "technology", "description", "service", "docs", "tags"},
}


def parse(code: str, *, max_elements: int = MAX_ELEMENTS) -> Model:
    """Parse and check a C4 source; raise :class:`SpecError` listing every problem."""
    data = _load(code)
    if not isinstance(data, dict):
        raise SpecError(
            ["source must be a JSON object with people, systems and relations"]
        )
    p = _Problems()
    unknown = sorted(set(data) - _TOP_KEYS)
    if unknown:
        p.add(
            f"unknown top-level field(s) {', '.join(unknown)}; "
            f"use {', '.join(sorted(_TOP_KEYS))}"
        )
    elements: dict[str, Element] = {}
    order: list[str] = []

    def element(raw: Any, level: str, where: str, parent: str | None) -> dict | None:
        if not isinstance(raw, dict):
            p.add(f"{where} must be an object")
            return None
        unknown = sorted(set(raw) - _UNKNOWN_KEYS[level])
        if unknown:
            p.add(
                f"{where} has unknown field(s) {', '.join(unknown)}; "
                f"use {', '.join(sorted(_UNKNOWN_KEYS[level]))}"
            )
        ident = raw.get("id")
        if not isinstance(ident, str) or not _ID.match(ident):
            p.add(
                f"{where}.id must be a short identifier (letters, digits, _ . -), got {ident!r}"
            )
            return None
        if ident in elements:
            p.add(
                f"{where}.id {ident!r} is already used by a {elements[ident].level}; "
                "ids must be unique across people, systems, containers and components"
            )
            return None
        name = _text(raw, "name", where, p, 80) or ident
        docs = _text(raw, "docs", where, p, 300)
        if docs and not re.match(r"^https://[^\s\"'<>]+$", docs):
            p.add(f"{where}.docs must be an https:// URL")
            docs = ""
        fields = {
            "id": ident,
            "name": name,
            "level": level,
            "description": _text(raw, "description", where, p),
            "docs": docs,
            "parent": parent,
        }
        return fields

    for i, raw in enumerate(_items(data, "people", "", p)):
        where = f"people[{i}]"
        fields = element(raw, "person", where, None)
        if fields:
            fields["external"] = _flag(raw, "external", where, p)
            elements[fields["id"]] = Element(**fields)
            order.append(fields["id"])

    for i, raw in enumerate(_items(data, "systems", "", p)):
        where = f"systems[{i}]"
        fields = element(raw, "system", where, None)
        if not fields:
            continue
        system_id = fields["id"]
        fields["external"] = _flag(raw, "external", where, p)
        elements[system_id] = Element(**fields)
        order.append(system_id)
        containers: list[str] = []
        for j, craw in enumerate(_items(raw, "containers", f"{where}.", p)):
            cwhere = f"{where}.containers[{j}]"
            cfields = element(craw, "container", cwhere, system_id)
            if not cfields:
                continue
            container_id = cfields["id"]
            kind = craw.get("kind", "app")
            if kind not in CONTAINER_KINDS:
                p.add(
                    f"{cwhere}.kind must be one of {', '.join(CONTAINER_KINDS)}, got {kind!r}"
                )
                kind = "app"
            cfields.update(
                technology=_text(craw, "technology", cwhere, p, 120),
                kind=kind,
                service=_text(craw, "service", cwhere, p, 60),
                external=elements[system_id].external,
            )
            elements[container_id] = Element(**cfields)
            order.append(container_id)
            containers.append(container_id)
            components: list[str] = []
            for k, kraw in enumerate(_items(craw, "components", f"{cwhere}.", p)):
                kwhere = f"{cwhere}.components[{k}]"
                kfields = element(kraw, "component", kwhere, container_id)
                if not kfields:
                    continue
                kfields.update(
                    technology=_text(kraw, "technology", kwhere, p, 120),
                    service=_text(kraw, "service", kwhere, p, 60),
                    external=elements[system_id].external,
                )
                elements[kfields["id"]] = Element(**kfields)
                order.append(kfields["id"])
                components.append(kfields["id"])
            elements[container_id] = _with_children(elements[container_id], components)
        elements[system_id] = _with_children(elements[system_id], containers)

    if not elements and not p.items:
        p.add("the model is empty: add at least one person or system")
    if len(elements) > max_elements:
        p.add(f"too many elements: {len(elements)} (the limit is {max_elements})")

    model = Model(
        title=_text(data, "title", "source", p, 120) or "C4 model",
        description=_text(data, "description", "source", p),
        theme="dark",
        elements=elements,
        relations=[],
        order=order,
    )
    theme = data.get("theme", "dark")
    if theme not in THEMES:
        p.add(f"theme must be one of {', '.join(THEMES)}, got {theme!r}")
    else:
        model.theme = theme

    direction = data.get("direction", "auto")
    if direction not in DIRECTIONS:
        p.add(f"direction must be one of {', '.join(DIRECTIONS)}, got {direction!r}")
    else:
        model.direction = direction

    raw_relations = _items(data, "relations", "", p)
    if len(raw_relations) > MAX_RELATIONS:
        p.add(
            f"too many relations: {len(raw_relations)} (the limit is {MAX_RELATIONS})"
        )
    ids = list(elements)
    for i, raw in enumerate(raw_relations[:MAX_RELATIONS]):
        where = f"relations[{i}]"
        if not isinstance(raw, dict):
            p.add(f"{where} must be an object with from and to")
            continue
        ends: list[str] = []
        for key in ("from", "to"):
            ref = raw.get(key)
            if not isinstance(ref, str) or not ref:
                p.add(f"{where}.{key} is required (an element id)")
            elif ref not in elements:
                p.add(
                    f"{where}.{key} {ref!r} is not a known element; known ids: {_known(ids)}"
                )
            else:
                ends.append(ref)
        if len(ends) != 2:
            continue
        source, target = ends
        if source == target:
            p.add(f"{where} connects {source!r} to itself")
            continue
        if source in model.ancestors(target) or target in model.ancestors(source):
            inner, outer = (
                (target, source)
                if source in model.ancestors(target)
                else (source, target)
            )
            p.add(
                f"{where} connects {inner!r} to {outer!r}, which contains it; "
                "relate elements to their siblings or to other elements instead"
            )
            continue
        model.relations.append(
            Relation(
                source,
                target,
                label=_text(raw, "label", where, p, 120),
                technology=_text(raw, "technology", where, p, 80),
                is_async=_flag(raw, "async", where, p),
            )
        )

    view = data.get("view")
    if view is not None:
        _check_view(view, model, p)
    if p.items:
        raise SpecError(p.items)
    return model


def _with_children(item: Element, children: list[str]) -> Element:
    return Element(**{**item.__dict__, "children": tuple(children)})


def _check_view(view: Any, model: Model, p: _Problems) -> None:
    if not isinstance(view, dict):
        p.add(
            'view must be an object such as {"level": "container", "focus": "<system id>"}'
        )
        return
    level = view.get("level", "context")
    if level not in LEVELS:
        p.add(f"view.level must be one of {', '.join(LEVELS)}, got {level!r}")
        return
    focus = view.get("focus")
    if focus is None:
        if level == "context":
            return
        wanted = "system" if level == "container" else "container"
        p.add(
            f"view.focus is required for the {level} level: give the id of a {wanted}"
        )
        return
    if focus not in model.elements:
        p.add(
            f"view.focus {focus!r} is not a known element; known ids: {_known(list(model.elements))}"
        )
        return
    item = model.elements[focus]
    if level == "context":
        if item.level not in ("person", "system"):
            p.add(
                f"view.focus {focus!r} is a {item.level}; the context level focuses a person "
                "or a system (use level container or component to open it)"
            )
            return
    elif level == "container":
        if item.level != "system":
            p.add(
                f"view.focus {focus!r} is a {item.level}; the container level needs a system id"
            )
            return
        if not item.children:
            p.add(
                f"view.focus {focus!r} has no containers to show; add systems[].containers"
            )
            return
    else:
        if item.level != "container":
            p.add(
                f"view.focus {focus!r} is a {item.level}; the component level needs a container id"
            )
            return
        if not item.children:
            p.add(
                f"view.focus {focus!r} has no components to show; add containers[].components"
            )
            return
    model.level, model.focus = level, focus
