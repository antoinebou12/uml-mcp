"""Optional protocol background execution for persistent server processes."""

from __future__ import annotations

import os
from collections.abc import Callable
from functools import partial, wraps
from typing import Any

from mcp_core.core.settings_file import TasksConfig

TASK_TOOLS = frozenset({"generate_uml", "generate_uml_image", "generate_uml_batch"})


def effective_tasks(config: TasksConfig) -> TasksConfig:
    values = config.model_dump()
    for field, variable in {
        "enabled": "MCP_TASKS_ENABLED",
        "url": "FASTMCP_DOCKET_URL",
        "name": "FASTMCP_DOCKET_NAME",
        "concurrency": "FASTMCP_DOCKET_CONCURRENCY",
    }.items():
        if variable in os.environ:
            values[field] = os.environ[variable]
    return TasksConfig.model_validate(values)


def validate_tasks(config: TasksConfig) -> None:
    if not config.enabled:
        return
    if os.environ.get("VERCEL"):
        raise ValueError(
            "Background tasks require a persistent worker; disable tasks on Vercel."
        )
    if not config.url.startswith(("memory://", "redis://", "rediss://")):
        raise ValueError("tasks.url must use memory://, redis:// or rediss://.")
    if config.url.startswith(("redis://", "rediss://")) and not os.environ.get(
        "FASTMCP_TASKS_ENCRYPTION_KEY"
    ):
        raise ValueError(
            "Redis tasks require FASTMCP_TASKS_ENCRYPTION_KEY to protect caller context."
        )


def install_tasks(server: Any, config: TasksConfig) -> None:
    config = effective_tasks(config)
    validate_tasks(config)
    if not config.enabled:
        return
    try:
        from fastmcp_tasks import TasksExtension
    except ImportError as exc:
        raise RuntimeError(
            'Background tasks require installing "uml-mcp[tasks]".'
        ) from exc
    server.add_extension(
        TasksExtension(url=config.url, name=config.name, concurrency=config.concurrency)
    )


def async_tool(func: Callable[..., Any]) -> Callable[..., Any]:
    """Preserve schemas and request context while offloading blocking renders."""

    @wraps(func)
    async def run(*args: Any, **kwargs: Any) -> Any:
        from anyio import to_thread

        return await to_thread.run_sync(partial(func, *args, **kwargs))

    return run
