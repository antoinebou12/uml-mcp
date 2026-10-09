---
title: Mermaid
description: Mermaid diagram syntax, supported formats, and live examples for use with generate_uml.
tags:
  - mermaid
---

# Mermaid

[Mermaid](https://mermaid.js.org/) is a JavaScript-based text-to-diagram tool. UML-MCP renders Mermaid through Kroki (server-side) and falls back to [Mermaid.ink](https://mermaid.ink/) when needed.

| Property | Value |
| --- | --- |
| `diagram_type` | `mermaid` |
| Backend | Mermaid (via Kroki) → Mermaid.ink fallback |
| Output formats | `svg`, `png` |
| Resource shortcuts | `uml://templates` (key `mermaid`), `uml://examples` (key `mermaid`) |
| Prompts | `mermaid_sequence_api`, `mermaid_gantt`, `convert_class_to_mermaid` |

!!! tip "Browser-rendered preview vs server render"

    The blocks below render in your browser via Mermaid's runtime. Calling `generate_uml(diagram_type="mermaid", code=...)` returns a server-rendered SVG/PNG you can embed anywhere.

## Calling `generate_uml`

```json
{
  "name": "generate_uml",
  "arguments": {
    "diagram_type": "mermaid",
    "code": "flowchart LR; A-->B; A-->C;",
    "output_format": "svg"
  }
}
```

## Supported diagram kinds

Mermaid covers many shapes from a single backend. Pick the right opening keyword:

| Kind | Opening directive | Notes |
| --- | --- | --- |
| Flowchart | `flowchart LR` (or `graph TD`) | Use for control flow, decision trees, dependency graphs. |
| Sequence | `sequenceDiagram` | Pair with `participant`, `->>`, `-->>`, `alt`/`else`. |
| Class | `classDiagram` | Visibility prefixes: `+`, `-`, `#`, `~`. Relationships: `<|--`, `*--`, `o--`, `..>`. |
| State | `stateDiagram-v2` | Use `[*]` for start/end pseudostates. |
| ER | `erDiagram` | Cardinality: `||--o{`, `}|..|{`. |
| Gantt | `gantt` | Set `dateFormat` and `axisFormat`; sections group tasks. |
| Pie | `pie` | Add `showData` for numeric labels. |

## Quick samples

### Flowchart

```mermaid
flowchart LR
    Cursor -->|generate_uml| MCP --> Kroki --> SVG((SVG))
```

### Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant A as Agent
    participant M as MCP
    U->>A: "draw a sequence diagram"
    A->>M: tools/call generate_uml
    M-->>A: { url, content_base64 }
    A-->>U: rendered diagram
```

### Class

```mermaid
classDiagram
    class Diagram {
        +String diagram_type
        +String code
        +render() Result
    }
    class Result {
        +String url
        +String? local_path
    }
    Diagram --> Result
```

### State

```mermaid
stateDiagram-v2
    [*] --> Validate
    Validate --> Render: ok
    Validate --> Error: invalid
    Render --> [*]
    Error --> [*]
```

## Validation tips

!!! warning "Common pitfalls"

    - **Mismatched arrows**: `->>` (solid) vs `-->>` (dashed) in sequence diagrams; mixing breaks Kroki.
    - **Reserved keywords**: avoid `end`, `subgraph`, `graph`, `flowchart` as bare node IDs in flowcharts.
    - **Special characters in labels**: wrap with double quotes, for example `A["Process (main)"]`.

Run `validate_uml(diagram_type="mermaid", code=..., strict=true)` to surface these before calling Kroki.

## Themes

`theme` works for Mermaid: pass one of `default`, `dark`, `forest`, `neutral` or `base` and the
server adds Mermaid's own `%%{init: {'theme': '...'}}%%` directive (after any `---` frontmatter).
It applies to the Kroki render and to the mermaid.ink fallback alike. Your own `%%{init}%%`
directive, or a `theme:` in the frontmatter `config`, always wins, and a name that is not a Mermaid
theme (such as a PlantUML theme) is ignored.

## Input that is cleaned up for you

Before rendering (and before `validate_uml` checks it), the server repairs input that Mermaid
cannot parse as written, and leaves valid diagrams untouched:

| Input | What happens |
| --- | --- |
| Wrapped in a markdown fence (```` ```mermaid ````), with or without text after it | The fence is removed |
| One line with double-escaped newlines (`graph TD\n A --> B`) | The `\n` become real newlines (only when the diagram has no real newline and the header is followed directly by `\n`) |
| Zero-width characters (U+200B, U+200C, U+200D, U+2060) | Removed. Mermaid rejects them with `Lexical error … Unrecognized text`, and they cannot be seen |

## Syntax errors name the line

When Mermaid rejects a diagram, the error carries the parser's own diagnosis, so the diagram can be
fixed without guessing:

```text
Diagram syntax error: Parse error on line 4: ...D A --> B B --> Expecting 'AMP', 'COLON', 'PIPE',
..., got 'EOF'. Fix the diagram source and retry (examples: uml://examples).
```

The same applies to the other Kroki backends (Graphviz, D2, PlantUML, …). Server stack traces and
file paths are stripped from the message.

See also: [Tutorials → Mermaid live examples](../tutorials/mermaid.md), [Diagram Assistant](../diagram-assistant.md).
