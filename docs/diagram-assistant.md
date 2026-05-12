# Diagram Assistant

This page lists the MCP tools, resources, and prompts for generating and reading UML and other diagram types. The table maps four example user prompts to the tools and resources the server uses.

## Example prompts and behavior

| User prompt | Desired behavior | Tools | Resources |
|-------------|------------------|--------|-----------|
| "Show me a Mermaid sequence diagram for an API call" | Return valid Mermaid `sequenceDiagram` (client → API → backend) and optionally call `generate_uml("mermaid", code)`. | `generate_uml` | `uml://examples` (mermaid); see [Mermaid](diagrams/mermaid.md) for sequence API sample text |
| "Generate a Gantt chart using Mermaid syntax" | Return valid Mermaid `gantt` block and optionally call `generate_uml("mermaid", code)`. | `generate_uml` | `uml://templates` (mermaid), [Mermaid](diagrams/mermaid.md) (Gantt sample) |
| "Explain how to draw a BPMN process model" | Return concise guidance (elements, flow, BPMN 2.0.2 alignment) and optionally point to BPMN template/example. | `generate_uml` (`diagram_type` **bpmn**) | [BPMN guide](tutorials/bpmn.md), `uml://templates` (bpmn), `uml://examples` (bpmn) |
| "Convert this class diagram into Mermaid code" | Take PlantUML or description and output Mermaid `classDiagram`; optionally call `generate_uml("mermaid", code)`. | `generate_uml` | `uml://templates`, `uml://examples` |
| "Explain quicksort with a diagram" | Pick the right shape (flowchart, activity, state, or recursion tree), label each step with its Big-O complexity, and call `generate_uml` with the chosen `diagram_type`. | `generate_uml` | `algorithm_explainer` prompt, `uml://recipes` (`algorithm_flowchart`) |
| "Diagram the Transformer block from Vaswani+ 2017" | Produce an architecture flowchart with citations in node labels and clickable arXiv links; call `generate_uml` with `output_format` **svg** to keep links clickable. | `generate_uml` | `paper_concept_diagram` prompt, `uml://recipes` (`paper_concept`) |

## Tools

- **generate_uml**: Pass `diagram_type` (e.g. `class`, `sequence`, `mermaid`, `bpmn`) and `code`. Omit **`output_dir`** for URL / base64 only; set **`output_dir`** to save a file. **`generate_from_request`** in **`mcp_core/core/diagram_service.py`** calls **`generate_diagram`** in **`mcp_core/core/utils.py`**, then **`diagram_rendering.run_diagram_pipeline`** (Kroki first, optional fallbacks). Responses may include **`source`** (`kroki`, `plantuml_server`, or `mermaid_ink`).
- **validate_uml**: Local validation of type, format, and light syntax before render (no network).

## Resources

- **uml://types**: Available diagram types and backends.
- **uml://templates**: Starter template code per diagram type (including `mermaid`, `mermaid_gantt`-style content via Mermaid examples).
- **uml://examples**: Full examples per diagram type.
- **uml://formats**: Supported output formats per type.
- **uml://recipes**: Named cross-type starter recipes (`algorithm_flowchart`, `paper_concept`) with the `diagram_type` and `output_format` to pass to `generate_uml`.
- **uml://server-info**: Server name, version, tools, prompts.
- **uml://workflow**: Recommended workflow: plan first (type, elements, relationships), then call generate_uml.

## Prompts

Registered prompts that support the four scenarios above:

- **mermaid_sequence_api**: Produce a Mermaid sequence diagram for an API call (client, API, auth/DB, request/response, optional `alt`); then call `generate_uml("mermaid", code)`.
- **mermaid_gantt**: Produce a Mermaid Gantt chart with title, dateFormat, sections, and tasks; then call `generate_uml("mermaid", code)`.
- **bpmn_process_guide**: Explain how to draw a BPMN process (elements, flow, BPMN 2.0.2); point to `uml://templates` / `uml://examples` (bpmn), the [BPMN guide](tutorials/bpmn.md), and `generate_uml("bpmn", ...)`.
- **convert_class_to_mermaid**: Convert a class diagram (PlantUML or prose) into Mermaid `classDiagram` and optionally call `generate_uml("mermaid", code)`.
- **algorithm_explainer**: Pick the right shape for an algorithm (flowchart, activity, state, recursion tree), label every step with its Big-O complexity, and apply per-backend layout rules that minimise crossing arrows before calling `generate_uml`.
- **paper_concept_diagram**: Visualise a concept from one or more academic papers; encode citations in node labels and add clickable arXiv/DOI links (Mermaid `click`, PlantUML `[[ ]]`, D2 `link:`, Graphviz `URL=`). Recommends `output_format` **svg** so links stay clickable.

Other diagram prompts (e.g. `class_diagram`, `sequence_diagram`, `uml_diagram_with_thinking`) remain available for general UML generation.

## Supported diagram types

The server supports (among others): `class`, `sequence`, `activity`, `usecase`, `state`, `component`, `deployment`, `object`, `mermaid`, `d2`, `graphviz`, `erd`, `blockdiag`, `packetdiag`, `bpmn`, `c4plantuml`. See **uml://types** for the full list and descriptions.

## Reference

- Kroki cheatsheet and docs for syntax and supported diagram types.
- BPMN 2.0.2 (OMG) for BPMN terminology and element set.
- Skill: `.skill/skills/uml-diagramming/SKILL.md` and `references/DIAGRAM-TYPES.md` for type mappings and examples.
