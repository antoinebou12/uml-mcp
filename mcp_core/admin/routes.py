"""Admin console write/control API, shared by the local and enterprise routers."""

from __future__ import annotations

import asyncio
import json
import os
import signal
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from . import settings_service as svc
from .guards import Guards

NO_STORE = {"Cache-Control": "no-store"}


def _actor(request: Request) -> str | None:
    principal = getattr(request.state, "auth_principal", None)
    if principal is None:
        return "local"
    return getattr(principal, "username", None) or getattr(principal, "subject", None)


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="body must be JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    return body


def _config_error(exc: Exception) -> JSONResponse:
    from ..auth import AuthConfigError
    from ..core.settings_file import ConfigFileError

    if isinstance(exc, svc.ReadOnlyConfigError):
        return JSONResponse(
            {"error": "read_only", "detail": str(exc)},
            status_code=409,
            headers=NO_STORE,
        )
    if isinstance(exc, (ConfigFileError, AuthConfigError, KeyError)):
        return JSONResponse(
            {"error": "invalid", "detail": str(exc)}, status_code=422, headers=NO_STORE
        )
    raise exc


def schedule_stop(delay: float = 0.5) -> None:
    """Send SIGTERM to ourselves after the response is flushed (graceful shutdown)."""
    asyncio.get_running_loop().call_later(delay, os.kill, os.getpid(), signal.SIGTERM)


def add_admin_routes(router: APIRouter, guards: Guards) -> None:
    @router.get("/admin/api/settings/schema")
    async def settings_schema(request: Request) -> JSONResponse:
        guards.read(request)
        return JSONResponse(svc.schema(), headers=NO_STORE)

    @router.get("/admin/api/settings")
    async def settings_get(request: Request) -> JSONResponse:
        guards.read(request)
        return JSONResponse({**svc.current(), "mode": guards.mode}, headers=NO_STORE)

    @router.put("/admin/api/settings")
    async def settings_put(request: Request) -> JSONResponse:
        guards.write(request)
        body = await _json_body(request)
        try:
            result = svc.save(body.get("data") or {}, actor=_actor(request))
        except Exception as exc:  # noqa: BLE001 - mapped to 409/422
            return _config_error(exc)
        return JSONResponse(result, headers=NO_STORE)

    @router.post("/admin/api/settings/validate")
    async def settings_validate(request: Request) -> JSONResponse:
        guards.read(request)
        body = await _json_body(request)
        try:
            svc.validate({**(body.get("data") or {}), "version": 1})
        except Exception as exc:  # noqa: BLE001
            return _config_error(exc)
        return JSONResponse({"valid": True}, headers=NO_STORE)

    @router.post("/admin/api/settings/reset")
    async def settings_reset(request: Request) -> JSONResponse:
        guards.write(request)
        body = await _json_body(request)
        try:
            result = svc.reset(
                body.get("section"), body.get("profile"), actor=_actor(request)
            )
        except Exception as exc:  # noqa: BLE001
            return _config_error(exc)
        return JSONResponse(result, headers=NO_STORE)

    @router.post("/admin/api/setup/preview")
    async def setup_preview(request: Request) -> JSONResponse:
        """YAML the Setup form would write for a profile + feature set."""
        guards.read(request)
        import yaml

        from ..core.features import build_config

        body = await _json_body(request)
        try:
            data = build_config(
                str(body.get("profile") or "local"),
                set(body.get("features") or []),
                body.get("overrides") or None,
            )
        except (KeyError, ValueError) as exc:
            return _config_error(KeyError(str(exc)))
        return JSONResponse(
            {"data": data, "yaml": yaml.safe_dump(data, sort_keys=False)},
            headers=NO_STORE,
        )

    @router.get("/admin/api/setup/status")
    async def setup_status(request: Request) -> JSONResponse:
        guards.read(request)
        cur = svc.current()
        return JSONResponse(
            {
                k: cur[k]
                for k in (
                    "path",
                    "exists",
                    "writable",
                    "setup",
                    "setup_complete",
                    "features",
                )
            }
            | {"mode": guards.mode},
            headers=NO_STORE,
        )

    @router.post("/admin/api/server/stop")
    async def server_stop(request: Request) -> JSONResponse:
        guards.stop(request)
        from ..observability.audit import record_operation

        record_operation(
            operation_type="admin",
            operation_name="server.stop",
            operation_status="success",
            policy_decision="allow",
            policy_reason=f"admin console ({_actor(request)})",
        )
        schedule_stop()
        return JSONResponse({"stopping": True}, status_code=202, headers=NO_STORE)

    @router.get("/admin/api/logs")
    async def logs(
        request: Request,
        after: int = 0,
        level: str | None = None,
        q: str | None = None,
        limit: int = 500,
    ) -> JSONResponse:
        guards.read(request)
        from ..observability.logging_setup import RING

        records = RING.query(after=after, level=level, q=q, limit=limit)
        return JSONResponse(
            {"records": records, "last_seq": RING.seq}, headers=NO_STORE
        )

    @router.get("/admin/api/logs/stream")
    async def logs_stream(
        request: Request,
        level: str | None = None,
        q: str | None = None,
        max_seconds: int = 3600,
    ) -> StreamingResponse:
        guards.read(request)
        from ..observability.logging_setup import RING

        async def events():
            last = RING.seq
            for _ in range(max(1, min(max_seconds, 3600))):  # EventSource reconnects
                if await request.is_disconnected():
                    return
                for rec in RING.query(after=last, level=level, q=q):
                    last = rec["seq"]
                    yield f"id: {rec['seq']}\ndata: {json.dumps(rec)}\n\n"
                yield ": keep-alive\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={**NO_STORE, "X-Accel-Buffering": "no"},
        )

    @router.get("/admin/api/metrics/timeseries")
    async def timeseries(request: Request, minutes: int = 60) -> JSONResponse:
        guards.read(request)
        from ..observability.metrics import METRICS

        return JSONResponse({"points": METRICS.timeseries(minutes)}, headers=NO_STORE)

    @router.post("/admin/api/clients/{client}")
    async def client_install(request: Request, client: str) -> JSONResponse:
        """Register the local stdio server in an MCP client (local console only)."""
        guards.write(request)
        if guards.mode != "local":
            raise HTTPException(status_code=404, detail="Not Found")
        from ..core.client_install import install

        dry_run = request.query_params.get("dry_run") in ("1", "true")
        try:
            text, path = install(client, dry_run=dry_run)
        except ValueError as exc:
            return JSONResponse(
                {"error": "invalid", "detail": str(exc)}, status_code=422
            )
        return JSONResponse(
            {"path": str(path) if path else None, "config": text, "dry_run": dry_run},
            headers=NO_STORE,
        )


__all__ = ["add_admin_routes", "schedule_stop"]
