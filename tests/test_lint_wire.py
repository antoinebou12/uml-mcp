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
    only_optional = _tool(inputSchema={**optional, "additionalProperties": False})
    assert codes(lint_tool(only_optional)) == {"tool-no-required"}


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
    no_description = _tool(description="")  # exactly one error: tool-no-description
    one_error = Surface("s", "1", tools=[no_description], instructions="use it")
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


def _tool(**over):
    base = {
        "name": "render_diagram",
        "title": "Render",
        "description": "Render a diagram from source and return its URL.",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"code": {"type": "string", "description": "source"}},
            "required": ["code"],
        },
        "outputSchema": {"type": "object"},
    }
    base.update(over)
    return base


def test_a_complete_tool_is_clean():
    assert lint_tool(_tool()) == []


def test_extended_tool_rules():
    got = codes(lint_tool(_tool(name="bad name/with slash")))
    assert {"tool-name-invalid", "tool-name-convention"} <= got
    no_title = _tool()
    no_title.pop("title")
    assert "tool-no-title" in codes(lint_tool(no_title))
    assert "tool-missing-hints" in codes(lint_tool(_tool(annotations={"title": "x"})))
    no_out = _tool()
    no_out.pop("outputSchema")
    assert "tool-no-output-schema" in codes(lint_tool(no_out))
    assert "output-schema-not-object" in codes(
        lint_tool(_tool(outputSchema={"type": "array"}))
    )
    open_schema = _tool()
    open_schema["inputSchema"] = {
        **open_schema["inputSchema"],
        "additionalProperties": True,
    }
    assert "tool-schema-open" in codes(lint_tool(open_schema))
    assert "tool-too-large" in codes(lint_tool(_tool(description="x" * 7000)))


def test_extended_server_rules():
    s = Surface(
        "s",
        "1",
        tools=[_tool()],
        prompts=[
            {"name": "p", "description": "d" * 20},
            {"name": "p", "description": "d" * 20},
        ],
        resources=[
            {
                "uri": "u://a",
                "name": "a",
                "description": "d" * 20,
                "mimeType": "text/plain",
            }
        ]
        * 2,
    )
    got = codes(lint_server(s))
    assert {
        "server-no-instructions",
        "server-duplicate-prompts",
        "server-duplicate-resources",
    } <= got
    s.instructions = "Use render_diagram."
    assert "server-no-instructions" not in codes(lint_server(s))


def test_suppressions_are_reported_not_scored():
    from mcp_core.quality.wire import apply_ignores, parse_ignore

    t = _tool()
    t["inputSchema"] = {**t["inputSchema"], "required": []}
    s = Surface(
        "s",
        "1",
        tools=[t],
        instructions="hi",
        ignores={"tool:render_diagram": {"tool-no-required": "all optional"}},
    )
    report = lint_surface(s)
    assert report.score == 100 and report.issues == []
    assert report.suppressed[0]["code"] == "tool-no-required"
    assert report.suppressed[0]["reason"] == "all optional"
    assert report.as_dict()["suppressed"]
    assert parse_ignore("tool-no-title") == ("*", "tool-no-title")
    assert parse_ignore("a@tool:x") == ("tool:x", "a")
    from mcp_core.quality.lint import LintIssue

    kept, sup = apply_ignores(
        [LintIssue("warning", "prop-no-description", "tool:x.p", "m")],
        {"tool:x": {"prop-no-description": "why"}},
    )
    assert kept == [] and sup[0]["target"] == "tool:x.p"
