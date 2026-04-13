---
name: mcp-python
description: Create and extend MCP (Model Context Protocol) servers in Python using FastMCP and the official SDK. Covers tools, resources, prompts, STDIO vs HTTP transports, logging rules for STDIO, and production best practices. Use when building or modifying MCP servers in Python, adding tools/resources/prompts, debugging MCP servers, or choosing transport and client config.
---

# MCP Servers in Python

Create and extend MCP servers in Python with FastMCP and the official MCP Python SDK. Based on [MCP Build a server](https://modelcontextprotocol.io/docs/develop/build-server) and [MCP Best Practices](https://mcp-best-practice.github.io/mcp-best-practice/best-practice/).

## When to Use

- Building or extending MCP servers in Python
- Adding tools, resources, or prompts
- Debugging MCP server connection or tool discovery
- Choosing transport (stdio vs streamable HTTP)
- Configuring clients (Claude Desktop, Cursor) to run the server

## Core Concepts

- **Tools**: Functions callable by the LLM (with user approval). Have explicit input/output and side-effect disclosure.
- **Resources**: Readable data (files, API responses) the client fetches for context. URI-based.
- **Prompts**: Pre-written templates for specific tasks; reduce prompt drift.
- **Discovery**: Clients enumerate tools/resources/prompts and get schemas at connect time.
- **Transports**: **stdio** for local, per-user processes; **streamable HTTP** for remote, shared services.

## FastMCP Quick Reference

Python 3.12, MCP Python SDK 1.2.0+. Use `uv add "mcp[cli]"` or `uv add fastmcp` (or project may use `fastmcp` package).

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("my-server")

@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.
    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    # ... fetch and return string
    return result

@mcp.resource("config://{key}")
def get_config(key: str) -> str:
    """Get config value by key."""
    return config_store.get(key, "")

@mcp.prompt()
def plan_task(goal: str, steps: int = 5) -> str:
    """Generate a step-by-step plan. Args: goal, steps (default 5)."""
    return f"Plan for: {goal} in {steps} steps."

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
```

- **Tool schemas**: FastMCP infers names, types, and descriptions from type hints and docstrings (Args/Returns).
- **Run**: `mcp.run(transport="stdio")` for stdio; use streamable HTTP for remote deployment.

## STDIO Critical Rule

For **STDIO-based servers**, never write to **stdout**. JSON-RPC uses stdout; any print or stdout write corrupts messages and breaks the server.

- **Bad**: `print("Processing")`, `sys.stdout.write(...)`
- **Good**: `import logging` and `logging.info(...)` (logging writes to stderr by default), or log to a file.

For HTTP-based servers, stdout logging is fine.

## Best Practices (Short)

- **Single responsibility**: One clear domain and auth boundary per server.
- **Bounded toolsets**: Focused tools with specific contracts; avoid kitchen-sink servers.
- **Contracts first**: Strict input/output schemas, explicit side effects, documented errors.
- **Stateless by default**: No hidden in-memory state; use external stores if needed.
- **Least privilege**: Precise tools; gate high-impact or destructive actions behind approval.
- **Additive change**: Version tool schemas; prefer additive evolution; deprecate with notice.

## Scaffolding a New Server

```bash
uvx create-mcp-server
# Follow prompts; then:
cd <generated-project>
uv sync --dev --all-extras
uv run <server-module>
```

## Client Config (stdio)

Example for Claude Desktop or Cursor MCP (stdio, using uv):

```json
{
  "mcpServers": {
    "my-server": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/project", "run", "server.py"]
    }
  }
}
```

Use absolute path to the project directory. On Windows use forward slashes or escaped backslashes in JSON.

## References

- [Build an MCP server (Python)](https://modelcontextprotocol.io/docs/develop/build-server)
- [MCP Best Practices](https://mcp-best-practice.github.io/mcp-best-practice/best-practice/)
- [MCP Python SDK](https://modelcontextprotocol.github.io/python-sdk/)
