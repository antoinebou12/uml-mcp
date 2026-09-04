# Configuration

Configure UML-MCP with environment variables and MCP client config files.

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

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_OUTPUT_DIR` / `UML_MCP_OUTPUT_DIR` | Directory to save generated diagrams | `./output` |
| `KROKI_SERVER` | URL of the Kroki server | `https://kroki.io` |
| `PLANTUML_SERVER` | URL of the PlantUML server | `http://plantuml-server:8080` |
| `USE_LOCAL_KROKI` | Use local Kroki server (true/false) | `false` |
| `USE_LOCAL_PLANTUML` | Use local PlantUML server (true/false) | `false` |
| `MCP_DIAGRAM_FALLBACK` | After Kroki fails, try PlantUML server / Mermaid.ink | **On** for typical desktop; **off** when `VERCEL` is set or `USE_LOCAL_KROKI=true` unless overridden |
| `FASTMCP_STATELESS_HTTP` | Enable stateless HTTP for multi-worker/horizontal scaling (true/false) | `false` |
| `MCP_READ_ONLY` | Reject `output_dir` and never write diagram files to disk | `false` |
| `MCP_MAX_CODE_LENGTH` | Maximum diagram source length (characters) | `500000` |
| `MCP_MAX_RENDER_SECONDS` | HTTP timeout budget for Kroki/fallback image fetch (seconds) | `30` |
| `MCP_KROKI_MERMAID_TIMEOUT_SECONDS` | Fail-fast Kroki deadline for Mermaid before mermaid.ink fallback (capped by `MCP_MAX_RENDER_SECONDS`) | `8` |
| `MCP_BATCH_MAX_ITEMS` | Maximum items per `generate_uml_batch` call | `20` |
| `MCP_BATCH_CONCURRENCY` | Max parallel workers for `generate_uml_batch` (clamped 1–16). Mermaid-majority batches are further capped at 2 to reduce Mermaid.ink stampedes on hosted deployments. | `4` |
| `MCP_RATE_LIMIT_PER_MINUTE` | Per-client IP requests per minute for `/mcp`, `/generate_diagram`, `/kroki_encode` (FastAPI only). `0` disables. | `0` |
| `MCP_URL_ONLY` | Return Kroki/playground URLs only (no fetch of rendered bytes, no `content_base64` in serverless). On Vercel defaults to true when unset. Exceptions: `generate_uml_image` always fetches bytes; `generate_uml` with `png`/`jpeg` also force-fetches. | See below |
| `MCP_MEMORY_ONLY` | Never write diagram files to disk | Vercel: true when unset |

When **`MCP_URL_ONLY=true`**, the server avoids downloading rendered image bytes inside the process (lower latency and cost on serverless). Responses omit `content_base64` unless you disable URL-only mode. Exceptions: **`generate_uml_image`** always fetches bytes so MCP clients can show an inline image in chat; **`generate_uml`** with **`png`** or **`jpeg`** also force-fetches. Render results include structured **`display_markdown`** (markdown image + URL + playground). **`MCP_MEMORY_ONLY=true`** skips all file writes; use URL/base64-from-client fetch if needed.

## Health check (HTTP deployment)

When running the FastAPI app (`app.py`) for HTTP deployment (e.g. Vercel, Docker, uvicorn), a **health endpoint** is available:

- **Endpoint**: `GET /health` (no authentication required)
- **Response**: `{"status": "healthy", "modules_available": true|false}`
  - `status`: Always `"healthy"` when the server is up.
  - `modules_available`: Whether diagram backends (Kroki, PlantUML, etc.) could be loaded.

Use `/health` for load balancers, Kubernetes or Docker liveness/readiness probes, Vercel checks, and similar monitoring whenever you run the FastAPI app (`app.py`).

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

- **`config/cursor_config.json`**: Cursor
- **`config/claude_desktop_config.json`**: Claude Desktop
- **`config/README.md`**: Where each app stores its config and how to copy the examples

For **Claude Code**, you can install the bundled plugin from this repo’s marketplace instead of pasting JSON; see [Claude Code integration](integrations/claude_code.md).

Copy the relevant `mcpServers` block into your client’s config file and set `cwd` to your `uml-mcp` project root. The examples use **`args`: `["-u", "server.py"]`** (unbuffered stdio, path relative to `cwd`). The main server entry point is **`server.py`**. Optional `env` keys include `KROKI_SERVER`, `MCP_OUTPUT_DIR`, and `MCP_DIAGRAM_FALLBACK` (see table above).

## Advanced configuration

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

Set `output_format` in the MCP tool arguments when you generate a diagram.

## Server card and config schema (Smithery / quality score)

Smithery and other MCP clients read the server card for tool metadata and optional session fields:

- The server card at `/.well-known/mcp/server-card.json` lists tool annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) and a config schema URL (`configSchemaUrl`: `config-schema.json`).
- The session config schema is served at `/.well-known/mcp/config-schema.json` (same path as the card) so clients can resolve it when the card is loaded from that origin. It includes `read_only` (maps to `MCP_READ_ONLY`) alongside output directory, Kroki/PlantUML URLs, and theme defaults.
- When publishing on Smithery, add session configuration from `smithery-config-schema.json` in the project settings (see [Vercel/Smithery integration](integrations/vercel_smithery.md)).
