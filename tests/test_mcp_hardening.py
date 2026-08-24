"""Regression tests for MCP result contracts, caching, security, and discovery."""

from __future__ import annotations

import os
import time
from unittest.mock import patch

import pytest

from mcp_core.core import server as server_module
from mcp_core.core.config import MCP_SETTINGS
from mcp_core.core.render_cache import get_render_cache
from mcp_core.tools.diagram_tools import (
    generate_uml,
    generate_uml_batch,
    list_diagram_types,
    validate_uml,
)
from mcp_core.tools.schemas import DiagramResult, DiagramTypesOutput, GenerateUMLInput
from mcp_core.tools.tool_decorator import _normalize_output_schema


@pytest.fixture(autouse=True)
def _clear_render_cache():
    cache = get_render_cache()
    cache.clear()
    yield
    cache.clear()


def test_pydantic_output_schema_is_converted_to_json_schema():
    schema = _normalize_output_schema(DiagramResult)
    assert schema is not None
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "code" in schema["properties"]
    assert "cache_hit" in schema["properties"]


def test_dynamic_diagram_type_schema_matches_raw_map_shape():
    schema = _normalize_output_schema(DiagramTypesOutput)
    assert schema is not None
    assert schema["type"] == "object"
    assert "additionalProperties" in schema


def test_list_diagram_types_filters_without_breaking_zero_argument_shape():
    all_types = list_diagram_types()
    assert "class" in all_types

    sequence_types = list_diagram_types(query="sequence")
    assert "sequence" in sequence_types
    assert all(
        "sequence" in (
            name + " " + info["description"] + " " + info["backend"]
        ).lower()
        for name, info in sequence_types.items()
    )

    plantuml_svg = list_diagram_types(backend="plantuml", output_format="svg", limit=2)
    assert 1 <= len(plantuml_svg) <= 2
    assert all(info["backend"] == "plantuml" for info in plantuml_svg.values())
    assert all("svg" in info["formats"] for info in plantuml_svg.values())


def test_validate_uml_returns_structured_diagnostics():
    result = validate_uml(
        "mermaid",
        "sequenceDiagram\nA->>",
        strict=True,
    )
    assert result["valid"] is False
    assert result["diagnostics"]
    diagnostic = result["diagnostics"][0]
    assert diagnostic["severity"] == "error"
    assert diagnostic["code"] == "MERMAID_DANGLING_ARROW"
    assert diagnostic["line"] == 2


def test_validate_uml_reports_deterministic_normalization():
    result = validate_uml("class", "class A")
    assert result["valid"] is True
    assert result["normalized"] is True
    assert "added @startuml wrapper" in result["changes"]
    assert "added @enduml wrapper" in result["changes"]
    assert result["corrected_code"].startswith("@startuml")


def test_output_dir_is_sandboxed_when_arbitrary_paths_are_not_allowed(
    monkeypatch, tmp_path
):
    root = tmp_path / "allowed"
    root.mkdir()
    monkeypatch.setenv("MCP_OUTPUT_ROOT", str(root))
    monkeypatch.setenv("MCP_ALLOW_ARBITRARY_OUTPUT_DIR", "false")
    monkeypatch.setattr(MCP_SETTINGS, "read_only", False)
    monkeypatch.setattr(MCP_SETTINGS, "memory_only", False)

    allowed = GenerateUMLInput(
        diagram_type="class",
        code="class A",
        output_dir=str(root / "diagrams"),
    )
    assert allowed.output_dir

    with pytest.raises(ValueError, match="configured output root"):
        GenerateUMLInput(
            diagram_type="class",
            code="class A",
            output_dir=str(tmp_path / "outside"),
        )


def test_generate_uml_uses_real_cache_when_enabled(monkeypatch):
    monkeypatch.setenv("MCP_RENDER_CACHE_ENABLED", "true")
    cache = get_render_cache()
    cache.clear()

    rendered = {
        "code": "graph TD; A-->B;",
        "url": "https://kroki.io/mermaid/svg/cache-test",
        "playground": None,
        "local_path": None,
        "source": "kroki",
        "render_ms": 12.5,
        "mime_type": "image/svg+xml",
    }
    with patch("mcp_core.core.diagram_service.generate_diagram", return_value=rendered) as render:
        first = generate_uml("mermaid", "graph TD; A-->B;")
        second = generate_uml("mermaid", "graph TD; A-->B;")

    assert render.call_count == 1
    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert second["url"] == first["url"]
    assert cache.stats()["hits"] >= 1


def test_cache_key_changes_for_render_options(monkeypatch):
    monkeypatch.setenv("MCP_RENDER_CACHE_ENABLED", "true")
    cache = get_render_cache()
    cache.clear()

    rendered = {
        "code": "@startuml\nclass A\n@enduml",
        "url": "https://example.test/a.svg",
        "playground": None,
        "local_path": None,
        "source": "kroki",
    }
    with patch("mcp_core.core.diagram_service.generate_diagram", return_value=rendered) as render:
        generate_uml("class", "class A", scale=1.0)
        generate_uml("class", "class A", scale=2.0)
    assert render.call_count == 2


def test_batch_keeps_input_order_under_concurrency(monkeypatch):
    monkeypatch.setenv("MCP_BATCH_CONCURRENCY", "3")

    def fake_render(index, raw, output_dir):
        time.sleep((2 - index) * 0.01)
        return {"index": index, "code": raw["code"], "success": True}

    items = [
        {"diagram_type": "mermaid", "code": "a"},
        {"diagram_type": "mermaid", "code": "b"},
        {"diagram_type": "mermaid", "code": "c"},
    ]
    with patch("mcp_core.tools.diagram_tools._render_batch_item", side_effect=fake_render):
        result = generate_uml_batch(items)

    assert [row["index"] for row in result["results"]] == [0, 1, 2]


def test_fastmcp_security_env_mapping(monkeypatch):
    for name in (
        "FASTMCP_HTTP_ALLOWED_HOSTS",
        "FASTMCP_HTTP_ALLOWED_ORIGINS",
        "FASTMCP_HTTP_HOST_ORIGIN_PROTECTION",
    ):
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "uml-mcp.vercel.app,localhost")
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", '["https://example.test"]')
    server_module._configure_fastmcp_http_security()

    assert os.environ["FASTMCP_HTTP_HOST_ORIGIN_PROTECTION"] == "true"
    assert "uml-mcp.vercel.app" in os.environ["FASTMCP_HTTP_ALLOWED_HOSTS"]
    assert "https://example.test" in os.environ["FASTMCP_HTTP_ALLOWED_ORIGINS"]
