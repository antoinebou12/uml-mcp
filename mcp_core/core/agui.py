"""AG-UI (Agent-User Interaction Protocol) event emission for diagram generation.

This module wraps the synchronous ``generate_from_request`` render pipeline and exposes
it as an async stream of AG-UI compatible events. Consumers (chat frontends such as
CopilotKit, the AG-UI terminal client, or any SSE reader) subscribe to the stream and
render an inline, live diagram instead of a click-through URL.

The event names here follow the AG-UI core event model (``RUN_STARTED``, ``STEP_STARTED``,
``TOOL_CALL_*``, ``STATE_*``, ``RUN_FINISHED``, ``RUN_ERROR``, ``CUSTOM``). The module is
transport-agnostic: it yields plain dicts and app.py is responsible for serializing them
over SSE/WebSocket. This lets the same emitter serve both the single-request streaming
route and the canonical start + events URL pair.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from .diagram_service import DiagramRequest, generate_from_request

logger = logging.getLogger(__name__)

# AG-UI core event names emitted by this module.
RUN_STARTED = "RUN_STARTED"
STEP_STARTED = "STEP_STARTED"
STEP_FINISHED = "STEP_FINISHED"
TOOL_CALL_START = "TOOL_CALL_START"
TOOL_CALL_RESULT = "TOOL_CALL_RESULT"
STATE_SNAPSHOT = "STATE_SNAPSHOT"
CUSTOM = "CUSTOM"
RUN_FINISHED = "RUN_FINISHED"
RUN_ERROR = "RUN_ERROR"

# Required (non-null) fields on a successful render that the generative-UI payload needs.
_RENDER_API_FIELDS = (
    "code",
    "url",
    "playground",
    "local_path",
    "content_base64",
    "source",
    "output_format",
)


def new_run_id() -> str:
    """Return a fresh run id (UUID4 hex)."""
    return uuid.uuid4().hex


def _event(event_type: str, *, run_id: str, **data: Any) -> dict[str, Any]:
    """Build a single AG-UI event dict with the shared envelope fields."""
    payload: dict[str, Any] = {
        "type": event_type,
        "run_id": run_id,
        "timestamp": int(time.time() * 1000),
    }
    payload.update(data)
    return payload


def _public_result(result: dict[str, Any]) -> dict[str, Any]:
    """Trim a render result dict to the API-facing fields AG-UI consumers need.

    Keeps the diagram code, URL(s), inline base64, source, and cache flag while dropping
    transient fields such as ``cache_lookup_ms`` and ``instance_type`` that are irrelevant
    to a UI.
    """
    public = {key: result.get(key) for key in _RENDER_API_FIELDS}
    public["success"] = bool(result.get("success")) and not bool(result.get("error"))
    public["cache_hit"] = bool(result.get("cache_hit"))
    return public


def _tool_call_id(diagram_type: str) -> str:
    """Stable-ish id for the ``generate_uml`` tool call for correlation in events."""
    return f"uml-{new_run_id()[:12]}"


async def diagram_generation_events(
    req: DiagramRequest,
    *,
    run_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield AG-UI events for a single diagram render, running in a worker thread.

    The synchronous ``generate_from_request`` performs network I/O (Kroki/PlantUML) and
    renders SVG, so it is offloaded with ``asyncio.to_thread`` to keep the event loop free.

    Args:
        req: The validated tool-level render request.
        run_id: Optional explicit run id; a fresh one is generated when omitted.

    Yields:
        AG-UI event dicts in execution order.
    """
    run_id = run_id or new_run_id()
    start = time.perf_counter()
    diag = (req.diagram_type or "").strip().lower() or "unknown"

    yield _event(RUN_STARTED, run_id=run_id, agent="uml-mcp", diagram_type=diag)

    step_id = "render"
    yield _event(
        STEP_STARTED,
        run_id=run_id,
        step_id=step_id,
        name="Render diagram",
        diagram_type=diag,
    )

    # TOOL_CALL_START mirrors what the MCP generate_uml tool does, so AG-UI consumers see
    # the same "tool" semantics they would from the MCP tool.
    tool_call_id = _tool_call_id(diag)
    yield _event(
        TOOL_CALL_START,
        run_id=run_id,
        tool_call_id=tool_call_id,
        tool="generate_uml",
        args={
            "diagram_type": diag,
            "output_format": req.output_format,
            "theme": req.theme,
            "scale": req.scale,
        },
    )

    # STATE_SNAPSHOT carries the editable diagram source so the frontend can render it as
    # an in-place, editable editor (shared state model).
    yield _event(
        STATE_SNAPSHOT,
        run_id=run_id,
        state={
            "diagram_type": diag,
            "code": req.code,
            "output_format": req.output_format,
            "theme": req.theme,
            "scale": req.scale,
        },
    )

    try:
        result = await asyncio.to_thread(generate_from_request, req)
    except Exception as exc:
        logger.exception("AG-UI render failed")
        yield _event(
            RUN_ERROR,
            run_id=run_id,
            error={
                "code": "RENDER_FAILED",
                "message": f"Unexpected render failure: {type(exc).__name__}: {exc!s}",
                "retryable": False,
                "diagram_type": diag,
            },
        )
        return

    duration_ms = round((time.perf_counter() - start) * 1000.0, 3)

    if result.get("error"):
        error_detail = result.get("error_detail") or {}
        yield _event(
            RUN_ERROR,
            run_id=run_id,
            error={
                "code": error_detail.get("code", "RENDER_FAILED"),
                "message": str(result["error"]),
                "retryable": bool(error_detail.get("retryable", False)),
                "diagram_type": diag,
                "line": error_detail.get("line"),
                "column": error_detail.get("column"),
                "suggestion": error_detail.get("suggestion"),
            },
        )
        return

    output = _public_result(result)
    yield _event(
        TOOL_CALL_RESULT,
        run_id=run_id,
        tool_call_id=tool_call_id,
        tool="generate_uml",
        output=output,
        duration_ms=duration_ms,
    )

    yield _event(
        STEP_FINISHED,
        run_id=run_id,
        step_id=step_id,
        status="success",
        duration_ms=duration_ms,
    )

    # CUSTOM event carrying the generative-UI payload: the frontend renders this inline
    # (image via base64 or URL) rather than sending the user to a click-through link.
    yield _event(
        CUSTOM,
        run_id=run_id,
        message="Diagram generated",
        payload={
            "kind": "diagram",
            "render_format": output.get("output_format") or req.output_format,
            "content_base64": output.get("content_base64"),
            "url": output.get("url"),
            "playground": output.get("playground"),
            "local_path": output.get("local_path"),
            "source": output.get("source"),
            "diagram_type": diag,
            "code": output.get("code"),
        },
        cache_hit=output["cache_hit"],
    )

    yield _event(
        RUN_FINISHED,
        run_id=run_id,
        outcome={"type": "success"},
        output=output,
        duration_ms=duration_ms,
    )


def sse_frame(event: dict[str, Any]) -> str:
    """Serialize an AG-UI event as a single SSE ``data:`` frame."""
    import json

    return f"data: {json.dumps(event, default=str)}\n\n"


__all__ = [
    "CUSTOM",
    "RUN_ERROR",
    "RUN_FINISHED",
    "RUN_STARTED",
    "STATE_SNAPSHOT",
    "STEP_FINISHED",
    "STEP_STARTED",
    "TOOL_CALL_RESULT",
    "TOOL_CALL_START",
    "diagram_generation_events",
    "new_run_id",
    "sse_frame",
]
