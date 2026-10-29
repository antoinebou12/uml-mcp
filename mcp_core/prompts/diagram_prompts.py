"""
MCP prompts for diagram generation using the decorator pattern
"""

import inspect
import json
import logging
import re
from collections.abc import Callable
from typing import Any, TypeVar, cast

from ..core.config import MCP_SETTINGS

logger = logging.getLogger(__name__)

# Store for registered prompts when using decorator pattern
_registered_prompts: dict[str, dict[str, Any]] = {}

F = TypeVar("F", bound=Callable[..., Any])


def mcp_prompt(
    name: str,
    description: str | None = None,
    category: str = "default",
    *,
    publish: bool = True,
) -> Callable[[F], F]:
    """
    Decorator for registering a function as an MCP prompt.

    Args:
        name: Prompt name
        description: Prompt description (defaults to function docstring if not provided)
        category: Prompt category for organization
        publish: When False, keep the helper for tests/recipes but omit from
            ``prompts/list`` (notation lives in per-type agent skills instead).

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
            "publish": publish,
        }

        # Return function unchanged
        return cast(F, func)

    return decorator


# Base UML diagram prompt function (only generic plan-then-generate prompt on the wire)
@mcp_prompt(
    "uml_diagram",
    description=(
        "Plan-then-generate any catalog diagram_type. "
        "context: diagram_type?, thinking=false?"
    ),
)
def uml_diagram_prompt(context: dict[str, Any] | None = None) -> str:
    """Plan-then-generate with layout tips for any catalog diagram type."""
    context = context or {}
    thinking = context.get("thinking", True)
    planning = ""
    if thinking is not False and str(thinking).lower() not in ("0", "false", "no"):
        planning = """Plan (not inside tool `code`): (1) `diagram_type` from uml://types, (2) scope ≤25 Mermaid / ≤30 PlantUML elements, (3) one focal path. Use sequential-thinking if available.

"""

    prompt = (
        planning
        + """You write diagram source and call uml-mcp tools.

Discover: uml://types, uml://formats, or `.skill/skills/<diagram_type>/SKILL.md`. Syntax must match the type's backend.
Render: **validate_uml** when unsure → **generate_uml** (omit `output_dir` unless saving) or **generate_uml_image** for chat PNG. Prefer URL + playground in the reply.
Emit: fenced source for the reader; tool `code` is raw DSL only (no fences).
PlantUML: `@startuml`…`@enduml`. Mermaid sequence: one statement per line.
Theme: pass `theme` on generate_uml when the page is light/dark/B&W — use the **diagram_theme** prompt or `.skill/skills/<type>/SKILL.md` Themes section.
"""
    )

    if "diagram_type" in context:
        diagram_type = context["diagram_type"]
        prompt += (
            f'\nTarget: set diagram_type to "{diagram_type}" exactly on generate_uml.\n'
        )

    return prompt + _layout_overlap_appendix()


def _layout_overlap_appendix() -> str:
    """Compact per-backend rules to minimize crossing arrows (advice only)."""
    return """
## Layout (reduce crossings)
- Cap size (~25 Mermaid / ~30 PlantUML nodes); split rather than cram; declare related nodes adjacent.
- **Mermaid:** one of `flowchart TD` or `LR`; `subgraph` clusters; short edge labels; do not mix `-->` / `-.->` / `==>` without meaning.
- **PlantUML:** `skinparam linetype ortho` + `left to right direction` (non-sequence); directional arrows (`-down->`, `-right->`); `together { }`; sequence: contact order, `autoactivate on`, no upward messages.
- **D2:** `direction: right|down`; containers for groups; ELK if dagre crosses.
- **Graphviz:** `rankdir=LR|TB`; `splines=ortho`; `subgraph cluster_*`.
"""


# Alias kept for tests / callers; not published (uml_diagram already plans).
@mcp_prompt(
    "uml_diagram_with_thinking",
    description="Alias of uml_diagram (plan-then-generate). Prefer uml_diagram.",
    category="uml",
    publish=False,
)
def uml_diagram_with_thinking_prompt(context: dict[str, Any] | None = None) -> str:
    """Same text as ``uml_diagram`` (planning is on by default)."""
    return uml_diagram_prompt(context)


# Class diagram prompt (notation → agent skill ``class``; not on prompts/list)
@mcp_prompt(
    "class_diagram",
    description="Generate UML class diagram from a natural language description. Produces PlantUML code with classes, attributes, methods, visibility, inheritance, composition, and associations.",
    publish=False,
)
def class_diagram_prompt(context: dict[str, Any] | None = None) -> str:
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
    publish=False,
)
def sequence_diagram_prompt(context: dict[str, Any] | None = None) -> str:
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
    publish=False,
)
def activity_diagram_prompt(context: dict[str, Any] | None = None) -> str:
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
    publish=False,
)
def usecase_diagram_prompt(context: dict[str, Any] | None = None) -> str:
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
    publish=False,
)
def mermaid_sequence_api_prompt(context: dict[str, Any] | None = None) -> str:
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
    publish=False,
)
def mermaid_gantt_prompt(context: dict[str, Any] | None = None) -> str:
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
    publish=False,
)
def bpmn_process_guide_prompt(context: dict[str, Any] | None = None) -> str:
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
    publish=False,
)
def c4_model_prompt(context: dict[str, Any] | None = None) -> str:
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
    publish=False,
)
def wireviz_harness_prompt(context: dict[str, Any] | None = None) -> str:
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
    publish=False,
)
def bpmn_executable_process_prompt(context: dict[str, Any] | None = None) -> str:
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
    publish=False,
)
def convert_class_to_mermaid_prompt(context: dict[str, Any] | None = None) -> str:
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
    description="Algorithm diagram with Big-O labels; uml://recipes algorithm_flowchart.",
    category="algorithm",
)
def algorithm_explainer_prompt(context: dict[str, Any] | None = None) -> str:
    """Explain an algorithm as a diagram with per-step Big-O labels."""
    context = context or {}
    prompt = """Explain an algorithm with a diagram. Every step needs a Big-O label; put the aggregate complexity once in the title/note.

Shape → diagram_type:
- Linear/branching control flow → **mermaid** flowchart TD or **activity**
- Recursion / call tree → **mermaid** tree or **d2** (direction: down)
- Data-structure state machine → **state**
- Pipeline / dataflow → **mermaid** flowchart LR or **d2** (direction: right)

Labels: Mermaid Step["Partition<br/><i>O(n)</i>"]; PlantUML :Partition\\nO(n);; D2 multi-line \\n. Terminals stadium; decisions diamond; mark base cases vs recursive calls.
Starter: uml://recipes → algorithm_flowchart. Then validate_uml → generate_uml (prefer svg; omit output_dir unless saving). No error-edge from every node; one error sink.
"""
    if "algorithm" in context:
        prompt += f"\nTarget algorithm: **{context['algorithm']}**. Name it in the title and first node.\n"
    return prompt + _layout_overlap_appendix()


@mcp_prompt(
    "paper_concept_diagram",
    description="Paper/concept diagram with clickable citations (SVG); uml://recipes paper_concept.",
    category="research",
)
def paper_concept_diagram_prompt(context: dict[str, Any] | None = None) -> str:
    """Academic-paper concept diagram with clickable citation links."""
    context = context or {}
    prompt = """Diagram a paper concept with short [Author+ Year] labels and real clickable links (never invent URLs).

Pick type: architecture → mermaid LR or d2; comparison → mermaid/graphviz; citation graph → graphviz.
Links: Mermaid click Id "https://arxiv.org/abs/…" "Title" _blank; PlantUML [[url label]]; D2 link:; Graphviz URL=. Full title in tooltip, not the node label.
Must use output_format **svg** (PNG drops links). Starter: uml://recipes → paper_concept. Then generate_uml with raw code.
"""
    if "paper" in context:
        prompt += (
            f"\nPrimary paper: **{context['paper']}**. Cite it on the focal node.\n"
        )
    return prompt + _layout_overlap_appendix()


_CONTEXT_HELP = 'Optional JSON object, e.g. {"diagram_type": "class"}.'


def _parse_context(raw: str) -> dict[str, Any]:
    """Decode the ``context`` prompt argument (a JSON object, as a string)."""
    if not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise ValueError(f"context must be a JSON object: {exc}") from exc
    if not isinstance(value, dict):
        raise TypeError("context must be a JSON object")
    return value


def _summary(func: Callable[..., Any]) -> str:
    """The docstring text before its ``Args:`` / ``Returns:`` sections."""
    doc = inspect.getdoc(func) or ""
    return re.split(r"\n\s*(?:Args|Returns):", doc, maxsplit=1)[0].strip()


def _with_string_context(func: Callable[..., str]) -> Callable[..., str]:
    """Advertise ``context`` as a plain string argument that carries JSON.

    MCP prompt arguments are strings on the wire. Annotating the parameter as a dict made
    FastMCP append a whole JSON Schema sentence to every prompt's argument description,
    which every client then loads on connect (about 40 tokens a prompt). FastMCP does that
    for any annotation other than exactly ``str``, so the description comes from the
    docstring instead. The prompt functions themselves still take the decoded dict.
    """

    def prompt(context: str = "") -> str:
        return func(context=_parse_context(context))

    prompt.__name__ = getattr(func, "__name__", "prompt")
    prompt.__doc__ = f"{_summary(func)}\n\nArgs:\n    context: {_CONTEXT_HELP}\n"
    return prompt


def register_prompts_with_server(server: Any) -> list[str]:
    """
    Register published prompts with the MCP server (``publish=True`` only).

    Args:
        server: The MCP server instance

    Returns:
        List of registered prompt names
    """
    to_publish = {
        name: info
        for name, info in _registered_prompts.items()
        if info.get("publish", True)
    }
    logger.info(
        "Registering %s of %s prompts with the MCP server",
        len(to_publish),
        len(_registered_prompts),
    )

    registered_prompt_names = []

    from ..observability.audit import instrument

    for prompt_name, prompt_info in to_publish.items():
        func = _with_string_context(
            instrument(prompt_info["function"], "prompt", prompt_name)
        )

        # Pass the short decorator description so connect-time stays small
        # (docstrings describe the body, not the prompts/list blurb).
        desc = str(prompt_info.get("description") or "").strip() or None
        prompt_decorator = server.prompt(prompt_name, description=desc)
        prompt_decorator(func)

        registered_prompt_names.append(prompt_name)
        logger.debug(f"Registered prompt: {prompt_name}")

    return registered_prompt_names


def register_diagram_prompts(server: Any) -> list[str]:
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


def get_prompt_registry() -> dict[str, dict[str, Any]]:
    """
    Get the registry of all prompts registered with the decorator

    Returns:
        Dictionary of prompt metadata
    """
    return _registered_prompts


def get_published_prompt_registry() -> dict[str, dict[str, Any]]:
    """Prompts that appear on MCP ``prompts/list`` (``publish`` not False)."""
    return {
        name: info
        for name, info in _registered_prompts.items()
        if info.get("publish", True)
    }


@mcp_prompt(
    "diagram_theme",
    description=(
        "Pick a generate_uml theme for light, dark/black, or B&W backgrounds. "
        "context: background?, diagram_type?"
    ),
    category="uml",
)
def diagram_theme_prompt(context: dict[str, Any] | None = None) -> str:
    """Choose PlantUML / Mermaid / D2 themes that stay legible on the page background."""
    from mcp_core.core.config import DIAGRAM_TYPES
    from mcp_core.core.diagram_themes import (
        D2_BW_BG,
        D2_DARK_BG,
        D2_LIGHT_BG,
        MERMAID_BW_BG,
        MERMAID_DARK_BG,
        MERMAID_LIGHT_BG,
        PLANTUML_BW_BG,
        PLANTUML_DARK_BG,
        PLANTUML_LIGHT_BG,
        normalize_background,
        pick_theme,
        themes_for_background,
    )

    context = context or {}
    background = normalize_background(
        context.get("background") or context.get("bg") or context.get("page")
    )
    diagram_type = (context.get("diagram_type") or "").strip().lower()

    light_p = ", ".join(f"`{t}`" for t in PLANTUML_LIGHT_BG)
    dark_p = ", ".join(f"`{t}`" for t in PLANTUML_DARK_BG)
    bw_p = ", ".join(f"`{t}`" for t in PLANTUML_BW_BG)
    light_m = ", ".join(f"`{t}`" for t in MERMAID_LIGHT_BG)
    dark_m = ", ".join(f"`{t}`" for t in MERMAID_DARK_BG)
    bw_m = ", ".join(f"`{t}`" for t in MERMAID_BW_BG)
    light_d = ", ".join(f"`{t}`" for t in D2_LIGHT_BG)
    dark_d = ", ".join(f"`{t}`" for t in D2_DARK_BG)
    bw_d = ", ".join(f"`{t}`" for t in D2_BW_BG)

    prompt = f"""Pick a **`theme`** for `generate_uml` / `generate_uml_image` so ink stays readable on the page.

## Background modes
- **light** / white chat canvas → pastel fills, dark text.
- **dark** / **black** page → light strokes; never use pale-on-white themes.
- **bw** / print / monochrome → high-contrast, little chroma (plain / sketchy / mimeograph).

## PlantUML (+ class, sequence, activity, …, c4plantuml)
- light: {light_p}
- dark/black: {dark_p}
- bw: {bw_p}
Pass `theme` (e.g. `cerulean`); the server injects `!theme <name>` after `@startuml`.

## Mermaid
- light: {light_m}
- dark/black: {dark_m}
- bw: {bw_m}

## D2
- light: {light_d}
- dark/black: {dark_d}
- bw: {bw_d}

## Other backends (no MCP theme)
Use source styling for contrast: nomnoml `#fill`/`#stroke`, Graphviz `fillcolor`, Vega `background`.
On a **black** canvas prefer light fills (`#eee8d5`) and dark strokes (`#33322E`).

## Workflow
1. Decide background: light | dark | bw (from the user or UI).
2. Load `.skill/skills/<diagram_type>/SKILL.md` Themes/Styling if needed.
3. Call **validate_uml** when unsure, then **generate_uml** / **generate_uml_image** with `theme` set.
4. Prefer SVG for crisp B&W print; PNG for chat.
"""

    if diagram_type and diagram_type in DIAGRAM_TYPES:
        backend = DIAGRAM_TYPES[diagram_type].backend
        picks = themes_for_background(backend, background)
        default = pick_theme(backend, background)
        prompt += (
            f'\nTarget: `diagram_type="{diagram_type}"` (backend `{backend}`), '
            f"background **{background}**.\n"
        )
        if default:
            listed = ", ".join(f"`{t}`" for t in picks)
            prompt += f"Default `theme`: **`{default}`**. Also good: {listed}.\n"
        else:
            prompt += "This backend has no MCP `theme`; follow the Styling section of its skill.\n"
    else:
        prompt += (
            f"\nActive background mode: **{background}**. "
            'Pass context like `{"background":"bw","diagram_type":"class"}`.\n'
        )

    return prompt


@mcp_prompt(
    "architecture_report",
    description="Markdown architecture report with generate_uml diagrams and TOC.",
    category="report",
)
def architecture_report_prompt(context: dict[str, Any] | None = None) -> str:
    """Full Markdown architecture report with rendered diagrams."""
    context = context or {}
    subject = (
        context.get("subject") or context.get("repository") or "the current repository"
    )
    return f"""You are a software architect. Produce a **Markdown architecture report** for {subject}.
Read the code and configuration first (entry points, packages, deployment files, CI); never invent components.

Report structure (number every section and link it from the table of contents):

# <Project> — architecture report
## Table of contents  (links: [1. Introduction](#1-introduction), …)
## 1. Introduction — purpose, scope, audience, one-paragraph summary
## 2. Inputs and outputs — table: interface | direction (in/out) | protocol/format | example
## 3. Use case diagram — PlantUML `usecase` (actors, system boundary, main use cases)
## 4. Sequence diagram — Mermaid `sequenceDiagram` of the most important request path (include auth/errors)
## 5. Class diagram — PlantUML `class` (or Mermaid `classDiagram`) of the core modules/types
## 6. Activity diagram — PlantUML `activity` of the main processing flow (decisions, fallbacks)
## 7. Deployment diagram — PlantUML `deployment` (or C4 `c4plantuml`): clients, runtime, containers, external services
## 8. User flow — Mermaid `flowchart LR` from the user's first action to the result
## 9. Inventory — Mermaid `mindmap` (or a table) of packages, endpoints, tools, configs, workflows
## 10. Risks and next steps
## References — numbered links [1], [2] … cited in the text

For every diagram section:
1. One sentence explaining what the diagram shows.
2. Call **validate_uml** (strict) and fix errors, then **generate_uml** with the matching `diagram_type`
   (`usecase`, `sequence` or `mermaid`, `class`, `activity`, `deployment`/`c4plantuml`, `mermaid`).
3. Embed the result as `![<title>](<url from the tool>)` followed by `[Playground](<playground>)` and the
   diagram source in a fenced block (```plantuml or ```mermaid). Never link local `output/` paths.
4. Keep each diagram under ~25 elements; split views rather than cramming.

Close with a short "Diagram index" table: number | section | type | backend | URL.
Rendering goes through Kroki (https://kroki.io, https://github.com/yuzutech/kroki).
"""
