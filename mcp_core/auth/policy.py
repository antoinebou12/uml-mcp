"""Permission model: scopes (delegated) and app roles (app-only) -> read/write/admin.

Follows Microsoft's "verify scopes for delegated tokens, app roles for app-only
tokens" guidance. MCP JSON-RPC requests are classified per method and, for
``tools/call``, per tool via the tool registry's ``readOnlyHint`` annotation.
Unknown tools and unknown methods require ``write`` (fail safe).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from .errors import AuthError, plain_error
from .settings import AuthSettings

if TYPE_CHECKING:  # pragma: no cover
    from .validator import Principal

_RANK = {"read": 1, "write": 2, "admin": 3}

READ_METHODS: frozenset[str] = frozenset(
    {
        "initialize",
        "ping",
        "tools/list",
        "resources/list",
        "resources/read",
        "resources/templates/list",
        "resources/subscribe",
        "resources/unsubscribe",
        "prompts/list",
        "prompts/get",
        "completion/complete",
        "logging/setLevel",
        "server/discover",
    }
)

#: REST surfaces protected when ``protect_rest`` is on: (method, path) -> permission.
REST_POLICY: dict[tuple[str, str], str] = {
    ("POST", "/generate_diagram"): "write",
    ("POST", "/kroki_encode"): "read",
    ("POST", "/ag-ui"): "write",
    ("POST", "/ag-ui/start"): "write",
    ("POST", "/ag-ui/generate"): "write",
}


def permissions_for(principal: Principal, settings: AuthSettings) -> set[str]:
    """Effective permissions of a verified principal."""
    roles = principal.roles
    role_perms: set[str] = set()
    if roles & set(settings.writer_roles):
        role_perms |= {"read", "write"}
    if roles & set(settings.reader_roles):
        role_perms.add("read")
    perms: set[str] = set()
    if principal.kind == "delegated":
        if settings.write_scope in principal.scopes:
            perms |= {"read", "write"}
        if settings.read_scope in principal.scopes:
            perms.add("read")
        if settings.require_user_roles:
            perms &= role_perms
    else:
        perms |= role_perms
    if roles & set(settings.admin_roles):
        perms.add("admin")
    return perms


class Policy:
    """Decide the permission a request needs and build challenge scopes."""

    def __init__(self, settings: AuthSettings, tool_registry: dict[str, dict] | None):
        self.settings = settings
        self._tools: dict[str, str] = {}
        for name, info in (tool_registry or {}).items():
            annotations = (info or {}).get("annotations") or {}
            self._tools[name] = "read" if annotations.get("readOnlyHint") else "write"
        self._tools.update(settings.tool_permissions)

    # ----------------------------------------------------------- requirements
    def required_for_rest(self, method: str, path: str) -> str | None:
        if not self.settings.protect_rest:
            return None
        method = "GET" if method == "HEAD" else method
        if method == "GET" and path.startswith("/ag-ui/events/"):
            return "read"
        return REST_POLICY.get((method, path))

    def tool_permission(self, name: str) -> str:
        return self._tools.get(name, "write")

    def required_for_message(self, msg: dict[str, Any]) -> str:
        method = msg.get("method")
        if method is None:
            return "read"  # JSON-RPC response/result sent back by the client
        if method in self.settings.method_permissions:
            return self.settings.method_permissions[method]
        if method == "tools/call":
            name = (msg.get("params") or {}).get("name")
            return self.tool_permission(str(name))
        if method in READ_METHODS or method.startswith("notifications/"):
            return "read"
        return "write"

    def required_for_jsonrpc(self, messages: Iterable[dict[str, Any]]) -> str:
        best = "read"
        for msg in messages:
            perm = self.required_for_message(msg)
            if _RANK[perm] > _RANK[best]:
                best = perm
        return best

    @staticmethod
    def has(principal: Principal, permission: str) -> bool:
        return permission in principal.permissions

    @staticmethod
    def needs_body_peek(principal: Principal) -> bool:
        return not {"read", "write"} <= principal.permissions

    # ------------------------------------------------------------- challenges
    def scope_for(self, permission: str) -> list[str]:
        s = self.settings
        prefix = s.effective_scope_prefix
        if s.scope_strategy == "default":
            return [f"{s.upstream_scope_prefix}.default"]
        if permission == "read":
            return [f"{prefix}{s.read_scope}"]
        if permission == "write":
            return [f"{prefix}{s.read_scope}", f"{prefix}{s.write_scope}"]
        return []  # admin is an app role, not a scope

    def challenge_scopes(self, required: str | None = None) -> list[str]:
        """Scopes for a 401: the permission a route needs (default read+write)."""
        return self.scope_for(required or "write")

    def insufficient_scope_scopes(
        self, required: str, principal: Principal
    ) -> list[str]:
        """403 ``scope``: required ∪ already-granted scopes (MCP step-up guidance)."""
        needed = self.scope_for(required)
        if not needed:
            return []
        granted = [
            f"{self.settings.effective_scope_prefix}{s}"
            for s in sorted(principal.scopes)
            if s in (self.settings.read_scope, self.settings.write_scope)
        ]
        if self.settings.scope_strategy == "default":
            return needed
        out: list[str] = []
        for scope in [*needed, *granted]:
            if scope not in out:
                out.append(scope)
        return out

    def advertised_scopes(self) -> list[str]:
        s = self.settings
        if s.scope_strategy == "default":
            scopes = [f"{s.upstream_scope_prefix}.default"]
        else:
            scopes = [
                f"{s.effective_scope_prefix}{s.read_scope}",
                f"{s.effective_scope_prefix}{s.write_scope}",
            ]
        if s.advertise_offline_access:
            scopes.append("offline_access")
        return scopes


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key {key!r}")
        out[key] = value
    return out


def parse_jsonrpc_body(raw: bytes) -> list[dict[str, Any]] | None:
    """Strictly parse an MCP POST body.

    Returns the list of JSON-RPC messages, ``None`` when the body is empty, and
    raises :class:`AuthError` (400) for anything ambiguous: invalid UTF-8, BOM,
    duplicate keys, empty/invalid batches or non-string ``method``/tool names.
    """
    if not raw.strip():
        return None
    if raw.startswith(b"\xef\xbb\xbf"):
        raise plain_error(400, "invalid_request", "JSON body must not start with a BOM")
    try:
        text = raw.decode("utf-8", errors="strict")
        data = json.loads(text, object_pairs_hook=_reject_duplicates)
    except (UnicodeDecodeError, ValueError) as exc:
        raise plain_error(
            400, "invalid_request", f"Request body is not strict JSON: {exc}"
        ) from exc
    messages = data if isinstance(data, list) else [data]
    if not messages:
        raise plain_error(400, "invalid_request", "Empty JSON-RPC batch")
    for msg in messages:
        if not isinstance(msg, dict):
            raise plain_error(
                400, "invalid_request", "JSON-RPC message must be an object"
            )
        method = msg.get("method")
        if method is not None and not isinstance(method, str):
            raise plain_error(
                400, "invalid_request", "JSON-RPC 'method' must be a string"
            )
        if method == "tools/call":
            params = msg.get("params")
            if not isinstance(params, dict) or not isinstance(params.get("name"), str):
                raise plain_error(
                    400, "invalid_request", "tools/call requires a string params.name"
                )
    return messages


__all__ = [
    "READ_METHODS",
    "REST_POLICY",
    "AuthError",
    "Policy",
    "parse_jsonrpc_body",
    "permissions_for",
]
