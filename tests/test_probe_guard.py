import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_core.core.probe_guard import ProbeGuardMiddleware


@pytest.fixture
def client():
    async def endpoint(request):
        return PlainTextResponse("reached application")

    return TestClient(
        ProbeGuardMiddleware(Starlette(routes=[Route("/{path:path}", endpoint)]))
    )


@pytest.mark.parametrize(
    "path",
    [
        "/credentials.json",
        "/google-key.json",
        "/.config/gcloud/application_default_credentials.json",
        "/wp-admin/phpinfo.php",
        "/phpinfo.php.bak",
        "/phpinfo.php~",
        "/_environment",
        "/.env",
        "/.env.production",
        "/.git/config",
        "/%252eenv",
        "/firebase-key.json",
    ],
)
def test_probes_rejected_before_dispatch(client, path):
    response = client.get(path)
    assert response.status_code == 403
    assert response.content == b""
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/mcp",
        "/health",
        "/healthz",
        "/docs",
        "/openapi.json",
        "/.well-known/openai-apps-challenge",
        "/.well-known/oauth-protected-resource",
        "/admin",
        "/admin/api/settings",
        "/favicon.ico",
    ],
)
def test_public_routes_are_not_blocked(client, path):
    assert client.get(path).status_code == 200


def test_probe_does_not_ban_shared_gateway_peer(client):
    assert client.get("/phpinfo.php").status_code == 403
    assert client.get("/mcp").status_code == 200


def test_main_application_installs_guard():
    from app import app

    assert any(m.cls is ProbeGuardMiddleware for m in app.user_middleware)
