# Fallback Mechanism Implementation Summary

## Overview

Implemented an intelligent fallback mechanism that automatically tries alternative rendering services when Kroki (the primary service) fails. This ensures maximum reliability for diagram generation.

## What Was Implemented

### 1. Core Fallback Logic (`mcp_core/core/utils.py`)

Modified `generate_diagram()` function to:
- **Always try Kroki first** - All diagram types first attempt to use Kroki.io
- **Automatic fallback on failure** - If Kroki fails, automatically tries alternative services
- **Comprehensive error reporting** - Returns detailed errors from both primary and fallback attempts

Added two fallback helper functions:
- `_generate_diagram_plantuml_fallback()` - Falls back to PlantUML server for UML diagrams
- `_generate_diagram_mermaid_fallback()` - Falls back to Mermaid.ink for Mermaid diagrams

### 2. Fallback Strategy

#### PlantUML Diagrams (Class, Sequence, Activity, etc.)
- **Primary:** Kroki.io
- **Fallback:** Configured PlantUML server (default: `http://plantuml-server:8080`)
- **Configuration:** `PLANTUML_SERVER` environment variable

#### Mermaid Diagrams
- **Primary:** Kroki.io
- **Fallback:** Mermaid.ink (public service)
- **Configuration:** None required (works out of the box)

#### Other Diagram Types (D2, Graphviz, ERD, etc.)
- **Primary:** Kroki.io
- **Fallback:** None (returns error with details)

### 3. Testing (`tests/test_fallback_mechanism.py`)

Comprehensive test suite with 5 test cases:
1. `test_fallback_plantuml_success` - Verifies PlantUML fallback works when Kroki fails
2. `test_fallback_mermaid_success` - Verifies Mermaid.ink fallback works when Kroki fails
3. `test_fallback_no_fallback_available` - Verifies proper error for types without fallback
4. `test_fallback_not_triggered_on_success` - Ensures fallback not used when Kroki succeeds
5. `test_kroki_http_error_triggers_fallback` - Verifies HTTP errors trigger fallback

**Test Results:** All 13 tests pass (8 existing + 5 new)
**Coverage:** Increased from 53% to 79% in `mcp_core/core/utils.py`

### 4. Documentation

#### Updated Files:
- `README.md` - Added fallback feature to Features section and new Architecture section
- `docs/fallback-mechanism.md` - Comprehensive documentation on fallback mechanism

#### New Files:
- `examples/test_fallback.py` - Demonstration script showing fallback in action
- `FALLBACK_IMPLEMENTATION.md` - This summary document

### 5. Example Usage

```python
from mcp_core.core.utils import generate_diagram

# Generate a class diagram
result = generate_diagram(
    diagram_type="class",
    code="class User { +String name }",
    output_format="svg",
    output_dir="./output"
)

# The system:
# 1. Tries Kroki first
# 2. If Kroki fails, automatically tries PlantUML server
# 3. Returns result with url, playground, local_path, or error
```

## Key Benefits

1. **Reliability** - Diagrams generated even when primary service is down
2. **Transparency** - Users don't need to know about fallback (it just works)
3. **No Breaking Changes** - Existing code continues to work unchanged
4. **Well-Tested** - Comprehensive test coverage ensures correctness
5. **Configurable** - Can use local or remote fallback services
6. **Detailed Logging** - Clear information about which service was used

## Configuration

### Environment Variables

```bash
# Primary service (always tried first)
KROKI_SERVER=https://kroki.io

# Fallback for PlantUML diagrams
PLANTUML_SERVER=http://plantuml-server:8080

# Optional: Use local servers
USE_LOCAL_KROKI=true
USE_LOCAL_PLANTUML=true
```

### Running Local Services

```bash
# Start PlantUML server
docker run -d -p 8080:8080 plantuml/plantuml-server

# Configure
export PLANTUML_SERVER=http://localhost:8080
```

## Logging Output

When fallback is triggered, you'll see logs like:

```
INFO: Generating class diagram (Kroki first, fallback if needed)
INFO: Attempting Kroki for class diagram
WARNING: Kroki failed for class: Cannot connect to Kroki. Attempting fallback...
INFO: Falling back to PlantUML server for class
INFO: Successfully generated class diagram via PlantUML fallback
```

## Files Modified

1. `mcp_core/core/utils.py` - Core fallback implementation
2. `README.md` - Updated feature list and added architecture section
3. `tests/test_fallback_mechanism.py` - New comprehensive test suite
4. `examples/test_fallback.py` - New demonstration script
5. `docs/fallback-mechanism.md` - New documentation

## Testing

Run all tests:
```bash
uv run pytest tests/test_core_utils.py tests/test_fallback_mechanism.py -v
```

Run demo script:
```bash
uv run python examples/test_fallback.py
```

## Future Enhancements

Potential improvements:
1. Add D2 local binary fallback
2. Add Graphviz local installation fallback
3. Implement retry logic with exponential backoff
4. Cache which service succeeded for faster future attempts
5. Add health check endpoints before attempting services

## Success Metrics

- ✅ All 13 tests passing
- ✅ 79% code coverage in core utils (up from 53%)
- ✅ No breaking changes to existing API
- ✅ Backward compatible with existing code
- ✅ Comprehensive documentation
- ✅ Working demonstration example
