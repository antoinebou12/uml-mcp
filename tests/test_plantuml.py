"""Tests for the PlantUML client."""

from typing import Any, cast

import httpx
import pytest

from tools.kroki.plantuml import PlantUML, PlantUMLConnectionError, PlantUMLError


def test_form_auth_requires_url_and_body():
    """Form authentication validates its required fields."""
    PlantUML("https://example.test/plantuml/png", form_auth=cast(Any, {}))

    with pytest.raises(PlantUMLError, match="'url'"):
        PlantUML(
            "https://example.test/plantuml/png",
            form_auth=cast(Any, {"body": {"username": "alice"}}),
        )

    with pytest.raises(PlantUMLError, match="'body'"):
        PlantUML(
            "https://example.test/plantuml/png",
            form_auth=cast(Any, {"url": "https://example.test/login"}),
        )


def test_form_auth_cookies_persist_on_client():
    """Cookies from form login are sent by the shared HTTP client."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/login":
            return httpx.Response(200, headers={"set-cookie": "session=abc; Path=/"})
        return httpx.Response(200, text="ok")

    client = PlantUML(
        "https://example.test/plantuml/png",
        form_auth={
            "url": "https://example.test/login",
            "body": {"username": "alice", "password": "secret"},
        },
        http_opts={"transport": httpx.MockTransport(handler)},
    )

    client.process("@startuml\n@enduml")

    assert "Cookie" not in client.request_opts
    assert requests[1].headers["cookie"] == "session=abc"


def test_process_passes_request_options():
    """Per-request HTTP options are passed through to the diagram fetch."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text="ok")

    client = PlantUML(
        "https://example.test/plantuml/png",
        http_opts={"transport": httpx.MockTransport(handler)},
        request_opts={"headers": {"X-Diagram-Request": "1"}},
    )

    client.process("@startuml\n@enduml")

    assert requests[0].headers["x-diagram-request"] == "1"


def test_form_auth_http_errors_become_connection_errors():
    """Authentication HTTP failures are wrapped as PlantUML connection errors."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request)

    with pytest.raises(PlantUMLConnectionError, match="Error authenticating"):
        PlantUML(
            "https://example.test/plantuml/png",
            form_auth={
                "url": "https://example.test/login",
                "body": {"username": "alice", "password": "wrong"},
            },
            http_opts={"transport": httpx.MockTransport(handler)},
        )
