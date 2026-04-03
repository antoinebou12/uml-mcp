"""Tests for the mermaid module (state serialization and URL generation)."""

import pytest

from tools.kroki.mermaid import (
    MERMAID_INK_BASE,
    MERMAID_LIVE_EDIT_BASE,
    MermaidUrls,
    deserialize_state,
    generate_diagram_state,
    generate_mermaid_live_editor_url,
    generate_mermaid_urls,
    get_edit_url,
    get_image_url,
    serialize_state,
)


def test_generate_diagram_state():
    """generate_diagram_state returns a dict with code and mermaid theme."""
    state = generate_diagram_state("graph TD\n  A-->B", theme="dark")
    assert state["code"] == "graph TD\n  A-->B"
    assert state["mermaid"] == {"theme": "dark"}
    assert state["updateEditor"] is True
    assert state["updateDiagram"] is True


def test_generate_diagram_state_strips_code():
    """generate_diagram_state strips leading/trailing whitespace from code."""
    state = generate_diagram_state("  graph TD\n  A-->B  ")
    assert state["code"] == "graph TD\n  A-->B"


def test_serialize_deserialize_roundtrip_pako():
    """serialize_state and deserialize_state roundtrip with pako."""
    state = generate_diagram_state("graph TD\n  A-->B", theme="default")
    serialized = serialize_state(state, serde="pako")
    assert serialized.startswith("pako:")
    restored = deserialize_state(serialized)
    assert restored["code"] == state["code"]
    assert restored["mermaid"] == state["mermaid"]


def test_serialize_deserialize_roundtrip_base64():
    """serialize_state and deserialize_state roundtrip with base64."""
    state = generate_diagram_state("graph TD\n  A-->B")
    serialized = serialize_state(state, serde="base64")
    assert serialized.startswith("base64:")
    restored = deserialize_state(serialized)
    assert restored["code"] == state["code"]


def test_serialize_state_invalid_serde():
    """serialize_state raises ValueError for unknown serde."""
    state = generate_diagram_state("x")
    with pytest.raises(ValueError, match="Unknown serde type"):
        serialize_state(state, serde="invalid")


def test_deserialize_state_invalid_serde():
    """deserialize_state raises ValueError for unknown serde in payload."""
    with pytest.raises(ValueError, match="Unknown serde type"):
        deserialize_state("unknown:payload")


def test_generate_mermaid_urls_from_text():
    """generate_mermaid_urls with diagram_text returns MermaidUrls."""
    urls = generate_mermaid_urls(diagram_text="graph TD\n  A-->B", theme="default")
    assert isinstance(urls, MermaidUrls)
    assert urls.code == "graph TD\n  A-->B"
    assert urls.image_url.startswith(MERMAID_INK_BASE + "/svg/")
    assert "pako:" in urls.image_url
    assert urls.edit_url.startswith(MERMAID_LIVE_EDIT_BASE)
    assert "pako:" in urls.edit_url


def test_generate_mermaid_urls_from_state():
    """generate_mermaid_urls with diagram_state uses state and returns code."""
    state = generate_diagram_state("sequenceDiagram\n  A->>B: hi")
    urls = generate_mermaid_urls(diagram_state=state)
    assert urls.code == "sequenceDiagram\n  A->>B: hi"
    assert MERMAID_INK_BASE in urls.image_url
    assert MERMAID_LIVE_EDIT_BASE in urls.edit_url


def test_generate_mermaid_urls_state_overrides_text():
    """When both diagram_state and diagram_text are given, diagram_state is used."""
    state = generate_diagram_state("code from state")
    urls = generate_mermaid_urls(diagram_state=state, diagram_text="ignored")
    assert urls.code == "code from state"


def test_generate_mermaid_urls_requires_input():
    """generate_mermaid_urls raises ValueError when neither state nor text given."""
    with pytest.raises(
        ValueError, match="Provide either diagram_state or diagram_text"
    ):
        generate_mermaid_urls()


def test_generate_mermaid_urls_image_format():
    """generate_mermaid_urls respects image_format for image URL."""
    urls_svg = generate_mermaid_urls(
        diagram_text="graph TD\n  A-->B", image_format="svg"
    )
    urls_png = generate_mermaid_urls(
        diagram_text="graph TD\n  A-->B", image_format="png"
    )
    assert f"{MERMAID_INK_BASE}/svg/" in urls_svg.image_url
    assert f"{MERMAID_INK_BASE}/png/" in urls_png.image_url


def test_get_image_url():
    """get_image_url returns only the mermaid.ink image URL."""
    url = get_image_url("graph TD\n  A-->B", theme="dark")
    assert url.startswith(MERMAID_INK_BASE)
    assert "/svg/" in url


def test_get_edit_url():
    """get_edit_url returns only the mermaid.live edit URL."""
    url = get_edit_url("graph TD\n  A-->B")
    assert url.startswith(MERMAID_LIVE_EDIT_BASE)


def test_generate_mermaid_live_editor_url_backward_compat():
    """generate_mermaid_live_editor_url returns MermaidUrls (backward compat)."""
    state = generate_diagram_state("graph TD\n  A-->B")
    urls = generate_mermaid_live_editor_url(state)
    assert isinstance(urls, MermaidUrls)
    assert urls.code == state["code"]
    assert MERMAID_INK_BASE in urls.image_url
    assert MERMAID_LIVE_EDIT_BASE in urls.edit_url


def test_mermaid_urls_frozen():
    """MermaidUrls is immutable."""
    urls = generate_mermaid_urls(diagram_text="x")
    with pytest.raises(AttributeError):
        urls.code = "y"  # type: ignore[misc]
