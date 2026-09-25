"""Read-only operations API for the admin dashboard (audit, metrics, limits, config, lint, tools).

Mounted under ``/admin/api`` by the enterprise admin router (MCP.Admin role) or,
when auth is off and ``admin.allow_local_without_auth`` is true, by
:func:`build_local_admin_router` (loopback clients only).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from ..observability.audit import get_audit_logger
from ..observability.metrics import METRICS
from ..observability.ratelimit import LIMITER

NO_STORE = {"Cache-Control": "no-store"}
Guard = Callable[[Request], None]


def _config_payload() -> dict[str, Any]:
    import os

    from ..core.settings_file import ENV_MAP, get_config

    loaded = get_config()
    return {
        "config_file": str(loaded.path) if loaded.path else None,
        "sections": loaded.app.model_dump(mode="json", exclude={"auth"}),
        "sources": {
            f"{section}.{key}": {
                "env": env_name,
                "source": loaded.source_of(env_name, os.environ),
                "set": env_name in os.environ,
            }
            for (section, key), env_name in ENV_MAP.items()
        },
    }


def _tools_payload() -> list[dict[str, Any]]:
    from ..core.settings_file import get_app_config
    from ..tools.tool_decorator import get_tool_registry

    app = get_app_config()
    out = []
    for name, info in sorted(get_tool_registry().items()):
        ann = info.get("annotations") or {}
        limit = app.rate_limit.tools.get(name)
        out.append(
            {
                "name": name,
                "enabled": app.tool_enabled(name),
                "permission": "read" if ann.get("readOnlyHint") else "write",
                "annotations": {k: v for k, v in ann.items() if k != "title"},
                "rate_limit_per_minute": limit.requests_per_minute if limit else None,
                "description": info.get("description"),
            }
        )
    return out


def add_ops_routes(router: APIRouter, guard: Guard) -> None:
    @router.get("/admin/api/audit")
    async def audit(
        request: Request,
        status: str | None = None,
        decision: str | None = None,
        operation: str | None = None,
        user: str | None = None,
        since: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> JSONResponse:
        guard(request)
        memory = get_audit_logger().memory
        if memory is None:
            return JSONResponse(
                {
                    "enabled": False,
                    "records": [],
                    "hint": "enable audit with the 'memory' sink in uml-mcp.yaml",
                },
                headers=NO_STORE,
            )
        records = memory.query(
            status=status,
            decision=decision,
            operation=operation,
            user=user,
            since=since,
            limit=max(1, min(limit, 1000)),
            offset=max(0, offset),
        )
        return JSONResponse({"enabled": True, "records": records}, headers=NO_STORE)

    @router.get("/admin/api/audit/export")
    async def audit_export(request: Request) -> Response:
        guard(request)
        memory = get_audit_logger().memory
        lines = [json.dumps(r, default=str) for r in (memory.records if memory else [])]
        return Response(
            "\n".join(lines) + ("\n" if lines else ""),
            media_type="application/x-ndjson",
            headers={
                **NO_STORE,
                "Content-Disposition": f'attachment; filename="uml-mcp-audit-{int(time.time())}.jsonl"',
            },
        )

    @router.get("/admin/api/metrics")
    async def metrics(request: Request) -> JSONResponse:
        guard(request)
        return JSONResponse(METRICS.snapshot(), headers=NO_STORE)

    @router.get("/admin/api/rate-limits")
    async def rate_limits(request: Request) -> JSONResponse:
        guard(request)
        from ..core.settings_file import get_app_config

        return JSONResponse(
            {
                "policy": get_app_config().rate_limit.model_dump(mode="json"),
                "hot_keys": LIMITER.hot_keys(),
                "rejected": METRICS.snapshot()["rate_limited"],
            },
            headers=NO_STORE,
        )

    @router.get("/admin/api/config")
    async def config(request: Request) -> JSONResponse:
        guard(request)
        return JSONResponse(_config_payload(), headers=NO_STORE)

    @router.get("/admin/api/config/download")
    async def config_download(request: Request) -> Response:
        guard(request)
        import yaml

        from ..core.settings_file import get_config

        data = dict(get_config().data) or {"version": 1}
        body = (
            "# Effective uml-mcp.yaml (generated; review before applying)\n"
            + yaml.safe_dump(data, sort_keys=False)
        )
        return Response(
            body,
            media_type="application/yaml",
            headers={
                **NO_STORE,
                "Content-Disposition": 'attachment; filename="uml-mcp.yaml"',
            },
        )

    @router.get("/admin/api/lint")
    async def lint(request: Request) -> JSONResponse:
        guard(request)
        from ..quality.lint import run_lint

        return JSONResponse([i.as_dict() for i in run_lint()], headers=NO_STORE)

    @router.get("/admin/api/lint/report")
    async def lint_report(request: Request) -> JSONResponse:
        """Grade/score/tokens (protocol rules) + definition/config rules."""
        guard(request)
        from ..quality.lint import run_lint
        from ..quality.wire import fetch_surface, lint_surface

        data: dict[str, Any] = {
            "grade": None,
            "score": None,
            "token_estimate": None,
            "counts": {},
            "issues": [],
        }
        try:
            data.update(lint_surface(await fetch_surface()).as_dict())
        except Exception as exc:  # noqa: BLE001 - e.g. mocked FastMCP in tests
            data["wire_error"] = str(exc)
        data["issues"] = data["issues"] + [i.as_dict() for i in run_lint()]
        return JSONResponse(data, headers=NO_STORE)

    @router.get("/admin/api/tools")
    async def tools(request: Request) -> JSONResponse:
        guard(request)
        return JSONResponse(_tools_payload(), headers=NO_STORE)


def build_local_admin_router() -> APIRouter:
    """Dashboard without auth, loopback only (``admin.allow_local_without_auth``)."""
    from ..admin_ui import add_spa_routes
    from .guards import local_guards
    from .routes import add_admin_routes

    router = APIRouter(include_in_schema=False)
    guards = local_guards()
    add_spa_routes(router, guards.read)

    @router.get("/admin/api/overview")
    async def overview(request: Request) -> JSONResponse:
        guards.read(request)
        from ..core.config import MCP_SETTINGS

        return JSONResponse(
            {
                "mode": "none",
                "local": True,
                "version": MCP_SETTINGS.version,
                "uptime_seconds": METRICS.snapshot()["uptime_seconds"],
            },
            headers=NO_STORE,
        )

    add_ops_routes(router, guards.read)
    add_admin_routes(router, guards)
    return router


def metrics_response() -> Response:
    return Response(METRICS.prometheus(), media_type="text/plain; version=0.0.4")


__all__ = [
    "add_ops_routes",
    "build_local_admin_router",
    "metrics_response",
]
