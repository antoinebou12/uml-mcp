"""Tests for mcp_core.core.graph_model (A2 — common graph interchange model)."""

from __future__ import annotations

from typing import Any

import pytest

from mcp_core.core.graph_model import (
    GraphEdge,
    GraphGroup,
    GraphNode,
    GraphViewState,
    InterchangeError,
    InterchangeGraph,
    NodeViewState,
    SourceRef,
    validate_source_ref_paths,
)


# ---------------------------------------------------------------- helpers
def _minimal_graph(**kwargs) -> InterchangeGraph:
    defaults: dict[str, Any] = {
        "title": "test",
        "nodes": [GraphNode(id="n1", label="Node 1")],
        "edges": [],
        "groups": [],
        "flows": [],
        "view_state": GraphViewState(),
        "source_type": "test",
    }
    defaults.update(kwargs)
    return InterchangeGraph(**defaults)


# ---------------------------------------------------------------- happy path
def test_minimal_graph_validates():
    g = _minimal_graph()
    g.validate()  # must not raise


def test_graph_with_edge_validates():
    g = _minimal_graph(
        nodes=[GraphNode(id="a", label="A"), GraphNode(id="b", label="B")],
        edges=[GraphEdge(id="e1", source="a", target="b")],
    )
    g.validate()


def test_graph_with_groups_validates():
    g = _minimal_graph(
        nodes=[GraphNode(id="n1", label="N1", group="g1")],
        groups=[GraphGroup(id="g1", label="Group 1", kind="bounded_context")],
    )
    g.validate()


def test_nested_groups_validate():
    g = _minimal_graph(
        nodes=[GraphNode(id="n1", label="N1", group="child")],
        groups=[
            GraphGroup(id="parent", label="Parent"),
            GraphGroup(id="child", label="Child", parent="parent"),
        ],
    )
    g.validate()


def test_source_refs_valid():
    ref = SourceRef(path="mcp_core/core/server.py", line=42, confidence="high")
    g = _minimal_graph(nodes=[GraphNode(id="n1", label="N1", source_refs=[ref])])
    g.validate()


def test_flow_edge_ids():
    nodes = [GraphNode(id=f"n{i}", label=f"N{i}") for i in range(3)]
    edges = [
        GraphEdge(id="e1", source="n0", target="n1", flow_step=0),
        GraphEdge(id="e2", source="n1", target="n2", flow_step=1),
    ]
    g = _minimal_graph(nodes=nodes, edges=edges, flows=[["e1", "e2"]])
    g.validate()


# ---------------------------------------------------------------- hard caps
def test_cap_nodes():
    from mcp_core.core.graph_model import MAX_NODES

    nodes = [GraphNode(id=f"n{i}", label=f"N{i}") for i in range(MAX_NODES + 1)]
    g = _minimal_graph(nodes=nodes)
    with pytest.raises(InterchangeError, match="nodes: at most"):
        g.validate()


def test_cap_edges():
    from mcp_core.core.graph_model import MAX_EDGES

    nodes = [GraphNode(id="a", label="A"), GraphNode(id="b", label="B")]
    edges = [
        GraphEdge(id=f"e{i}", source="a", target="b") for i in range(MAX_EDGES + 1)
    ]
    with pytest.raises(InterchangeError, match="edges: at most"):
        # Duplicates will also trigger; test cap first
        _minimal_graph(nodes=nodes, edges=edges).validate()


# ---------------------------------------------------------------- id validation
def test_invalid_node_id():
    g = _minimal_graph(nodes=[GraphNode(id="bad id!", label="X")])
    with pytest.raises(InterchangeError, match="nodes\\[0\\].id.*invalid"):
        g.validate()


def test_duplicate_node_id():
    g = _minimal_graph(
        nodes=[GraphNode(id="dup", label="A"), GraphNode(id="dup", label="B")]
    )
    with pytest.raises(InterchangeError, match="duplicate"):
        g.validate()


def test_duplicate_edge_id():
    nodes = [GraphNode(id="a", label="A"), GraphNode(id="b", label="B")]
    edges = [
        GraphEdge(id="e1", source="a", target="b"),
        GraphEdge(id="e1", source="b", target="a"),
    ]
    g = _minimal_graph(nodes=nodes, edges=edges)
    with pytest.raises(InterchangeError, match="duplicate"):
        g.validate()


# ---------------------------------------------------------------- edge ref validation
def test_edge_missing_source_node():
    g = _minimal_graph(
        nodes=[GraphNode(id="b", label="B")],
        edges=[GraphEdge(id="e1", source="nonexistent", target="b")],
    )
    with pytest.raises(InterchangeError, match="no such node"):
        g.validate()


def test_edge_self_loop():
    g = _minimal_graph(
        nodes=[GraphNode(id="a", label="A")],
        edges=[GraphEdge(id="e1", source="a", target="a")],
    )
    with pytest.raises(InterchangeError, match="self-loop"):
        g.validate()


# ---------------------------------------------------------------- group cycle detection
def test_group_cycle_detected():
    g = _minimal_graph(
        nodes=[GraphNode(id="n1", label="N1", group="g1")],
        groups=[
            GraphGroup(id="g1", label="G1", parent="g2"),
            GraphGroup(id="g2", label="G2", parent="g1"),
        ],
    )
    with pytest.raises(InterchangeError, match="ancestor.*cycle"):
        g.validate()


# ---------------------------------------------------------------- source ref security
def test_source_ref_path_traversal_rejected():
    ref = SourceRef(path="../etc/passwd", confidence="high")
    g = _minimal_graph(nodes=[GraphNode(id="n1", label="N1", source_refs=[ref])])
    with pytest.raises(InterchangeError, match="path traversal"):
        g.validate()


def test_source_ref_absolute_path_rejected():
    ref = SourceRef(path="/etc/passwd", confidence="high")
    g = _minimal_graph(nodes=[GraphNode(id="n1", label="N1", source_refs=[ref])])
    with pytest.raises(InterchangeError, match="path traversal"):
        g.validate()


def test_source_ref_invalid_confidence():
    ref = SourceRef(path="some/file.py", confidence="hallucinated")
    g = _minimal_graph(nodes=[GraphNode(id="n1", label="N1", source_refs=[ref])])
    with pytest.raises(InterchangeError, match="confidence"):
        g.validate()


# ---------------------------------------------------------------- validate_source_ref_paths
def test_validate_source_ref_paths_ok():
    ref = SourceRef(path="mcp_core/core/server.py", confidence="high")
    g = _minimal_graph(nodes=[GraphNode(id="n1", label="N1", source_refs=[ref])])
    problems = validate_source_ref_paths(g, {"mcp_core/core/server.py"})
    assert problems == []


def test_validate_source_ref_paths_missing():
    ref = SourceRef(path="hallucinated/path.py", confidence="low")
    g = _minimal_graph(nodes=[GraphNode(id="n1", label="N1", source_refs=[ref])])
    problems = validate_source_ref_paths(g, {"mcp_core/core/server.py"})
    assert any("does not exist" in p for p in problems)


# ---------------------------------------------------------------- view state separation
def test_view_state_separate_from_model():
    """Moving a node in the view must not affect the graph structure."""
    node = GraphNode(
        id="n1", label="N1", view_state=NodeViewState(x=100.0, y=200.0, pinned=True)
    )
    g = _minimal_graph(nodes=[node])
    g.validate()
    # Modifying view_state is allowed; it does not touch canonical fields
    g.nodes[0].view_state.x = 999.0
    g.validate()  # still valid


# ---------------------------------------------------------------- provenance metadata
def test_provenance_defaults_to_discovered():
    g = _minimal_graph()
    assert g.provenance == "discovered"


def test_provenance_model_assisted():
    g = _minimal_graph(provenance="model-assisted")
    g.validate()
