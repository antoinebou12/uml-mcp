"""ASGI middleware protecting ``/mcp``, REST and admin surfaces with bearer tokens.

Pure ASGI (not ``BaseHTTPMiddleware``) so Streamable HTTP / SSE responses stream
untouched and the request body can be buffered and replayed. Order for a
protected request: 400 (malformed) -> 401/503 (authentication) -> 403 (scope)
-> downstream routing (404/405) -> handler. Everything else passes through.

Every 401 tells the client what is missing and where to discover the
authorization server (``WWW-Authenticate: Bearer resource_metadata=..., scope=...``).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, MutableMapping
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl

from . import errors
from .audit import AuditEvent, subject_hash
from .policy import parse_jsonrpc_body

if TYPE_CHECKING:  # pragma: no cover
    from .integration import AuthRuntime
    from .validator import Principal

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

MAX_AUTH_HEADER = 16 * 1024
BODY_READ_TIMEOUT = 30.0


def is_mcp_path(path: str) -> bool:
    return path == "/mcp" or path.startswith("/mcp/")


def is_admin_api_path(path: str) -> bool:
    return path == "/admin/api" or path.startswith("/admin/api/")


class AuthMiddleware:
    """Enforce enterprise auth on protected paths (see module docstring)."""

    def __init__(self, app: Callable[..., Awaitable[None]], runtime: AuthRuntime):
        self.app = app
        self.runtime = runtime

    # ----------------------------------------------------------------- routing
    def _classify(self, method: str, path: str) -> tuple[str, str | None] | None:
        """Return (surface, fixed permission) or None when not protected."""
        if is_mcp_path(path):
            return "mcp", None
        if is_admin_api_path(path) or path == "/metrics":
            return "admin", "admin"
        perm = self.runtime.policy.required_for_rest(method, path)
        if perm is not None:
            return "rest", perm
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return
        target = self._classify(method, path)
        if target is None:
            await self.app(scope, receive, send)
            return
        surface, fixed_perm = target
        settings = self.runtime.settings
        rm = settings.prm_url_mcp if surface == "mcp" else settings.prm_url_root
        request_id = _header(scope, b"x-request-id")
        policy = self.runtime.policy
        challenge = policy.challenge_scopes(fixed_perm if surface == "rest" else None)
        tool: str | None = None
        principal: Principal | None = None
        try:
            token = self._extract_token(scope)
            principal = await self.runtime.validator.validate(token)
            required = fixed_perm or "read"
            if (
                surface == "mcp"
                and method == "POST"
                and policy.needs_body_peek(principal)
            ):
                body, receive = await _buffer_body(scope, receive, settings.body_limit)
                messages = parse_jsonrpc_body(body)
                if messages:
                    _check_mcp_headers(scope, messages)
                    required = policy.required_for_jsonrpc(messages)
                    tool = _tool_name(messages)
            if not policy.has(principal, required):
                raise self._forbidden(required, principal, tool)
        except errors.AuthError as err:
            self._audit(scope, err.status, err.reason, request_id, principal, tool)
            _record_denial(scope, err, principal, tool)
            status, headers, payload = errors.error_response_parts(
                err,
                request_id=request_id,
                resource_metadata=rm,
                challenge_scope=challenge,
            )
            await _send_raw(send, status, headers, payload)
            return

        # Authenticated: never forward the client's token downstream.
        headers = [
            (k, v) for k, v in scope.get("headers", []) if k.lower() != b"authorization"
        ]
        new_scope = dict(scope)
        new_scope["headers"] = headers
        state = dict(scope.get("state") or {})
        state["auth_principal"] = principal
        new_scope["state"] = state
        if surface == "mcp" and path == "/mcp":
            # Match the /mcp mount directly instead of a 307 that re-sends the token
            # (and can downgrade to http:// behind a TLS-terminating ingress).
            new_scope["path"] = "/mcp/"
            new_scope["raw_path"] = b"/mcp/"
        from ..observability.context import reset_context, set_context

        ctx_token = set_context(
            user_id=principal.username or principal.subject or None,
            tenant_id=principal.tenant_id,
            client_id=principal.client_id,
            policy_decision="allow",
            policy_reason=f"{required} permission ({principal.kind})",
        )
        try:
            await self.app(new_scope, receive, send)
        finally:
            reset_context(ctx_token)

    # ----------------------------------------------------------------- helpers
    def _extract_token(self, scope: Scope) -> str:
        query = scope.get("query_string", b"").decode("latin-1", "replace")
        if query and any(
            k == "access_token" for k, _ in parse_qsl(query, keep_blank_values=True)
        ):
            raise errors.invalid_request(
                "token_in_query",
                "Access tokens must be sent in the Authorization header, never in the "
                "URL query string",
            )
        values = [
            v for k, v in scope.get("headers", []) if k.lower() == b"authorization"
        ]
        if not values:
            raise errors.missing_token(
                "Missing Authorization header. Send 'Authorization: Bearer <access_token>' "
                "obtained from an authorization server listed in the protected resource "
                "metadata"
            )
        if len(values) > 1:
            raise errors.invalid_request(
                "multiple_authorization_headers",
                "Send exactly one Authorization header",
            )
        raw = values[0]
        if len(raw) > MAX_AUTH_HEADER:
            raise errors.invalid_request(
                "token_too_large", "Authorization header is too large"
            )
        value = raw.decode("latin-1", "replace").strip()
        scheme, _, token = value.partition(" ")
        if scheme.lower() != "bearer":
            raise errors.missing_token(
                f"Authorization scheme {scheme[:20]!r} is not supported; use "
                "'Authorization: Bearer <access_token>'",
                reason="unsupported_auth_scheme",
            )
        token = token.strip()
        if not token:
            raise errors.invalid_token("malformed_token", "Bearer token is empty")
        return token

    def _forbidden(
        self, required: str, principal: Principal, tool: str | None
    ) -> errors.AuthError:
        policy = self.runtime.policy
        s = self.runtime.settings
        scopes = policy.insufficient_scope_scopes(required, principal)
        subject = f"Tool '{tool}'" if tool else "This request"
        if required == "admin":
            need = f"app role {' or '.join(s.admin_roles)}"
        elif principal.kind == "app":
            roles = (
                s.writer_roles
                if required == "write"
                else s.reader_roles + s.writer_roles
            )
            need = f"app role {' or '.join(roles)}"
        else:
            scope_name = s.write_scope if required == "write" else s.read_scope
            need = f"scope {scope_name}"
            if s.require_user_roles:
                roles = s.writer_roles if required == "write" else s.reader_roles
                need += f" and app role {' or '.join(roles)}"
        return errors.insufficient_scope(
            f"{subject} requires the '{required}' permission ({need})",
            scope=scopes or None,
            required=required,
            granted=sorted(principal.permissions),
        )

    def _audit(
        self,
        scope: Scope,
        status: int,
        reason: str,
        request_id: str | None,
        principal: Principal | None,
        tool: str | None,
    ) -> None:
        self.runtime.audit.record(
            AuditEvent(
                ts=self.runtime.audit.now(),
                method=scope.get("method", ""),
                path=scope.get("path", ""),
                status=status,
                reason=reason,
                request_id=request_id,
                tenant_id=principal.tenant_id if principal else None,
                client_id=principal.client_id if principal else None,
                subject_hash=subject_hash(principal.subject) if principal else None,
                tool=tool,
            )
        )


def _record_denial(
    scope: Scope, err: errors.AuthError, principal: Principal | None, tool: str | None
) -> None:
    """Feed the MXCP-style audit trail (policy_decision=deny) and metrics."""
    from ..observability.audit import record_operation
    from ..observability.context import reset_context, set_context

    token = set_context(
        user_id=(principal.username or principal.subject) if principal else None,
        tenant_id=principal.tenant_id if principal else None,
        client_id=principal.client_id if principal else None,
    )
    try:
        record_operation(
            operation_type="tool" if tool else "http",
            operation_name=tool or f"{scope.get('method', '')} {scope.get('path', '')}",
            operation_status="error",
            error=f"HTTP {err.status}",
            policy_decision="deny",
            policy_reason=err.reason,
        )
    finally:
        reset_context(token)


def _header(scope: Scope, name: bytes) -> str | None:
    for k, v in scope.get("headers", []):
        if k.lower() == name:
            return v.decode("latin-1", "replace")[:128]
    return None


def _tool_name(messages: list[dict[str, Any]]) -> str | None:
    for msg in messages:
        if msg.get("method") == "tools/call":
            return (msg.get("params") or {}).get("name")
    return None


def _check_mcp_headers(scope: Scope, messages: list[dict[str, Any]]) -> None:
    """Routing headers (if a client sends them) must agree with the body."""
    header_method = _header(scope, b"mcp-method")
    if (
        header_method is not None
        and len(messages) == 1
        and header_method != messages[0].get("method")
    ):
        raise errors.plain_error(
            400, "invalid_request", "Mcp-Method header does not match the body"
        )


async def _buffer_body(
    scope: Scope, receive: Receive, limit: int
) -> tuple[bytes, Receive]:
    encoding = (_header(scope, b"content-encoding") or "identity").strip().lower()
    if encoding not in ("", "identity"):
        raise errors.plain_error(
            415,
            "unsupported_content_encoding",
            "Compressed request bodies are not accepted",
        )
    chunks: list[bytes] = []
    size = 0
    pending: list[Message] = []
    while True:
        try:
            message = await asyncio.wait_for(receive(), timeout=BODY_READ_TIMEOUT)
        except TimeoutError as exc:
            raise errors.plain_error(
                408, "request_timeout", "Request body too slow"
            ) from exc
        if message["type"] == "http.disconnect":
            pending.append(message)
            break
        body = message.get("body", b"")
        size += len(body)
        if size > limit:
            raise errors.plain_error(
                413, "request_too_large", f"Request body exceeds {limit} bytes"
            )
        chunks.append(body)
        if not message.get("more_body", False):
            break
    data = b"".join(chunks)
    replayed = False

    async def replay() -> Message:
        nonlocal replayed
        if not replayed:
            replayed = True
            return {"type": "http.request", "body": data, "more_body": False}
        if pending:
            return pending.pop(0)
        return await receive()

    return data, replay


async def _send_raw(
    send: Send, status: int, headers: list[tuple[bytes, bytes]], body: bytes
) -> None:
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


__all__ = ["AuthMiddleware", "is_admin_api_path", "is_mcp_path"]
