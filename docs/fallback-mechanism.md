# Diagram Generation Fallback Mechanism

## Overview

UML-MCP implements an intelligent fallback mechanism to ensure maximum reliability when generating diagrams. The system always tries Kroki first (the primary method), and automatically falls back to alternative rendering services if Kroki is unavailable.

## How It Works

### Primary Method: Kroki

All diagram generation requests first attempt to use [Kroki.io](https://kroki.io), a unified API that supports 30+ diagram types including:
- PlantUML (Class, Sequence, Activity, State, Component, Deployment, Object, Use Case)
- Mermaid
- D2
- Graphviz
- ERD
- BlockDiag
- BPMN
- C4 with PlantUML
- And many more...

### Automatic Fallback

When Kroki fails (connection errors, HTTP errors, service downtime, etc.), the system automatically attempts to use alternative rendering services based on the diagram type:

#### PlantUML Diagrams
**Fallback:** Local or remote PlantUML server

For all PlantUML-based diagrams (class, sequence, activity, state, component, deployment, object, usecase), the system falls back to the configured PlantUML server.

- Default server: `http://plantuml-server:8080`
- Can be configured via `PLANTUML_SERVER` environment variable
- Supports all PlantUML diagram types
- Maintains same output format as primary method

#### Mermaid Diagrams
**Fallback:** Mermaid.ink

For Mermaid diagrams, the system falls back to [Mermaid.ink](https://mermaid.ink), a free public service for rendering Mermaid diagrams.

- No configuration required
- Supports SVG and PNG output formats
- Provides playground URLs for editing

#### Other Diagram Types
For diagram types without an HTTP fallback (D2, Graphviz, ERD, etc.), the system returns an error after Kroki fails. The response includes `attempts` (Kroki plus a `none` entry) and `fallback_used: false`.

## Implementation note

The Kroki-first policy is implemented synchronously in **`mcp_core/core/diagram_rendering.py`**: `try_kroki_render` (Kroki only), `run_fallback_if_needed` (PlantUML server or Mermaid.ink when applicable), and `run_diagram_pipeline` (orchestrates both). The MCP tool layer validates inputs in **`mcp_core/core/diagram_service.py`** before calling **`mcp_core/core/utils.generate_diagram`**, which builds a `DiagramRenderContext` and runs the pipeline.

On success, the result dictionary may include a **`source`** field indicating which path produced the image: `kroki`, `plantuml_server`, or `mermaid_ink` (useful for logs and debugging).

### Response diagnostics (generate_uml / generate_diagram_url)

Successful and failed renders also expose structured fields for debugging and observability:

| Field | Meaning |
|-------|---------|
| `source` | Winning renderer: `kroki`, `plantuml_server`, or `mermaid_ink`. |
| `fallback_used` | `true` if Kroki failed and a secondary backend succeeded. |
| `attempts` | List of `{ "backend", "ok", "error_summary"? }` in order (Kroki first, then fallback if applicable). |
| `render_ms` | Wall time for the pipeline call (milliseconds). |
| `cache_hit` | `true` when the result was served from the in-memory LRU cache (memory-only requests only). |
| `mime_type` | Normalized type for the requested format when applicable (e.g. `image/svg+xml` for SVG). |

## Configuration

### Environment Variables

```bash
# Primary service (always tried first)
export KROKI_SERVER=https://kroki.io

# PlantUML fallback server
export PLANTUML_SERVER=http://localhost:8080

# Enable local servers (optional)
export USE_LOCAL_KROKI=true
export USE_LOCAL_PLANTUML=true
```

### Local Development

For local development, you can run PlantUML server using Docker:

```bash
# Run PlantUML server
docker run -d -p 8080:8080 plantuml/plantuml-server

# Configure the server
export PLANTUML_SERVER=http://localhost:8080
export USE_LOCAL_PLANTUML=true
```

## Error Handling

When Kroki fails and a fallback was attempted but also failed, the error message combines both. When no fallback exists for the diagram backend, the message states that no fallback is available. Inspect the **`attempts`** array on the response for per-backend status.

Example (PlantUML fallback failed after Kroki failed):
```
Primary (Kroki) failed: Cannot connect to diagram service. 
Check KROKI_SERVER and network connectivity. 
Fallback also failed: [Errno 11001] getaddrinfo failed
```

## Testing

The fallback mechanism is thoroughly tested with dedicated test cases in `tests/test_fallback_mechanism.py`:

- `test_fallback_plantuml_success`: Verifies PlantUML fallback works
- `test_fallback_mermaid_success`: Verifies Mermaid.ink fallback works
- `test_fallback_no_fallback_available`: Verifies proper error when no fallback exists
- `test_fallback_not_triggered_on_success`: Verifies fallback not used when primary succeeds
- `test_kroki_http_error_triggers_fallback`: Verifies HTTP errors trigger fallback

Run tests:
```bash
uv run pytest tests/test_fallback_mechanism.py -v
```

## Example Usage

See `examples/test_fallback.py` for a complete demonstration:

```bash
uv run python examples/test_fallback.py
```

This example shows:
1. Normal operation using Kroki (when available)
2. Automatic fallback to PlantUML server for UML diagrams
3. Automatic fallback to Mermaid.ink for Mermaid diagrams

## Logging

The fallback mechanism provides detailed logging:

```
INFO: Generating class diagram (Kroki first, fallback if needed)
INFO: Attempting Kroki for class diagram
WARNING: Kroki failed for class: Cannot connect to Kroki. Attempting fallback...
INFO: Falling back to PlantUML server for class
INFO: Successfully generated class diagram via PlantUML fallback
```

## Architecture

The Kroki-first pipeline lives in **`mcp_core/core/diagram_rendering.py`**: `try_kroki_render`, then `run_fallback_if_needed` for PlantUML or Mermaid backends. **`mcp_core/core/utils.py`** keeps **`generate_diagram()`** as the public entry (read-only handling, output directory setup, diagram type resolution, then `run_diagram_pipeline`). MCP tools validate and delegate via **`mcp_core/core/diagram_service.py`**.

On successful render, the result dict may include **`source`**: `kroki` (primary), `plantuml_server`, or `mermaid_ink` (fallbacks), for logging or client use.

## Benefits

1. **Reliability**: Diagrams generated even when primary service is down
2. **No configuration required**: Works out of the box with sensible defaults
3. **Transparent**: Users don't need to know about fallback mechanism
4. **Flexible**: Can use local or remote services
5. **Well-tested**: Comprehensive test coverage ensures reliability

## Future Enhancements

Potential improvements to the fallback mechanism:

1. Add fallback for D2 diagrams (local D2 binary)
2. Add fallback for Graphviz (local Graphviz installation)
3. Implement retry logic with exponential backoff
4. Cache successful service to try it first next time
5. Add health checks for services before attempting
