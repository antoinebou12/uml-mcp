"""Common graph interchange model for UML-MCP plugins.

All new diagram plugins produce an :class:`InterchangeGraph` as their canonical
representation.  The viewer uses it to power interaction modes (explore, drilldown,
trace, story, compare, inspect, arrange, overlays) independently of the original
notation.  Plugin-specific source types keep their own JSON syntax; adapters
translate into this model when semantic interactions are needed.

Security constraints
--------------------
* ``source_ref`` paths are validated against the actual file tree at the declared
  ``commit_sha`` before being stored.  Hallucinated paths are rejected.
* Hard caps prevent resource exhaustion.  All caps are enforced before layout.
* ``view_state`` (camera and node positions) is always kept separate from the
  canonical model; moving a node in the viewer never mutates the source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ------------------------------------------------------------------ hard caps
MAX_NODES = 2_000
MAX_EDGES = 8_000
MAX_GROUPS = 200
MAX_LABEL = 200
MAX_METADATA_KEYS = 50
MAX_FLOW_STEPS = 1_000
MAX_SOURCE_REFS = 20

_ID_RE = re.compile(r"^[A-Za-z0-9_.:\-]{1,128}$")
_PATH_TRAVERSAL_RE = re.compile(r"\.\.|^/|^[A-Za-z]:\\")
_SAFE_PROTOCOLS = {"https", "http", ""}


class InterchangeError(ValueError):
    """Raised when an interchange graph fails validation."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


# --------------------------------------------------------------- source refs
@dataclass
class SourceRef:
    """A pointer to the file and line that produced a node or edge.

    ``confidence`` is ``"high"`` (direct import/annotation) or ``"low"`` (inferred
    heuristically).  ``commit_sha`` pins the revision so links never go stale.
    """

    path: str
    line: int | None = None
    commit_sha: str | None = None
    confidence: str = "high"  # "high" | "low"


# -------------------------------------------------------------- view state
@dataclass
class NodeViewState:
    """Ephemeral position of a node in the canvas.  Never part of the canonical model."""

    x: float = 0.0
    y: float = 0.0
    pinned: bool = False


@dataclass
class GraphViewState:
    """Ephemeral camera state.  Exportable but never merged back into the source."""

    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0


# --------------------------------------------------------------- graph model
@dataclass
class GraphNode:
    """A node in the interchange graph."""

    id: str
    label: str
    kind: str | None = None  # e.g. "aggregate", "service", "lambda", "bounded_context"
    group: str | None = None  # parent GraphGroup.id
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_refs: list[SourceRef] = field(default_factory=list)
    view_state: NodeViewState = field(default_factory=NodeViewState)


@dataclass
class GraphEdge:
    """A directed edge between two nodes."""

    id: str
    source: str  # GraphNode.id (or "node_id:port")
    target: str
    label: str | None = None
    kind: str | None = None  # e.g. "depends_on", "calls", "publishes", "upstream"
    flow_step: int | None = None  # Story-mode sequence index
    metadata: dict[str, Any] = field(default_factory=dict)
    source_refs: list[SourceRef] = field(default_factory=list)


@dataclass
class GraphGroup:
    """A named container for nodes (bounded context, layer, cloud region…)."""

    id: str
    label: str
    kind: str = "boundary"  # e.g. "bounded_context", "layer", "cloud_region", "vpc"
    parent: str | None = None  # parent GraphGroup.id for nesting
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class InterchangeGraph:
    """The canonical graph representation used by the viewer and interaction modes.

    ``source_type`` identifies the originating diagram type (e.g. ``"hexagonal_architecture"``).
    ``provenance`` describes how the graph was built:
    ``"discovered"`` (deterministic evidence extraction), ``"inferred"`` (heuristic),
    ``"model-assisted"`` (LLM summarisation; must retain source_refs for every claim).
    """

    title: str | None
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    groups: list[GraphGroup]
    flows: list[list[str]]  # ordered edge ID sequences for Story mode
    view_state: GraphViewState
    source_type: str
    provenance: str = "discovered"  # "discovered" | "inferred" | "model-assisted"

    def validate(self) -> None:
        """Raise :class:`InterchangeError` if the graph violates any constraint."""
        problems: list[str] = []
        _check_caps(self, problems)
        _check_ids(self, problems)
        _check_refs(self.nodes, self.edges, problems)
        _check_source_refs(self.nodes, self.edges, problems)
        _check_group_cycles(self.groups, problems)
        if problems:
            raise InterchangeError(problems)


# ------------------------------------------------------------ validation helpers
def _check_caps(g: InterchangeGraph, problems: list[str]) -> None:
    if len(g.nodes) > MAX_NODES:
        problems.append(f"nodes: at most {MAX_NODES} (got {len(g.nodes)})")
    if len(g.edges) > MAX_EDGES:
        problems.append(f"edges: at most {MAX_EDGES} (got {len(g.edges)})")
    if len(g.groups) > MAX_GROUPS:
        problems.append(f"groups: at most {MAX_GROUPS} (got {len(g.groups)})")
    if sum(len(f) for f in g.flows) > MAX_FLOW_STEPS:
        problems.append(f"flows: at most {MAX_FLOW_STEPS} total steps")


def _check_ids(g: InterchangeGraph, problems: list[str]) -> None:
    node_ids: set[str] = set()
    for i, n in enumerate(g.nodes):
        if not _ID_RE.match(n.id):
            problems.append(f"nodes[{i}].id {n.id!r}: invalid characters or length")
        if n.id in node_ids:
            problems.append(f"nodes[{i}].id {n.id!r}: duplicate")
        node_ids.add(n.id)
    edge_ids: set[str] = set()
    for i, e in enumerate(g.edges):
        if not _ID_RE.match(e.id):
            problems.append(f"edges[{i}].id {e.id!r}: invalid characters or length")
        if e.id in edge_ids:
            problems.append(f"edges[{i}].id {e.id!r}: duplicate")
        edge_ids.add(e.id)
    group_ids: set[str] = set()
    for i, grp in enumerate(g.groups):
        if not _ID_RE.match(grp.id):
            problems.append(f"groups[{i}].id {grp.id!r}: invalid characters or length")
        if grp.id in group_ids:
            problems.append(f"groups[{i}].id {grp.id!r}: duplicate")
        group_ids.add(grp.id)


def _check_refs(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    problems: list[str],
) -> None:
    node_ids = {n.id for n in nodes}
    for i, e in enumerate(edges):
        src = e.source.split(":")[0]
        tgt = e.target.split(":")[0]
        if src not in node_ids:
            problems.append(f"edges[{i}].source {e.source!r}: no such node")
        if tgt not in node_ids:
            problems.append(f"edges[{i}].target {e.target!r}: no such node")
        if src == tgt:
            problems.append(f"edges[{i}]: self-loop on node {src!r}")


def _check_source_refs(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    problems: list[str],
) -> None:
    """Reject path traversal; do NOT check file existence here (caller does that)."""
    all_refs: list[tuple[str, SourceRef]] = [
        (f"nodes[{i}].source_refs[{j}]", ref)
        for i, n in enumerate(nodes)
        for j, ref in enumerate(n.source_refs)
    ] + [
        (f"edges[{i}].source_refs[{j}]", ref)
        for i, e in enumerate(edges)
        for j, ref in enumerate(e.source_refs)
    ]
    for loc, ref in all_refs:
        if _PATH_TRAVERSAL_RE.search(ref.path):
            problems.append(f"{loc}.path {ref.path!r}: path traversal not allowed")
        if ref.confidence not in ("high", "low"):
            problems.append(
                f"{loc}.confidence {ref.confidence!r}: must be 'high' or 'low'"
            )
        if len(ref.path) > 512:
            problems.append(f"{loc}.path: exceeds 512 characters")


def _check_group_cycles(groups: list[GraphGroup], problems: list[str]) -> None:
    parent_of = {g.id: g.parent for g in groups if g.parent is not None}
    for start in parent_of:
        seen: set[str] = set()
        current: str | None = start
        while current in parent_of:
            if current in seen:
                problems.append(f"groups: {start!r} is its own ancestor (cycle)")
                break
            seen.add(current)
            current = parent_of[current]


# --------------------------------------------------------------- public helpers
def validate_source_ref_paths(
    graph: InterchangeGraph,
    existing_paths: set[str],
) -> list[str]:
    """Return a list of problems for source_ref paths not in *existing_paths*.

    Called by the repo-map plugin after building the file tree to reject
    hallucinated paths.  Uses the graph's own ``commit_sha`` from each ref.
    """
    problems: list[str] = []
    all_refs: list[tuple[str, SourceRef]] = [
        (f"nodes[{i}].source_refs[{j}]", ref)
        for i, n in enumerate(graph.nodes)
        for j, ref in enumerate(n.source_refs)
    ] + [
        (f"edges[{i}].source_refs[{j}]", ref)
        for i, e in enumerate(graph.edges)
        for j, ref in enumerate(e.source_refs)
    ]
    for loc, ref in all_refs:
        if ref.path and ref.path not in existing_paths:
            problems.append(f"{loc}.path {ref.path!r}: does not exist at pinned revision")
    return problems


__all__ = [
    "MAX_NODES",
    "MAX_EDGES",
    "MAX_GROUPS",
    "InterchangeError",
    "SourceRef",
    "NodeViewState",
    "GraphViewState",
    "GraphNode",
    "GraphEdge",
    "GraphGroup",
    "InterchangeGraph",
    "validate_source_ref_paths",
]
