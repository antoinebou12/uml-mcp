"""Redirect URI policy for the ``entra-proxy`` facade (RFC 8252 / MCP 2025-11-25).

Built in: VS Code web redirects (exact) and loopback redirects on any port
(``127.0.0.1``, ``[::1]``, ``localhost``; http only, path matched exactly by the
registration). Admins may add exact extras (for example a Cursor
``cursor://`` callback, which MCP does not consider compliant: opt-in only).
"""

from __future__ import annotations

from urllib.parse import urlsplit

BUILTIN_EXACT = frozenset(
    {"https://vscode.dev/redirect", "https://insiders.vscode.dev/redirect"}
)
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def is_loopback(uri: str) -> bool:
    parts = urlsplit(uri)
    return parts.scheme == "http" and (parts.hostname or "") in LOOPBACK_HOSTS


def redirect_allowed(uri: str, extra: list[str] | tuple[str, ...] = ()) -> bool:
    """Is ``uri`` acceptable as a client redirect URI at all?"""
    if not isinstance(uri, str) or not uri or len(uri) > 2048:
        return False
    parts = urlsplit(uri)
    if parts.fragment or parts.username or parts.password:
        return False
    if uri in BUILTIN_EXACT or uri in extra:
        return True
    return is_loopback(uri)


def redirect_matches(requested: str, registered: str) -> bool:
    """Registration match: exact, except loopback ports are ignored (RFC 8252 §7.3)."""
    if requested == registered:
        return True
    if is_loopback(requested) and is_loopback(registered):
        a, b = urlsplit(requested), urlsplit(registered)
        return (a.hostname, a.path, a.query) == (b.hostname, b.path, b.query)
    return False


__all__ = ["BUILTIN_EXACT", "is_loopback", "redirect_allowed", "redirect_matches"]
