"""Inspect exported chat events as data; never execute their requests or prompts."""

from __future__ import annotations

import base64
from collections import Counter
from io import BytesIO
from typing import Any

from PIL import Image

VIEWER_TOOLS = {
    "generate_uml",
    "generate_uml_image",
    "generate_uml_batch",
    "rerender_diagram",
}


def extract_calls(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Join streaming start/args/result events without counting a call twice."""
    if not isinstance(document, dict):
        raise TypeError("Expected a JSON object with a turns array")
    turns = document.get("turns")
    if not isinstance(turns, list):
        raise TypeError("Expected a chat export with a turns array")
    calls: list[dict[str, Any]] = []
    for turn in turns:
        if not isinstance(turn, dict) or not isinstance(turn.get("response"), list):
            raise TypeError("Each turn must have a response event array")
        pending: dict[str, dict[str, Any]] = {}
        for event in turn.get("response", []):
            if not isinstance(event, dict) or event.get("type") not in {
                "tool-call-start",
                "tool-call-args",
                "tool-result",
            }:
                continue
            call_id = event.get("toolCallId")
            if not isinstance(call_id, str):
                continue
            if call_id not in pending:
                call = {
                    "tool": event.get("toolName", "unknown"),
                    "arguments": {},
                    "result": None,
                }
                pending[call_id] = call
                calls.append(call)
            call = pending[call_id]
            raw = event.get("raw")
            args = event.get("args", raw.get("args") if isinstance(raw, dict) else None)
            if isinstance(args, dict):
                call["arguments"] = args
            if event["type"] == "tool-result":
                result = event.get("result")
                normalized: dict[str, Any] = (
                    dict(result)
                    if isinstance(result, dict)
                    else {"content": [{"type": "text", "text": str(result)}]}
                )
                call["result"] = normalized
                if event.get("isError"):
                    normalized["isError"] = True
    return calls


def preview_info(item: dict[str, Any]) -> dict[str, Any]:
    """Describe preview transport and dimensions, without claiming visual success."""
    info = {
        "diagram_type": item.get("diagram_type"),
        "output_format": item.get("output_format"),
        "mime_type": item.get("mime_type"),
        "flags": [],
    }
    flags = info["flags"]
    encoded = item.get("content_base64")
    if item.get("preview_resized"):
        flags.append("compact_preview")
    if isinstance(encoded, str) and encoded:
        try:
            content = base64.b64decode(encoded, validate=True)
            info["bytes"] = len(content)
            if str(item.get("mime_type")).split(";")[0] in {"image/png", "image/jpeg"}:
                with Image.open(BytesIO(content)) as image:
                    info["width"], info["height"] = image.size
                    if max(image.size) <= 160:
                        flags.append("tiny_raster")
                if item.get("output_format") == "svg":
                    flags.append("svg_request_has_raster_preview")
        except (ValueError, OSError, Image.DecompressionBombError):
            flags.append("invalid_image_bytes")
    elif item.get("output_format") == "html" and not (
        item.get("url") or item.get("local_path")
    ):
        flags.append("html_requires_app_or_followup")
    elif not encoded:
        flags.append("no_inline_preview")
    if item.get("source_omitted"):
        flags.append("source_omitted")
    return info


def summarize_calls(calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep render errors separate from thumbnail limitations and test evidence."""
    entries = []
    for index, call in enumerate(calls, 1):
        result = call.get("result")
        entry = {"call": index, "tool": call["tool"], "errors": [], "previews": []}
        if not isinstance(result, dict):
            entry["pending"] = True
        else:
            if result.get("isError"):
                entry["errors"].append(
                    " ".join(
                        str(c.get("text", ""))
                        for c in result.get("content", [])
                        if c.get("type") == "text"
                    )[:2000]
                )
            structured = result.get("structuredContent")
            if isinstance(structured, dict) and call["tool"] in VIEWER_TOOLS:
                rows = structured.get("results", [structured])
                for row in rows if isinstance(rows, list) else []:
                    if not isinstance(row, dict):
                        continue
                    if row.get("success") is False or row.get("error"):
                        entry["errors"].append(
                            f"Item {row.get('index', 0)}: {row.get('error', 'Render failed')}"
                        )
                    else:
                        entry["previews"].append(preview_info(row))
        entries.append(entry)
    return {
        "tool_calls": len(calls),
        "counts": dict(Counter(c["tool"] for c in calls)),
        "error_calls": sum(bool(e["errors"]) for e in entries),
        "entries": entries,
        "visual_verification": "UNVERIFIED: inspect previews and downloaded files in a capable host",
    }
