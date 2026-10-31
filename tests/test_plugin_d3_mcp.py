"""The D3 plugin as an MCP client sees it: the real server, the real client, real HTTP.

``mcp_report`` (see ``fixtures_d3``) runs the real FastMCP server in a subprocess with the
plugin enabled, then calls it through an MCP client and through the ``/mcp`` HTTP route.
These tests check what came back: advertised tools, types and samples, the pages and
images, saved files, and the errors a model gets when it writes a bad source.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.fixtures_d3 import D3_SRC

ALL = ("d3_force", "d3_architecture", "d3_topology")


def samples() -> dict[str, tuple[str, str]]:
    from uml_mcp_plugin_d3.samples import SAMPLES

    return SAMPLES


def test_the_plugin_tool_and_types_are_advertised(mcp_report) -> None:
    assert {"d3_catalog", "generate_uml", "validate_uml"} <= set(mcp_report["tools"])
    assert mcp_report["catalog_hints"]["read_only_hint"] is True
    for dtype in ALL:
        assert mcp_report["types"][dtype]["backend"] == "plugin:d3"
        assert mcp_report["types"][dtype]["formats"] == ["html", "svg"]
        assert mcp_report["formats"][dtype] == ["html", "svg"]
    assert mcp_report["types"]["class"]["backend"] == "plantuml"  # built-ins unchanged
    assert "html" not in mcp_report["formats"]["class"]


def test_examples_and_templates_teach_the_source_format(mcp_report) -> None:
    for dtype, (example, template) in samples().items():
        assert mcp_report["examples"][dtype] == example
        assert mcp_report["templates"][dtype] == template
        assert json.loads(mcp_report["examples"][dtype])["nodes"]
    assert json.loads(mcp_report["examples"]["d3_architecture"])["provider"] == "aws"


@pytest.mark.parametrize("dtype", ALL)
def test_svg_comes_back_as_an_image_a_chat_can_show(mcp_report, dtype: str) -> None:
    got = mcp_report["generated"][f"{dtype}.svg"]
    assert "error" not in got, got
    assert got["source"] == "plugin:d3" and got["success"] is True
    assert got["mime_type"] == "image/svg+xml" and got["output_format"] == "svg"
    assert got["attempts"] == [{"backend": "plugin:d3", "ok": True}]
    assert [b["type"] for b in got["blocks"]] == ["text", "image"]
    assert got["blocks"][1]["mime"] == "image/png"
    assert got["summary"].startswith(f"Generated {dtype} successfully")
    svg = (Path(mcp_report["pages_dir"]) / f"{dtype}.svg").read_text(encoding="utf-8")
    assert svg.startswith("<svg") and "<title>" in svg


@pytest.mark.parametrize("dtype", ALL)
def test_html_comes_back_as_a_standalone_page(mcp_report, dtype: str) -> None:
    got = mcp_report["generated"][f"{dtype}.html"]
    assert "error" not in got, got
    assert got["source"] == "plugin:d3" and got["output_format"] == "html"
    assert got["mime_type"] == "text/html; charset=utf-8"
    assert [b["type"] for b in got["blocks"]] == [
        "text"
    ]  # nothing a chat could display
    page = (Path(mcp_report["pages_dir"]) / f"{dtype}.html").read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>") and "Content-Security-Policy" in page
    assert '<script type="application/json" id="spec">' in page
    assert all(label in page for label in ("Save HTML", "Save SVG", "Save PNG"))
    assert 'class="d3d ' in page and "Legend" in page  # the shared look and its legend
    # the offline setting reached the plugin through plugins.settings.d3
    assert "https://cdn.jsdelivr.net" not in page and got["bytes"] > 250_000


def test_html_can_be_saved_as_a_file_through_output_dir(mcp_report) -> None:
    saved = mcp_report["saved"]
    assert "error" not in saved, saved
    path = Path(saved["local_path"])
    assert (
        path.suffix == ".html"
        and path.parent == Path(mcp_report["saved_dir"]).resolve()
    )
    assert path.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert saved["has_content"] is False  # the bytes are not repeated in the result
    assert saved["summary"].endswith(f"Saved to: {saved['local_path']}")


def test_a_markdown_fence_around_the_json_is_tolerated(mcp_report) -> None:
    assert mcp_report["fenced"] is True


def test_a_bad_source_gets_an_error_that_says_what_to_fix(mcp_report) -> None:
    errors = mcp_report["errors"]
    assert "links[0].to 'zzz': no such node" in errors["unknown_node"]
    assert "not valid JSON" in errors["not_json"]
    assert "not supported for diagram type 'class'" in errors["html_for_builtin"]
    assert "choose one of: html, svg" in errors["pdf_for_d3"]
    assert "use one of aws, azure, gcp" in errors["bad_provider"]


def test_validate_uml_checks_the_source_without_rendering(mcp_report) -> None:
    good, bad = mcp_report["validate"]["good"], mcp_report["validate"]["bad"]
    assert (
        good["valid"] is True and good["backend"] == "plugin:d3" and not good["errors"]
    )
    assert bad["valid"] is False
    joined = " | ".join(bad["errors"])
    for expected in ("provider 'oracle'", "duplicate", "kind 'toaster'"):
        assert expected in joined  # every problem at once, not just the first
    assert {d["code"] for d in bad["diagnostics"]} == {"INVALID_DIAGRAM"}


def test_the_catalog_tool_lists_what_a_model_can_use(mcp_report) -> None:
    catalog = mcp_report["catalog"]
    assert catalog["services"] and all(
        k.startswith("aws:") for k in catalog["services"]
    )
    assert "aws:s3" in catalog["services"] and "database" in catalog["kinds"]
    assert set(catalog["categories"]) == {
        "frontend", "backend", "database", "cloud", "security", "messagebus", "external",
    }  # fmt: skip
    assert set(catalog["diagram_types"]) == set(ALL)
    assert mcp_report["catalog_all_providers"] == [
        "aws", "azure", "gcp", "generic", "kubernetes", "onprem", "tech",
    ]  # fmt: skip


def test_a_batch_renders_what_it_can(mcp_report) -> None:
    assert [(r["index"], r["success"]) for r in mcp_report["batch"]] == [
        (0, True),
        (1, False),
    ]
    assert "at least one node" in mcp_report["batch"][1]["error"]


def test_the_same_server_over_http(mcp_report) -> None:
    http = mcp_report["http"]
    assert "d3_catalog" in http["tools"] and http["is_error"] is False
    assert http["content_types"] == ["text", "image"] and http["image_mime"] == [
        "image/png"
    ]
    assert http["structured_source"] == "plugin:d3"


def test_the_plugin_package_ships_everything_it_loads() -> None:
    """The wheel is built from src/uml_mcp_plugin_d3, so every asset must be inside it."""
    package = D3_SRC / "uml_mcp_plugin_d3"
    names = {p.name for p in (package / "assets").iterdir()}
    assert names == {
        "arch.js",
        "bounds.js",
        "common.js",
        "force.js",
        "router.js",
        "d3.v7.9.0.min.js",
        "d3.LICENSE",
        "brands",
    }
    for name in ("pyproject.toml", "README.md"):
        assert (D3_SRC.parent / name).is_file(), name


def test_the_plugin_tool_lints_clean(mcp_report) -> None:
    """`uml-mcp lint` grades the whole server, plugin tool included."""
    lint = mcp_report["lint"]
    assert lint["grade"] == "A" and lint["score"] == 100 and lint["issues"] == []
    # the plugin's one deliberate exception is documented with its reason, not silently dropped
    assert [
        "tool-no-required",
        "tool:d3_catalog",
        "the only argument is an optional filter",
    ] in lint["suppressed"]
    assert all(
        target != "tool:d3_catalog" or code == "tool-no-required"
        for code, target, _ in lint["suppressed"]
    )
