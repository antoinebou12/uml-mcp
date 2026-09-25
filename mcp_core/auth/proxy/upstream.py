"""Upstream (Microsoft Entra ID) calls for the ``entra-proxy`` facade."""

from __future__ import annotations

import base64
import hashlib
import time
import uuid
from typing import Any, cast
from urllib.parse import urlencode

import httpx

from ..entra import entra_authority_host, entra_authorize_endpoint, entra_token_endpoint
from ..settings import AuthSettings

ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"


class UpstreamError(Exception):
    def __init__(self, error: str, description: str, status: int = 400):
        super().__init__(description)
        self.error = error
        self.description = description
        self.status = status


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class UpstreamClient:
    def __init__(self, settings: AuthSettings, http: httpx.AsyncClient | None = None):
        assert settings.entra is not None
        self.settings = settings
        self.entra = settings.entra
        host = entra_authority_host(self.entra.cloud)
        self.authorize_endpoint = entra_authorize_endpoint(host, self.entra.tenant_id)
        self.token_endpoint = entra_token_endpoint(host, self.entra.tenant_id)
        self._http = http

    @property
    def authority_origin(self) -> str:
        return "https://" + entra_authority_host(self.entra.cloud)

    def upstream_scopes(self, short_scopes: list[str]) -> str:
        prefix = self.settings.upstream_scope_prefix
        if self.settings.scope_strategy == "default":
            scopes = [f"{prefix}.default"]
        else:
            scopes = [f"{prefix}{s}" for s in short_scopes]
        if self.settings.proxy.refresh_tokens:
            scopes.append("offline_access")
        return " ".join(scopes)

    def authorize_url(self, *, state: str, verifier: str, scopes: list[str]) -> str:
        params = {
            "client_id": self.entra.client_id,
            "response_type": "code",
            "redirect_uri": f"{self.settings.origin}/oauth/callback",
            "response_mode": "query",
            "scope": self.upstream_scopes(scopes),
            "state": state,
            "code_challenge": pkce_challenge(verifier),
            "code_challenge_method": "S256",
        }
        # Deliberately no RFC 8707 ``resource``: Entra v2 rejects it (AADSTS9010010).
        return f"{self.authorize_endpoint}?{urlencode(params)}"

    def client_auth(self) -> dict[str, str]:
        proxy = self.settings.proxy
        kind = proxy.credential_kind
        if kind == "certificate":
            return {
                "client_assertion_type": ASSERTION_TYPE,
                "client_assertion": self._certificate_assertion(),
            }
        if kind == "secret":
            assert proxy.client_secret is not None
            return {"client_secret": proxy.client_secret.get_secret_value()}
        if kind == "workload_identity":
            assert proxy.federated_token_file is not None
            with open(proxy.federated_token_file, encoding="utf-8") as fh:
                assertion = fh.read().strip()  # re-read: kubelet rotates the token
            return {
                "client_assertion_type": ASSERTION_TYPE,
                "client_assertion": assertion,
            }
        raise UpstreamError("server_error", "no upstream client credential", 500)

    def _certificate_assertion(self) -> str:
        import jwt
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization

        proxy = self.settings.proxy
        assert proxy.client_certificate_pem and proxy.client_private_key_pem
        cert = x509.load_pem_x509_certificate(proxy.client_certificate_pem.encode())
        thumb = cert.fingerprint(hashes.SHA256())
        key = serialization.load_pem_private_key(
            proxy.client_private_key_pem.get_secret_value().encode(), password=None
        )
        now = int(time.time())
        claims = {
            "aud": self.token_endpoint,
            "iss": self.entra.client_id,
            "sub": self.entra.client_id,
            "jti": str(uuid.uuid4()),
            "nbf": now,
            "iat": now,
            "exp": now + 300,
        }
        header = {"x5t#S256": base64.urlsafe_b64encode(thumb).rstrip(b"=").decode()}
        return jwt.encode(claims, cast(Any, key), algorithm="PS256", headers=header)

    async def _post(self, data: dict[str, str]) -> dict[str, Any]:
        client = self._http or httpx.AsyncClient(timeout=10.0)
        try:
            resp = await client.post(
                self.token_endpoint, data={**data, **self.client_auth()}, timeout=10.0
            )
        except httpx.HTTPError as exc:
            raise UpstreamError(
                "temporarily_unavailable", "identity provider unreachable", 503
            ) from exc
        finally:
            if self._http is None:
                await client.aclose()
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if resp.status_code >= 500:
            raise UpstreamError(
                "temporarily_unavailable", "identity provider error", 503
            )
        if resp.status_code != 200 or "access_token" not in body:
            error = str(body.get("error") or "invalid_grant")
            if error not in ("invalid_grant", "invalid_scope", "invalid_request"):
                error = "invalid_grant"
            desc = str(body.get("error_description") or "upstream token request failed")
            raise UpstreamError(error, desc.split("\r\n")[0][:300])
        return body

    async def exchange_code(
        self, code: str, verifier: str, scopes: list[str]
    ) -> dict[str, Any]:
        return await self._post(
            {
                "grant_type": "authorization_code",
                "client_id": self.entra.client_id,
                "code": code,
                "redirect_uri": f"{self.settings.origin}/oauth/callback",
                "code_verifier": verifier,
                "scope": self.upstream_scopes(scopes),
            }
        )

    async def refresh(self, refresh_token: str, scopes: list[str]) -> dict[str, Any]:
        return await self._post(
            {
                "grant_type": "refresh_token",
                "client_id": self.entra.client_id,
                "refresh_token": refresh_token,
                "scope": self.upstream_scopes(scopes),
            }
        )


__all__ = ["UpstreamClient", "UpstreamError", "pkce_challenge"]
