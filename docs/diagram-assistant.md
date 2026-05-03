# Diagram Assistant

Diagram Assistant lists the MCP tools, resources, and prompts used to generate and read UML and other diagram types. The table shows four example prompts and how the server handles them.

## Example prompts and behavior

| User prompt | Desired behavior | Tools | Resources |
|-------------|------------------|--------|-----------|
| "Show me a Mermaid sequence diagram for an API call" | Return valid Mermaid `sequenceDiagram` (client → API → backend) and optionally call `generate_uml("mermaid", code)`. | `generate_uml` | `uml://examples` (mermaid), `uml://mermaid-examples` (sequence_api) |
| "Generate a Gantt chart using Mermaid syntax" | Return valid Mermaid `gantt` block and optionally call `generate_uml("mermaid", code)`. | `generate_uml` | `uml://mermaid-examples` (gantt), `uml://templates` |
| "Explain how to draw a BPMN process model" | Return concise guidance (elements, flow, BPMN 2.0.2 alignment) and optionally point to BPMN template/example. | `generate_uml` (`diagram_type` **bpmn**) | `uml://bpmn-guide`, `uml://templates` (bpmn) |
| "Convert this class diagram into Mermaid code" | Take PlantUML or description and output Mermaid `classDiagram`; optionally call `generate_uml("mermaid", code)`. | `generate_uml` | `uml://templates`, `uml://examples` |

## Tools

- **generate_uml**: Pass `diagram_type` (e.g. `class`, `sequence`, `mermaid`, `bpmn`) and `code`. Omit **`output_dir`** for URL / base64 only; set **`output_dir`** to save a file. **`generate_from_request`** in **`mcp_core/core/diagram_service.py`** calls **`generate_diagram`** in **`mcp_core/core/utils.py`**, then **`diagram_rendering.run_diagram_pipeline`** (Kroki first, optional fallbacks). Responses may include **`source`** (`kroki`, `plantuml_server`, or `mermaid_ink`).
- **validate_uml**: Local validation of type, format, and light syntax before render (no network).

## Resources

- **uml://types**: Available diagram types and backends.
- **uml://templates**: Starter template code per diagram type (including `mermaid`, `mermaid_gantt`-style content via Mermaid examples).
- **uml://examples**: Full examples per diagram type.
- **uml://mermaid-examples**: Named Mermaid examples: `sequence_api` (API call sequence), `gantt` (Gantt chart).
- **uml://bpmn-guide**: Short BPMN 2.0.2-oriented guide: core elements (Start/End events, Task, Gateways, Sequence Flow, Lanes), flow rules, and pointer to BPMN template/tools.
- **uml://formats**: Supported output formats per type.
- **uml://server-info**: Server name, version, tools, prompts.
- **uml://workflow**: Recommended workflow: plan first (type, elements, relationships), then call generate_uml.

## Prompts

Registered prompts that support the four scenarios above:

- **mermaid_sequence_api**: Produce a Mermaid sequence diagram for an API call (client, API, auth/DB, request/response, optional `alt`); then call `generate_uml("mermaid", code)`.
- **mermaid_gantt**: Produce a Mermaid Gantt chart with title, dateFormat, sections, and tasks; then call `generate_uml("mermaid", code)`.
- **bpmn_process_guide**: Explain how to draw a BPMN process (elements, flow, BPMN 2.0.2); point to `uml://bpmn-guide` and `generate_uml("bpmn", ...)`.
- **convert_class_to_mermaid**: Convert a class diagram (PlantUML or prose) into Mermaid `classDiagram` and optionally call `generate_uml("mermaid", code)`.

Other diagram prompts (e.g. `class_diagram`, `sequence_diagram`, `uml_diagram_with_thinking`) remain available for general UML generation.

## Supported diagram types

The server supports (among others): `class`, `sequence`, `activity`, `usecase`, `state`, `component`, `deployment`, `object`, `mermaid`, `d2`, `graphviz`, `erd`, `blockdiag`, `packetdiag`, `bpmn`, `c4plantuml`. See **uml://types** for the full list and descriptions.

## Reference

- Kroki cheatsheet and docs for syntax and supported diagram types.
- BPMN 2.0.2 (OMG) for BPMN terminology and element set.
- Skill: `.skill/skills/uml-diagramming/SKILL.md` and `references/DIAGRAM-TYPES.md` for type mappings and examples.
