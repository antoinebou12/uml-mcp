"""Progress and log notifications from generate_uml_batch.

Unit tests pin ordering and the notification sequence; the subprocess test drives a
real FastMCP server through its real client (the main suite runs on the mock server).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any

import pytest

from mcp_core.tools import diagram_tools, notifications

MERMAID = {"diagram_type": "mermaid", "code": "graph TD; A-->B;"}


def test_notifications_are_silent_noops_outside_a_request():
    """REST routes, tests and the mock server have no MCP request context."""
    notifications.report_progress(1, 2, "halfway")
    notifications.log("info", "hello")
    notifications.log("not-a-level", "falls back to info")


def test_batch_keeps_input_order_and_reports_progress(monkeypatch):
    progress: list[tuple[float, float, str]] = []
    logs: list[tuple[str, str]] = []
    monkeypatch.setattr(
        notifications, "report_progress", lambda p, t, m: progress.append((p, t, m))
    )
    monkeypatch.setattr(notifications, "log", lambda lvl, msg: logs.append((lvl, msg)))

    def fake_render(request: Any) -> dict[str, Any]:
        # The first item is the slowest, so completion order is the reverse of input.
        index = int(request.code.split("#")[1])
        time.sleep(0.15 * (3 - index))
        if index == 1:
            return {"success": False, "error": "boom"}
        return {
            "success": True,
            "diagram_type": request.diagram_type,
            "source": "fake",
            "render_ms": index,
            "marker": index,
        }

    monkeypatch.setattr(diagram_tools, "generate_from_request", fake_render)

    items = [{**MERMAID, "code": f"graph TD; A-->B; %%#{i}"} for i in range(3)]
    out = diagram_tools.generate_uml_batch(items)

    rows = out["results"]
    assert [row["index"] for row in rows] == [0, 1, 2]
    assert [row.get("marker") for row in rows] == [0, None, 2]
    assert rows[1]["error"] == "boom"

    assert progress[0][:2] == (0, 3)
    assert [p for p, _t, _m in progress] == [0, 1, 2, 3]
    assert {t for _p, t, _m in progress} == {3}

    assert len(logs) == 3
    assert [lvl for lvl, _ in logs].count("warning") == 1
    warning = next(msg for lvl, msg in logs if lvl == "warning")
    assert "boom" in warning and "[2/3]" in warning


def test_batch_validation_failure_is_a_warning_not_an_exception(monkeypatch):
    logs: list[tuple[str, str]] = []
    monkeypatch.setattr(notifications, "log", lambda lvl, msg: logs.append((lvl, msg)))
    monkeypatch.setattr(notifications, "report_progress", lambda *_a: None)

    malformed: list[Any] = ["not an object"]  # callers can send anything over MCP
    out = diagram_tools.generate_uml_batch(malformed)

    assert out["results"][0]["success"] is False
    assert logs and logs[0][0] == "warning"


_E2E = """
import asyncio, json
from fastmcp import Client
from mcp_core.core.server import get_mcp_server

ITEMS = [
    {"diagram_type": "mermaid", "code": "graph TD; Alpha-->Beta;"},
    {"diagram_type": "mermaid", "code": "graph TD; SYNTAX_ERROR-->X;"},
    {"diagram_type": "mermaid", "code": "graph TD; Gamma-->Delta;"},
]

async def main():
    progress, logs = [], []

    async def on_progress(p, t, m):
        progress.append([p, t, m])

    async def on_log(msg):
        data = msg.data if isinstance(msg.data, dict) else {"msg": str(msg.data)}
        logs.append([str(msg.level), data.get("msg")])

    server = get_mcp_server()
    async with Client(server, progress_handler=on_progress, log_handler=on_log) as c:
        result = await c.call_tool("generate_uml_batch", {"items": ITEMS})
        rows = result.structured_content["results"]
    async with Client(server) as plain:  # a client that asked for nothing still works
        again = await plain.call_tool("generate_uml_batch", {"items": ITEMS[:1]})
    print("E2E_JSON " + json.dumps({
        "progress": progress,
        "logs": logs,
        "indexes": [r["index"] for r in rows],
        "ok": [bool(r.get("success", True)) and not r.get("error") for r in rows],
        "plain_rows": len(again.structured_content["results"]),
    }))

asyncio.run(main())
"""


@pytest.mark.usefixtures("loopback_bypasses_proxy")
def test_real_fastmcp_client_receives_progress_and_logs(kroki):
    env = os.environ.copy()
    env.update(
        {
            "USE_REAL_FASTMCP": "1",
            "MOCK_FASTMCP": "0",
            "TESTING": "0",
            "DEVELOPMENT": "0",
            "UML_MCP_CONFIG": "none",
            "KROKI_SERVER": kroki.url,
            "MCP_MEMORY_ONLY": "true",
            "MCP_URL_ONLY": "false",
            "MCP_DIAGRAM_FALLBACK": "false",
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
            "PYTHONUNBUFFERED": "1",
        }
    )
    completed = subprocess.run(
        [sys.executable, "-c", _E2E],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, (
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    line = next(
        ln for ln in completed.stdout.splitlines() if ln.startswith("E2E_JSON ")
    )
    report = json.loads(line.removeprefix("E2E_JSON "))

    assert report["indexes"] == [0, 1, 2]
    assert report["ok"] == [True, False, True]
    assert [p for p, _t, _m in report["progress"]] == [0, 1, 2, 3]
    assert {t for _p, t, _m in report["progress"]} == {3}
    levels = [lvl for lvl, _msg in report["logs"]]
    assert levels.count("warning") == 1 and levels.count("info") == 2
    assert report["plain_rows"] == 1


# Regression for scripts/run_vercel_kroki_stress.py: hand-rolled HTTP clients send no
# progressToken and parse the FIRST event of the response. Notifications sent to them
# turned that first event into a log line, so every batch row came back empty.
_HTTP = """
import json, logging
logging.disable(logging.CRITICAL)
from fastapi.testclient import TestClient
from app import app

ITEMS = [
    {"diagram_type": "mermaid", "code": "graph TD; A-->B;"},
    {"diagram_type": "mermaid", "code": "graph TD; C-->D;"},
]

def call(meta):
    params = {"name": "generate_uml_batch", "arguments": {"items": ITEMS}}
    if meta is not None:
        params["_meta"] = meta
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params}

def events(response):
    if "event-stream" not in response.headers.get("content-type", ""):
        return [response.json()]
    return [
        json.loads(line[5:].strip())
        for line in response.text.splitlines()
        if line.startswith("data:") and line[5:].strip()
    ]

report = {}
with TestClient(app) as client:
    headers = {"Accept": "application/json, text/event-stream"}
    for label, meta in (("plain", None), ("opted_in", {"progressToken": "t1"})):
        evs = events(client.post("/mcp", json=call(meta), headers=headers))
        report[label] = [e.get("method", "result" if "result" in e else "?") for e in evs]
print("HTTP_JSON " + json.dumps(report))
"""


def test_http_clients_without_a_token_get_only_the_result():
    env = os.environ.copy()
    env.update(
        {
            "USE_REAL_FASTMCP": "1",
            "MOCK_FASTMCP": "0",
            "TESTING": "0",
            "DEVELOPMENT": "0",
            "UML_MCP_CONFIG": "none",
            "FASTMCP_STATELESS_HTTP": "true",
            "MCP_URL_ONLY": "true",
            "MCP_MEMORY_ONLY": "true",
        }
    )
    completed = subprocess.run(
        [sys.executable, "-c", _HTTP],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, (
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    line = next(
        ln for ln in completed.stdout.splitlines() if ln.startswith("HTTP_JSON ")
    )
    report = json.loads(line.removeprefix("HTTP_JSON "))

    # No token: one event, and it is the tool result (what the stress script reads).
    assert report["plain"] == ["result"]
    # Token sent: updates stream first and the result is the last event.
    assert report["opted_in"][0] == "notifications/progress"
    assert report["opted_in"][-1] == "result"
    assert "notifications/message" in report["opted_in"]
