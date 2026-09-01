"""
Tests for the AG-UI (Agent-User Interaction Protocol) event streaming endpoints.
"""

import json
import os

os.environ["TESTING"] = "true"

import pytest
from fastapi.testclient import TestClient

from app import _AGUI_RUNS, app

client = TestClient(app)


def _success_result() -> dict:
    """A successful render result, mirroring what generate_from_request returns."""
    return {
        "code": "@startuml\nclass Test\n@enduml",
        "url": "https://kroki.io/plantuml/svg/abc123",
        "playground": "https://playground.example.com/demo",
        "local_path": None,
        "content_base64": "PHN2Zz5oaTwvc3ZnPg==",
        "source": "kroki",
        "output_format": "svg",
        "success": True,
        "cache_hit": False,
    }


def _error_result() -> dict:
    return {
        "error": "Cannot connect to Kroki",
        "error_detail": {
            "code": "RENDER_FAILED",
            "message": "Cannot connect to Kroki",
            "diagram_type": "mermaid",
            "backend": "kroki",
            "retryable": True,
            "line": None,
            "column": None,
            "suggestion": None,
        },
    }


def _parse_events(response) -> list[dict]:
    events = []
    for line in response.text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


def _mock_render(monkeypatch, result: dict) -> None:
    from mcp_core.core import agui

    monkeypatch.setattr(agui, "generate_from_request", lambda req: result)


def test_agui_generate_streams_full_event_sequence(monkeypatch):
    """POST /ag-ui/generate returns the full AG-UI lifecycle as SSE."""
    _mock_render(monkeypatch, _success_result())
    response = client.post(
        "/ag-ui/generate",
        json={
            "diagram_type": "mermaid",
            "code": "graph TD; A-->B;",
            "output_format": "svg",
        },
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    events = _parse_events(response)
    types = [e["type"] for e in events]
    assert types[0] == "RUN_STARTED"
    assert types[-1] == "RUN_FINISHED"
    assert "STEP_STARTED" in types
    assert "STEP_FINISHED" in types
    assert "TOOL_CALL_START" in types
    assert "TOOL_CALL_RESULT" in types
    assert "STATE_SNAPSHOT" in types
    assert "CUSTOM" in types

    # Every event shares the same run_id.
    run_ids = {e.get("run_id") for e in events}
    assert len(run_ids) == 1

    # The CUSTOM event carries the generative-UI payload (inline base64 + URL + source).
    custom = next(e for e in events if e["type"] == "CUSTOM")
    assert custom["payload"]["content_base64"] == _success_result()["content_base64"]
    assert custom["payload"]["url"].endswith("abc123")
    assert custom["payload"]["diagram_type"] == "mermaid"
    assert custom["payload"]["code"].startswith("@startuml")

    # STATE_SNAPSHOT exposes the editable source for in-place editing.
    state = next(e for e in events if e["type"] == "STATE_SNAPSHOT")
    assert state["state"]["code"] == "graph TD; A-->B;"
    assert state["state"]["output_format"] == "svg"


def test_agui_generate_runs_in_worker_thread(monkeypatch):
    """The synchronous render is offloaded so the event loop is not blocked."""
    import threading

    from mcp_core.core import agui

    seen_thread = {}

    def fake_render(req):
        seen_thread["name"] = threading.current_thread().name
        return _success_result()

    monkeypatch.setattr(agui, "generate_from_request", fake_render)
    response = client.post(
        "/ag-ui/generate",
        json={"diagram_type": "class", "code": "@startuml\nclass A\n@enduml"},
    )
    assert response.status_code == 200
    assert seen_thread["name"] != "MainThread"


def test_agui_generate_emits_run_error(monkeypatch):
    """A failed render surfaces as a RUN_ERROR terminal event."""
    _mock_render(monkeypatch, _error_result())
    response = client.post(
        "/ag-ui/generate",
        json={
            "diagram_type": "mermaid",
            "code": "graph TD; A-->B;",
        },
    )
    assert response.status_code == 200
    events = _parse_events(response)
    assert events[-1]["type"] == "RUN_ERROR"
    assert events[-1]["error"]["message"] == "Cannot connect to Kroki"
    assert events[-1]["error"]["retryable"] is True


def test_agui_start_then_events(monkeypatch):
    """start-then-subscribe pattern: POST /ag-ui/start -> GET /ag-ui/events/{run_id}."""
    _mock_render(monkeypatch, _success_result())
    start = client.post(
        "/ag-ui/start",
        json={
            "diagram_type": "mermaid",
            "code": "graph TD; A-->B;",
            "output_format": "svg",
        },
    )
    assert start.status_code == 200
    data = start.json()
    run_id = data["run_id"]
    assert data["status"] == "started"
    assert f"/ag-ui/events/{run_id}" in data["events_url"]

    events = _parse_events(client.get(f"/ag-ui/events/{run_id}"))
    assert events[-1]["type"] == "RUN_FINISHED"
    assert all(e.get("run_id") == run_id for e in events)
    # The process-local run store is cleaned up after streaming completes.
    assert run_id not in _AGUI_RUNS


def test_agui_events_unknown_run_404():
    """Subscribing to an unknown run returns 404."""
    response = client.get("/ag-ui/events/does-not-exist")
    assert response.status_code == 404


def test_agui_run_requires_diagram_type_and_code():
    """Missing required fields are rejected by the request model."""
    response = client.post("/ag-ui/generate", json={"output_format": "svg"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_diagram_generation_events_sequence(monkeypatch):
    """Unit-level check of the event emitter sequence and termination."""
    from mcp_core.core import agui
    from mcp_core.core.diagram_service import DiagramRequest

    monkeypatch.setattr(agui, "generate_from_request", lambda req: _success_result())
    req = DiagramRequest(diagram_type="class", code="@startuml\nclass A\n@enduml")
    events = [ev async for ev in agui.diagram_generation_events(req, run_id="run-1")]

    assert all(e.get("run_id") == "run-1" for e in events)
    assert events[0]["type"] == "RUN_STARTED"
    assert events[-1]["type"] == "RUN_FINISHED"
    # RUN_ERROR is never emitted on success.
    assert "RUN_ERROR" not in {e["type"] for e in events}
