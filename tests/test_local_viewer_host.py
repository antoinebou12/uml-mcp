"""The local viewer forwards real tool arguments and rejects cross-origin requests."""

from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer

import httpx
import pytest

from scripts import run_local_viewer as viewer


@pytest.fixture
def local_host(tmp_path, monkeypatch):
    monkeypatch.setattr(viewer, "OUT", tmp_path)
    (tmp_path / "index.html").write_text(viewer.PAGE, encoding="utf-8")
    calls = []

    async def call(name, args):
        calls.append((name, args))
        if name == "broken":
            raise ValueError("Renderer failed")
        return {"structuredContent": {"success": True}, "isError": False}

    monkeypatch.setattr(viewer, "call", call)
    server = ThreadingHTTPServer(("127.0.0.1", 0), viewer.Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    with httpx.Client(
        base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
    ) as client:
        try:
            yield client, calls
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)


def test_local_host_serves_all_examples_without_render_wrapper(local_host):
    client, _ = local_host
    page = client.get("/")
    assert page.status_code == 200
    assert "Render locally" not in page.text
    assert "100dvh" in page.text
    assert "local/select-example" in page.text
    assert len(client.get("/api/sources").json()) == 15


def test_tool_arguments_and_failures_reach_the_viewer(local_host):
    client, calls = local_host
    args = {"diagram_type": "timeline", "code": '{"title":"Roadmap"}'}
    result = client.post("/api/tool", json={"name": "generate_uml", "arguments": args})
    assert result.status_code == 200
    assert result.json()["structuredContent"]["success"] is True
    assert calls == [("generate_uml", args)]
    failure = client.post("/api/tool", json={"name": "broken"})
    assert failure.status_code == 400
    assert failure.json() == {"error": "Renderer failed"}
    assert client.get("/api/sources").status_code == 200


def test_cross_origin_and_form_posts_do_not_call_tools(local_host):
    client, calls = local_host
    blocked = client.post(
        "/api/tool",
        json={"name": "generate_uml"},
        headers={"Origin": "https://unrelated.example"},
    )
    assert blocked.status_code == 403
    assert client.post("/api/tool", data={"name": "generate_uml"}).status_code == 415
    assert calls == []


@pytest.mark.asyncio
async def test_host_does_not_expose_other_server_tools():
    with pytest.raises(ValueError, match="not enabled"):
        await viewer.call("unrelated_tool", {})
