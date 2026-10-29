import base64
from io import BytesIO

from PIL import Image

from mcp_core.apps.preview import compact_preview
from mcp_core.tools.tool_decorator import _as_mcp_tool_result


def test_large_valid_image_still_displays():
    raw = BytesIO()
    Image.effect_noise((1000, 700), 80).save(raw, format="PNG")
    original = base64.b64encode(raw.getvalue()).decode()
    assert len(original) > 48_000
    result = _as_mcp_tool_result(
        "generate_uml",
        {
            "code": "graph TD; A-->B",
            "content_base64": original,
            "mime_type": "image/png",
            "url": "https://example.com/full.png",
        },
    )
    data = result.structured_content
    assert data["preview_resized"] is True
    assert len(data["content_base64"]) <= 48_000
    assert data["url"] == "https://example.com/full.png"
    Image.open(BytesIO(base64.b64decode(data["content_base64"]))).verify()
    import json

    assert (
        len(json.dumps(data))
        + sum(len(getattr(c, "data", getattr(c, "text", ""))) for c in result.content)
        < 150_000
    )


def test_large_svg_produces_png():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"><rect width="400" height="200" fill="red"/><!--'
        + "x" * 50_000
        + "--></svg>"
    )
    result = compact_preview(
        base64.b64encode(svg.encode()).decode(), "image/svg+xml", 48_000
    )
    assert result and len(result) <= 48_000
    assert base64.b64decode(result).startswith(b"\x89PNG")


def test_unsupported_content_is_not_executed():
    assert compact_preview("A" * 50_000, "text/html", 48_000) is None


def test_svg_external_resources_are_not_loaded():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><image href="file:///private.png"/></svg>'
    assert (
        compact_preview(
            base64.b64encode(svg.encode()).decode(), "image/svg+xml", 48_000
        )
        is None
    )


def test_escaped_source_and_diagnostics_fit_initial_budget():
    import json

    from mcp_core.tools.tool_decorator import _bounded_viewer_result

    data = _bounded_viewer_result(
        {
            "code": "\u263a" * 12_000,
            "content_base64": "A" * 48_000,
            "attempts": [{"error": "x" * 100_000}],
        }
    )
    assert len(json.dumps(data)) + len(data["content_base64"]) < 125_000
    assert data["source_omitted"]


def test_app_only_tools_do_not_count_toward_model_token_budget():
    from mcp_core.quality.wire import Surface, token_estimate

    plain = Surface("s", "1", tools=[{"name": "render"}])
    with_app = Surface(
        "s",
        "1",
        tools=[
            {"name": "render"},
            {"name": "viewer", "_meta": {"ui": {"visibility": ["app"]}}},
        ],
    )
    assert token_estimate(plain) == token_estimate(with_app)
