"""Reject requests for common exploit targets before application dispatch."""

import re
from urllib.parse import unquote

from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

_CREDENTIAL_FILES = frozenset(
    {
        "credentials.json",
        "google-credentials.json",
        "google-key.json",
        "application_default_credentials.json",
        "key.json",
        "keyfile.json",
        "firebase-adminsdk.json",
        "firebase-key.json",
        "gcp-sa.json",
        "gcp-credentials.json",
        "gcp-key.json",
        "sa.json",
        "service-account.json",
    }
)
_PHP_TARGET = re.compile(r"\.php(?:[./~]|$)", re.IGNORECASE)


def is_probe_path(path: str) -> bool:
    # ASGI paths are decoded already; decode again for nested encodings.
    for _ in range(3):
        decoded = unquote(path)
        if decoded == path:
            break
        path = decoded
    parts = [p for p in path.replace("\\", "/").lower().split("/") if p]
    return bool(
        any(
            p in {".git", ".svn", ".hg", ".aws", ".ssh"}
            or p == ".env"
            or p.startswith(".env.")
            for p in parts
        )
        or parts
        and parts[-1] in _CREDENTIAL_FILES
        or _PHP_TARGET.search(path)
        or path.lower().rstrip("/") in {"/_environment", "/_profiler/phpinfo"}
    )


class ProbeGuardMiddleware:
    """Apply the same path protection on Vercel and container hosts.

    Do not ban by peer IP: hosted gateways can share one peer across clients.
    Rejected requests never reach routing, rendering, auth or request logging.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and is_probe_path(scope.get("path", "")):
            await Response(status_code=403, headers={"Cache-Control": "no-store"})(
                scope, receive, send
            )
            return
        await self.app(scope, receive, send)
