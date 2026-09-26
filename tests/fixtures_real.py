"""Real-server fixtures: app.py in a subprocess, wired to a Kroki backend.

Kroki tiers (``kroki_tier`` / ``tier_stack``):

* ``fake``   – an in-test Kroki (always available, no network);
* ``local``  – a real Kroki at ``UML_MCP_TEST_KROKI_URL``
  (``docker compose up -d kroki mermaid blockdiag`` → ``http://127.0.0.1:8001``);
* ``public`` – https://kroki.io, only with ``UML_MCP_TEST_PUBLIC_KROKI=1``
  (marked ``public_kroki``; skipped when unreachable).
"""

from __future__ import annotations

import asyncio
import base64
import io
import os
import re
import socket
import subprocess
import sys
import threading
import time
import zlib
from collections.abc import Callable, Coroutine, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Self

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCAL = httpx.Client(trust_env=False, timeout=15)
TOKEN = "journey-token"
PUBLIC_KROKI = "https://kroki.io"
PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _png(width: int = 64, height: int = 32) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, "PNG")
    return buf.getvalue()


# ------------------------------------------------------------------ fake Kroki
class FakeKroki:
    """Minimal Kroki: POST /{type}/{format} and GET /{type}/{format}/{encoded}.

    The SVG echoes the words of the source so label checks work like on real
    Kroki; sources containing ``SYNTAX_ERROR`` get a Kroki-style HTTP 400.
    """

    def __init__(self) -> None:
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import Response
        from starlette.routing import Route

        self.requests: list[tuple[str, str, str]] = []
        png = _png()

        def respond(dtype: str, fmt: str, body: str) -> Response:
            self.requests.append((dtype, fmt, body))
            if "SYNTAX_ERROR" in body:
                return Response("Error 400: syntax error in diagram", status_code=400)
            if fmt == "png":
                return Response(png, media_type="image/png")
            words = "".join(f"<text>{w}</text>" for w in re.findall(r"\w+", body))
            svg = f'<svg xmlns="http://www.w3.org/2000/svg"><g>{words}</g></svg>'
            return Response(svg, media_type="image/svg+xml")

        async def post(request: Request) -> Response:
            p = request.path_params
            return respond(p["dtype"], p["fmt"], (await request.body()).decode())

        async def get(request: Request) -> Response:
            p = request.path_params
            try:
                raw = base64.urlsafe_b64decode(p["encoded"])
                body = zlib.decompress(raw).decode()
            except Exception:  # noqa: BLE001 - keep the raw path for odd encodings
                body = p["encoded"]
            return respond(p["dtype"], p["fmt"], body)

        app = Starlette(
            routes=[
                Route("/{dtype}/{fmt}", post, methods=["POST"]),
                Route("/{dtype}/{fmt}/{encoded:path}", get, methods=["GET"]),
            ]
        )
        import uvicorn

        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning")
        )
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self) -> Self:
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                return self
            time.sleep(0.05)
        raise RuntimeError("fake Kroki did not start")

    def __exit__(self, *exc: object) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


@dataclass
class KrokiBackend:
    name: str
    url: str
    fake: FakeKroki | None = None
    real: bool = field(init=False)

    def __post_init__(self) -> None:
        self.real = self.fake is None


# ---------------------------------------------------------------- real server
@contextmanager
def loopback_no_proxy() -> Iterator[None]:
    """Clients honour HTTP(S)_PROXY; loopback must never go through it."""
    saved = {k: os.environ.get(k) for k in ("NO_PROXY", "no_proxy")}
    for key in saved:
        current = [v for v in (os.environ.get(key) or "").split(",") if v]
        os.environ[key] = ",".join([*current, "127.0.0.1", "localhost"])
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture(scope="module")
def loopback_bypasses_proxy() -> Iterator[None]:
    with loopback_no_proxy():
        yield


@contextmanager
def start_stack(
    tmp: Path, kroki_url: str, *, keep_proxy: bool = False
) -> Iterator[dict[str, Any]]:
    """Run app.py (real FastMCP) against ``kroki_url`` with an empty config."""
    cfg = tmp / "uml-mcp.yaml"
    cfg.write_text(
        "admin: {allow_local_without_auth: true}\n"
        "audit: {enabled: true, sinks: [memory]}\n",
        encoding="utf-8",
    )
    port = free_port()
    dropped = ("MCP_AUTH", "KROKI") + (() if keep_proxy else PROXY_VARS)
    env = {k: v for k, v in os.environ.items() if not k.startswith(dropped)}
    no_proxy = [v for v in env.get("NO_PROXY", "").split(",") if v]
    env.update(
        {
            "UML_MCP_CONFIG": str(cfg),
            "USE_REAL_FASTMCP": "1",
            "MOCK_FASTMCP": "",
            "UML_MCP_ADMIN_TOKEN": TOKEN,
            "KROKI_SERVER": kroki_url,
            "MCP_DIAGRAM_FALLBACK": "false",
            "MCP_MEMORY_ONLY": "true",
            "NO_PROXY": ",".join([*no_proxy, "127.0.0.1", "localhost"]),
            "HOME": str(tmp / "home"),
            "XDG_CONFIG_HOME": str(tmp / "xdg"),
        }
    )
    env["no_proxy"] = env["NO_PROXY"]
    log_path = tmp / "server.log"
    with log_path.open("wb") as log:
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app:app"]
            + ["--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        base = f"http://127.0.0.1:{port}"
        try:
            for _ in range(80):
                try:
                    if LOCAL.get(f"{base}/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.25)
            else:
                pytest.fail("server did not start: " + log_path.read_text()[-3000:])
            yield {"base": base, "cfg": cfg, "log": log_path, "kroki": kroki_url}
        finally:
            proc.terminate()
            proc.wait(timeout=10)


def run_in_thread(
    session: Callable[[], Coroutine[Any, Any, dict[str, Any]]],
) -> dict[str, Any]:
    """Run an async client session in its own thread (Playwright owns a loop)."""
    out: dict[str, Any] = {}
    errors: list[BaseException] = []

    def target() -> None:
        try:
            out.update(asyncio.run(session()))
        except BaseException as exc:  # noqa: BLE001 - re-raised in the test thread
            errors.append(exc)

    worker = threading.Thread(target=target)
    worker.start()
    worker.join(timeout=180)
    if errors:
        raise errors[0]
    assert out, "client session did not finish"
    return out


# ------------------------------------------------------------ Kroki tiers
def _reachable(url: str, *, trust_env: bool) -> str | None:
    try:
        with httpx.Client(trust_env=trust_env, timeout=10) as client:
            response = client.get(f"{url.rstrip('/')}/health")
        if response.status_code == 200:
            return None
        return f"HTTP {response.status_code}"
    except httpx.HTTPError as exc:
        return f"{type(exc).__name__}: {exc}"


@pytest.fixture(scope="module")
def kroki() -> Iterator[FakeKroki]:
    with FakeKroki() as fake:
        yield fake


@pytest.fixture(scope="module")
def stack(tmp_path_factory, kroki) -> Iterator[dict[str, Any]]:
    """app.py wired to the fake Kroki; empty config (first run)."""
    with start_stack(tmp_path_factory.mktemp("journey"), kroki.url) as running:
        yield running


@pytest.fixture(
    scope="module",
    params=["fake", "local", pytest.param("public", marks=pytest.mark.public_kroki)],
)
def kroki_tier(request) -> Iterator[KrokiBackend]:
    if request.param == "fake":
        with FakeKroki() as fake:
            yield KrokiBackend("fake", fake.url, fake)
        return
    if request.param == "local":
        url = os.environ.get("UML_MCP_TEST_KROKI_URL", "").rstrip("/")
        if not url:
            pytest.skip(
                "set UML_MCP_TEST_KROKI_URL (docker compose up -d kroki mermaid "
                "blockdiag → http://127.0.0.1:8001)"
            )
        problem = _reachable(url, trust_env=False)
        if problem:
            pytest.fail(f"UML_MCP_TEST_KROKI_URL={url} is set but unhealthy: {problem}")
        yield KrokiBackend("local", url)
        return
    if os.environ.get("UML_MCP_TEST_PUBLIC_KROKI") != "1":
        pytest.skip("set UML_MCP_TEST_PUBLIC_KROKI=1 to render through kroki.io")
    problem = _reachable(PUBLIC_KROKI, trust_env=True)
    if problem:
        pytest.skip(f"{PUBLIC_KROKI} unreachable from here: {problem}")
    yield KrokiBackend("public", PUBLIC_KROKI)


@pytest.fixture(scope="module")
def tier_stack(tmp_path_factory, kroki_tier) -> Iterator[dict[str, Any]]:
    """app.py wired to the Kroki tier under test."""
    tmp = tmp_path_factory.mktemp(f"tier-{kroki_tier.name}")
    with start_stack(
        tmp, kroki_tier.url, keep_proxy=kroki_tier.name == "public"
    ) as running:
        yield {**running, "tier": kroki_tier}
