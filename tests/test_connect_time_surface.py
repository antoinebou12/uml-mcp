"""What every client loads on connect stays small: prompt arguments and output schemas.

``tools/list`` and ``prompts/list`` are repeated in every conversation, so their size is a
recurring cost. ``uml-mcp lint --token-budget`` gates the total; these tests pin the two
causes of the last reduction so they cannot creep back, and that nothing a client relies on
changed.
"""

from __future__ import annotations

import json

import pytest
from fastmcp import Client, FastMCP

from mcp_core.prompts.diagram_prompts import (
    _parse_context,
    _summary,
    get_prompt_registry,
    register_diagram_prompts,
)
from mcp_core.tools.schemas import BatchDiagramResult, DiagramResult, ValidationResult
from mcp_core.tools.tool_decorator import _normalize_output_schema


@pytest.fixture
def server() -> FastMCP:
    server = FastMCP("connect-time-surface-test")
    register_diagram_prompts(server)
    return server


# ---------------------------------------------------------------- prompt `context`
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", {}),
        ("   ", {}),
        ("{}", {}),
        ('{"diagram_type": "class"}', {"diagram_type": "class"}),
    ],
)
def test_context_accepts_a_json_object(raw: str, expected: dict) -> None:
    assert _parse_context(raw) == expected


@pytest.mark.parametrize("raw", ["class", "[1, 2]", "null", '"text"', "{not json"])
def test_context_rejects_anything_that_is_not_a_json_object(raw: str) -> None:
    # malformed JSON is a ValueError, valid JSON of the wrong type a TypeError
    with pytest.raises((ValueError, TypeError), match="context must be a JSON object"):
        _parse_context(raw)


@pytest.mark.asyncio
async def test_every_prompt_advertises_one_short_optional_context_argument(
    server: FastMCP,
) -> None:
    prompts = await server.list_prompts()
    assert len(prompts) == len(get_prompt_registry()) >= 16
    for prompt in prompts:
        arguments = {a.name: a for a in prompt.arguments or []}
        assert set(arguments) == {"context"}, prompt.name
        argument = arguments["context"]
        assert not argument.required, prompt.name
        assert "JSON object" in (argument.description or ""), prompt.name
        # FastMCP appends a whole JSON Schema sentence to any parameter that is not a
        # plain ``str``; that boilerplate was about 40 tokens a prompt on every connect.
        assert "JSON schema" not in (argument.description or ""), prompt.name
        assert len(argument.description or "") < 120, prompt.name


@pytest.mark.asyncio
async def test_prompt_descriptions_are_the_docstring_summaries(
    server: FastMCP,
) -> None:
    registry = get_prompt_registry()
    for prompt in await server.list_prompts():
        assert prompt.description == _summary(registry[prompt.name]["function"])


@pytest.mark.asyncio
async def test_context_json_still_reaches_the_prompt(server: FastMCP) -> None:
    async with Client(server) as client:
        with_context = await client.get_prompt(
            "uml_diagram", {"context": json.dumps({"diagram_type": "class"})}
        )
        without = await client.get_prompt("uml_diagram")

    assert (
        'set diagram_type to "class" exactly' in with_context.messages[0].content.text
    )
    assert "Target:" not in without.messages[0].content.text


@pytest.mark.asyncio
async def test_a_context_that_is_not_json_is_an_error(server: FastMCP) -> None:
    async with Client(server) as client:
        with pytest.raises(Exception, match="JSON object"):
            await client.get_prompt("uml_diagram", {"context": "class"})


# ---------------------------------------------------------------- output schemas
def test_output_schemas_list_nested_keys_instead_of_expanding_them() -> None:
    """A nested model per field tripled the size of every tool definition."""
    schema = _normalize_output_schema(DiagramResult)
    assert schema is not None
    assert "$defs" not in schema
    props = schema["properties"]
    for name in ("error_detail", "attempts"):
        assert props[name]["description"], name
        assert "properties" not in json.dumps(props[name]), name
    # Every top-level field is still advertised.
    assert {"url", "playground", "content_base64", "cache_hit", "attempts"} <= set(
        props
    )

    validation = _normalize_output_schema(ValidationResult)
    assert validation is not None
    assert "$defs" not in validation
    assert validation["properties"]["diagnostics"]["description"]


def test_batch_items_share_the_single_result_fields() -> None:
    schema = _normalize_output_schema(BatchDiagramResult)
    assert schema is not None
    item = next(iter(schema["$defs"].values()))
    assert set(item["properties"]) == {"index", *DiagramResult.model_fields}
    assert item["required"] == ["index"]  # a failed item may have no code


def test_failed_results_with_nested_detail_still_validate() -> None:
    failed = {
        "code": "graph TD; A-->",
        "success": False,
        "error": "Parse error on line 1",
        "error_detail": {"code": "syntax_error", "message": "m", "retryable": False},
        "attempts": [{"backend": "kroki", "ok": False, "error_summary": "400"}],
    }
    detail = DiagramResult.model_validate(failed).error_detail
    assert detail is not None
    assert detail["code"] == "syntax_error"
    batch = BatchDiagramResult.model_validate(
        {"results": [{"index": 0, **failed}, {"index": 1}]}
    )
    assert batch.results[1].code is None
    assert (
        ValidationResult.model_validate(
            {
                "valid": False,
                "diagnostics": [{"severity": "error", "code": "x", "message": "m"}],
            }
        ).diagnostics[0]["code"]
        == "x"
    )
