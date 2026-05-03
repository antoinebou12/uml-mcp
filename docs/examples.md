# Usage Examples

Prompts, Cursor usage, and direct MCP tool calls.

## Basic usage with Cursor

With UML-MCP configured in Cursor, you might ask:

```
Generate a class diagram for a banking system with Account, Customer, and Transaction classes.
```

The assistant calls UML-MCP tools and shows the diagram in the conversation.

## Assistant prompts

Example prompts:

### Class Diagram

```
Create a class diagram showing the relationships between the following classes:
- Person (name, age, email)
- Student (studentId, enrollCourse())
- Teacher (employeeId, teachCourse())
- Course (courseId, title, description)

Students can enroll in multiple courses, and each course can have one teacher.
```

### Sequence Diagram

```
Generate a sequence diagram for an e-commerce checkout process involving:
- Customer
- ShoppingCart
- OrderSystem
- PaymentProcessor
- InventorySystem
```

### Component Diagram

```
Create a component diagram for a microservices architecture with:
- API Gateway
- User Service
- Product Service
- Order Service
- Payment Service
- Notification Service
```

## Diagram assistant (Mermaid, Gantt, BPMN, class → Mermaid)

Named prompts, `uml://` resources, and how tools map to Mermaid sequences, Gantt charts, BPMN, and class-to-Mermaid conversion are covered in [Diagram Assistant](diagram-assistant.md).

## Engine-specific tutorials

Tracks with copy-paste prompts, optional **Sequential Thinking** MCP (separate server), `generate_uml` with **`output_format: svg`**, and committed SVG samples:

- [Mermaid live examples + prompts and SVG](tutorials/mermaid.md)
- [PlantUML prompts and SVG](tutorials/plantuml-prompts-svg.md)
- [D2 prompts and SVG](tutorials/d2-prompts-svg.md)
- [TikZ prompts and SVG](tutorials/tikz-prompts-svg.md)

## Using MCP Tools Directly

To call UML-MCP from your own application, invoke the tools directly:

### Python Example

```python
import json
import subprocess

def generate_class_diagram(code):
    # Start the MCP server process
    process = subprocess.Popen(
        ["python", "server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Prepare MCP request (use generate_uml with diagram_type for any diagram)
    request = {
        "type": "tool",
        "name": "generate_uml",
        "args": {
            "diagram_type": "class",
            "code": code,
            "output_dir": "./output"
        }
    }

    # Send request to MCP server
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()

    # Read response
    response = json.loads(process.stdout.readline())

    # Close process
    process.terminate()

    return json.loads(response["result"])

# Example usage (PlantUML class diagram)
diagram = generate_class_diagram("""
@startuml
class User {
  -name: String
  -email: String
  +register(): void
  +login(): boolean
}
@enduml
""")

print(f"Diagram URL: {diagram['url']}")
print(f"Local file: {diagram['local_path']}")
```

## Integration examples

### Web Application

```javascript
async function generateDiagram(diagramType, code) {
  const response = await fetch('/api/diagram', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      type: diagramType,
      code: code
    }),
  });

  const result = await response.json();
  document.getElementById('diagram').src = result.url;
  document.getElementById('playground-link').href = result.playground;
}
```

### Command Line

```bash
echo '{
  "type": "tool",
  "name": "generate_uml",
  "args": {
    "diagram_type": "sequence",
    "code": "@startuml\nAlice -> Bob: Hello\nBob --> Alice: Hi\n@enduml",
    "output_dir": "./diagrams"
  }
}' | python server.py
```
