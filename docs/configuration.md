# Configuration

UML-MCP can be configured using environment variables and MCP client config files.

## Running with FastMCP CLI

When a `fastmcp.json` file is present in the project root, you can run the server with the [FastMCP CLI](https://gofastmcp.com/):

```bash
# Use config from fastmcp.json (auto-detected in current directory)
fastmcp run

# Or specify the config file explicitly
fastmcp run fastmcp.json

# Or run a specific file; the CLI looks for a variable named mcp, server, or app
fastmcp run server.py
```

Command-line options override values in `fastmcp.json` (e.g. `fastmcp run --port 8080`). For the full local CLI with options like `--list-tools`, use `python server.py` instead.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_OUTPUT_DIR` / `UML_MCP_OUTPUT_DIR` | Directory to save generated diagrams | `./output` |
| `KROKI_SERVER` | URL of the Kroki server | `https://kroki.io` |
| `PLANTUML_SERVER` | URL of the PlantUML server | `http://plantuml-server:8080` |
| `USE_LOCAL_KROKI` | Use local Kroki server (true/false) | `false` |
| `USE_LOCAL_PLANTUML` | Use local PlantUML server (true/false) | `false` |
| `MCP_DIAGRAM_FALLBACK` | After Kroki fails, try PlantUML server / Mermaid.ink | **On** for typical desktop; **off** when `VERCEL` is set or `USE_LOCAL_KROKI=true` unless overridden |
| `FASTMCP_STATELESS_HTTP` | Enable stateless HTTP for multi-worker/horizontal scaling (true/false) | `false` |

## Health check (HTTP deployment)

When running the FastAPI app (`app.py`) for HTTP deployment (e.g. Vercel, Docker, uvicorn), a **health endpoint** is available:

- **Endpoint**: `GET /health` (no authentication required)
- **Response**: `{"status": "healthy", "modules_available": true|false}`
  - `status`: Always `"healthy"` when the server is up.
  - `modules_available`: Whether diagram backends (Kroki, PlantUML, etc.) could be loaded.

Use this endpoint for load balancers, readiness/liveness probes (e.g. Kubernetes, Docker, Vercel), and monitoring. For HTTP deployment, the FastAPI app’s `/health` is the canonical health endpoint for readiness checks.

When running the MCP server via `fastmcp run` with HTTP transport only (no FastAPI app), the standalone server does not expose `/health` unless you add a custom route; use the FastAPI app if you need the health endpoint.

## Stateless HTTP (multi-worker / horizontal scaling)

When running **multiple workers or instances** (e.g. `uvicorn app:app --workers 4` or multiple pods behind a load balancer), FastMCP’s default server-side sessions can break because sessions are stored per process. Enable **stateless HTTP** so each request gets a fresh context:

Set the environment variable:

```bash
FASTMCP_STATELESS_HTTP=true
```

This is recommended for multi-worker or horizontally scaled deployments. The MCP server is created with `stateless_http=True` when this variable is set to `1`, `true`, or `yes` (case-insensitive).

## MCP client configuration

Example MCP server config snippets for **Cursor** and **Claude Desktop** are in the **[`config/`](https://github.com/antoinebou12/uml-mcp/tree/main/config)** folder in this repo:

- **`config/cursor_config.json`** — Cursor
- **`config/claude_desktop_config.json`** — Claude Desktop
- **`config/README.md`** — Where each app stores its config and how to copy the examples

Copy the relevant `mcpServers` block into your client’s config file and set `cwd` to your `uml-mcp` project root. The examples use **`args`: `["-u", "server.py"]`** (unbuffered stdio, path relative to `cwd`). The main server entry point is **`server.py`**. Optional `env` keys include `KROKI_SERVER`, `MCP_OUTPUT_DIR`, and `MCP_DIAGRAM_FALLBACK` (see table above).

## Advanced Configuration

### Custom Templates

You can customize diagram templates by modifying the templates in the `tools/kroki/kroki_templates.py` file.

### Output Formats

Each diagram type supports specific output formats:

| Diagram Type | Supported Formats |
|--------------|-------------------|
| PlantUML     | png, svg, pdf, txt |
| Mermaid      | svg, png |
| D2           | svg, png |
| Graphviz     | png, svg, pdf, jpeg |

You can specify the output format when generating diagrams through the MCP tools.

## Server card and config schema (Smithery / quality score)

For better **Configuration UX** and MCP quality scores:

- The server card at `/.well-known/mcp/server-card.json` includes **tool annotations** (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) and a **config schema URL** (`configSchemaUrl`: `config-schema.json`).
- The session config schema is served at `/.well-known/mcp/config-schema.json` (same path as the card) so clients can resolve it when the card is loaded from that origin.
- When publishing via Smithery CLI, pass the config schema:  
  `[smithery.ai/new](https://smithery.ai/new) (web); add session config from `smithery-config-schema.json` in Settings`  
  See [Vercel/Smithery integration](integrations/vercel_smithery.md).
