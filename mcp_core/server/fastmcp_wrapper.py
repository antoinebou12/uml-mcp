"""
Wrapper for FastMCP server to ensure compatibility
"""

import json
import logging
import os
import sys
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# Resolved at import time (production vs mock); avoids mypy no-redef on import vs class.
_FastMCP_cls: type[Any]
_Context_cls: type[Any]

# Determine if we should use the mock implementation
use_mock = False

# Integration tests can request real FastMCP (for FastMCP Client testing); must be set before import
use_real_for_tests = os.environ.get("USE_REAL_FASTMCP", "").lower() in (
    "1",
    "true",
    "yes",
)

# Check if we're in a development or test environment (unless USE_REAL_FASTMCP is set)
is_dev_or_test = not use_real_for_tests and (
    os.environ.get("TESTING", "false").lower() in ("true", "1", "yes")
    or os.environ.get("DEVELOPMENT", "false").lower() in ("true", "1", "yes")
    or "pytest" in sys.modules
    or os.environ.get("MOCK_FASTMCP", "false").lower() in ("true", "1", "yes")
)

if is_dev_or_test:
    use_mock = True
    logger.warning("Using mock FastMCP implementation for development/testing")
else:
    try:
        import fastmcp

        if not hasattr(fastmcp, "FastMCP"):
            raise ImportError("FastMCP class not found in fastmcp package")
        logger.info("Using production FastMCP implementation")
        from fastmcp import FastMCP as _ImportedFastMCP

        _FastMCP_cls = _ImportedFastMCP

        # Context may be in fastmcp or fastmcp.context (2.x / 3.x)
        try:
            from fastmcp import Context as _ImportedContext

            _Context_cls = _ImportedContext
        except ImportError:
            try:
                import importlib

                _ctx_mod = importlib.import_module("fastmcp.context")
                _Context_cls = _ctx_mod.Context
            except ImportError:

                class _StubContext:
                    def __init__(self) -> None:
                        self.data: dict[str, Any] = {}

                    def get(self, key: str, default: Any = None) -> Any:
                        return self.data.get(key, default)

                    def set(self, key: str, value: Any) -> None:
                        self.data[key] = value

                _Context_cls = _StubContext
    except ImportError as e:
        logger.error(f"FastMCP package error: {e!s}")
        raise ImportError(
            "FastMCP package is required but not installed. Set MOCK_FASTMCP=true to use mock implementation."
        )

USING_MOCK_FASTMCP = use_mock

# Define mock classes if needed
if use_mock:

    class _MockContext:
        def __init__(self) -> None:
            self.data: dict[str, Any] = {}

        def get(self, key: str, default: Any = None) -> Any:
            return self.data.get(key, default)

        def set(self, key: str, value: Any) -> None:
            self.data[key] = value

    class _MockFastMCP:
        def __init__(self, name: str, **kwargs):
            self.name = name
            self._tools: dict[str, Callable[..., Any]] = {}
            self._prompts: dict[str, Callable[..., Any]] = {}
            self._resources: dict[str, Callable[..., Any]] = {}
            self.logger = logging.getLogger(__name__)

        def tool(self, *args, **kwargs):
            def decorator(func: Callable) -> Callable:
                tool_name_raw = kwargs.get("name", getattr(func, "__name__", "tool"))
                tool_name = (
                    tool_name_raw
                    if isinstance(tool_name_raw, str)
                    else str(tool_name_raw)
                )
                self._tools[tool_name] = func
                return func

            return decorator

        def prompt(self, prompt_name: str | None = None):
            def decorator(func: Callable) -> Callable:
                raw = (
                    prompt_name
                    if prompt_name is not None
                    else getattr(func, "__name__", "prompt")
                )
                name = raw if isinstance(raw, str) else str(raw)
                self._prompts[name] = func
                return func

            return decorator

        def resource(self, path: str):
            def decorator(func: Callable) -> Callable:
                self._resources[path] = func
                return func

            return decorator

        def run(
            self,
            transport: str = "stdio",
            host: str | None = None,
            port: int | None = None,
        ):
            if transport == "stdio":
                self._run_stdio()
            elif transport == "http":
                self._run_http(host or "127.0.0.1", port if port is not None else 8000)
            else:
                raise ValueError(f"Unsupported transport: {transport}")

        def _run_stdio(self):
            """Run the server in stdio mode"""
            self.logger.info(f"Starting {self.name} in stdio mode")
            while True:
                try:
                    line = input()
                    if not line:
                        continue
                    request = json.loads(line)
                    response = self._handle_request(request)
                    print(json.dumps(response))
                except EOFError:
                    break
                except Exception as e:  # noqa: BLE001 - keep the stdio loop alive for any request error
                    self.logger.error(f"Error handling request: {e}")
                    response = {"error": str(e)}
                    print(json.dumps(response))

        def _run_http(self, host: str, port: int):
            raise NotImplementedError(
                "Mock FastMCP does not support HTTP transport. "
                "Set USE_REAL_FASTMCP=1 or install the real fastmcp package."
            )

        def run_http(self, host: str = "127.0.0.1", port: int = 8000):
            """Public HTTP entry point called by start_server()."""
            self._run_http(host, port)

        def _handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
            """Handle an MCP request and return the response."""
            try:
                if "type" not in request:
                    raise ValueError("Missing request type")

                if request["type"] == "tool":
                    tool_name = request.get("tool")
                    if tool_name not in self._tools:
                        raise ValueError(f"Unknown tool: {tool_name}")
                    tool = self._tools[tool_name]
                    args = request.get("args", {})
                    result = tool(**args)
                    return {"result": result}

                elif request["type"] == "prompt":
                    prompt_name = request.get("prompt")
                    if prompt_name not in self._prompts:
                        raise ValueError(f"Unknown prompt: {prompt_name}")
                    prompt = self._prompts[prompt_name]
                    args = request.get("args", {})
                    result = prompt(**args)
                    return {"result": result}

                elif request["type"] == "resource":
                    path = request.get("path")
                    if path not in self._resources:
                        raise ValueError(f"Unknown resource: {path}")
                    resource = self._resources[path]
                    result = resource()
                    return {"result": result}

                else:
                    raise ValueError(f"Unknown request type: {request['type']}")

            except Exception as e:  # noqa: BLE001 - any tool failure becomes an error response
                return {"error": str(e)}

    _Context_cls = _MockContext
    _FastMCP_cls = _MockFastMCP


FastMCP = _FastMCP_cls
Context = _Context_cls

# Export the required classes
__all__ = ["USING_MOCK_FASTMCP", "Context", "FastMCP"]
