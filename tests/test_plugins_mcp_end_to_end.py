"""The stack-diagram, archify and LLM-visualizer plugins through a real MCP server.

A child process runs the real FastMCP server with the three plugins enabled and drives it
the way clients do. It covers what a client **without** MCP Apps gets (an inline PNG and an
SVG), what an MCP App client gets (HTML saved to a file), the ``theme`` argument, batches,
validation errors and the ``uml-mcp lint`` grade.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "examples/plugins"
PACKAGES = (
    "uml-mcp-plugin-stack-diagram",
    "uml-mcp-plugin-archify",
    "uml-mcp-plugin-llm-visualizer",
)

_DRIVER = r"""
import asyncio, base64, importlib.metadata as md, json, logging, sys
from pathlib import Path

logging.disable(logging.CRITICAL)
out_dir = Path(sys.argv[1])
for src in sys.argv[2:]:
    sys.path.insert(0, src)

from mcp_core.plugins import loader
from mcp_core.plugins.api import RENDERERS_GROUP

EPS = {RENDERERS_GROUP: [
    md.EntryPoint("stack-diagram", "uml_mcp_plugin_stack_diagram:StackDiagramRenderer", RENDERERS_GROUP),
    md.EntryPoint("archify", "uml_mcp_plugin_archify:ArchifyRenderer", RENDERERS_GROUP),
    md.EntryPoint("llm-visualizer", "uml_mcp_plugin_llm_visualizer:LLMVisualizerRenderer", RENDERERS_GROUP),
]}
loader.entry_points = lambda group: EPS.get(group, [])

from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp_core.core.server import get_mcp_server
from uml_mcp_plugin_archify.samples import ARCHITECTURE, SEQUENCE, WORKFLOW
from uml_mcp_plugin_llm_visualizer.samples import AUTOENCODER, EXAMPLE, TRANSFORMER
from uml_mcp_plugin_stack_diagram.samples import CLOUD_EXAMPLE
from uml_mcp_plugin_stack_diagram.samples import EXAMPLE as STACK

CASES = {
    "stack_diagram": STACK,
    "archify_architecture": ARCHITECTURE,
    "archify_workflow": WORKFLOW,
    "archify_sequence": SEQUENCE,
    "llm_2d": TRANSFORMER,
    "llm_3d": EXAMPLE,
}
pages = out_dir / "pages"
pages.mkdir(parents=True, exist_ok=True)


async def call(client, name, arguments):
    try:
        return {"result": await client.call_tool(name, arguments)}
    except ToolError as exc:
        return {"error": str(exc)}


def block_types(result):
    return [b.type for b in result.content]


async def main():
    report = {}
    server = get_mcp_server()
    async with Client(server) as client:
        types = json.loads((await client.read_resource("uml://types"))[0].text)
        examples = json.loads((await client.read_resource("uml://examples"))[0].text)
        report["listed"] = sorted(t for t in CASES if t in json.dumps(types))
        report["examples"] = sorted(t for t in CASES if t in examples)

        report["svg"], report["png"], report["html"] = {}, {}, {}
        for dtype, code in CASES.items():
            svg = await call(client, "generate_uml", {"diagram_type": dtype, "code": code, "output_format": "svg"})
            data = svg["result"].structured_content if "result" in svg else {}
            report["svg"][dtype] = {
                "error": svg.get("error"),
                "success": data.get("success"),
                "source": data.get("source"),
                "mime": data.get("mime_type"),
                "has_bytes": bool(data.get("content_base64")),
            }
            if data.get("content_base64"):
                (pages / f"{dtype}.svg").write_bytes(base64.b64decode(data["content_base64"]))

            png = await call(client, "generate_uml_image", {"diagram_type": dtype, "code": code})
            if "result" in png:
                pd = png["result"].structured_content or {}
                report["png"][dtype] = {"blocks": block_types(png["result"]), "mime": pd.get("mime_type"), "success": pd.get("success")}
            else:
                report["png"][dtype] = {"error": png["error"]}

            html = await call(client, "generate_uml", {"diagram_type": dtype, "code": code, "output_format": "html", "output_dir": str(pages)})
            if "result" in html:
                hd = html["result"].structured_content
                path = hd.get("local_path")
                report["html"][dtype] = {"local_path": bool(path), "is_page": bool(path) and Path(path).read_text(encoding="utf-8").lstrip().startswith("<!doctype html>"), "source": hd.get("source")}
            else:
                report["html"][dtype] = {"error": html["error"]}

        # the theme argument is written into the JSON source, so every plugin follows it
        report["theme"] = {}
        for dtype, light_bg in (("stack_diagram", "#fafbfc"), ("archify_architecture", "#f6f8fc"), ("llm_2d", "#f8fafc")):
            got = await call(client, "generate_uml", {"diagram_type": dtype, "code": CASES[dtype], "output_format": "svg", "theme": "light"})
            svg = base64.b64decode(got["result"].structured_content["content_base64"]).decode()
            report["theme"][dtype] = light_bg in svg

        report["errors"] = {
            "bad_direction": (await call(client, "generate_uml", {"diagram_type": "stack_diagram", "output_format": "svg", "code": '{"nodes": [{"id": "a"}], "direction": "UP"}'}))["error"],
            "bad_preset": (await call(client, "generate_uml", {"diagram_type": "archify_architecture", "output_format": "svg", "code": '{"nodes": [{"id": "a"}], "preset": "neon"}'}))["error"],
            "bad_sequence": (await call(client, "generate_uml", {"diagram_type": "archify_sequence", "output_format": "svg", "code": '{"participants": [{"id": "a"}], "messages": []}'}))["error"],
            "bad_group": (await call(client, "generate_uml", {"diagram_type": "llm_2d", "output_format": "svg", "code": '{"layers": [{"id": "a", "group": "x"}]}'}))["error"],
        }
        good = (await call(client, "validate_uml", {"diagram_type": "archify_architecture", "code": ARCHITECTURE, "output_format": "svg"}))["result"]
        bad = (await call(client, "validate_uml", {"diagram_type": "stack_diagram", "output_format": "svg", "code": '{"nodes": [{"id": "a"}], "edges": [{"from": "a", "to": "zz"}]}'}))["result"]
        report["validate"] = {"good": good.structured_content, "bad": bad.structured_content}

        batch = (await call(client, "generate_uml_batch", {"items": [
            {"diagram_type": "stack_diagram", "code": CLOUD_EXAMPLE, "output_format": "svg"},
            {"diagram_type": "archify_workflow", "code": WORKFLOW, "output_format": "svg"},
            {"diagram_type": "llm_2d", "code": AUTOENCODER, "output_format": "svg"},
        ]}))["result"]
        report["batch"] = [bool(r.get("success")) for r in batch.structured_content["results"]]

    from mcp_core.quality.wire import fetch_surface, lint_surface

    lint = lint_surface(await fetch_surface())
    report["lint"] = {"grade": lint.grade, "issues": [f"{i.code}@{i.target}" for i in lint.issues]}
    print("PLUGINS_JSON " + json.dumps(report))


asyncio.run(main())
"""


def run_driver(work: Path) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    config = work / "uml-mcp.yaml"
    config.write_text(
        "plugins:\n  enabled: [stack-diagram, archify, llm-visualizer]\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        {
            "USE_REAL_FASTMCP": "1",
            "MOCK_FASTMCP": "0",
            "TESTING": "0",
            "DEVELOPMENT": "0",
            "UML_MCP_CONFIG": str(config),
            "MCP_OUTPUT_ROOT": str(work),
            "MCP_MEMORY_ONLY": "false",
            "MCP_URL_ONLY": "false",
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": str(ROOT) + os.pathsep + env.get("PYTHONPATH", ""),
        }
    )
    sources = [str(PLUGINS / name / "src") for name in PACKAGES]
    done = subprocess.run(
        [sys.executable, "-c", _DRIVER, str(work), *sources],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    assert done.returncode == 0, f"stdout:\n{done.stdout}\nstderr:\n{done.stderr}"
    line = next(ln for ln in done.stdout.splitlines() if ln.startswith("PLUGINS_JSON "))
    return json.loads(line.removeprefix("PLUGINS_JSON "))


@pytest.fixture(scope="module")
def report(tmp_path_factory) -> dict:
    return run_driver(tmp_path_factory.mktemp("plugins-mcp"))


TYPES = (
    "stack_diagram",
    "archify_architecture",
    "archify_workflow",
    "archify_sequence",
    "llm_2d",
    "llm_3d",
)


def test_types_and_examples_are_advertised(report):
    assert report["listed"] == sorted(TYPES)
    assert report["examples"] == sorted(TYPES)


@pytest.mark.parametrize("dtype", TYPES)
def test_svg_works_for_any_client(report, dtype):
    row = report["svg"][dtype]
    assert row["error"] is None and row["success"] is True, row
    assert row["mime"] == "image/svg+xml" and row["has_bytes"]
    assert row["source"].startswith("plugin:")


@pytest.mark.parametrize("dtype", TYPES)
def test_clients_without_mcp_apps_get_an_inline_png(report, dtype):
    """``generate_uml_image`` is what chat clients without MCP Apps call: it must be a picture."""
    row = report["png"][dtype]
    assert "error" not in row, row
    assert row["success"] is True and row["mime"] == "image/png", row
    assert "image" in row["blocks"], row


@pytest.mark.parametrize("dtype", TYPES)
def test_mcp_app_clients_get_a_saved_interactive_page(report, dtype):
    row = report["html"][dtype]
    assert "error" not in row, row
    assert row["local_path"] and row["is_page"], row


def test_theme_argument_reaches_every_plugin(report):
    assert report["theme"] == {
        "stack_diagram": True,
        "archify_architecture": True,
        "llm_2d": True,
    }


def test_errors_explain_how_to_fix_the_source(report):
    errors = report["errors"]
    assert "direction" in errors["bad_direction"]
    assert "preset must be one of" in errors["bad_preset"]
    assert "at least two" in errors["bad_sequence"]
    assert "unknown group" in errors["bad_group"]


def test_validate_and_batch(report):
    assert report["validate"]["good"]["valid"] is True
    assert report["validate"]["bad"]["valid"] is False
    assert "unknown node" in json.dumps(report["validate"]["bad"])
    assert report["batch"] == [True, True, True]


def test_lint_grade_is_not_hurt_by_the_plugins(report):
    assert report["lint"]["grade"] == "A", report["lint"]
