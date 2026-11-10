import base64
import hashlib
import json

import pytest

from mcp_core.core.mermaid_source import mermaid_theme_from_source
from mcp_core.core.viewer_theme import apply_viewer_theme
from mcp_core.tools.diagram_export import download_diagram


def test_source_download_is_chunked_and_integrity_checked():
    code = "source text\n" * 8000
    chunks, offset, digest = [], 0, None
    while True:
        result = download_diagram(
            "mermaid", code, "source", offset=offset, sha256=digest
        )
        assert len(result["chunk"]) <= 32_000
        chunks.append(result["chunk"])
        digest = result["sha256"]
        offset = result["next_offset"]
        if offset == result["total"]:
            break
    raw = base64.b64decode("".join(chunks))
    assert raw.decode() == code
    assert hashlib.sha256(raw).hexdigest() == digest
    assert "error" in download_diagram("mermaid", "changed", "source", sha256=digest)
    assert "error" in download_diagram("mermaid", code, "source", offset=3)


def test_interactive_html_export_is_offline(d3_plugin):
    d3_plugin()
    code = json.dumps(
        {
            "nodes": [
                {"id": "a", "service": "tech:chatgpt"},
                {"id": "b", "service": "tech:claude"},
            ],
            "links": [{"from": "a", "to": "b"}],
        }
    )
    parts, offset, digest = [], 0, None
    while True:
        result = download_diagram(
            "d3_architecture", code, "html", offset=offset, sha256=digest
        )
        assert "error" not in result, result
        parts.append(result["chunk"])
        offset, digest = result["next_offset"], result["sha256"]
        if offset == result["total"]:
            break
    page = base64.b64decode("".join(parts)).decode()
    assert page.startswith("<!doctype html>")
    assert "cdn.jsdelivr.net" not in page
    assert "Save HTML" in page and "Save PNG" in page


def test_themes_override_previously_prepared_sources():
    assert "!theme cyborg" in apply_viewer_theme(
        "@startuml\n!theme cerulean\nA -> B\n@enduml", "sequence", "cyborg"
    )
    mermaid = apply_viewer_theme(
        "%%{init: {'theme': 'neutral'}}%%\ngraph TD; A-->B", "mermaid", "dark"
    )
    assert mermaid_theme_from_source(mermaid) == "dark"
    assert "103" in apply_viewer_theme(
        "vars: {d2-config: {theme-id: 0}}\na -> b", "d2", "dark"
    )
    assert (
        json.loads(apply_viewer_theme('{"nodes":[]}', "d3_force", "dark"))["theme"]
        == "dark"
    )


def test_c4_and_mermaid_playgrounds_keep_source_theme():
    from tools.kroki.kroki import Kroki

    client = Kroki()
    plantuml = client.get_playground_url("c4plantuml", "@startuml\nA -> B\n@enduml")
    assert plantuml and "/plantuml/uml/" in plantuml
    url = client.get_playground_url(
        "mermaid", "%%{init: {'theme':'dark'}}%%\ngraph TD; A-->B"
    )
    assert url and url.startswith("https://mermaid.live/edit#")


def test_bundled_cloud_and_ai_logos_are_inline():
    from xml.etree import ElementTree as ET

    from uml_mcp_plugin_d3 import D3Renderer

    services = ["aws:s3", "gcp:run", "tech:chatgpt", "tech:claude"]
    code = json.dumps(
        {
            "nodes": [{"id": str(i), "service": s} for i, s in enumerate(services)],
            "links": [],
        }
    )
    svg = D3Renderer().render("d3_architecture", code, "svg").content
    root = ET.fromstring(svg)
    ns = "{http://www.w3.org/2000/svg}"
    # each logo is embedded once as a <symbol> and drawn with <use>: nothing is fetched
    assert len(list(root.iter(f"{ns}symbol"))) == 4
    uses = [u.get("href") for u in root.iter(f"{ns}use")]
    assert len(uses) == 4 and all(h and h.startswith("#logo-") for h in uses)
    assert b"https://cdn" not in svg


def test_named_plantuml_theme_is_inserted_on_separate_line():
    from mcp_core.core.diagram_rendering import prepare_diagram_code

    source = "@startuml C4_Level_2_Containers\nA -> B: Request\n@enduml"
    prepared = prepare_diagram_code(source, "c4plantuml", "cerulean")
    assert prepared.splitlines()[:2] == [
        "@startuml C4_Level_2_Containers",
        "!theme cerulean",
    ]
    assert "!theme plain" in prepare_diagram_code(source, "c4plantuml", "light")


def test_linked_svg_can_produce_preview_without_loading_navigation_url():
    from mcp_core.apps.preview import compact_preview

    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="80"><a href="https://example.com"><text x="10" y="40">Readable linked label</text></a></svg>'
    assert compact_preview(base64.b64encode(svg).decode(), "image/svg+xml", 48000)
    image = svg.replace(
        b'<a href="https://example.com">', b'<image href="https://example.com/x.png"/>'
    )
    assert (
        compact_preview(base64.b64encode(image).decode(), "image/svg+xml", 48000)
        is None
    )


@pytest.mark.parametrize(
    "format,mime",
    [
        ("svg", "image/svg+xml"),
        ("png", "image/png"),
        ("html", "text/html"),
        ("pdf", "application/pdf"),
    ],
)
def test_d3_supports_all_viewer_file_exports(d3_plugin, format, mime):
    from io import BytesIO

    from PIL import Image
    from uml_mcp_plugin_d3.samples import SAMPLES

    d3_plugin()
    code = SAMPLES["d3_architecture"][0]
    parts, offset, digest = [], 0, None
    while True:
        result = download_diagram(
            "d3_architecture", code, format, offset=offset, sha256=digest
        )
        assert "error" not in result, result
        assert result["mime_type"] == mime
        parts.append(result["chunk"])
        offset, digest = result["next_offset"], result["sha256"]
        if offset == result["total"]:
            break
    raw = base64.b64decode("".join(parts))
    assert hashlib.sha256(raw).hexdigest() == digest
    if format == "pdf":
        assert raw.startswith(b"%PDF-") and b"/Subtype /Image" in raw
        assert b"/CreationDate" not in raw and b"/ModDate" not in raw
    elif format == "png":
        assert Image.open(BytesIO(raw)).width > 2000
    elif format == "html":
        assert b"cdn.jsdelivr.net" not in raw and b"plugin-download" in raw


def test_chunked_plugin_download_reuses_the_bounded_render_cache(
    d3_plugin, monkeypatch
):
    from uml_mcp_plugin_d3 import D3Renderer
    from uml_mcp_plugin_d3.samples import SAMPLES

    from mcp_core.core.render_cache import get_render_cache

    d3_plugin()
    monkeypatch.setenv("MCP_RENDER_CACHE_ENABLED", "1")
    cache = get_render_cache()
    cache.clear()
    calls = []
    render = D3Renderer.render

    def record(self, *args):
        calls.append(args)
        return render(self, *args)

    monkeypatch.setattr(D3Renderer, "render", record)
    try:
        code = SAMPLES["d3_architecture"][0]
        first = download_diagram("d3_architecture", code, "png")
        assert first["next_offset"] < first["total"]
        second = download_diagram(
            "d3_architecture",
            code,
            "png",
            offset=first["next_offset"],
            sha256=first["sha256"],
        )
        assert second["offset"] == first["next_offset"] and len(calls) == 1
        assert "error" in download_diagram(
            "d3_architecture",
            code,
            "png",
            offset=first["next_offset"],
            sha256="changed",
        )
        assert (
            download_diagram("mermaid", " source ", "source")["sha256"]
            != download_diagram("mermaid", "source", "source")["sha256"]
        )
    finally:
        cache.clear()


def _download_all(diagram_type: str, code: str, fmt: str) -> bytes:
    encoded, offset, digest = "", 0, None
    while True:
        part = download_diagram(diagram_type, code, fmt, offset=offset, sha256=digest)
        assert "error" not in part, part
        encoded += part["chunk"]
        offset, digest = part["next_offset"], part["sha256"]
        if offset >= part["total"]:
            return base64.b64decode(encoded)


def test_plugin_html_downloads_are_the_plugins_own_interactive_pages():
    """The MCP App loads a page too big to send inline through download_diagram.

    It must get the plugin's interactive page, not its SVG wrapped in HTML, for every
    plugin type that renders HTML (D3 has its own path, with D3 inlined).
    """
    from mcp_core.plugins.loader import RENDERERS, load_plugins

    load_plugins()
    checked = 0
    for diagram_type, renderer in sorted(RENDERERS.items()):
        spec = renderer.diagram_types[diagram_type]
        if "html" not in spec.formats or diagram_type.startswith("d3_"):
            continue
        assert spec.example is not None, diagram_type
        native = renderer.render(diagram_type, spec.example, "html").content
        assert _download_all(diagram_type, spec.example, "html") == native, diagram_type
        checked += 1
    assert checked >= 6
