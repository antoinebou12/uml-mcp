"""Unit tests for request ID middleware and rate-limit helper."""

from unittest.mock import patch

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import mcp_core.core.http_observability as http_obs
from mcp_core.core.config import MCP_SETTINGS
from mcp_core.core.http_observability import (
    RequestIdAndRateLimitMiddleware,
    _rate_limited,
)


@pytest.fixture(autouse=True)
def _clear_rate_buckets():
    http_obs._rate_buckets.clear()
    yield
    http_obs._rate_buckets.clear()


class TestRateLimitedHelper:
    """Tests for _rate_limited (sliding window per client IP)."""

    def test_disabled_when_limit_zero(self):
        assert _rate_limited("1.2.3.4", 0) is False
        assert _rate_limited("1.2.3.4", 0) is False

    def test_allows_up_to_limit_then_blocks(self):
        assert _rate_limited("10.0.0.1", 2) is False
        assert _rate_limited("10.0.0.1", 2) is False
        assert _rate_limited("10.0.0.1", 2) is True

    def test_buckets_are_per_client_ip(self):
        assert _rate_limited("10.0.0.2", 1) is False
        assert _rate_limited("10.0.0.3", 1) is False

    def test_old_entries_expire_after_sixty_seconds(self, monkeypatch):
        """Stale timestamps are dropped so the window can accept new requests."""
        times = iter([100.0, 100.0, 161.0, 161.0])

        monkeypatch.setattr(http_obs.time, "monotonic", lambda: next(times))
        assert _rate_limited("10.0.0.9", 1) is False
        assert _rate_limited("10.0.0.9", 1) is True
        assert _rate_limited("10.0.0.9", 1) is False


def _make_app() -> Starlette:
    async def ok(_request):
        return PlainTextResponse("ok")

    return Starlette(routes=[Route("/mcp", ok), Route("/other", ok)])


class TestRequestIdAndRateLimitMiddleware:
    """Integration-style tests for RequestIdAndRateLimitMiddleware."""

    def test_propagates_incoming_x_request_id(self):
        app = _make_app()
        app.add_middleware(RequestIdAndRateLimitMiddleware)
        client = TestClient(app)

        r = client.get("/other", headers={"X-Request-ID": "fixed-id"})
        assert r.status_code == 200
        assert r.headers["X-Request-ID"] == "fixed-id"

    def test_generates_x_request_id_when_absent(self):
        app = _make_app()
        app.add_middleware(RequestIdAndRateLimitMiddleware)
        client = TestClient(app)

        r = client.get("/other")
        assert r.status_code == 200
        assert "X-Request-ID" in r.headers
        assert len(r.headers["X-Request-ID"]) >= 8

    def test_rate_limit_returns_429_on_protected_paths(self):
        app = _make_app()
        app.add_middleware(RequestIdAndRateLimitMiddleware)
        client = TestClient(app)

        with patch.object(MCP_SETTINGS, "rate_limit_per_minute", 2):
            assert client.get("/mcp").status_code == 200
            assert client.get("/mcp").status_code == 200
            r3 = client.get("/mcp")
            assert r3.status_code == 429
            assert r3.json()["detail"] == "Rate limit exceeded. Try again later."
            assert "X-Request-ID" in r3.headers

    def test_non_protected_path_not_subject_to_rate_limit(self):
        app = _make_app()
        app.add_middleware(RequestIdAndRateLimitMiddleware)
        client = TestClient(app)

        with patch.object(MCP_SETTINGS, "rate_limit_per_minute", 1):
            assert client.get("/other").status_code == 200
            assert client.get("/other").status_code == 200
