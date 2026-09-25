"""Per-request context propagated to tool/resource/prompt audit records."""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class RequestContext:
    caller_type: str = "stdio"  # http | stdio
    request_id: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    client_id: str | None = None
    rate_key: str | None = None
    policy_decision: str = "n/a"  # allow | deny | n/a
    policy_reason: str | None = None


_CTX: contextvars.ContextVar[RequestContext] = contextvars.ContextVar(
    "uml_mcp_request_context",
    default=RequestContext(),  # noqa: B039 - frozen dataclass, never mutated
)


def current_context() -> RequestContext:
    return _CTX.get()


def set_context(**changes: object) -> contextvars.Token[RequestContext]:
    """Update fields of the current context; returns a token for ``reset``."""
    return _CTX.set(replace(_CTX.get(), **changes))  # type: ignore[arg-type]


def reset_context(token: contextvars.Token[RequestContext]) -> None:
    _CTX.reset(token)


__all__ = ["RequestContext", "current_context", "reset_context", "set_context"]
