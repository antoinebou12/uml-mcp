"""
Example demonstrating the fallback mechanism.

This script shows how the system automatically falls back from Kroki
to alternative rendering services when Kroki is unavailable.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp_core.core.utils import generate_diagram  # noqa: E402
from mcp_core.core.config import MCP_SETTINGS  # noqa: E402


def test_diagram_generation_with_fallback():
    """
    Test diagram generation with automatic fallback.

    This example demonstrates:
    1. Normal operation using Kroki (when available)
    2. Automatic fallback to PlantUML server for UML diagrams
    3. Automatic fallback to Mermaid.ink for Mermaid diagrams
    """

    # Create output directory
    output_dir = project_root / "output" / "fallback_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Testing Diagram Generation with Fallback Mechanism")
    print("=" * 70)
    print()

    # Test 1: PlantUML Class Diagram
    print("1. Testing PlantUML Class Diagram")
    print("-" * 70)
    plantuml_code = """
    class User {
        +String username
        +String email
        +login()
        +logout()
    }

    class Order {
        +int orderId
        +Date orderDate
        +calculateTotal()
    }

    User "1" --> "*" Order : places
    """

    result = generate_diagram(
        diagram_type="class",
        code=plantuml_code,
        output_format="svg",
        output_dir=str(output_dir),
    )

    if "error" in result and result["error"]:
        print(f"  [ERROR] {result['error']}")
    else:
        print("  [SUCCESS]")
        print(f"  URL: {result['url']}")
        print(f"  Playground: {result.get('playground', 'N/A')}")
        if result.get("local_path"):
            print(f"  Saved to: {result['local_path']}")
    print()

    # Test 2: Mermaid Diagram
    print("2. Testing Mermaid Diagram")
    print("-" * 70)
    mermaid_code = """
    graph TD
        A[Start] --> B{Is it working?}
        B -->|Yes| C[Great!]
        B -->|No| D[Check fallback]
        C --> E[End]
        D --> E
    """

    result = generate_diagram(
        diagram_type="mermaid",
        code=mermaid_code,
        output_format="svg",
        output_dir=str(output_dir),
    )

    if "error" in result and result["error"]:
        print(f"  [ERROR] {result['error']}")
    else:
        print("  [SUCCESS]")
        print(f"  URL: {result['url']}")
        print(f"  Playground: {result.get('playground', 'N/A')}")
        if result.get("local_path"):
            print(f"  Saved to: {result['local_path']}")
    print()

    # Test 3: PlantUML Sequence Diagram
    print("3. Testing PlantUML Sequence Diagram")
    print("-" * 70)
    sequence_code = """
    @startuml
    Alice -> Bob: Authentication Request
    Bob --> Alice: Authentication Response

    Alice -> Bob: Another authentication Request
    Alice <-- Bob: another authentication Response
    @enduml
    """

    result = generate_diagram(
        diagram_type="sequence",
        code=sequence_code,
        output_format="svg",
        output_dir=str(output_dir),
    )

    if "error" in result and result["error"]:
        print(f"  [ERROR] {result['error']}")
    else:
        print("  [SUCCESS]")
        print(f"  URL: {result['url']}")
        print(f"  Playground: {result.get('playground', 'N/A')}")
        if result.get("local_path"):
            print(f"  Saved to: {result['local_path']}")
    print()

    print("=" * 70)
    print("Configuration:")
    print(f"  Kroki Server: {MCP_SETTINGS.kroki_server}")
    print(f"  PlantUML Server: {MCP_SETTINGS.plantuml_server}")
    print("=" * 70)
    print()
    print("How the fallback works:")
    print("  1. All diagrams first attempt to use Kroki")
    print("  2. If Kroki fails (connection error, HTTP error, etc.):")
    print("     - PlantUML diagrams -> PlantUML server fallback")
    print("     - Mermaid diagrams -> Mermaid.ink fallback")
    print("     - Other types -> Error with details from both attempts")
    print()


if __name__ == "__main__":
    test_diagram_generation_with_fallback()
