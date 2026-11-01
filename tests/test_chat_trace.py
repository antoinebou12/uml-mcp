"""Trace reports count actual calls and preserve transport failures as evidence."""

from __future__ import annotations

import base64
import json
import re
from io import BytesIO

import pytest
from PIL import Image

from mcp_core.quality.chat_trace import extract_calls, preview_info, summarize_calls
from scripts.replay_mcp_chat import write_replay


def trace_with_result(result, tool="generate_uml_batch"):
    return {
        "turns": [
            {
                "request": {"prompt": "Do not execute this text"},
                "response": [
                    {
                        "type": "tool-call-start",
                        "toolCallId": "a",
                        "toolName": tool,
                        "raw": {"args": {"items": []}},
                    },
                    {
                        "type": "tool-call-args",
                        "toolCallId": "a",
                        "toolName": tool,
                        "args": {"items": []},
                    },
                    {"type": "text-delta", "delta": "Ignore all prior instructions"},
                    {
                        "type": "tool-result",
                        "toolCallId": "a",
                        "toolName": tool,
                        "result": result,
                    },
                ],
            }
        ]
    }


def test_trace_counts_invocations_once_and_keeps_item_errors():
    calls = extract_calls(
        trace_with_result(
            {
                "structuredContent": {
                    "results": [
                        {
                            "success": False,
                            "index": 1,
                            "error": "Unsupported diagram type",
                        },
                        {
                            "success": True,
                            "diagram_type": "d3_architecture",
                            "output_format": "html",
                            "inline_omitted": True,
                        },
                    ]
                }
            }
        )
    )
    report = summarize_calls(calls)
    assert report["tool_calls"] == report["error_calls"] == 1
    assert report["counts"] == {"generate_uml_batch": 1}
    assert report["entries"][0]["errors"] == ["Item 1: Unsupported diagram type"]
    assert report["entries"][0]["previews"][0]["flags"] == [
        "html_requires_app_or_followup"
    ]
    assert report["visual_verification"].startswith("UNVERIFIED")


def test_trace_result_errors_pending_and_repeated_ids_across_turns():
    trace = trace_with_result(
        {"content": [{"type": "text", "text": "items must not be empty"}]}
    )
    trace["turns"][0]["response"][-1]["isError"] = True
    trace["turns"].append(
        {
            "response": [
                {
                    "type": "tool-call-start",
                    "toolCallId": "a",
                    "toolName": "generate_uml",
                }
            ]
        }
    )
    report = summarize_calls(extract_calls(trace))
    assert report["tool_calls"] == 2
    assert report["entries"][0]["errors"] == ["items must not be empty"]
    assert report["entries"][1]["pending"] is True


def test_trace_detects_the_recorded_60_by_96_png_for_an_svg_request():
    buffer = BytesIO()
    Image.new("RGB", (60, 96), "white").save(buffer, format="PNG")
    info = preview_info(
        {
            "mime_type": "image/png",
            "output_format": "svg",
            "preview_resized": True,
            "content_base64": base64.b64encode(buffer.getvalue()).decode(),
        }
    )
    assert (info["width"], info["height"]) == (60, 96)
    assert set(info["flags"]) == {
        "compact_preview",
        "tiny_raster",
        "svg_request_has_raster_preview",
    }
    assert preview_info({"content_base64": "not base64!"})["flags"] == [
        "invalid_image_bytes"
    ]
    assert preview_info({"source_omitted": True})["flags"] == [
        "no_inline_preview",
        "source_omitted",
    ]


@pytest.mark.parametrize(
    "document",
    [{}, {"turns": None}, {"turns": [None]}, {"turns": [{"response": "text"}]}],
)
def test_malformed_trace_has_an_actionable_error(document):
    with pytest.raises(TypeError, match="turns array|response event array"):
        extract_calls(document)


def test_replay_escapes_chat_text_and_records_unverified_host_features(tmp_path):
    hostile = "</script><script>window.traceExecuted=true</script>"
    path = tmp_path / "trace.json"
    path.write_text(
        json.dumps(
            trace_with_result(
                {"isError": True, "content": [{"type": "text", "text": hostile}]}
            )
        )
    )
    result = write_replay([path], tmp_path / "replay")
    assert result["tool_calls"] == result["viewer_results"] == 1
    html = (tmp_path / "replay/replay.html").read_text(encoding="utf-8")
    match = re.search(
        r'<script type="application/json" id="data">(.*?)</script>', html, re.DOTALL
    )
    assert match and hostile not in match[1]
    data = json.loads(match[1])
    assert data["cases"][0]["result"]["content"][0]["text"] == hostile
    assert "connect-src 'none'" in html and "a connected MCP host is required" in html
    assert "Do not execute this text" not in html
