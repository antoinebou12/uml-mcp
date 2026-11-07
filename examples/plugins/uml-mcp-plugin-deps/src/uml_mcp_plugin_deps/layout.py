"""From a graph to a layered tree: who is shown, at which level, and where.

The root sits at the left, its direct dependencies in the next column and transitive
ones further right. A package reached along several paths appears once, under the
parent that reaches it first (breadth first, so at its shallowest level); the other
parents are listed as ``also required by``.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .model import KIND_RANK, Edge, Graph, Package

#: Hard ceiling for ``plugins.settings.deps.max_nodes``.
MAX_NODES = 2000
#: Default number of packages drawn; the rest are summarised in a notice.
DEFAULT_MAX_NODES = 300

ROW = 30
PILL_H = 22
COL_GAP = 46
CHAR_W = 6.6


@dataclass
class Tree:
    graph: Graph
    order: list[str]  # shown packages, breadth first from the root
    parent: dict[str, str | None]
    children: dict[str, list[str]]
    depth: dict[str, int]
    edges: list[Edge]  # every edge between shown packages
    total: int  # packages reachable from the root
    unreachable: int  # packages nothing in the tree depends on
    duplicates: dict[str, list[str]]  # name -> ids, for names with several versions
    pos: dict[str, tuple[float, float]] = field(default_factory=dict)
    widths: dict[str, float] = field(default_factory=dict)
    columns: list[float] = field(default_factory=list)

    @property
    def capped(self) -> bool:
        return len(self.order) < self.total


def label(package: Package, requested: str = "") -> str:
    """Pill text: ``name@version``, or ``name range`` when only a range is known."""
    if package.version:
        return f"{package.name}@{package.version}"
    return f"{package.name} {requested}".strip() if requested else package.name


def pill_width(text: str, licence: str) -> float:
    width = 22 + len(text) * CHAR_W
    if licence:
        width += 12 + min(len(licence), 12) * 5.6
    return round(min(width, 340), 1)


def build(graph: Graph, max_nodes: int = DEFAULT_MAX_NODES) -> Tree:
    out: dict[str, list[Edge]] = {}
    for edge in graph.edges:
        out.setdefault(edge.source, []).append(edge)
    for edges in out.values():
        edges.sort(
            key=lambda e: (
                KIND_RANK.get(e.kind, 9),
                graph.packages[e.target].name.lower(),
                graph.packages[e.target].version,
            )
        )
    parent: dict[str, str | None] = {graph.root: None}
    depth = {graph.root: 0}
    order = [graph.root]
    queue = deque([graph.root])
    while queue:
        current = queue.popleft()
        for edge in out.get(current, []):
            if edge.target in parent:
                continue
            parent[edge.target] = current
            depth[edge.target] = depth[current] + 1
            order.append(edge.target)
            queue.append(edge.target)
    total = len(order)
    shown = order[: max(1, max_nodes)]
    keep = set(shown)
    children: dict[str, list[str]] = {pid: [] for pid in shown}
    for pid in shown[1:]:
        owner = parent[pid]
        assert owner is not None
        children[owner].append(pid)
    names: dict[str, list[str]] = {}
    for pid in shown:
        if not graph.packages[pid].root:
            names.setdefault(graph.packages[pid].name.lower(), []).append(pid)
    tree = Tree(
        graph=graph,
        order=shown,
        parent={pid: parent[pid] for pid in shown},
        children=children,
        depth={pid: depth[pid] for pid in shown},
        edges=[e for e in graph.edges if e.source in keep and e.target in keep],
        total=total,
        unreachable=len(graph.packages) - total,
        duplicates={n: ids for n, ids in names.items() if len(ids) > 1},
    )
    _place(tree)
    return tree


def requested(tree: Tree, pid: str) -> str:
    """The range the tree parent asked for (empty when unknown)."""
    owner = tree.parent.get(pid)
    for edge in tree.edges:
        if edge.source == owner and edge.target == pid:
            return edge.range
    return ""


def _place(tree: Tree) -> None:
    """Columns by depth (as wide as their widest pill); rows from a tidy tree walk."""
    packages = tree.graph.packages
    ranges = {(e.source, e.target): e.range for e in tree.edges}
    widest: dict[int, float] = {}
    for pid in tree.order:
        owner = tree.parent[pid]
        text = label(packages[pid], ranges.get((owner, pid), "") if owner else "")
        width = pill_width(text, packages[pid].license)
        tree.widths[pid] = width
        level = tree.depth[pid]
        widest[level] = max(widest.get(level, 0.0), width)
    x = 0.0
    for level in range(max(widest) + 1):
        tree.columns.append(x)
        x += widest[level] + COL_GAP
    # an iterative post-order walk: leaves take the next row, parents centre on theirs
    row = 0
    ys: dict[str, float] = {}
    stack: list[tuple[str, bool]] = [(tree.graph.root, False)]
    while stack:
        pid, visited = stack.pop()
        kids = tree.children[pid]
        if kids and not visited:
            stack.append((pid, True))
            stack.extend((kid, False) for kid in reversed(kids))
            continue
        if kids:
            ys[pid] = (ys[kids[0]] + ys[kids[-1]]) / 2
        else:
            ys[pid] = row * ROW
            row += 1
        tree.pos[pid] = (tree.columns[tree.depth[pid]], ys[pid])
