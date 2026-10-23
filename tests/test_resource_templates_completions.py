"""Resource templates and completion/complete for uml:// progressive discovery."""

from __future__ import annotations

import json

import pytest
from fastmcp import Client, FastMCP
from mcp.types import (
    CompletionArgument,
    PromptReference,
    ResourceTemplateReference,
)

from mcp_core.resources.completions import (
    RECIPE_IDS,
    complete_argument,
    filter_completion_values,
    theme_names,
)
from mcp_core.resources.diagram_resources import (
    get_example_for_type,
    get_formats_for_type,
    get_recipe_for_id,
    get_template_for_type,
    register_diagram_resources,
)


def test_filter_completion_values_prefix_and_cap():
    values = filter_completion_values(
        ["sequence", "seqdiag", "class", "mermaid"], "seq"
    )
    assert values == ["seqdiag", "sequence"]
    many = [f"t{i:03d}" for i in range(150)]
    assert len(filter_completion_values(many, None, limit=100)) == 100


def test_per_type_template_and_example_json():
    tmpl = json.loads(get_template_for_type("mermaid"))
    assert tmpl["diagram_type"] == "mermaid"
    assert isinstance(tmpl["template"], str) and tmpl["template"]
    ex = json.loads(get_example_for_type("class"))
    assert ex["diagram_type"] == "class"
    assert isinstance(ex["example"], str) and ex["example"]
    formats = json.loads(get_formats_for_type("d2"))
    assert "svg" in formats["formats"]
    recipe = json.loads(get_recipe_for_id("algorithm_flowchart"))
    assert recipe["diagram_type"] == "mermaid"
    bad = json.loads(get_template_for_type("not-a-type"))
    assert "error" in bad


def test_complete_diagram_type_on_resource_template():
    ref = ResourceTemplateReference(
        type="ref/resource", uri="uml://templates/{diagram_type}"
    )
    arg = CompletionArgument(name="diagram_type", value="mer")
    values = complete_argument(ref, arg, None)
    assert values is not None
    assert "mermaid" in values
    assert all(v.startswith("mer") or "mer" in v for v in values)


def test_complete_recipe_id():
    ref = ResourceTemplateReference(
        type="ref/resource", uri="uml://recipes/{recipe_id}"
    )
    arg = CompletionArgument(name="recipe_id", value="alg")
    values = complete_argument(ref, arg, None)
    assert values == ["algorithm_flowchart"]
    assert set(RECIPE_IDS) <= set(
        complete_argument(ref, CompletionArgument(name="recipe_id", value=""), None)
        or []
    )


def test_complete_diagram_theme_prompt_background():
    ref = PromptReference(type="ref/prompt", name="diagram_theme")
    arg = CompletionArgument(name="context", value='{"background": "da')
    values = complete_argument(ref, arg, None)
    assert values is not None
    assert "dark" in values


def test_theme_names_by_backend():
    assert "cerulean" in theme_names(diagram_type="class")
    assert "forest" in theme_names(diagram_type="mermaid")
    assert "dark" in theme_names(diagram_type="d2")


@pytest.mark.asyncio
async def test_templates_and_completions_over_real_mcp():
    server = FastMCP("uml-templates-test", cache_ttl=300, cache_scope="public")
    register_diagram_resources(server)
    async with Client(server, timeout=10) as client:
        templates = await client.list_resource_templates()
        uris = {t.uri_template for t in templates}
        assert "uml://templates/{diagram_type}" in uris
        assert "uml://examples/{diagram_type}" in uris
        assert "uml://formats/{diagram_type}" in uris
        assert "uml://recipes/{recipe_id}" in uris

        contents = await client.read_resource("uml://templates/mermaid")
        payload = json.loads(contents[0].text)
        assert payload["diagram_type"] == "mermaid"
        assert payload["template"]

        completion = await client.complete(
            ref=ResourceTemplateReference(
                type="ref/resource", uri="uml://templates/{diagram_type}"
            ),
            argument={"name": "diagram_type", "value": "c"},
        )
        assert "class" in completion.values
        assert "c4plantuml" in completion.values or any(
            v.startswith("c") for v in completion.values
        )
