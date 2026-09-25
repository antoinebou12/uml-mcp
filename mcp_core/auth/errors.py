"""Auth error taxonomy and RFC 6750 ``WWW-Authenticate`` challenge builder.

Status mapping (RFC 6750 §3.1, MCP 2025-11-25 authorization):

* 400 ``invalid_request``  – malformed request (token in query, duplicate headers)
* 401 (no ``error``)        – no credentials at all ("what is missing" is in the body)
* 401 ``invalid_token``     – bad/expired/foreign token
* 403 ``insufficient_scope``– valid token, not enough permission (step-up)
* 503 ``temporarily_unavailable`` – key material unreachable (fail closed)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

# RFC 6750 error_description charset: %x20-21 / %x23-5B / %x5D-7E
_DESC_BAD = re.compile(r"[^\x20-\x21\x23-\x5b\x5d-\x7e]")
_JWTISH = re.compile(r"eyJ[A-Za-z0-9_\-]{6,}(\.[A-Za-z0-9_\-]*){0,2}")


def sanitize_description(text: str, limit: int = 300) -> str:
    """Make ``text`` safe for a quoted-string and never echo token material."""
    text = _JWTISH.sub("<redacted>", text)
    text = _DESC_BAD.sub("'", text.replace('"', "'").replace("\\", "/"))
    return text[:limit]


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


@dataclass
class AuthError(Exception):
    """Base error: rendered as a JSON body plus optional ``WWW-Authenticate``."""

    status: int
    reason: str
    description: str
    error: str | None = None  # RFC 6750 error code for the challenge
    challenge: bool = True
    scope: list[str] | None = None
    retry_after: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        return f"{self.status} {self.reason}: {self.description}"


def missing_token(description: str, reason: str = "token_missing") -> AuthError:
    return AuthError(
        401,
        reason,
        description,
        error=None,
        extra={"missing": ["Authorization: Bearer <access_token>"]},
    )


def invalid_request(reason: str, description: str) -> AuthError:
    return AuthError(400, reason, description, error="invalid_request")


def invalid_token(reason: str, description: str, **extra: Any) -> AuthError:
    return AuthError(401, reason, description, error="invalid_token", extra=extra)


def insufficient_scope(
    description: str,
    *,
    scope: list[str] | None,
    required: str,
    granted: list[str],
) -> AuthError:
    return AuthError(
        403,
        "insufficient_scope",
        description,
        error="insufficient_scope",
        scope=scope,
        extra={"required": required, "granted": granted},
    )


def unavailable(reason: str, description: str, retry_after: int = 30) -> AuthError:
    return AuthError(
        503,
        reason,
        description,
        error="temporarily_unavailable",
        challenge=False,
        retry_after=retry_after,
    )


def plain_error(status: int, reason: str, description: str) -> AuthError:
    """Non-challenge errors from the body peek (413/415/408/400)."""
    return AuthError(
        status, reason, description, error="invalid_request", challenge=False
    )


def build_www_authenticate(
    err: AuthError | None,
    *,
    resource_metadata: str,
    scope: list[str] | None,
    realm: str = "uml-mcp",
) -> str:
    """Build a ``Bearer`` challenge.

    No ``error`` attribute when credentials are absent (RFC 6750 §3.1); always a
    ``resource_metadata`` (RFC 9728 §5.1) and ``scope`` when known.
    """
    parts = [f"realm={_quote(realm)}"]
    if err is not None and err.error:
        parts.append(f"error={_quote(err.error)}")
        parts.append(
            f"error_description={_quote(sanitize_description(err.description))}"
        )
    if scope:
        parts.append(f"scope={_quote(' '.join(scope))}")
    parts.append(f"resource_metadata={_quote(resource_metadata)}")
    return "Bearer " + ", ".join(parts)


def error_payload(
    err: AuthError,
    *,
    request_id: str | None,
    resource_metadata: str | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "error": err.error or "unauthorized",
        "error_description": sanitize_description(err.description, limit=500),
        "reason": err.reason,
        "status": err.status,
    }
    if err.scope:
        body["scope"] = " ".join(err.scope)
    if resource_metadata and err.challenge:
        body["resource_metadata"] = resource_metadata
    body.update(err.extra)
    if request_id:
        body["request_id"] = request_id
    return body


def error_response_parts(
    err: AuthError,
    *,
    request_id: str | None,
    resource_metadata: str,
    challenge_scope: list[str] | None,
) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    """Return ``(status, headers, body)`` ready for a raw ASGI response."""
    scope = err.scope if err.status == 403 else challenge_scope
    body = json.dumps(
        error_payload(err, request_id=request_id, resource_metadata=resource_metadata),
        separators=(",", ":"),
    ).encode("utf-8")
    headers: list[tuple[bytes, bytes]] = [
        (b"content-type", b"application/json"),
        (b"cache-control", b"no-store"),
        (b"pragma", b"no-cache"),
        (b"content-length", str(len(body)).encode()),
    ]
    if err.challenge and err.status in (400, 401, 403):
        value = build_www_authenticate(
            err if err.error else None,
            resource_metadata=resource_metadata,
            scope=scope,
        )
        headers.append((b"www-authenticate", value.encode("latin-1", "replace")))
    if err.retry_after is not None:
        headers.append((b"retry-after", str(err.retry_after).encode()))
    if request_id:
        headers.append((b"x-request-id", request_id.encode("latin-1", "replace")))
    return err.status, headers, body


__all__ = [
    "AuthError",
    "build_www_authenticate",
    "error_payload",
    "error_response_parts",
    "insufficient_scope",
    "invalid_request",
    "invalid_token",
    "missing_token",
    "plain_error",
    "sanitize_description",
    "unavailable",
]
