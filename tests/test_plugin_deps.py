"""The deps plugin: file detection, parsers, the SVG tree, the page and its safety."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from html import escape, unescape
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "examples/plugins/uml-mcp-plugin-deps/src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from uml_mcp_plugin_deps import DepsRenderer
from uml_mcp_plugin_deps.layout import build
from uml_mcp_plugin_deps.model import SpecError, docs_url
from uml_mcp_plugin_deps.parsers import parse
from uml_mcp_plugin_deps.samples import EXAMPLE, GRAPH, REQUIREMENTS, TEMPLATE

TYPE = "dependency_graph"

PACKAGE_LOCK = json.dumps(
    {
        "name": "web",
        "version": "1.0.0",
        "lockfileVersion": 3,
        "packages": {
            "": {
                "name": "web",
                "version": "1.0.0",
                "license": "MIT",
                "dependencies": {"express": "^4.21.0", "ui": "file:packages/ui"},
                "devDependencies": {"jest": "^29.0.0"},
                "peerDependencies": {"react": ">=18"},
            },
            "node_modules/express": {
                "version": "4.21.1",
                "license": "MIT",
                "dependencies": {"debug": "2.6.9", "qs": "^6.13.0"},
            },
            "node_modules/debug": {
                "version": "4.3.7",
                "license": "MIT",
                "dev": True,
                "dependencies": {"ms": "^2.1.3"},
            },
            "node_modules/express/node_modules/debug": {
                "version": "2.6.9",
                "license": "MIT",
                "dependencies": {"ms": "2.0.0"},
            },
            "node_modules/express/node_modules/ms": {
                "version": "2.0.0",
                "license": "MIT",
            },
            "node_modules/ms": {"version": "2.1.3", "license": "MIT", "dev": True},
            "node_modules/qs": {"version": "6.13.0", "license": "BSD-3-Clause"},
            "node_modules/jest": {
                "version": "29.7.0",
                "license": "MIT",
                "dev": True,
                "dependencies": {"debug": "^4.3.4"},
                "devDependencies": {"never-installed": "1.0.0"},
            },
            "node_modules/react": {"version": "18.3.1", "license": "MIT", "peer": True},
            "node_modules/ui": {"resolved": "packages/ui", "link": True},
            "packages/ui": {
                "name": "ui",
                "version": "0.1.0",
                "dependencies": {"qs": "^6"},
            },
        },
    }
)

UV_LOCK = """\
version = 1
requires-python = ">=3.12"

[[package]]
name = "app"
version = "0.1.0"
source = { editable = "." }
dependencies = [{ name = "httpx" }, { name = "uvicorn", extra = ["standard"] }]

[package.optional-dependencies]
cli = [{ name = "typer" }]

[package.dev-dependencies]
dev = [{ name = "pytest" }]

[package.metadata]
requires-dist = [
    { name = "httpx", specifier = ">=0.27" },
    { name = "uvicorn", extras = ["standard"], specifier = ">=0.30" },
    { name = "typer", marker = "extra == 'cli'", specifier = ">=0.12" },
]

[package.metadata.requires-dev]
dev = [{ name = "pytest", specifier = ">=8" }]

[[package]]
name = "httpx"
version = "0.27.2"
source = { registry = "https://pypi.org/simple" }
dependencies = [{ name = "anyio", version = "4.6.2" }]

[[package]]
name = "anyio"
version = "4.6.2"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "anyio"
version = "3.7.1"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "uvicorn"
version = "0.32.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [{ name = "h11" }]

[package.optional-dependencies]
standard = [{ name = "uvloop" }]

[[package]]
name = "h11"
version = "0.14.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "uvloop"
version = "0.21.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "typer"
version = "0.12.5"
source = { registry = "https://pypi.org/simple" }
dependencies = [{ name = "anyio", version = "3.7.1" }]

[[package]]
name = "pytest"
version = "8.3.3"
source = { registry = "https://pypi.org/simple" }
"""

PYPROJECT = """\
[project]
name = "My_App"
version = "2.0.0"
license = "Apache-2.0"
dependencies = ["requests[socks]>=2.31", "Typing_Extensions==4.12.2; python_version < '3.13'"]

[project.optional-dependencies]
docs = ["mkdocs>=1.6"]

[dependency-groups]
lint = ["ruff>=0.6"]
dev = ["pytest>=8", {include-group = "lint"}]

[tool.poetry.dependencies]
python = "^3.12"
rich = {version = "^13.0", optional = true}

[tool.poetry.group.test.dependencies]
hypothesis = "^6"
"""


def kinds(graph) -> dict[str, str]:
    return {pid: p.kind for pid, p in graph.packages.items() if not p.root}


# ------------------------------------------------------------------------- registration


def test_registers_one_sandboxed_type_with_html_and_svg():
    renderer = DepsRenderer()
    spec = renderer.diagram_types[TYPE]
    assert set(renderer.diagram_types) == {TYPE}
    assert spec.formats == ("html", "svg")
    assert spec.security_profile == "sandboxed"
    assert spec.example and spec.template
    assert renderer.validate(TYPE, spec.example) == []
    assert renderer.validate(TYPE, spec.template) == []


def test_bundled_by_default():
    from mcp_core.plugins.loader import BUNDLED_RENDERERS

    assert "deps" in BUNDLED_RENDERERS


def test_configure_bounds_max_nodes():
    renderer = DepsRenderer()
    renderer.configure({"max_nodes": 10})
    assert renderer.max_nodes == 10
    for bad in (0, 5000):
        with pytest.raises(ValueError, match="max_nodes"):
            renderer.configure({"max_nodes": bad})


def test_unknown_type_and_format_are_refused():
    renderer = DepsRenderer()
    with pytest.raises(ValueError, match="unknown diagram type"):
        renderer.render("other", EXAMPLE, "svg")
    with pytest.raises(ValueError, match="html or svg"):
        renderer.render(TYPE, EXAMPLE, "png")
    with pytest.raises(ValueError, match="invalid dependency_graph source"):
        renderer.render(TYPE, "", "svg")


# ------------------------------------------------------------------------------ parsers


def test_package_json_kinds_ranges_and_docs():
    graph = parse(EXAMPLE)
    assert graph.source_kind == "package.json"
    assert graph.root == "storefront"
    assert graph.packages["storefront"].license == "MIT"
    assert kinds(graph) == {
        "react": "runtime",
        "react-dom": "runtime",
        "zod": "runtime",
        "@tanstack/react-query": "runtime",
        "typescript": "peer",
        "fsevents": "optional",
        "vite": "dev",
        "vitest": "dev",
        "eslint": "dev",
    }
    ranges = {e.target: e.range for e in graph.edges}
    assert ranges["react"] == "^18.3.1"
    assert graph.packages["@tanstack/react-query"].docs == (
        "https://www.npmjs.com/package/@tanstack/react-query"
    )
    assert not graph.has_lock


def test_package_json_exact_versions_and_optional_peers():
    graph = parse(
        json.dumps(
            {
                "name": "x",
                "dependencies": {"left-pad": "1.3.0"},
                "peerDependencies": {"react": "^18"},
                "peerDependenciesMeta": {"react": {"optional": True}},
            }
        )
    )
    assert graph.packages["left-pad"].version == "1.3.0"
    assert graph.packages["react"].kind == "optional"


def test_package_json_problems_are_named():
    with pytest.raises(SpecError) as err:
        parse('{"name": "x", "dependencies": {"a": 1}, "devDependencies": []}')
    text = " ".join(err.value.problems)
    assert "package.json: dependencies.a must be a version range string" in text
    assert "devDependencies must be an object" in text


def test_package_lock_resolves_nested_versions_links_and_flags():
    graph = parse(PACKAGE_LOCK)
    assert graph.source_kind == "package-lock.json" and graph.has_lock
    edges = {(e.source, e.target): e for e in graph.edges}
    # express gets its own nested debug 2.6.9, which gets the nested ms 2.0.0
    assert ("express@4.21.1", "debug@2.6.9") in edges
    assert ("debug@2.6.9", "ms@2.0.0") in edges
    assert ("jest@29.7.0", "debug@4.3.7") in edges
    assert ("debug@4.3.7", "ms@2.1.3") in edges
    # the workspace link points at the package itself
    assert ("web", "ui@0.1.0") in edges and ("ui@0.1.0", "qs@6.13.0") in edges
    assert edges[("web", "express@4.21.1")].range == "^4.21.0"
    # a dependency's devDependencies are never installed
    assert not any(t.startswith("never-installed") for _, t in edges)
    k = kinds(graph)
    assert k["jest@29.7.0"] == "dev" and k["react@18.3.1"] == "peer"
    assert k["qs@6.13.0"] == "runtime" and k["debug@2.6.9"] == "runtime"
    assert graph.packages["qs@6.13.0"].license == "BSD-3-Clause"
    tree = build(graph)
    assert set(tree.duplicates) == {"debug", "ms"}
    assert tree.depth["ms@2.0.0"] == 3


def test_lockfile_v1_asks_for_a_newer_lock():
    with pytest.raises(SpecError, match="lockfileVersion 1 has no `packages` map"):
        parse('{"name": "x", "lockfileVersion": 1, "dependencies": {}}')


def test_pyproject_pep621_groups_and_poetry():
    graph = parse(PYPROJECT)
    assert graph.source_kind == "pyproject.toml"
    assert graph.root == "my-app"
    root = graph.packages["my-app"]
    assert (root.name, root.version, root.license) == ("My_App", "2.0.0", "Apache-2.0")
    k = kinds(graph)
    assert k["requests"] == "runtime" and k["typing-extensions"] == "runtime"
    assert k["mkdocs"] == "optional" and k["rich"] == "optional"
    assert k["pytest"] == "dev" and k["ruff"] == "dev" and k["hypothesis"] == "dev"
    assert "python" not in graph.packages
    te = graph.packages["typing-extensions"]
    assert te.version == "4.12.2" and "python_version" in te.marker
    assert graph.packages["requests"].extras == "socks"
    assert graph.packages["mkdocs"].group == "docs"
    assert set(graph.packages["ruff"].group.split(", ")) == {"lint", "dev"}
    assert te.docs == "https://pypi.org/project/typing-extensions/"


def test_pyproject_problems_say_where():
    bad = '[project]\nname = "x"\ndependencies = ["ok>=1", 3, "!!bad"]\n'
    with pytest.raises(SpecError) as err:
        parse(bad)
    assert err.value.problems == [
        "pyproject.toml: project.dependencies[1] must be a requirement string",
        "pyproject.toml: project.dependencies[2]: could not parse requirement '!!bad'",
    ]
    cycle = '[project]\nname = "x"\n[dependency-groups]\na = [{include-group = "a"}]\n'
    with pytest.raises(SpecError, match="cycle"):
        parse(cycle)


def test_this_repos_pyproject_renders():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    graph = parse(text)
    assert graph.root == "uml-mcp"
    assert graph.packages["fastmcp-slim"].kind == "runtime"
    assert graph.packages["fastmcp-slim"].extras == "server"
    assert any(p.kind == "dev" for p in graph.packages.values())
    renderer = DepsRenderer()
    for fmt in ("svg", "html"):
        assert renderer.render(TYPE, text, fmt).content


def test_requirements_txt_lines():
    graph = parse(
        REQUIREMENTS
        + "pkg-a==1.0 \\\n    --hash=sha256:abc\n"
        + "-e git+https://example.com/repo.git#egg=local_pkg\n"
        + "--index-url https://example.com/simple\n"
        + "lib @ https://example.com/lib-1.0.whl\n"
    )
    assert graph.source_kind == "requirements.txt"
    assert graph.packages["uvicorn"].version == "0.32.0"
    assert graph.packages["uvicorn"].extras == "standard"
    assert "python_version" in graph.packages["httpx"].marker
    assert graph.packages["pkg-a"].version == "1.0"
    assert "local-pkg" in graph.packages
    ranges = {e.target: e.range for e in graph.edges}
    assert ranges["fastapi"] == ">=0.115"
    assert ranges["lib"].startswith("@ https://")
    assert any("dev.txt" in note for note in graph.notes)


def test_requirements_errors_carry_line_numbers():
    with pytest.raises(SpecError) as err:
        parse("requests==2\n!!!nope\n")
    assert err.value.problems == [
        "requirements.txt line 2: could not parse requirement '!!!nope'"
    ]
    with pytest.raises(SpecError, match="could not detect the file kind"):
        parse("!!!\n???\n")
    with pytest.raises(SpecError, match="no requirements found"):
        parse("# only a comment\n--index-url https://example.com\n")


def test_uv_lock_versions_extras_groups_and_ranges():
    graph = parse(UV_LOCK)
    assert graph.source_kind == "uv.lock" and graph.root == "app"
    edges = {(e.source, e.target): e for e in graph.edges}
    assert edges[("app", "httpx@0.27.2")].range == ">=0.27"
    assert edges[("app", "pytest@8.3.3")].range == ">=8"
    assert edges[("app", "typer@0.12.5")].range == ">=0.12"
    # the dependency picks the version the lock pinned for it
    assert ("httpx@0.27.2", "anyio@4.6.2") in edges
    assert ("typer@0.12.5", "anyio@3.7.1") in edges
    # uvicorn[standard] pulls in its standard extra
    assert ("uvicorn@0.32.0", "uvloop@0.21.0") in edges
    k = kinds(graph)
    assert k["typer@0.12.5"] == "optional" and k["anyio@3.7.1"] == "optional"
    assert k["pytest@8.3.3"] == "dev" and k["uvloop@0.21.0"] == "runtime"
    assert graph.packages["typer@0.12.5"].group == "cli"
    assert set(build(graph).duplicates) == {"anyio"}


def test_this_repos_uv_lock_renders():
    text = (ROOT / "uv.lock").read_text(encoding="utf-8")
    graph = parse(text)
    assert graph.root == "uml-mcp"
    tree = build(graph)
    assert tree.total == len(graph.packages)  # every locked package is reachable
    assert DepsRenderer().render(TYPE, text, "svg").content.startswith(b"<svg")


def test_generic_graph_and_its_errors():
    graph = parse(GRAPH)
    assert (
        graph.source_kind == "JSON graph"
        and graph.title == "billing-service dependencies"
    )
    assert graph.packages["pytest@8.3.3"].kind == "dev"
    assert graph.packages["fastapi@0.115.4"].name == "fastapi"
    assert graph.packages["anyio@3.7.1"].docs == "https://pypi.org/project/anyio/"
    bad = {
        "root": "a",
        "nodes": [
            {"id": "a"},
            {"id": "a"},
            {"id": "b", "kind": "weird", "docs": "http://x"},
            {"version": "1"},
        ],
        "edges": [{"from": "a", "to": "zzz"}],
    }
    with pytest.raises(SpecError) as err:
        parse(json.dumps(bad))
    text = " | ".join(err.value.problems)
    assert "duplicate id 'a'" in text
    assert "kind must be runtime, dev, optional or peer" in text
    assert "docs must be an https:// URL" in text
    assert "nodes[3] needs a non-empty string id" in text
    assert "unknown node 'zzz' (known ids: a, b)" in text
    assert err.value.problems[0].startswith("JSON graph: ")


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("", "the source is empty"),
        (
            '{"name": "x",',
            "looks like JSON but could not be parsed: .* at line 1, column 14",
        ),
        ("[1, 2]", "JSON source must be an object"),
        ('{"theme": "dark"}', "could not tell which file this JSON is"),
        ("[project\nname = 1\n", r"looks like TOML but could not be parsed: .*line 1"),
        ("[tool.other]\nx = 1\n[x]\n", ""),
        (
            '[[package]]\nname = "a"\n[metadata]\nlock-version = "2.0"\n',
            "poetry.lock is not supported",
        ),
        ('[[package]]\nname = "a"\nversion = "1"\n', "no project package found"),
        ("[something]\nx = 1\n", "could not tell which TOML file"),
    ],
)
def test_detection_messages(source, message):
    if not message:
        # a pyproject with only tool tables still parses, and says it has no dependencies
        assert "no dependencies" in parse(source).notes[0]
        return
    with pytest.raises(SpecError) as err:
        parse(source)
    assert re.search(message, err.value.problems[0]), err.value.problems


def test_docs_urls_only_for_valid_names():
    assert docs_url("pypi", "Foo.Bar_baz") == "https://pypi.org/project/foo-bar-baz/"
    assert docs_url("npm", "@scope/pkg") == "https://www.npmjs.com/package/@scope/pkg"
    assert docs_url("npm", "bad name/../x") == ""
    assert docs_url("", "anything") == ""


# ---------------------------------------------------------------------------- rendering


def _svg(source: str, **settings) -> str:
    renderer = DepsRenderer()
    if settings:
        renderer.configure(settings)
    return renderer.render(TYPE, source, "svg").content.decode()


def test_svg_is_a_layered_tree_with_legend_and_badges():
    text = _svg(GRAPH)
    root = ET.fromstring(text)
    assert root.tag.endswith("svg") and "<script" not in text
    assert "billing-service dependencies" in text
    assert "7 packages · 3 direct · 4 transitive · 1 with several versions" in text
    assert "several versions" in text and "×2" in text
    assert "BSD-3-Clause" in text
    ns = "{http://www.w3.org/2000/svg}"
    pos = {}
    for g in root.iter(f"{ns}g"):
        label = g.find(f"{ns}text")
        if "node" in (g.get("class") or "") and label is not None:
            moved = re.match(r"translate\(([-\d.]+)", g.get("transform", ""))
            assert moved
            pos[label.text] = float(moved.group(1))
    # columns grow from the project to the deepest level
    assert (
        pos["billing-service@1.0.0"] < pos["fastapi@0.115.4"] < pos["starlette@0.41.2"]
    )
    assert pos["starlette@0.41.2"] < pos["anyio@4.6.2"]
    assert pos["pytest@8.3.3"] == pos["fastapi@0.115.4"]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_svg_themes(theme):
    data = json.loads(EXAMPLE)
    data["theme"] = theme
    text = _svg(json.dumps(data))
    assert f'class="deps-svg {theme}"' in text


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_static_svg_rasterizes_with_visible_colours(theme):
    from io import BytesIO

    import resvg_py
    from PIL import Image
    from uml_mcp_plugin_deps.svg import PALETTES

    data = json.loads(EXAMPLE)
    data["theme"] = theme
    text = _svg(json.dumps(data))
    png = resvg_py.svg_to_bytes(svg_string=text)
    image = Image.open(BytesIO(png)).convert("RGB")
    expected = tuple(bytes.fromhex(PALETTES[theme]["bg"][1:]))
    assert image.getpixel((0, 0)) == expected
    assert image.convert("L").getextrema()[0] != image.convert("L").getextrema()[1]


def test_cap_keeps_the_closest_packages_and_says_so():
    text = _svg(PACKAGE_LOCK, max_nodes=4)
    assert "Showing 3 of 9 packages" in text and "max_nodes" in text
    page = DepsRenderer()
    page.configure({"max_nodes": 4})
    html = page.render(TYPE, PACKAGE_LOCK, "html").content.decode()
    assert "Showing 3 of 9 packages" in html
    data = json.loads(
        _grab(r'<script type="application/json" id="deps-data">(.*?)</script>', html)
    )
    assert len(data["nodes"]) == 4
    assert all(n["d"] <= 1 for n in data["nodes"])


def _grab(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.DOTALL)
    assert match, pattern
    return match.group(1)


HOSTILE = json.dumps(
    {
        "root": "app",
        "title": "</script><script>alert(1)</script>",
        "nodes": [
            {"id": "app"},
            {"id": "<img src=x onerror=alert(1)>", "license": "<b>MIT</b>"},
        ],
        "edges": [
            {"from": "app", "to": "<img src=x onerror=alert(1)>", "range": "</script>"}
        ],
    }
)


def test_hostile_names_stay_text():
    svg = _svg(HOSTILE)
    ET.fromstring(svg)
    assert "<img" not in svg and "<script" not in svg
    html = DepsRenderer().render(TYPE, HOSTILE, "html").content.decode()
    data = _grab(r'<script type="application/json" id="deps-data">(.*?)</script>', html)
    assert "<" not in data and json.loads(data)["nodes"][1]["name"].startswith("<img")
    assert html.count("<script") == 2
    assert "<img" not in html.split("<script", 1)[0]


def test_page_is_csp_locked_and_offline():
    html = DepsRenderer().render(TYPE, EXAMPLE, "html").content.decode()
    csp = unescape(
        _grab(r'http-equiv="Content-Security-Policy" content="([^"]+)"', html)
    )
    script = _grab(r"<script>(.*?)</script>", html)
    style = _grab(r"<style>(.*?)</style>", html)
    for text in (script, style):
        digest = base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
        assert f"sha256-{digest}" in csp
    assert "default-src 'none'" in csp
    assert "fetch(" not in script and "XMLHttpRequest" not in script
    assert ' style="' not in html


# ------------------------------------------------------------------------------ browser

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as pw:
        chromium = pw.chromium.launch()
        yield chromium
        chromium.close()


def _open(browser, source: str, width: int = 1200, height: int = 800):
    page = browser.new_page(viewport={"width": width, "height": height})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.set_content(DepsRenderer().render(TYPE, source, "html").content.decode())
    return page, errors


def test_page_tree_search_card_path_and_docs(browser):
    page, errors = _open(browser, UV_LOCK)
    assert page.evaluate("window.__deps.visible().length") == 9
    assert page.locator("#canvas .node").count() == 9
    # search, then Enter selects the first hit and opens its card
    page.fill("#search", "uvloop")
    assert page.inner_text("#found") == "1 found"
    page.press("#search", "Enter")
    assert page.is_visible("#card")
    assert page.inner_text("#card-title") == "uvloop"
    assert "app › uvicorn › uvloop" in page.inner_text("#card-body")
    assert "required by · 1" in page.inner_text("#card-body").lower()
    # the path from the project is highlighted, the rest dimmed
    assert page.locator(".node.path").count() == 3
    assert page.locator(".edge.path").count() == 2
    assert page.locator(".node.sel").count() == 1
    # Open documentation goes to the registry page
    page.evaluate(
        "() => { window.__opened = []; window.open = (u) => { window.__opened.push(u); }; }"
    )
    page.click("#card-docs")
    assert page.evaluate("window.__opened") == ["https://pypi.org/project/uvloop/"]
    # picking a dependent from the card moves the selection
    page.click("#card-body .list button")
    assert page.inner_text("#card-title") == "uvicorn"
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    assert page.is_hidden("#card")
    assert not errors


def test_page_collapse_filters_view_theme_and_export(browser):
    page, errors = _open(browser, PACKAGE_LOCK)
    total = page.evaluate("window.__deps.visible().length")
    express = page.evaluate("window.__deps.index('express@4.21.1')")
    page.click(f'[data-toggle="{express}"]')
    collapsed = page.evaluate("window.__deps.visible().length")
    assert collapsed < total
    assert "debug@2.6.9" not in page.evaluate("window.__deps.visible()")
    page.click(f'[data-toggle="{express}"]')
    assert page.evaluate("window.__deps.visible().length") == total
    # hide dev dependencies
    page.click('[data-kind="dev"]')
    assert page.get_attribute('[data-kind="dev"]', "aria-pressed") == "false"
    assert "jest@29.7.0" not in page.evaluate("window.__deps.visible()")
    page.click('[data-kind="dev"]')
    # duplicates are flagged
    assert page.locator(".node.dup").count() == 4
    # force view keeps every edge, then back to the tree
    page.click("#view-graph")
    assert page.get_attribute("#view-graph", "aria-pressed") == "true"
    assert page.locator("#canvas .edge").count() == page.evaluate(
        "JSON.parse(document.getElementById('deps-data').textContent).edges.length"
    )
    page.click("#view-tree")
    # theme toggles
    before = page.get_attribute("html", "data-theme")
    page.click("#theme")
    assert page.get_attribute("html", "data-theme") != before
    # exports: a standalone SVG and a page that reloads
    svg = page.evaluate("window.__deps.svgExport().text")
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg") and "<style>" in svg and "web@1.0.0" in svg
    html = page.evaluate("window.__deps.htmlExport()")
    assert html.startswith("<!doctype html>") and 'id="deps-data"' in html
    with page.expect_download() as download:
        page.click("#export")
        page.click("#save-svg")
    assert download.value.suggested_filename == "web-1-0-0-dependencies.svg"
    reopened = browser.new_page()
    reopened.on("pageerror", lambda e: errors.append(str(e)))
    reopened.set_content(html)
    assert reopened.locator("#canvas .node").count() == total
    reopened.close()
    assert not errors


def test_page_fits_a_small_chat_frame(browser):
    source = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    page, errors = _open(browser, source, 560, 430)
    canvas = page.locator("#canvas").bounding_box()
    assert canvas and canvas["height"] > 250 and canvas["width"] == 560
    assert page.evaluate("document.documentElement.scrollWidth") <= 560
    # the project is on screen at a readable scale
    assert page.evaluate("window.__deps.scale") >= 0.7
    root = page.locator("#canvas .node.root").bounding_box()
    assert root and 0 <= root["x"] < 560 and canvas["y"] <= root["y"] < 430
    page.evaluate("window.__deps.select(1)")
    card = page.locator("#card").bounding_box()
    assert card and card["x"] >= 0 and card["x"] + card["width"] <= 560
    assert card["y"] + card["height"] <= 430
    # the selected package stays visible above the card
    sel = page.locator("#canvas .node.sel").bounding_box()
    assert sel and canvas["y"] <= sel["y"] and sel["y"] + sel["height"] <= card["y"]
    page.click("#view-graph")
    page.click("#fit")
    assert not errors


def test_embedded_page_uses_the_host_bridge(browser):
    page_html = DepsRenderer().render(TYPE, EXAMPLE, "html").content.decode()
    host = browser.new_page(viewport={"width": 700, "height": 520})
    errors: list[str] = []
    host.on("pageerror", lambda e: errors.append(str(e)))
    host.set_content(
        "<script>window.msgs=[];addEventListener('message',e=>msgs.push(e.data))</script>"
        f'<iframe id="f" width="560" height="430" srcdoc="{escape(page_html, quote=True)}"></iframe>'
    )
    frame = host.frame_locator("#f")
    frame.locator("#canvas .node.root").wait_for()
    inner = host.frames[1]
    assert inner.evaluate("document.documentElement.dataset.embedded") == "1"
    assert inner.is_hidden("h1")
    host.wait_for_function("msgs.some(m => m.type === 'uml-mcp/plugin-ready')")
    index = inner.evaluate("window.__deps.index('react')")
    inner.evaluate(f"window.__deps.select({index})")
    inner.evaluate("() => { window.open = () => null; }")
    frame.locator("#card-docs").click()
    host.wait_for_function("msgs.some(m => m.type === 'uml-mcp/open-link')")
    link = host.evaluate("msgs.find(m => m.type === 'uml-mcp/open-link').url")
    assert link == "https://www.npmjs.com/package/react"
    assert not errors
    host.close()


def test_template_page_has_no_errors(browser):
    page, errors = _open(browser, TEMPLATE)
    assert page.locator("#canvas .node").count() == 2
    assert not errors
