"""Wire-level FastMCP schema compatibility regression tests."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP

from mcp_core.tools.diagram_tools import register_diagram_tools
from mcp_core.tools.schema_compat import install_schema_compat
from mcp_core.tools.schemas import DiagramTypesOutput


@pytest.mark.asyncio
async def test_tools_list_advertises_required_array_and_output_contract() -> None:
    server = FastMCP("schema-contract-test")
    register_diagram_tools(server)
    install_schema_compat(server)

    tools = {tool.name: tool for tool in await server.list_tools()}
    assert set(tools) >= {
        "generate_uml",
        "validate_uml",
        "list_diagram_types",
        "generate_uml_batch",
    }

    # Some inspectors incorrectly flag an omitted JSON Schema `required` keyword.
    # Advertise it explicitly for every tool, including [] when all inputs are optional.
    for name in (
        "generate_uml",
        "validate_uml",
        "list_diagram_types",
        "generate_uml_batch",
    ):
        assert "required" in tools[name].parameters

    assert tools["list_diagram_types"].parameters["required"] == []
    assert set(tools["generate_uml"].parameters["required"]) == {
        "diagram_type",
        "code",
    }
    assert set(tools["validate_uml"].parameters["required"]) == {
        "diagram_type",
        "code",
    }
    assert tools["generate_uml_batch"].parameters["required"] == ["items"]

    # Exercise the actual registered FastMCP tool, then validate its structured
    # response against the same declared output model exposed to MCP clients.
    result = await tools["list_diagram_types"].run({"limit": 2})
    assert result.structured_content is not None
    parsed = DiagramTypesOutput.model_validate(result.structured_content)
    assert len(parsed.root) <= 2
