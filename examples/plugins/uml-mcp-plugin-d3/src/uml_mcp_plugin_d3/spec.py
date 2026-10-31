"""The JSON source formats of the three D3 diagram types, and their validation.

Every problem in a source is collected (not just the first) so that a model can fix them
all in one round trip. Unknown fields are rejected: a typo such as ``lable`` would
otherwise be silently ignored.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .icons import KINDS, PROVIDERS, resolve_service

#: Hard caps, so a request cannot ask for an arbitrarily expensive layout or page.
MAX_NODES = 400
MAX_LINKS = 1500
MAX_GROUPS = 80
MAX_PORTS = 12
MAX_LABEL = 120
#: A node's own logo is a data URI of at most this many characters (about 18 KB of image),
#: and a diagram may carry this many of them.
MAX_LOGO = 24_000
MAX_LOGOS = 40

_ID = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
_LOGO = re.compile(
    r"^data:image/(png|jpeg|webp|svg\+xml);base64,([A-Za-z0-9+/]+={0,2})$"
)
#: What an SVG logo may not contain (it is shown as an image, where scripts do not run,
#: but a logo has no business carrying any).
_LOGO_FORBIDDEN = ("<script", "foreignobject", "javascript:", " onload", " onerror")
_GROUP_TYPES = (
    "boundary",
    "system",
    "env",
    "region",
    "zone",
    "vpc",
    "subnet",
    "cluster",
    "account",
)


class SpecError(ValueError):
    """The source is not a valid spec; ``problems`` lists every issue found."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ------------------------------------------------------------------ d3_force
class ForceNode(_Model):
    id: str
    label: str | None = Field(default=None, max_length=MAX_LABEL)
    group: str | None = Field(default=None, max_length=MAX_LABEL)
    size: float = Field(default=1.0, ge=0.5, le=4.0)
    note: str | None = Field(default=None, max_length=400)


class ForceLink(_Model):
    source: str
    target: str
    label: str | None = Field(default=None, max_length=MAX_LABEL)
    value: float = Field(default=1.0, ge=0.1, le=10.0)


class ForceSpec(_Model):
    title: str | None = Field(default=None, max_length=MAX_LABEL)
    theme: Literal["light", "dark", "auto"] = "light"
    directed: bool = False
    charge: float = Field(default=-220.0, ge=-2000.0, le=-5.0)
    distance: float = Field(default=70.0, ge=10.0, le=400.0)
    nodes: list[ForceNode]
    links: list[ForceLink] = []


# ------------------------------------------------------------ d3_architecture
class ArchGroup(_Model):
    id: str
    label: str | None = Field(default=None, max_length=MAX_LABEL)
    type: str = "boundary"
    parent: str | None = None


class ArchNode(_Model):
    id: str
    label: str | None = Field(default=None, max_length=MAX_LABEL)
    service: str | None = Field(default=None, max_length=64)
    kind: str | None = Field(default=None, max_length=32)
    category: (
        Literal[
            "frontend",
            "backend",
            "database",
            "cloud",
            "security",
            "messagebus",
            "external",
        ]
        | None
    ) = None
    logo: str | None = Field(default=None, max_length=MAX_LOGO)
    group: str | None = None
    inputs: list[str] = []
    outputs: list[str] = []
    note: str | None = Field(default=None, max_length=400)


class ArchLink(_Model):
    # ``from`` is a Python keyword, so the field is accepted under its JSON name.
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, populate_by_name=True
    )

    source: str = Field(alias="from")
    target: str = Field(alias="to")
    label: str | None = Field(default=None, max_length=MAX_LABEL)
    style: Literal["solid", "dashed", "primary"] = "solid"


class ArchSpec(_Model):
    title: str | None = Field(default=None, max_length=MAX_LABEL)
    theme: Literal["light", "dark", "auto"] = "light"
    provider: str = "generic"
    direction: Literal["LR", "TB"] | None = None
    group_by: Literal["none", "category"] = "none"
    groups: list[ArchGroup] = []
    nodes: list[ArchNode]
    links: list[ArchLink] = []


Spec = ForceSpec | ArchSpec

#: diagram type -> (model, default direction for the layered layout)
TYPES: dict[str, type[BaseModel]] = {
    "d3_force": ForceSpec,
    "d3_architecture": ArchSpec,
    "d3_topology": ArchSpec,
}
DEFAULT_DIRECTION = {"d3_architecture": "LR", "d3_topology": "TB"}


def _loc(parts: tuple[Any, ...]) -> str:
    out = ""
    for part in parts:
        out += (
            f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
        )
    return out or "source"


def _pydantic_problems(exc: ValidationError) -> list[str]:
    problems = []
    for err in exc.errors():
        kind = err.get("type", "")
        where = _loc(tuple(err.get("loc", ())))
        if kind == "extra_forbidden":
            problems.append(f"{where}: unknown field")
        elif kind == "missing":
            problems.append(f"{where}: required")
        else:
            problems.append(f"{where}: {err.get('msg', 'invalid')}")
    return problems


def _check_ids(items: list[Any], what: str, problems: list[str]) -> set[str]:
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not _ID.match(item.id):
            problems.append(
                f"{what}[{index}].id {item.id!r}: use 1-64 letters, digits, '_', '-' or '.'"
            )
        if item.id in seen:
            problems.append(f"{what}[{index}].id {item.id!r}: duplicate")
        seen.add(item.id)
    return seen


def _check_force(spec: ForceSpec, problems: list[str]) -> None:
    ids = _check_ids(spec.nodes, "nodes", problems)
    for index, link in enumerate(spec.links):
        for end in ("source", "target"):
            name = getattr(link, end)
            if name not in ids:
                problems.append(f"links[{index}].{end} {name!r}: no such node")
        if link.source == link.target:
            problems.append(f"links[{index}]: a node cannot link to itself")


def _split_endpoint(value: str) -> tuple[str, str | None]:
    node, _, port = value.partition(":")
    return node, (port or None)


def _check_logos(spec: ArchSpec, problems: list[str]) -> None:
    """A logo is a small image given as a data URI; nothing else is fetched or run."""
    logos = [(i, n) for i, n in enumerate(spec.nodes) if n.logo is not None]
    if len(logos) > MAX_LOGOS:
        problems.append(f"nodes: at most {MAX_LOGOS} may carry a logo")
    for index, node in logos:
        match = _LOGO.match(node.logo or "")
        if match is None:
            problems.append(
                f"nodes[{index}].logo: use a data URI such as "
                "'data:image/png;base64,...' (png, jpeg, webp or svg+xml)"
            )
            continue
        try:
            raw = base64.b64decode(match.group(2), validate=True)
        except (binascii.Error, ValueError):
            problems.append(f"nodes[{index}].logo: the base64 data is not valid")
            continue
        if match.group(1) == "svg+xml":
            lowered = raw.decode("utf-8", errors="replace").lower()
            if any(bad in lowered for bad in _LOGO_FORBIDDEN):
                problems.append(
                    f"nodes[{index}].logo: an SVG logo may not contain scripts"
                )


def _check_arch(spec: ArchSpec, problems: list[str]) -> None:
    if spec.provider not in PROVIDERS:
        problems.append(
            f"provider {spec.provider!r}: use one of {', '.join(sorted(PROVIDERS))}"
        )
    ids = _check_ids(spec.nodes, "nodes", problems)
    group_ids = _check_ids(spec.groups, "groups", problems)
    _check_logos(spec, problems)
    if len(spec.groups) > MAX_GROUPS:
        problems.append(f"groups: at most {MAX_GROUPS} are supported")

    parent_of = {}
    for index, group in enumerate(spec.groups):
        if group.parent is not None:
            parent_of[group.id] = group.parent
            if group.parent not in group_ids:
                problems.append(
                    f"groups[{index}].parent {group.parent!r}: no such group"
                )
        if group.type not in _GROUP_TYPES:
            problems.append(
                f"groups[{index}].type {group.type!r}: use one of {', '.join(_GROUP_TYPES)}"
            )
    for start in parent_of:
        seen, current = set(), start
        while current in parent_of:
            if current in seen:
                problems.append(f"groups: {start!r} is its own ancestor")
                break
            seen.add(current)
            current = parent_of[current]

    ports: dict[str, tuple[set[str], set[str]]] = {}
    for index, node in enumerate(spec.nodes):
        if node.group is not None and node.group not in group_ids:
            problems.append(f"nodes[{index}].group {node.group!r}: no such group")
        if node.kind is not None and node.kind not in KINDS:
            problems.append(
                f"nodes[{index}].kind {node.kind!r}: use one of {', '.join(sorted(KINDS))}"
            )
        for side, names in (("inputs", node.inputs), ("outputs", node.outputs)):
            if len(names) > MAX_PORTS:
                problems.append(f"nodes[{index}].{side}: at most {MAX_PORTS} ports")
            for name in names:
                if not _ID.match(name):
                    problems.append(
                        f"nodes[{index}].{side} {name!r}: use 1-64 letters, digits, '_', '-' or '.'"
                    )
        ports[node.id] = (set(node.inputs), set(node.outputs))

    for index, link in enumerate(spec.links):
        for end, side_index, side in (("from", 1, "outputs"), ("to", 0, "inputs")):
            raw = link.source if end == "from" else link.target
            node, port = _split_endpoint(raw)
            if node not in ids:
                problems.append(f"links[{index}].{end} {raw!r}: no such node")
            elif port is not None and port not in ports[node][side_index]:
                problems.append(
                    f"links[{index}].{end} {raw!r}: node {node!r} has no {side[:-1]} port {port!r}"
                )
        if _split_endpoint(link.source)[0] == _split_endpoint(link.target)[0]:
            problems.append(f"links[{index}]: a node cannot link to itself")

    for index, node in enumerate(spec.nodes):
        if node.service is not None and node.kind is None:
            # Unknown services are allowed (they get a generic icon); a bad provider
            # prefix is almost certainly a typo, so say so.
            prefix = node.service.partition(":")[0] if ":" in node.service else None
            if prefix is not None and prefix not in PROVIDERS:
                problems.append(
                    f"nodes[{index}].service {node.service!r}: unknown provider "
                    f"{prefix!r} (use one of {', '.join(sorted(PROVIDERS))})"
                )

    members: dict[str, int] = {}
    for node in spec.nodes:
        current = node.group
        while current is not None:
            members[current] = members.get(current, 0) + 1
            current = parent_of.get(current)
    for index, group in enumerate(spec.groups):
        if members.get(group.id, 0) == 0:
            problems.append(f"groups[{index}] {group.id!r}: contains no nodes")


_FENCE = re.compile(r"^\s*```[A-Za-z0-9_-]*\s*\n(.*?)\n\s*```\s*$", re.DOTALL)


def _unfence(code: str) -> str:
    """The JSON inside a markdown code fence (models often wrap it), else ``code``."""
    match = _FENCE.match(code)
    return match.group(1) if match else code


def parse(diagram_type: str, code: str, *, max_nodes: int = MAX_NODES) -> Spec:
    """Parse and validate a source; raise :class:`SpecError` listing every problem."""
    model = TYPES.get(diagram_type)
    if model is None:
        raise SpecError([f"unknown diagram type {diagram_type!r}"])
    try:
        data = json.loads(_unfence(code))
    except json.JSONDecodeError as exc:
        raise SpecError(
            [f"not valid JSON (line {exc.lineno}, column {exc.colno}): {exc.msg}"]
        ) from exc
    if not isinstance(data, dict):
        raise SpecError(["the source must be a JSON object with a 'nodes' list"])
    try:
        spec = model.model_validate(data)
    except ValidationError as exc:
        raise SpecError(_pydantic_problems(exc)) from exc

    problems: list[str] = []
    if len(spec.nodes) > max_nodes:  # type: ignore[attr-defined]
        problems.append(f"nodes: at most {max_nodes} are supported")
    if len(spec.links) > MAX_LINKS:  # type: ignore[attr-defined]
        problems.append(f"links: at most {MAX_LINKS} are supported")
    if not spec.nodes:  # type: ignore[attr-defined]
        problems.append("nodes: at least one node is required")
    if isinstance(spec, ForceSpec):
        _check_force(spec, problems)
    else:
        assert isinstance(spec, ArchSpec)
        _check_arch(spec, problems)
    if problems:
        raise SpecError(problems)
    return spec  # type: ignore[return-value]


def parse_force(code: str, *, max_nodes: int = MAX_NODES) -> ForceSpec:
    """:func:`parse` for ``d3_force`` sources, typed."""
    parsed = parse("d3_force", code, max_nodes=max_nodes)
    assert isinstance(parsed, ForceSpec)  # TYPES maps d3_force to ForceSpec
    return parsed


def parse_arch(diagram_type: str, code: str, *, max_nodes: int = MAX_NODES) -> ArchSpec:
    """:func:`parse` for ``d3_architecture`` and ``d3_topology`` sources, typed."""
    if diagram_type not in DEFAULT_DIRECTION:
        raise SpecError(
            [f"{diagram_type!r} is not an architecture or topology diagram"]
        )
    parsed = parse(diagram_type, code, max_nodes=max_nodes)
    assert isinstance(parsed, ArchSpec)  # TYPES maps both to ArchSpec
    return parsed


def node_label(node: Any) -> str:
    """What to print on a node: its label, else the service's display name, else its id."""
    if node.label:
        return str(node.label)
    service = getattr(node, "service", None)
    if service:
        return resolve_service(service, getattr(node, "kind", None), "generic").name
    return str(node.id)
