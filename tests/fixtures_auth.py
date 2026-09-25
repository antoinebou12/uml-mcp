"""Shared fixtures for enterprise auth tests (real RSA keys, realistic Entra tokens)."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi import FastAPI, Request
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

TENANT = "11111111-2222-3333-4444-555555555555"
OTHER_TENANT = "99999999-8888-7777-6666-555555555555"
API_CLIENT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
VSCODE = "aebc6443-996d-45c2-90f0-388ff96faa56"
GRAPH = "00000003-0000-0000-c000-000000000000"
RESOURCE = "https://mcp.contoso.com/mcp"
V2_ISS = f"https://login.microsoftonline.com/{TENANT}/v2.0"
V1_ISS = f"https://sts.windows.net/{TENANT}/"
JWKS_URI = f"https://login.microsoftonline.com/{TENANT}/discovery/v2.0/keys"
ENC_KEY = "k1:" + "A" * 43  # 32 zero-ish bytes, base64url


@pytest.fixture(scope="session")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def rsa_key_2():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def ec_key():
    return ec.generate_private_key(ec.SECP256R1())


def public_pem(key) -> str:
    return (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )


def jwk_for(key, kid: str, **extra: Any) -> dict[str, Any]:
    if isinstance(key, rsa.RSAPrivateKey):
        data = json.loads(str(RSAAlgorithm.to_jwk(key.public_key())))
    else:
        data = json.loads(str(ECAlgorithm.to_jwk(key.public_key())))
    data.update({"kid": kid, "use": "sig"}, **extra)
    return data


def mint(
    claims: dict[str, Any],
    key,
    kid: str | None = "k1",
    alg: str = "RS256",
    headers: dict[str, Any] | None = None,
) -> str:
    hdr = dict(headers or {})
    if kid is not None:
        hdr["kid"] = kid
    return jwt.encode(claims, key, algorithm=alg, headers=hdr)


def entra_v2_claims(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    claims = {
        "aud": API_CLIENT,
        "iss": V2_ISS,
        "iat": now - 10,
        "nbf": now - 10,
        "exp": now + 3600,
        "tid": TENANT,
        "oid": str(uuid.uuid4()),
        "sub": "subject-123",
        "azp": VSCODE,
        "azpacr": "0",
        "scp": "mcp.read mcp.write",
        "ver": "2.0",
        "name": "Ada Lovelace",
    }
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


def entra_v1_claims(**overrides: Any) -> dict[str, Any]:
    claims = entra_v2_claims(
        aud=f"api://{API_CLIENT}", iss=V1_ISS, ver="1.0", azp=None, appid=VSCODE
    )
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


def entra_app_claims(roles=("MCP.Write.All",), **overrides: Any) -> dict[str, Any]:
    claims = entra_v2_claims(scp=None, roles=list(roles), idtyp="app")
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


class MockIdP:
    """httpx transport serving JWKS, metadata and a fake Entra token endpoint."""

    def __init__(self) -> None:
        self.jwks: dict[str, Any] = {"keys": []}
        self.fail = False
        self.calls: dict[str, int] = {}
        self.metadata: dict[str, dict[str, Any]] = {}
        self.token_responses: list[tuple[int, dict[str, Any]]] = []
        self.token_requests: list[dict[str, str]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls[path] = self.calls.get(path, 0) + 1
        if self.fail:
            raise httpx.ConnectError("down", request=request)
        if path.endswith("/keys"):
            return httpx.Response(200, json=self.jwks)
        if path.endswith("/token"):
            self.token_requests.append(
                dict(httpx.QueryParams(request.content.decode()))
            )
            status, body = self.token_responses.pop(0)
            return httpx.Response(status, json=body)
        url = str(request.url)
        if url in self.metadata:
            return httpx.Response(200, json=self.metadata[url])
        return httpx.Response(404, json={})

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


@pytest.fixture
def mock_idp(rsa_key) -> MockIdP:
    idp = MockIdP()
    idp.jwks = {
        "keys": [
            jwk_for(
                rsa_key,
                "k1",
                issuer="https://login.microsoftonline.com/{tenantid}/v2.0",
            )
        ]
    }
    return idp


def auth_env(**overrides: str) -> dict[str, str]:
    env = {
        "MCP_AUTH_MODE": "jwt",
        "MCP_AUTH_RESOURCE_URL": RESOURCE,
        "MCP_AUTH_ENTRA_TENANT_ID": TENANT,
        "MCP_AUTH_ENTRA_CLIENT_ID": API_CLIENT,
        "MCP_AUTH_PREFLIGHT": "off",
    }
    env.update(overrides)
    return {k: v for k, v in env.items() if v != ""}


@pytest.fixture
def settings_factory() -> Callable[..., Any]:
    from mcp_core.auth.settings import load_auth_settings

    def make(**overrides: str):
        return load_auth_settings(auth_env(**overrides))

    return make


FAKE_TOOLS = {
    "generate_uml": {"annotations": {"readOnlyHint": False}},
    "generate_uml_batch": {"annotations": {"readOnlyHint": False}},
    "generate_uml_image": {"annotations": {"readOnlyHint": False}},
    "validate_uml": {"annotations": {"readOnlyHint": True}},
    "list_diagram_types": {"annotations": {"readOnlyHint": True}},
}


class FakeMCP:
    """Stands in for FastMCP's Streamable HTTP app mounted at /mcp."""

    def __init__(self) -> None:
        self.seen: list[dict[str, Any]] = []

    async def __call__(self, scope, receive, send):
        body = b""
        while True:
            msg = await receive()
            body += msg.get("body", b"")
            if not msg.get("more_body"):
                break
        headers = {k.decode(): v.decode() for k, v in scope["headers"]}
        path = scope["path"][len(scope.get("root_path", "")) :] or "/"
        self.seen.append(
            {
                "path": path,
                "body": body,
                "headers": headers,
                "principal": (scope.get("state") or {}).get("auth_principal"),
            }
        )
        if path != "/":
            status, payload = 404, b'{"detail":"Not Found"}'
        elif scope["method"] not in ("POST", "DELETE"):
            status, payload = 405, b'{"detail":"Method Not Allowed"}'
        else:
            status, payload = 200, body or b"{}"
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": payload})


def build_auth_app(settings, *, http=None, tools=None, cors_origins=None):
    """Mirror app.py: auth installed before CORS, MCP mounted at /mcp, REST stubs."""
    from fastapi.middleware.cors import CORSMiddleware

    from mcp_core.auth.integration import (
        build_auth_runtime,
        cors_expose_headers,
        install_auth,
    )

    runtime = build_auth_runtime(settings, http=http, tool_registry=tools or FAKE_TOOLS)
    app = FastAPI()
    fake = FakeMCP()

    @app.post("/generate_diagram")
    async def gen(request: Request):
        return {"ok": True, "auth": "authorization" in request.headers}

    @app.post("/kroki_encode")
    async def enc():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    install_auth(app, runtime)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["https://app.example"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=cors_expose_headers(),
    )
    app.mount("/mcp", fake)
    app.state.fake_mcp = fake
    app.state.runtime = runtime
    return app


def rpc(method: str, **params: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
