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
For diagram types without a fallback mechanism (D2, Graphviz, ERD, etc.), the system returns an error with details from both the primary and fallback attempts.

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

When both the primary method (Kroki) and the fallback fail, the system returns a detailed error message containing:

1. **Primary error**: Details about why Kroki failed
2. **Fallback error**: Details about why the fallback also failed

Example error message:
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

The fallback logic is implemented in `mcp_core/core/utils.py`:

1. **generate_diagram()**: Main entry point, tries Kroki first
2. **_generate_diagram_plantuml_fallback()**: PlantUML server fallback
3. **_generate_diagram_mermaid_fallback()**: Mermaid.ink fallback

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
