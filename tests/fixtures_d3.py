"""Shared setup for the D3 plugin tests.

The plugin lives under ``examples/plugins`` and is not installed in the test environment,
so it is found through patched entry points (the way ``test_plugins.py`` loads the hello
plugin). ``mcp_report`` runs the REAL server (real FastMCP, not the suite's mock) in a
subprocess with the plugin enabled and drives it like an MCP client does: the in-process
client, then the ``/mcp`` HTTP route. It writes every page it receives to disk, so the
browser tests open exactly what an MCP client got.
"""

from __future__ import annotations

import importlib.metadata as md
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
D3_SRC = ROOT / "examples/plugins/uml-mcp-plugin-d3/src"
if str(D3_SRC) not in sys.path:  # loaded as a pytest plugin, so before any test module
    sys.path.insert(0, str(D3_SRC))

from mcp_core.core.config import MCP_SETTINGS
from mcp_core.core.settings_file import reset_config_cache
from mcp_core.plugins import loader
from mcp_core.plugins.api import RENDERERS_GROUP, TOOLS_GROUP
from mcp_core.tools.tool_decorator import _registered_tools

#: A one pixel PNG, as a data URI, for tests that need a node logo.
PNG_1PX = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/"
    "iZk9HQAAAABJRU5ErkJggg=="
)


def grab(pattern: str, text: str, flags: int = 0) -> re.Match[str]:
    """``re.search`` that fails the test, naming the pattern, when nothing matches."""
    match = re.search(pattern, text, flags)
    assert match is not None, f"no match for {pattern!r}"
    return match


def spec_of(html_text: str) -> dict:
    """The JSON data block of a rendered D3 page."""
    block = grab(
        r'<script type="application/json" id="spec">(.*?)</script>',
        html_text,
        re.DOTALL,
    )
    return json.loads(block.group(1))


D3_EPS = {
    TOOLS_GROUP: [md.EntryPoint("d3", "uml_mcp_plugin_d3:register", TOOLS_GROUP)],
    RENDERERS_GROUP: [
        md.EntryPoint("d3", "uml_mcp_plugin_d3:D3Renderer", RENDERERS_GROUP)
    ],
}


@pytest.fixture
def d3_plugin(tmp_path, monkeypatch):
    """The D3 plugin loaded in this process; ``settings`` is YAML under ``plugins:``."""
    monkeypatch.setattr(loader, "entry_points", lambda group: D3_EPS.get(group, []))
    monkeypatch.setenv("UML_MCP_CONFIG", str(tmp_path / "uml-mcp.yaml"))
    tools_before = set(_registered_tools)

    def enable(settings: str = "") -> list:
        (tmp_path / "uml-mcp.yaml").write_text(
            "plugins:\n  enabled: [d3]\n" + settings, encoding="utf-8"
        )
        reset_config_cache()
        return loader.load_plugins()

    yield enable
    for name in set(_registered_tools) - tools_before:
        del _registered_tools[name]
    for dtype in list(loader.RENDERERS):
        MCP_SETTINGS.diagram_types.pop(dtype, None)
    loader.RENDERERS.clear()
    loader.STATUS.clear()
    reset_config_cache()


# The driver runs in a child process: real FastMCP, the plugin enabled through patched
# entry points, then an MCP client in process and the same server over HTTP.
_DRIVER = r"""
import asyncio, base64, importlib.metadata as md, json, logging, sys
from pathlib import Path

logging.disable(logging.CRITICAL)
src, out_dir = sys.argv[1], Path(sys.argv[2])
sys.path.insert(0, src)

from mcp_core.plugins import loader
from mcp_core.plugins.api import RENDERERS_GROUP, TOOLS_GROUP

EPS = {
    TOOLS_GROUP: [md.EntryPoint("d3", "uml_mcp_plugin_d3:register", TOOLS_GROUP)],
    RENDERERS_GROUP: [md.EntryPoint("d3", "uml_mcp_plugin_d3:D3Renderer", RENDERERS_GROUP)],
}
loader.entry_points = lambda group: EPS.get(group, [])

from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp_core.core.server import get_mcp_server
from uml_mcp_plugin_d3.samples import SAMPLES

pages = out_dir / "pages"
pages.mkdir(parents=True, exist_ok=True)
saved_dir = out_dir / "saved"


def block_info(block):
    return {
        "type": block.type,
        "mime": getattr(block, "mime_type", None) or getattr(block, "mimeType", None),
    }


def text_of(contents):
    first = contents[0]
    return getattr(first, "text", None)


async def call(client, name, arguments):
    try:
        res = await client.call_tool(name, arguments)
    except ToolError as exc:
        return {"error": str(exc)}
    return {"result": res}


async def main():
    report = {"pages_dir": str(pages), "saved_dir": str(saved_dir)}
    server = get_mcp_server()
    async with Client(server) as client:
        report["tools"] = sorted(t.name for t in await client.list_tools())
        tool = next(t for t in await client.list_tools() if t.name == "d3_catalog")
        report["catalog_hints"] = dict(tool.annotations.model_dump(exclude_none=True)) if tool.annotations else {}
        for key in ("types", "examples", "templates", "formats"):
            report[key] = json.loads(text_of(await client.read_resource("uml://" + key)))

        report["generated"] = {}
        for dtype, (example, _template) in SAMPLES.items():
            for fmt in ("html", "svg"):
                got = await call(client, "generate_uml", {"diagram_type": dtype, "code": example, "output_format": fmt})
                if "error" in got:  # reported, so a failing test shows why
                    report["generated"][f"{dtype}.{fmt}"] = {"error": got["error"]}
                    continue
                res = got["result"]
                data = res.structured_content
                body = base64.b64decode(data["content_base64"])
                (pages / f"{dtype}.{fmt}").write_bytes(body)
                report["generated"][f"{dtype}.{fmt}"] = {
                    "source": data.get("source"),
                    "mime_type": data.get("mime_type"),
                    "output_format": data.get("output_format"),
                    "success": data.get("success"),
                    "attempts": data.get("attempts"),
                    "bytes": len(body),
                    "blocks": [block_info(b) for b in res.content],
                    "summary": res.content[0].text,
                }

        saved = await call(client, "generate_uml", {
            "diagram_type": "d3_architecture", "code": SAMPLES["d3_architecture"][0],
            "output_format": "html", "output_dir": str(saved_dir)})
        if "error" in saved:
            report["saved"] = {"error": saved["error"]}
        else:
            data = saved["result"].structured_content
            report["saved"] = {
                "local_path": data.get("local_path"),
                "has_content": "content_base64" in data,
                "summary": saved["result"].content[0].text,
            }

        report["fenced"] = bool((await call(client, "generate_uml", {
            "diagram_type": "d3_force",
            "code": "```json\n" + SAMPLES["d3_force"][1] + "\n```",
            "output_format": "svg"}))["result"].structured_content["success"])

        report["errors"] = {
            "unknown_node": (await call(client, "generate_uml", {
                "diagram_type": "d3_architecture", "output_format": "svg",
                "code": '{"nodes": [{"id": "a"}], "links": [{"from": "a", "to": "zzz"}]}'}))["error"],
            "not_json": (await call(client, "generate_uml", {
                "diagram_type": "d3_force", "code": "nodes: a, b", "output_format": "html"}))["error"],
            "html_for_builtin": (await call(client, "generate_uml", {
                "diagram_type": "class", "code": "@startuml\nclass A\n@enduml", "output_format": "html"}))["error"],
            # PNG is allowed via SVG→PNG raster; PDF remains unsupported for d3_*.
            "pdf_for_d3": (await call(client, "generate_uml", {
                "diagram_type": "d3_force", "code": SAMPLES["d3_force"][1], "output_format": "pdf"}))["error"],
            "bad_provider": (await call(client, "d3_catalog", {"provider": "oracle"}))["error"],
        }

        good = (await call(client, "validate_uml", {
            "diagram_type": "d3_architecture", "code": SAMPLES["d3_architecture"][0], "output_format": "html"}))["result"]
        bad = (await call(client, "validate_uml", {
            "diagram_type": "d3_architecture", "output_format": "svg",
            "code": '{"provider": "oracle", "nodes": [{"id": "a", "kind": "toaster"}, {"id": "a"}], "links": []}'}))["result"]
        report["validate"] = {"good": good.structured_content, "bad": bad.structured_content}

        catalog = (await call(client, "d3_catalog", {"provider": "aws"}))["result"]
        report["catalog"] = catalog.structured_content
        everything = (await call(client, "d3_catalog", {}))["result"]
        report["catalog_all_providers"] = sorted(everything.structured_content["providers"])

        batch = (await call(client, "generate_uml_batch", {"items": [
            {"diagram_type": "d3_force", "code": SAMPLES["d3_force"][1], "output_format": "svg"},
            {"diagram_type": "d3_topology", "code": '{"nodes": []}', "output_format": "svg"},
        ]}))["result"]
        report["batch"] = [
            {"index": r["index"], "success": bool(r.get("success")), "error": r.get("error")}
            for r in batch.structured_content["results"]
        ]

    # What `uml-mcp lint` says about the server a client just talked to.
    from mcp_core.quality.wire import fetch_surface, lint_surface

    lint = lint_surface(await fetch_surface())
    report["lint"] = {
        "grade": lint.grade,
        "score": lint.score,
        "issues": [f"{i.code}@{i.target}" for i in lint.issues],
        "suppressed": [
            [x["code"], x["target"], x["reason"]] for x in lint.suppressed
        ],
    }

    # The same server over HTTP (what a hosted MCP client uses): JSON-RPC to /mcp.
    from fastapi.testclient import TestClient
    from app import app

    def events(response):
        if "event-stream" not in response.headers.get("content-type", ""):
            return [response.json()]
        return [json.loads(line[5:].strip()) for line in response.text.splitlines()
                if line.startswith("data:") and line[5:].strip()]

    headers = {"Accept": "application/json, text/event-stream"}
    with TestClient(app) as http:
        def rpc(method, params, rid):
            body = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}
            return events(http.post("/mcp", json=body, headers=headers))[-1]

        listed = rpc("tools/list", {}, 1)
        called = rpc("tools/call", {"name": "generate_uml", "arguments": {
            "diagram_type": "d3_topology", "code": SAMPLES["d3_topology"][0], "output_format": "svg"}}, 2)
        result = called["result"]
        report["http"] = {
            "tools": sorted(t["name"] for t in listed["result"]["tools"]),
            "is_error": bool(result.get("isError")),
            "content_types": [c["type"] for c in result["content"]],
            "image_mime": [c.get("mimeType") for c in result["content"] if c["type"] == "image"],
            "structured_source": (result.get("structuredContent") or {}).get("source"),
        }
        (pages / "http_d3_topology.svg").write_bytes(base64.b64decode(result["structuredContent"]["content_base64"]))
    print("D3_JSON " + json.dumps(report))


asyncio.run(main())
"""


def run_driver(work: Path, settings: str = "") -> dict:
    """Run the real server with the D3 plugin enabled and return what its client saw."""
    work.mkdir(parents=True, exist_ok=True)
    config = work / "uml-mcp.yaml"
    config.write_text(f"plugins:\n  enabled: [d3]\n{settings}", encoding="utf-8")
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
            "FASTMCP_STATELESS_HTTP": "true",
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": str(ROOT) + os.pathsep + env.get("PYTHONPATH", ""),
        }
    )
    done = subprocess.run(
        [sys.executable, "-c", _DRIVER, str(D3_SRC), str(work)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert done.returncode == 0, f"stdout:\n{done.stdout}\nstderr:\n{done.stderr}"
    line = next(ln for ln in done.stdout.splitlines() if ln.startswith("D3_JSON "))
    return json.loads(line.removeprefix("D3_JSON "))


@pytest.fixture(scope="session")
def mcp_report(tmp_path_factory) -> dict:
    """What an MCP client sees from the real server with the D3 plugin (offline D3)."""
    return run_driver(
        tmp_path_factory.mktemp("d3-mcp"), "  settings:\n    d3: {d3_source: inline}\n"
    )
