"""
MCP prompts for diagram generation using the decorator pattern
"""

import logging
from typing import Any, Callable, Dict, List, Optional, TypeVar, cast

# Import FastMCP from wrapper to avoid circular imports
from mcp_core.server.fastmcp_wrapper import FastMCP

from ..core.config import MCP_SETTINGS

logger = logging.getLogger(__name__)

# Store for registered prompts when using decorator pattern
_registered_prompts: Dict[str, Dict[str, Any]] = {}

F = TypeVar("F", bound=Callable[..., Any])


def mcp_prompt(
    name: str, description: Optional[str] = None, category: str = "default"
) -> Callable[[F], F]:
    """
    Decorator for registering a function as an MCP prompt.

    Args:
        name: Prompt name
        description: Prompt description (defaults to function docstring if not provided)
        category: Prompt category for organization

    Returns:
        Decorated function

    Example:
        @mcp_prompt("class_diagram", description="Generate UML class diagram")
        def class_diagram_prompt(context: dict) -> str:
            # Implementation
            return prompt_text
    """

    def decorator(func: F) -> F:
        func_doc = func.__doc__ or ""
        func_description = description or func_doc.split("\n")[0] if func_doc else ""

        # Store prompt metadata
        _registered_prompts[name] = {
            "function": func,
            "name": name,
            "description": func_description,
            "category": category,
        }

        # Return function unchanged
        return cast(F, func)

    return decorator


# Base UML diagram prompt function
@mcp_prompt(
    "uml_diagram",
    description="Base prompt for UML diagram generation. Guides the model to produce diagram code (PlantUML, Mermaid, D2) for any diagram type including class, sequence, activity, use case, and more.",
)
def uml_diagram_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """
    Base prompt for UML diagram generation

    Args:
        context: Dictionary containing context information

    Returns:
        The prompt text
    """
    context = context or {}

    # Plan → code → tool call; Kroki renders by backend (plantuml / mermaid / d2 / …).
    prompt = """You are a software engineer and expert in UML and diagram notation.

Before writing code:
- Read the **uml://types** resource for valid `diagram_type` values and each type's Kroki backend (e.g. class/sequence → PlantUML family → backend `plantuml`; `mermaid` → `mermaid`; `d2` → `d2`). Your source syntax must match that backend.
- Read **uml://formats** for allowed `output_format` values for the type you choose.

Rendering is Kroki-first (server-side). Fallbacks exist only for some backends; correct syntax avoids HTTP 400s.

Tool:
- **generate_uml** — pass `output_dir` only when you must save a file locally; omit `output_dir` for URL, playground, and base64 only (serverless / read-only).

Workflow:
1. Plan: diagram type, notation (PlantUML / Mermaid / D2), elements, relationships. For ambiguous requests, state your choices briefly.
2. Output complete diagram source in a fenced code block for the human reader.
3. Call the tool with the **raw diagram string** as `code` (no markdown fences inside the argument — only the source text).

Syntax guardrails:
- **PlantUML**: include `@startuml` … `@enduml` in examples (the server may wrap minimal input, but full delimiters reduce Kroki errors). Use `!theme` only when appropriate for PlantUML types.
- **Mermaid**: valid `graph` / `flowchart` / `sequenceDiagram` / etc. syntax for your diagram.
- **D2**: valid D2 text for the chosen structure.

Quality: proper notation, all requested elements, readable layout, correct relationships.

"""

    # Add diagram type specific instructions if provided in context
    if "diagram_type" in context:
        diagram_type = context["diagram_type"]
        prompt += f'\nTarget: a {diagram_type} diagram. When calling generate_uml, set diagram_type to "{diagram_type}" exactly.\n'

    return prompt


def _layout_overlap_appendix() -> str:
    """Concrete, per-backend rules to minimize crossing/overlapping arrows.

    Reused across prompts that produce arrow-heavy diagrams (algorithms,
    architectures, concept graphs). Keep it short and declarative — these
    rules are advice for the LLM, not enforced by the rendering pipeline.
    """
    return """
## Reduce arrow overlap / crossings

General:
- Keep elements under ~25 (Mermaid) / ~30 (PlantUML). Split into an overview plus a detail diagram when larger.
- Declare related nodes adjacent in the source so the layout engine places them adjacent on screen.
- Prefer linear chains over hubs; if a hub is unavoidable, put it on its own row or column.

Mermaid (`mermaid`):
- Pick **one** direction header: `flowchart TD` (top–down) for algorithms; `flowchart LR` (left–right) for pipelines and architectures.
- Wrap related nodes in `subgraph name [Label] ... end` so they cluster together.
- Use `linkStyle` only on the **single** emphasis edge; do not mix `-->`, `-.->`, and `==>` arbitrarily.
- Prefer short edge labels; long labels force the engine to detour and cross other edges.

PlantUML (`class`, `sequence`, `activity`, `usecase`, `state`, `component`, `deployment`, `object`, `c4plantuml`):
- For non-sequence diagrams, add `skinparam linetype ortho` (or `polyline`) and `left to right direction` near the top.
- Use directional arrows (`-down->`, `-right->`, `-up->`, `-left->`) on edges that would otherwise cross.
- Group related elements with `together { ... }` so the layout keeps them on the same row/column.
- On sequence diagrams: declare participants in left-to-right contact order, use `autoactivate on`, and add `hide footbox` when there are no return messages. Never draw upward message arrows.

D2 (`d2`):
- Set `direction: right` (or `down`) at the top.
- Wrap related shapes in containers (`group: { a; b; a -> b }`) so the layout engine can route around them as a unit.
- When dagre still produces crossings, switch to ELK with `vars: { d2-config: { layout-engine: elk } }`.

Graphviz (`graphviz`):
- Start with `rankdir=LR;` (or `TB`) and consider `splines=ortho;` for clean orthogonal routing.
- Use `subgraph cluster_x { ... }` to keep related nodes adjacent.
- Constrain crossing edges with `constraint=false` only as a last resort.
"""


# UML diagram with explicit planning step (alias for plan-then-generate workflow)
@mcp_prompt(
    "uml_diagram_with_thinking",
    description="Generate UML diagram with an explicit plan-then-generate workflow. Plan first, then output code and call generate_uml (omit output_dir unless saving a file).",
    category="uml",
)
def uml_diagram_with_thinking_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """
    Prompt for generating UML diagrams with plan-then-generate. Same workflow as
    uml_diagram (plan first, then code and generate_uml), plus explicit planning
    instructions and optional sequential-thinking MCP guidance.
    """
    planning_preamble = """Before writing diagram code, complete an explicit plan (in your reasoning, not inside the raw `code` tool argument):
1. **diagram_type** — must match **uml://types**; pick notation (PlantUML / Mermaid / D2 / other) consistent with that type.
2. **Scope** — approximate node, state, or lifeline count; stay under ~25 elements for Mermaid and ~30 for PlantUML unless you split into two diagrams.
3. **Emphasis** — at most one focal element or path to highlight in the DSL, if any (avoid rainbow styling).

If a **sequential-thinking** MCP tool is available, use it for steps 1–3 so thoughts stay ordered and revisable before you emit source.

"""
    return planning_preamble + uml_diagram_prompt(context) + _layout_overlap_appendix()


# Class diagram prompt
@mcp_prompt(
    "class_diagram",
    description="Generate UML class diagram from a natural language description. Produces PlantUML code with classes, attributes, methods, visibility, inheritance, composition, and associations.",
)
def class_diagram_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """
    Prompt for generating UML class diagrams

    Args:
        context: Dictionary containing context information

    Returns:
        The prompt text
    """
    context = context or {}
    context["diagram_type"] = "class"

    # Get base prompt
    prompt = uml_diagram_prompt(context)

    # Add class diagram specific instructions
    prompt += """
For class diagrams, follow these additional guidelines:
1. Include class names, attributes, and methods with proper visibility (+, -, #)
2. Show inheritance using generalization relationships (empty triangle arrow)
3. Show composition using filled diamond and aggregation using empty diamond
4. Include proper multiplicities on associations (1, *, 0..1, etc.)
5. Group related classes together
6. Use interfaces where appropriate (with <<interface>> stereotype)

Example PlantUML class diagram syntax:
```
@startuml
class User {
  -name: String
  -email: String
  +login(): void
  +logout(): void
}

class Account {
  -balance: Decimal
  +deposit(amount: Decimal): void
  +withdraw(amount: Decimal): boolean
}

User "1" -- "*" Account : has >
@enduml
```

Provide the complete PlantUML code for the class diagram.

When calling **generate_uml**, use `diagram_type` **class**.
"""

    return prompt


# Sequence diagram prompt
@mcp_prompt(
    "sequence_diagram",
    description="Generate UML sequence diagram from a description. Produces PlantUML code with participants, lifelines, messages, activations, and optional return messages.",
)
def sequence_diagram_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """
    Prompt for generating UML sequence diagrams

    Args:
        context: Dictionary containing context information

    Returns:
        The prompt text
    """
    context = context or {}
    context["diagram_type"] = "sequence"

    # Get base prompt
    prompt = uml_diagram_prompt(context)

    # Add sequence diagram specific instructions
    prompt += """
For sequence diagrams, follow these additional guidelines:
1. Include all participants (actors, objects, systems) involved in the interaction
2. Show messages in chronological order from top to bottom
3. Include activations to show when objects are active
4. Use lifelines for all participants
5. Include return messages where appropriate
6. Add notes for clarification when needed

Example PlantUML sequence diagram syntax:
```
@startuml
actor User
participant "Web Browser" as Browser
participant "Web Server" as Server
database Database

User -> Browser: Enter credentials
activate Browser
Browser -> Server: Send login request
activate Server
Server -> Database: Validate credentials
activate Database
Database --> Server: Authentication result
deactivate Database
Server --> Browser: Login response
deactivate Server
Browser --> User: Display result
deactivate Browser
@enduml
```

Provide the complete PlantUML code for the sequence diagram.

When calling **generate_uml**, use `diagram_type` **sequence**.
"""

    return prompt


# Activity diagram prompt
@mcp_prompt(
    "activity_diagram",
    description="Generate UML activity diagram from a description. Produces PlantUML code with start/end, activities, decisions, forks, joins, and swimlanes.",
)
def activity_diagram_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """
    Prompt for generating UML activity diagrams

    Args:
        context: Dictionary containing context information

    Returns:
        The prompt text
    """
    context = context or {}
    context["diagram_type"] = "activity"

    # Get base prompt
    prompt = uml_diagram_prompt(context)

    # Add activity diagram specific instructions
    prompt += """
For activity diagrams, follow these additional guidelines:
1. Include clear start and end points
2. Show activities as rounded rectangles
3. Use decision nodes (diamonds) for branching
4. Include merge nodes where appropriate
5. Use swimlanes if activities are performed by different actors/systems
6. Include fork and join bars for parallel activities

Example PlantUML activity diagram syntax:
```
@startuml
start
:Login to system;
if (Valid credentials?) then (yes)
  :Display dashboard;
  fork
    :Check notifications;
  fork again
    :Load user data;
  end fork
  :Display user profile;
else (no)
  :Show error message;
  :Display login form;
endif
stop
@enduml
```

Provide the complete PlantUML code for the activity diagram.

When calling **generate_uml**, use `diagram_type` **activity**.
"""

    return prompt


# Use case diagram prompt
@mcp_prompt(
    "usecase_diagram",
    description="Generate UML use case diagram from a description. Produces PlantUML code with actors, use cases, system boundary, include/extend relationships, and associations.",
)
def usecase_diagram_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """
    Prompt for generating UML use case diagrams

    Args:
        context: Dictionary containing context information

    Returns:
        The prompt text
    """
    context = context or {}
    context["diagram_type"] = "usecase"

    # Get base prompt
    prompt = uml_diagram_prompt(context)

    # Add use case diagram specific instructions
    prompt += """
For use case diagrams, follow these additional guidelines:
1. Include actors represented as stick figures
2. Display use cases as ovals with descriptive text
3. Show system boundary as a rectangle containing the use cases
4. Include relationships: association (line), include (dashed arrow with
   <<include>>), extend (dashed arrow with <<extend>>)
5. Show actor generalizations if applicable

Example PlantUML use case diagram syntax:
```
@startuml
left to right direction
actor Customer
actor Administrator

rectangle "Online Shopping System" {
  usecase "Browse Products" as UC1
  usecase "Add to Cart" as UC2
  usecase "Checkout" as UC3
  usecase "Process Payment" as UC4
  usecase "Manage Products" as UC5

  Customer --> UC1
  Customer --> UC2
  Customer --> UC3
  UC3 ..> UC4 : <<include>>
  Administrator --> UC5
}
@enduml
```

Provide the complete PlantUML code for the use case diagram.

When calling **generate_uml**, use `diagram_type` **usecase**.
"""

    return prompt


# Mermaid sequence diagram for API call
@mcp_prompt(
    "mermaid_sequence_api",
    description="Produce a Mermaid sequence diagram for an API call flow: client, API, optional Auth/DB, request/response, and optional alt blocks for success vs error.",
    category="mermaid",
)
def mermaid_sequence_api_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """
    Prompt for a Mermaid sequenceDiagram showing a typical API call:
    client, API, optional auth/DB, request/response, and optional alt block.
    """
    context = context or {}
    return """You are a software engineer. Produce a Mermaid sequence diagram for an API call.

Output a valid Mermaid sequenceDiagram with:
- Participants: at least Client, API, and optionally Auth and/or DB (or backend service).
- A request from Client to API (e.g. POST /login or GET /resource).
- API interacting with Auth or backend/DB as needed.
- Response back to the client; use alt/else for success vs error if appropriate.

Syntax tips:
- Use participant or actor for each lifeline.
- Use ->> for request and -->> for response; + / - for activation if desired.
- Wrap conditional responses in alt ... else ... end.

Put the diagram in a single mermaid code block. Then call **generate_uml** with `diagram_type` **mermaid** and pass the raw Mermaid source as `code` (no markdown fences inside the tool argument). Omit **output_dir** when no file should be written.
"""


# Mermaid Gantt chart
@mcp_prompt(
    "mermaid_gantt",
    description="Generate a Mermaid Gantt chart with title, dateFormat, sections, and tasks including dependencies (after) and durations.",
    category="mermaid",
)
def mermaid_gantt_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """
    Prompt for a Mermaid gantt chart with title, dateFormat, sections, and tasks.
    """
    context = context or {}
    return """You are a software engineer. Produce a Mermaid Gantt chart.

Output a valid Mermaid gantt block with:
- title: short title for the chart
- dateFormat: e.g. YYYY-MM-DD
- At least one section with a label
- Multiple tasks with ids, optional dates/durations (e.g. 7d, 14d), and optional dependency (after <id>)

Example structure:
gantt
    title My project
    dateFormat  YYYY-MM-DD
    section Section A
    Task A1    :a1, 2024-01-01, 7d
    Task A2    :a2, after a1, 5d

Put the diagram in a single mermaid code block. Then call **generate_uml** with `diagram_type` **mermaid** and the raw source as `code`. Omit **output_dir** when no file should be written.
"""


# BPMN process model guidance
@mcp_prompt(
    "bpmn_process_guide",
    description="Explain how to draw a BPMN process model. Covers start/end events, tasks, gateways (XOR, AND, OR), sequence flow, lanes, pools, aligned with BPMN 2.0.2.",
    category="bpmn",
)
def bpmn_process_guide_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """
    Prompt that instructs the model to explain how to draw a BPMN process model:
    start/end events, tasks, gateways, sequence flow, lanes, aligned with BPMN 2.0.2.
    Optionally point to uml://templates (key bpmn), uml://examples (key bpmn), and generate_uml.
    """
    context = context or {}
    return """You are a process modeling expert. Explain how to draw a BPMN process model.

Provide concise guidance that covers:
1. Core elements (aligned with BPMN 2.0.2):
   - Start Event and End Event
   - Task (activity)
   - Gateways: Exclusive (X), Parallel (+), Inclusive (O)
   - Sequence Flow (solid arrows) and optionally Message Flow (dashed) between pools
   - Lanes and Pools for roles/systems
2. Flow rules: one start, one or more end; flows connect activities and gateways; gateways split/merge flows.
3. When to use BPMN: business processes, workflows, orchestration.

Optionally point the user to:
- **uml://templates** (key **bpmn**) for a minimal BPMN XML starter and element naming.
- **uml://examples** (key **bpmn**) for a fuller BPMN XML example.
- **generate_uml** with diagram_type **bpmn** to produce BPMN XML.
"""


@mcp_prompt(
    "c4_model",
    description=(
        "Produce C4 model diagrams using PlantUML C4 includes: context or container views, "
        "Person/System/Container/Component macros, relationships. Uses diagram_type c4plantuml."
    ),
    category="c4",
)
def c4_model_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """Task-specific guidance for C4 via Kroki c4plantuml backend (aligned with uml://templates key c4plantuml)."""
    context = context or {}
    return """You are a software architect. Produce a **C4 model** diagram using PlantUML C4 syntax.

Before writing code:
- Read **uml://types** and confirm `diagram_type` **c4plantuml** and allowed **output_format** values from **uml://formats**.
- Read **uml://templates** (key **c4plantuml**) and **uml://examples** for **c4plantuml** for a valid starter.

Rules:
1. Start with standard includes, e.g. `!include <C4/C4_Context>` for a system context diagram, or `!include <C4/C4_Container>` for containers (add `C4_Component` if needed).
2. Use **Person**, **System**, **System_Ext**, **Container**, **ContainerDb**, **Rel**, **Rel_Back**, **Rel_Neighbor** as appropriate; add a **title** line.
3. Keep boundaries clear: one diagram focuses on one C4 level (context vs container vs component) unless the user asks otherwise.
4. Output the **raw PlantUML/C4 source** (no markdown fences inside the tool argument).

Workflow:
1. Briefly state whether you are drawing a **context** or **container** (or component) view.
2. Output complete C4 PlantUML in a fenced block for the human reader.
3. Call **generate_uml** with `diagram_type` **c4plantuml** and pass the diagram source as `code`. Omit **output_dir** when no file should be written.
"""


@mcp_prompt(
    "wireviz_harness",
    description=(
        "Produce WireViz YAML for cable/connector harnesses: connectors, cables, colors, pins. "
        "Uses diagram_type wireviz."
    ),
    category="wireviz",
)
def wireviz_harness_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """Aligned with uml://templates and uml://examples for wireviz."""
    context = context or {}
    return """You are an electronics or systems engineer. Produce a **WireViz** harness description in **YAML**.

Before writing code:
- Read **uml://types** — backend for **wireviz** — and **uml://formats** for allowed outputs (typically png, svg).
- Read **uml://templates** (key **wireviz**) and **uml://examples** (**wireviz**) for structure.

YAML structure (typical):
- **connectors**: named connectors with **pin** entries (id: signal name).
- **cables**: gauge, length, color, and which connectors/wires they link.

Use valid YAML (no tabs; consistent indentation). Output the YAML in a fenced block for readability, then call **generate_uml** with `diagram_type` **wireviz** and the **raw YAML string** as `code` (no markdown inside the tool argument). Omit **output_dir** when no file should be written.
"""


@mcp_prompt(
    "bpmn_executable_process",
    description=(
        "Build a minimal executable BPMN 2.0 XML process: start, tasks, gateways, end, sequenceFlow. "
        "Uses diagram_type bpmn."
    ),
    category="bpmn",
)
def bpmn_executable_process_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """Task-first BPMN XML; aligned with uml://templates (key bpmn)."""
    context = context or {}
    return """You are a BPMN modeler. Produce an **executable BPMN 2.0** XML snippet suitable for Kroki **bpmn**.

Before writing code:
- Read **uml://formats** for **bpmn** and use **uml://templates** (key **bpmn**) for namespaces and element names.

Task-first steps:
1. Define a **bpmn:process** with `isExecutable="true"` (or `false` if the user wants a non-executable overview—match their request).
2. Include **startEvent**, **endEvent**, **userTask** / **task** / **serviceTask** as needed, **exclusiveGateway** or **parallelGateway** if branching, and **sequenceFlow** wiring all elements.
3. Use valid BPMN XML namespaces (see uml://templates **bpmn** example).

Output the full XML in a fenced block for the reader, then call **generate_uml** with `diagram_type` **bpmn** and pass the **raw XML** as `code` (no markdown fences inside the tool argument). Omit **output_dir** when no file should be written.
"""


# Convert class diagram to Mermaid
@mcp_prompt(
    "convert_class_to_mermaid",
    description="Convert a class diagram (PlantUML code or prose description) into Mermaid classDiagram syntax, mapping visibility, relationships, and inheritance.",
    category="mermaid",
)
def convert_class_to_mermaid_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """
    Prompt for converting a class diagram (PlantUML or prose) into Mermaid classDiagram.
    Instructs to output Mermaid classDiagram and optionally call generate_uml("mermaid", code).
    """
    context = context or {}
    return """You are a software engineer. Convert the user's class diagram into Mermaid classDiagram code.

The user will provide either:
- PlantUML class diagram code (@startuml ... class ... @enduml), or
- A prose description of classes, attributes, methods, and relationships.

Steps:
1. Identify each class: name, attributes (with types if given), and methods.
2. Map visibility: + public, - private, # protected (Mermaid: + - #).
3. Map relationships to Mermaid syntax:
   - Inheritance: ClassA --|> ClassB
   - Composition: ClassA *-- ClassB
   - Aggregation: ClassA o-- ClassB
   - Association: ClassA -- ClassB (add label with : label)
   - Dependency: ClassA ..> ClassB
4. Output a single Mermaid code block starting with classDiagram and containing all classes and relationships.

After producing the Mermaid code, call **generate_uml** with `diagram_type` **mermaid** and the raw source as `code`. Omit **output_dir** when no file should be written.
"""


@mcp_prompt(
    "algorithm_explainer",
    description=(
        "Explain an algorithm visually: control flow, recursion, or data-structure operation. "
        "Maps intent to diagram_type (mermaid flowchart, activity, state, d2), labels each step "
        "with its Big-O complexity, and applies layout rules that minimize arrow overlap."
    ),
    category="algorithm",
)
def algorithm_explainer_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """Task-focused prompt for explaining algorithms as diagrams.

    Steers the model through (1) picking a diagram shape that matches the
    algorithm's structure, (2) labeling each step with its complexity, and
    (3) using layout directives that reduce crossing arrows. Then call
    `generate_uml` with the chosen `diagram_type` and the raw source.
    """
    context = context or {}
    prompt = """You are a software engineer explaining an algorithm with a diagram.

Step 1 — Pick the diagram shape that matches the algorithm:
- **Linear / branching control flow** (sort, search, parser pass): Mermaid `flowchart TD` → `diagram_type` **mermaid**, or PlantUML activity → `diagram_type` **activity**.
- **Recursion or divide-and-conquer call tree** (merge sort, quicksort, DP recursion): Mermaid `flowchart TD` as a tree → `diagram_type` **mermaid**, or D2 with `direction: down` → `diagram_type` **d2**.
- **State changes of a data structure** (stack/queue/lock state machine, automaton): PlantUML state → `diagram_type` **state**.
- **Pipeline / dataflow stages**: Mermaid `flowchart LR` → `diagram_type` **mermaid**, or D2 with `direction: right` → `diagram_type` **d2**.

Step 2 — Annotate each step with its **time complexity** in the node label:
- Mermaid: `Step["Partition<br/><i>O(n)</i>"]` and place the overall complexity in the diagram title or a top note.
- PlantUML activity: `:Partition\\n<i>O(n)</i>;`
- D2: `Partition: "Partition\\nO(n)"` (multi-line labels with `\\n`).
- Place the **aggregate** complexity (e.g. `T(n) = 2T(n/2) + O(n) = O(n log n)`) in a single note or title — do not repeat it on every node.

Step 3 — Use consistent shapes:
- Mermaid: `Start([Start])` and `End([Stop])` for terminals (stadium); `{Decision?}` for branches; `[[Recursive call]]` for subroutine invocations; `[/Input/]` and `[\\Output\\]` for I/O when relevant.
- PlantUML activity: `start`, `stop`, `if/elseif/else/endif`, `repeat`/`while` for loops, `fork`/`join` for parallel branches.
- D2: `shape: stadium` for terminals, `shape: diamond` for decisions.

Step 4 — Mark **base cases** clearly (rounded / stadium) and **recursive calls** clearly (rectangles), so the reader can scan the tree quickly.

Step 5 — Workflow:
1. State briefly which shape and `diagram_type` you chose and why.
2. Emit the complete diagram source in a fenced block for the human reader (Mermaid / PlantUML / D2 as appropriate).
3. Call **generate_uml** with the chosen `diagram_type` and the **raw source** as `code` (no markdown fences inside the tool argument). Omit `output_dir` unless the user asked for a saved file. Prefer `output_format` **svg**.

Avoid:
- Skipping the complexity labels — they are the whole point of the diagram.
- Drawing every error path from every node (use one global error sink / note).
- Mixing arrow styles (`-->`, `-.->`, `==>`) inside one Mermaid diagram unless the change carries meaning.
"""
    if "algorithm" in context:
        prompt += f"\nTarget algorithm: **{context['algorithm']}**. Name it in the title and the first node.\n"
    return prompt + _layout_overlap_appendix()


@mcp_prompt(
    "paper_concept_diagram",
    description=(
        "Visualize a concept from an academic paper (ML architecture, method comparison, "
        "concept/citation graph). Encodes citations in node labels and adds clickable links "
        "to arXiv/DOI in Mermaid, PlantUML, D2, and Graphviz. Recommends SVG output."
    ),
    category="research",
)
def paper_concept_diagram_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """Task-focused prompt for academic-paper concept diagrams with clickable citation links."""
    context = context or {}
    prompt = """You are a research engineer explaining a concept from one or more academic papers as a diagram.

Step 1 — Pick the diagram language by intent:
- **ML / system architecture** (encoder–decoder, transformer block, training pipeline): Mermaid `flowchart LR` → `diagram_type` **mermaid**, or D2 → `diagram_type` **d2**.
- **Method comparison** (baseline vs. proposed) or **relationship between concepts**: Mermaid `flowchart` → `diagram_type` **mermaid**, or Graphviz `digraph` → `diagram_type` **graphviz**.
- **Citation / concept graph** (how papers depend on each other): Graphviz `digraph` → `diagram_type` **graphviz**.

Step 2 — Encode citations as short, in-label tags (e.g. `[Vaswani+ 2017]`), then attach a **clickable link** to the paper. Prefer arXiv `abs/` URLs (stable); fall back to DOI / publisher URL. **Never fabricate links** — if the user did not give a URL, leave the citation as text only.

Clickable-link syntax per backend:
- **Mermaid**: declare the node, then add a `click` line.
  ```
  flowchart LR
    Attn["Attention<br/>[Vaswani+ 2017]"]
    click Attn "https://arxiv.org/abs/1706.03762" "Attention Is All You Need" _blank
  ```
- **PlantUML** (works in `class`, `usecase`, `component`, `c4plantuml`): `[[url label]]` after the element.
  ```
  class Attention as "Attention\\n[Vaswani+ 2017]" [[https://arxiv.org/abs/1706.03762 Attention Is All You Need]]
  ```
- **D2**: `link:` property on the node.
  ```
  Attention: {
    label: "Attention\\n[Vaswani+ 2017]"
    link: "https://arxiv.org/abs/1706.03762"
  }
  ```
- **Graphviz**: `URL=`, optionally with `tooltip=` and `target="_blank"`.
  ```
  Attention [label="Attention\\n[Vaswani+ 2017]", URL="https://arxiv.org/abs/1706.03762", tooltip="Vaswani+ 2017", target="_blank"];
  ```

Step 3 — Keep labels short. Put long titles in the `tooltip` / second argument of `click`, not in the visible label.

Step 4 — Workflow:
1. State briefly which view (architecture / comparison / citation graph) and `diagram_type` you chose.
2. Emit complete diagram source in a fenced block for the human reader.
3. Call **generate_uml** with the chosen `diagram_type` and the **raw source** as `code`. Omit `output_dir` unless the user asked for a saved file.
4. Use `output_format` **svg** — PNG/JPEG renderings strip hyperlinks, so the `click` / `[[ ]]` / `URL=` directives become invisible.

Avoid:
- Inventing arXiv IDs, DOIs, or paper titles. If unsure, drop the link and keep only the textual citation.
- Putting full paper titles inside node labels (they bloat the layout and force arrow detours). Use `[Author+ Year]` in the label and the full title in the link's title/tooltip.
- Mixing diagram_types inside one diagram (e.g. PlantUML class syntax inside a Mermaid block).
"""
    if "paper" in context:
        prompt += (
            f"\nPrimary paper: **{context['paper']}**. Cite it on the focal node.\n"
        )
    return prompt + _layout_overlap_appendix()


def register_prompts_with_server(server: FastMCP) -> List[str]:
    """
    Register all decorated prompts with the MCP server

    Args:
        server: The MCP server instance

    Returns:
        List of registered prompt names
    """
    logger.info(f"Registering {len(_registered_prompts)} prompts with the MCP server")

    registered_prompt_names = []

    for prompt_name, prompt_info in _registered_prompts.items():
        func = prompt_info["function"]

        # Register with server using prompt decorator
        prompt_decorator = server.prompt(prompt_name)
        prompt_decorator(func)

        registered_prompt_names.append(prompt_name)
        logger.debug(f"Registered prompt: {prompt_name}")

    return registered_prompt_names


def register_diagram_prompts(server: FastMCP) -> List[str]:
    """
    Register diagram prompts with the MCP server

    Args:
        server: The MCP server instance

    Returns:
        List of registered prompt names
    """
    logger.info("Registering diagram prompts")

    # Register all prompts that were decorated with @mcp_prompt
    registered_prompts = register_prompts_with_server(server)

    # Store registered prompts in MCP_SETTINGS
    MCP_SETTINGS.prompts = registered_prompts

    logger.info(f"Registered {len(registered_prompts)} diagram prompts successfully")
    logger.debug(f"Registered prompts: {registered_prompts}")

    return registered_prompts


def get_prompt_registry() -> Dict[str, Dict[str, Any]]:
    """
    Get the registry of all prompts registered with the decorator

    Returns:
        Dictionary of prompt metadata
    """
    return _registered_prompts
