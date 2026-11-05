"""Background execution keeps the foreground schema and request context."""

import contextvars
import inspect
import threading

import pytest

from mcp_core.core.settings_file import TasksConfig, parse_app_config
from mcp_core.tools.background import async_tool, effective_tasks, validate_tasks


def test_task_config_environment_precedence(monkeypatch):
    config = parse_app_config({"tasks": {"enabled": True, "concurrency": 2}})
    monkeypatch.setenv("MCP_TASKS_ENABLED", "false")
    monkeypatch.setenv("FASTMCP_DOCKET_CONCURRENCY", "7")
    actual = effective_tasks(config.tasks)
    assert actual.enabled is False
    assert actual.concurrency == 7


def test_task_config_rejects_unsafe_deployment(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(ValueError, match="persistent worker"):
        validate_tasks(TasksConfig(enabled=True))
    monkeypatch.delenv("VERCEL")
    monkeypatch.delenv("FASTMCP_TASKS_ENCRYPTION_KEY", raising=False)
    with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
        validate_tasks(TasksConfig(enabled=True, url="redis://localhost:6379"))
    monkeypatch.setenv("FASTMCP_TASKS_ENCRYPTION_KEY", "configured")
    validate_tasks(TasksConfig(enabled=True, url="redis://localhost:6379"))


async def test_adapter_preserves_schema_context_and_worker_thread():
    request = contextvars.ContextVar("request", default="missing")
    request.set("caller")
    main_thread = threading.get_ident()

    def render(code: str, scale: int = 1) -> dict:
        return {
            "code": code,
            "scale": scale,
            "caller": request.get(),
            "worker": threading.get_ident() != main_thread,
        }

    adapted = async_tool(render)
    assert inspect.signature(adapted) == inspect.signature(render)
    assert inspect.iscoroutinefunction(adapted)
    assert await adapted("A -> B", scale=2) == {
        "code": "A -> B",
        "scale": 2,
        "caller": "caller",
        "worker": True,
    }


async def test_real_server_registration_and_foreground_call(monkeypatch):
    from fastmcp import Client, FastMCP

    from mcp_core.core.settings_file import AppConfig
    from mcp_core.tools.background import install_tasks
    from mcp_core.tools.tool_decorator import register_tools_with_server

    pytest.importorskip("fastmcp_tasks")
    config = AppConfig(tasks=TasksConfig(enabled=True))
    monkeypatch.setattr("mcp_core.core.settings_file.get_app_config", lambda: config)
    monkeypatch.delenv("VERCEL", raising=False)
    server = FastMCP("task-registration")
    install_tasks(server, config.tasks)
    register_tools_with_server(server)
    async with Client(server, mode="legacy") as client:
        result = await client.call_tool("list_diagram_types", {"query": "sequence"})
        assert not result.is_error


async def test_real_background_batch_completes(monkeypatch):
    from fastmcp import Client, FastMCP

    pytest.importorskip("fastmcp_tasks")
    from fastmcp_tasks.client import call_tool_task

    from mcp_core.core.settings_file import AppConfig
    from mcp_core.tools.background import install_tasks
    from mcp_core.tools.tool_decorator import register_tools_with_server

    config = AppConfig(tasks=TasksConfig(enabled=True))
    monkeypatch.setattr("mcp_core.core.settings_file.get_app_config", lambda: config)
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setattr(
        "mcp_core.tools.diagram_tools._render_batch_item",
        lambda index, raw, output_dir: {"index": index, "success": True},
    )
    server = FastMCP("background-batch")
    install_tasks(server, config.tasks)
    register_tools_with_server(server)
    async with Client(server) as client:
        task = await call_tool_task(
            client,
            "generate_uml_batch",
            {"items": [{"diagram_type": "plantuml", "code": "Alice -> Bob"}]},
        )
        await task.wait(timeout=20)
        result = await task.result()
        assert not result.is_error
        assert result.structured_content is not None
        assert result.structured_content["results"][0]["success"] is True
