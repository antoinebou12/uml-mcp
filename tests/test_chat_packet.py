"""Unit tests for stable chat display_markdown packets."""

from mcp_core.core.chat_packet import build_display_markdown


def test_build_display_markdown_full_packet():
    md = build_display_markdown(
        {
            "url": "https://example.com/d.png",
            "playground": "https://example.com/edit",
        }
    )
    assert md is not None
    assert "![diagram](https://example.com/d.png)" in md
    assert "**URL:** https://example.com/d.png" in md
    assert "**Playground:** https://example.com/edit" in md


def test_build_display_markdown_empty_without_urls():
    assert build_display_markdown({"url": None}) is None
    assert build_display_markdown({}) is None
