"""Admin console: Kroki status, a render playground and the local Docker stack.

* ``GET  /admin/api/kroki``            status of the configured Kroki (+ Docker, local)
* ``GET  /admin/api/kroki/catalog``    diagram types with formats and an example
* ``POST /admin/api/kroki/render``     render like ``generate_uml`` (playground)
* ``POST /admin/api/kroki/use``        point rendering at another Kroki (saved, live)
* ``POST /admin/api/kroki/docker/up``  start Kroki + companions (local console only)
* ``POST /admin/api/kroki/docker/down``
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from .guards import WRITE_HEADER, Guards

NO_STORE = {"Cache-Control": "no-store"}


async def _body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="body must be JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    return body


def _require_header(request: Request) -> None:
    """A custom header forces a CORS preflight, so other sites cannot POST here."""
    if request.headers.get(WRITE_HEADER) != "1":
        raise HTTPException(
            status_code=403, detail=f"{WRITE_HEADER}: 1 header required"
        )


def _audit(name: str, status: str, data: dict[str, Any], actor: str | None) -> None:
    from ..observability.audit import record_operation

    record_operation(
        operation_type="admin",
        operation_name=name,
        input_data=data,
        operation_status=status,
        policy_decision="allow",
        policy_reason=f"admin console{f' ({actor})' if actor else ''}",
    )


def _actor(request: Request) -> str | None:
    principal = getattr(request.state, "auth_principal", None)
    if principal is None:
        return "local"
    return getattr(principal, "username", None) or getattr(principal, "subject", None)


def _kroki_url() -> str:
    from ..core.config import MCP_SETTINGS

    return MCP_SETTINGS.kroki_server.rstrip("/")


def catalog() -> list[dict[str, Any]]:
    from tools.kroki.kroki_templates import DiagramExamples

    from ..core.config import MCP_SETTINGS

    return [
        {
            "name": name,
            "backend": spec.backend,
            "description": spec.description,
            "formats": list(spec.formats),
            "example": DiagramExamples.get_example(name),
        }
        for name, spec in sorted(MCP_SETTINGS.diagram_types.items())
    ]


def render(diagram_type: str, code: str, output_format: str) -> dict[str, Any]:
    """The ``generate_uml`` pipeline, always returning bytes (never files)."""
    from ..core.diagram_service import DiagramRequest, generate_from_request

    out = generate_from_request(
        DiagramRequest(
            diagram_type=diagram_type,
            code=code,
            output_dir=None,
            output_format=output_format,
            force_fetch=True,
        )
    )
    keep = (
        "content_base64",
        "mime_type",
        "url",
        "playground",
        "error",
        "error_detail",
        "render_ms",
        "source",
        "attempts",
    )
    return {k: out[k] for k in keep if k in out}


def use_kroki(url: str, actor: str | None) -> dict[str, Any]:
    """Save ``rendering.kroki_server`` and switch the running server to it."""
    from ..core.utils import use_kroki_server
    from . import settings_service as svc

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=422, detail="url must be http(s)://host[:port]")
    locked = svc.env_locked()
    if "rendering.kroki_server" in locked:
        raise HTTPException(
            status_code=409,
            detail=f"KROKI_SERVER is set by the environment ({locked['rendering.kroki_server']}); "
            "change it there",
        )
    os.environ.pop("KROKI_SERVER", None)  # came from the file; reload re-applies it
    data = svc.current()["data"]
    rendering = dict(data.get("rendering") or {})
    rendering["kroki_server"] = url.rstrip("/")
    data["rendering"] = rendering
    saved = svc.save(data, actor=actor)
    use_kroki_server(url)
    return {**saved, "kroki_server": url.rstrip("/"), "applied_live": True}


def add_kroki_routes(router: APIRouter, guards: Guards) -> None:
    @router.get("/admin/api/kroki")
    async def kroki_status(request: Request) -> JSONResponse:
        guards.read(request)
        from ..kroki import health, stack

        report = await asyncio.to_thread(health.probe, _kroki_url())
        body: dict[str, Any] = {"kroki": report, "mode": guards.mode, "docker": None}
        if guards.mode == "local":
            body["docker"] = await asyncio.to_thread(stack.status)
        return JSONResponse(body, headers=NO_STORE)

    @router.get("/admin/api/kroki/catalog")
    async def kroki_catalog(request: Request) -> JSONResponse:
        guards.read(request)
        return JSONResponse({"types": catalog()})

    @router.post("/admin/api/kroki/render")
    async def kroki_render(request: Request) -> JSONResponse:
        guards.read(request)
        _require_header(request)
        body = await _body(request)
        dtype = str(body.get("diagram_type") or "")
        code = str(body.get("code") or "")
        fmt = str(body.get("output_format") or "svg")
        out = await asyncio.to_thread(render, dtype, code, fmt)
        _audit(
            "kroki.render",
            "error" if out.get("error") else "success",
            {"diagram_type": dtype, "output_format": fmt, "chars": len(code)},
            _actor(request),
        )
        return JSONResponse(out, status_code=200, headers=NO_STORE)

    @router.post("/admin/api/kroki/use")
    async def kroki_use(request: Request) -> JSONResponse:
        guards.write(request)
        body = await _body(request)
        try:
            result = await asyncio.to_thread(
                use_kroki, str(body.get("url") or ""), _actor(request)
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 - config errors are shown in the UI
            return JSONResponse(
                {"error": "invalid", "detail": str(exc)}, status_code=422
            )
        return JSONResponse(result, headers=NO_STORE)

    async def _docker(request: Request, action: str) -> JSONResponse:
        guards.write(request)
        if guards.mode != "local":  # Kubernetes/Helm manage Kroki in enterprise mode
            raise HTTPException(status_code=404, detail="Not Found")
        from ..kroki import health, stack

        body = await _body(request) if action == "up" else {}
        try:
            if action == "up":
                port = int(body.get("port") or stack.DEFAULT_PORT)
                result = await asyncio.to_thread(stack.up, port)
                result["health"] = await asyncio.to_thread(
                    health.wait_until_ready, result["url"], 240.0, None, trust_env=False
                )
                if body.get("use"):
                    result["use"] = await asyncio.to_thread(
                        use_kroki, result["url"], _actor(request)
                    )
            else:
                result = await asyncio.to_thread(stack.down)
        except HTTPException:
            raise
        except (stack.StackError, ValueError) as exc:
            _audit(f"kroki.docker.{action}", "error", {"error": str(exc)}, None)
            status = 503 if isinstance(exc, stack.DockerUnavailable) else 422
            return JSONResponse(
                {"error": "docker", "detail": str(exc)}, status_code=status
            )
        _audit(f"kroki.docker.{action}", "success", {}, _actor(request))
        return JSONResponse(result, headers=NO_STORE)

    @router.post("/admin/api/kroki/docker/up")
    async def kroki_docker_up(request: Request) -> JSONResponse:
        return await _docker(request, "up")

    @router.post("/admin/api/kroki/docker/down")
    async def kroki_docker_down(request: Request) -> JSONResponse:
        return await _docker(request, "down")


__all__ = ["add_kroki_routes", "catalog", "render", "use_kroki"]
