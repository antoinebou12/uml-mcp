"""Dependency graph model shared by the parsers, the layout and both renderers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Dependency kinds, strongest first: a package reached both as a runtime and a dev
#: dependency is a runtime dependency.
KINDS = ("runtime", "peer", "optional", "dev")
KIND_RANK = {kind: rank for rank, kind in enumerate(KINDS)}

#: Package registries a documentation link can point to.
REGISTRY_URLS = {
    "pypi": "https://pypi.org/project/{name}/",
    "npm": "https://www.npmjs.com/package/{name}",
}

_PYPI_NORMALIZE = re.compile(r"[-_.]+")
_NPM_NAME = re.compile(
    r"^(@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*$", re.IGNORECASE
)
_PYPI_NAME = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")


class SpecError(ValueError):
    """The source could not be read; ``problems`` holds one readable message each."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def stronger(a: str, b: str) -> str:
    """The stronger of two kinds (``runtime`` beats ``dev``)."""
    if not a:
        return b
    if not b:
        return a
    return a if KIND_RANK.get(a, 9) <= KIND_RANK.get(b, 9) else b


def pypi_name(name: str) -> str:
    """PEP 503 normalised name: ``Typing_Extensions`` -> ``typing-extensions``."""
    return _PYPI_NORMALIZE.sub("-", name).lower()


def docs_url(ecosystem: str, name: str) -> str:
    """The registry page of a package, or an empty string when it has none."""
    if ecosystem == "pypi" and _PYPI_NAME.match(name):
        return REGISTRY_URLS["pypi"].format(name=pypi_name(name))
    if ecosystem == "npm" and _NPM_NAME.match(name):
        return REGISTRY_URLS["npm"].format(name=name)
    return ""


@dataclass
class Package:
    id: str
    name: str
    version: str = ""
    license: str = ""
    kind: str = ""
    group: str = ""
    ecosystem: str = ""
    extras: str = ""
    marker: str = ""
    docs: str = ""
    root: bool = False


@dataclass
class Edge:
    source: str
    target: str
    range: str = ""
    kind: str = "runtime"
    group: str = ""


@dataclass
class Graph:
    """A parsed dependency graph: ``root`` names the project in ``packages``."""

    source_kind: str
    root: str
    packages: dict[str, Package] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    title: str = ""
    theme: str = "auto"
    notes: list[str] = field(default_factory=list)
    has_lock: bool = False
    _index: dict[tuple[str, str], Edge] = field(default_factory=dict, repr=False)

    def add(self, package: Package) -> Package:
        """Add a package, or merge into the one already there; returns the stored one."""
        have = self.packages.get(package.id)
        if have is None:
            self.packages[package.id] = package
            return package
        for attr in ("version", "license", "ecosystem", "extras", "marker", "docs"):
            if not getattr(have, attr) and getattr(package, attr):
                setattr(have, attr, getattr(package, attr))
        have.kind = stronger(have.kind, package.kind)
        if package.group and package.group not in have.group.split(", "):
            have.group = ", ".join(g for g in (have.group, package.group) if g)
        return have

    def link(self, edge: Edge) -> None:
        """Add an edge; a second edge between the same packages keeps the stronger kind."""
        if edge.source == edge.target:
            return
        have = self._index.get((edge.source, edge.target))
        if have is not None:
            have.kind = stronger(have.kind, edge.kind)
            have.range = have.range or edge.range
            if edge.group and edge.group not in have.group.split(", "):
                have.group = ", ".join(g for g in (have.group, edge.group) if g)
            return
        self._index[(edge.source, edge.target)] = edge
        self.edges.append(edge)

    def finish(self) -> Graph:
        """Derive the kinds the source left out and the documentation links."""
        out: dict[str, list[Edge]] = {}
        for edge in self.edges:
            out.setdefault(edge.source, []).append(edge)
        # a package takes the strongest kind of the direct dependency it is reached through
        derived: dict[str, str] = {}
        for edge in out.get(self.root, []):
            todo = [edge.target]
            seen: set[str] = set()
            while todo:
                current = todo.pop()
                if current in seen:
                    continue
                seen.add(current)
                derived[current] = stronger(derived.get(current, ""), edge.kind)
                todo.extend(e.target for e in out.get(current, []))
        for pid, package in self.packages.items():
            if package.root:
                package.kind = ""
            elif not package.kind:
                package.kind = derived.get(pid, "runtime")
            if not package.docs and not package.root:
                package.docs = docs_url(package.ecosystem, package.name)
        return self
