"""Protocol-level lint rules (mcpx/MCP Playground grading): score, grade, tokens."""

from __future__ import annotations

import pytest

from mcp_core.quality.wire import (
    Surface,
    grade_for,
    lint_prompt,
    lint_resource,
    lint_server,
    lint_surface,
    lint_tool,
)
from mcp_core.tools.tool_decorator import compact_schema


def codes(issues) -> set[str]:
    return {i.code for i in issues}


def test_tool_rules():
    assert "tool-no-description" in codes(lint_tool({"name": "a", "inputSchema": {}}))
    assert "tool-short-description" in codes(
        lint_tool({"name": "a", "description": "tiny"})
    )
    assert "tool-long-description" in codes(
        lint_tool({"name": "a", "description": "x" * 501})
    )
    assert "tool-description-is-name" in codes(
        lint_tool({"name": "render_diagram", "description": "render diagram"})
    )
    assert "tool-no-schema" in codes(lint_tool({"name": "a", "description": "d" * 20}))
    assert "tool-name-convention" in codes(
        lint_tool({"name": "Bad Name!", "description": "d" * 20})
    )
    schema = {
        "type": "array",
        "properties": {"q": {}, "n": {"type": "integer", "description": "count"}},
        "required": ["missing"],
    }
    got = codes(
        lint_tool({"name": "t", "description": "d" * 20, "inputSchema": schema})
    )
    assert {
        "tool-schema-not-object",
        "prop-no-description",
        "prop-no-type",
        "required-not-in-properties",
    } <= got
    empty = codes(
        lint_tool(
            {"name": "t", "description": "d" * 20, "inputSchema": {"type": "object"}}
        )
    )
    assert "tool-empty-schema" in empty
    optional = {
        "type": "object",
        "properties": {"q": {"anyOf": [{"type": "string"}], "description": "query"}},
    }
    assert codes(
        lint_tool({"name": "t", "description": "d" * 20, "inputSchema": optional})
    ) == {"tool-no-required"}


def test_resource_prompt_and_server_rules():
    assert codes(lint_resource({"uri": "x://y"})) == {
        "resource-no-name",
        "resource-no-description",
        "resource-no-mimetype",
    }
    assert codes(lint_prompt({"name": "p", "arguments": [{"name": "a"}]})) == {
        "prompt-no-description",
        "prompt-arg-no-description",
    }
    empty = lint_server(Surface())
    assert {"server-empty", "server-no-name", "server-no-version"} <= codes(empty)
    dup = Surface("s", "1", tools=[{"name": "a"}, {"name": "a"}])
    assert "server-duplicate-tools" in codes(lint_server(dup))


def test_scoring_and_grades():
    assert lint_surface(Surface()).score == 0
    assert [grade_for(s) for s in (100, 90, 85, 75, 65, 10)] == [
        "A",
        "A",
        "B",
        "C",
        "D",
        "F",
    ]
    one_error = Surface(
        "s",
        "1",
        tools=[
            {
                "name": "a",
                "inputSchema": {
                    "type": "object",
                    "properties": {"x": {"type": "string", "description": "x"}},
                    "required": ["x"],
                },
            }
        ],
    )
    report = lint_surface(one_error)
    assert report.score == 85 and report.grade == "B" and report.token_estimate > 0


@pytest.mark.parametrize(
    ("schema", "expected"),
    [
        (
            {
                "title": "M",
                "type": "object",
                "properties": {"title": {"type": "string", "title": "Title"}},
            },
            {"type": "object", "properties": {"title": {"type": "string"}}},
        ),
        (
            {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
            {"type": ["string", "null"]},
        ),
        (
            {"anyOf": [{"$ref": "#/$defs/X"}, {"type": "null"}], "default": None},
            {"anyOf": [{"$ref": "#/$defs/X"}, {"type": "null"}]},
        ),
        ({"default": 0, "type": "integer"}, {"default": 0, "type": "integer"}),
    ],
)
def test_compact_schema_is_lossless(schema, expected):
    assert compact_schema(schema) == expected
