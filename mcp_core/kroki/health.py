"""Is a Kroki server usable? ``/health`` plus one real render per companion.

Kroki's ``/health`` only covers the core server. Mermaid, BPMN, Excalidraw and
blockdiag run in companion containers that can be missing or still starting, so
each is checked by rendering its catalog example.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

# diagram type -> companion container that renders it
COMPANIONS: dict[str, str] = {
    "mermaid": "kroki-mermaid",
    "blockdiag": "kroki-blockdiag",
    "bpmn": "kroki-bpmn",
    "excalidraw": "kroki-excalidraw",
}


def _example(dtype: str) -> str:
    from tools.kroki.kroki_templates import DiagramExamples

    return DiagramExamples.get_example(dtype)


def _version(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    kroki = (payload.get("version") or {}).get("kroki")
    if isinstance(kroki, dict):
        return kroki.get("number")
    return kroki if isinstance(kroki, str) else None


def probe(
    url: str,
    types: tuple[str, ...] | None = None,
    *,
    trust_env: bool = True,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Health of the Kroki at ``url``: reachability, version and each companion."""
    base = url.rstrip("/")
    types = tuple(COMPANIONS) if types is None else types
    result: dict[str, Any] = {
        "url": base,
        "reachable": False,
        "version": None,
        "error": None,
        "companions": {},
    }
    with httpx.Client(trust_env=trust_env, timeout=timeout) as client:
        try:
            health = client.get(f"{base}/health")
            result["reachable"] = health.status_code == 200
            if health.status_code == 200:
                try:
                    result["version"] = _version(health.json())
                except ValueError:
                    pass
            else:
                result["error"] = f"/health returned HTTP {health.status_code}"
        except httpx.HTTPError as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
            for dtype in types:
                result["companions"][dtype] = {"ok": False, "detail": "unreachable"}
            return result
        for dtype in types:
            try:
                response = client.post(
                    f"{base}/{dtype}/svg",
                    content=_example(dtype).encode(),
                    headers={"Content-Type": "text/plain"},
                )
                ok = response.status_code == 200 and bool(response.content)
                detail = "ok" if ok else f"HTTP {response.status_code}"
                if not ok and response.text:
                    detail += f": {response.text.strip().splitlines()[0][:120]}"
            except httpx.HTTPError as exc:
                ok, detail = False, f"{type(exc).__name__}: {exc}"
            result["companions"][dtype] = {"ok": ok, "detail": detail}
    return result


def ready(report: dict[str, Any]) -> bool:
    return bool(report["reachable"]) and all(
        c["ok"] for c in report["companions"].values()
    )


def wait_until_ready(
    url: str,
    timeout: float = 180.0,
    types: tuple[str, ...] | None = None,
    *,
    trust_env: bool = True,
    interval: float = 3.0,
) -> dict[str, Any]:
    """Probe until everything renders or ``timeout`` passes; return the last probe."""
    deadline = time.monotonic() + timeout
    while True:
        report = probe(url, types, trust_env=trust_env)
        if ready(report) or time.monotonic() > deadline:
            return report
        time.sleep(interval)


__all__ = ["COMPANIONS", "probe", "ready", "wait_until_ready"]
