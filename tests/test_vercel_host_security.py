"""Regression tests for FastMCP Host protection behind Vercel."""

from __future__ import annotations

import json
import os

from mcp_core.core import server as server_module


def _clear_security_env(monkeypatch) -> None:
    for name in (
        "FASTMCP_HTTP_ALLOWED_HOSTS",
        "FASTMCP_HTTP_ALLOWED_ORIGINS",
        "FASTMCP_HTTP_HOST_ORIGIN_PROTECTION",
        "MCP_ALLOWED_HOSTS",
        "MCP_ALLOWED_ORIGINS",
        "VERCEL",
        "VERCEL_URL",
        "VERCEL_BRANCH_URL",
        "VERCEL_PROJECT_PRODUCTION_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_vercel_hosts_are_added_to_fastmcp_allowlist(monkeypatch) -> None:
    _clear_security_env(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv(
        "VERCEL_URL",
        "uml-mcp-git-fix-vercel-mcp-host-421-antoinebou12.vercel.app",
    )
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "uml-mcp.vercel.app")

    server_module._configure_fastmcp_http_security()

    hosts = json.loads(os.environ["FASTMCP_HTTP_ALLOWED_HOSTS"])
    assert "uml-mcp.vercel.app" in hosts
    assert "uml-mcp-git-fix-vercel-mcp-host-421-antoinebou12.vercel.app" in hosts
    assert os.environ["FASTMCP_HTTP_HOST_ORIGIN_PROTECTION"] == "true"


def test_explicit_hosts_are_preserved_on_vercel(monkeypatch) -> None:
    _clear_security_env(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "uml.example.com")
    monkeypatch.setenv("VERCEL_URL", "uml-mcp.vercel.app")

    server_module._configure_fastmcp_http_security()

    hosts = json.loads(os.environ["FASTMCP_HTTP_ALLOWED_HOSTS"])
    assert hosts == ["uml.example.com", "uml-mcp.vercel.app"]


def test_non_vercel_without_allowlists_keeps_auto_protection(monkeypatch) -> None:
    _clear_security_env(monkeypatch)

    server_module._configure_fastmcp_http_security()

    assert os.environ["FASTMCP_HTTP_HOST_ORIGIN_PROTECTION"] == "auto"
    assert "FASTMCP_HTTP_ALLOWED_HOSTS" not in os.environ
    assert "FASTMCP_HTTP_ALLOWED_ORIGINS" not in os.environ
