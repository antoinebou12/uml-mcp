---
name: mermaid
description: >-
  Writes valid mermaid diagram source for uml-mcp (diagram_type=mermaid). A JavaScript based diagramming and charting tool Use when the user asks for mermaid or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# mermaid diagram (uml-mcp)

**`diagram_type`:** `mermaid`  
**Backend:** `mermaid`  
**Output formats:** svg, png

A JavaScript based diagramming and charting tool

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Notation tips

- Pick an opening kind: `flowchart`, `sequenceDiagram`, `classDiagram`, `stateDiagram-v2`, `erDiagram`, `gantt`, `pie`, `mindmap`.
- One statement per line for `sequenceDiagram` (no `;`-packed lines).
- API sequence: Client / API / optional Auth·DB with `alt` for errors.
- Gantt: `title`, `dateFormat`, sections, `after` dependencies.
- Class conversion: `classDiagram` with `<|--`, `*--`, `o--`, `-->`.

## Themes

Pass **`theme`** to `generate_uml` / `generate_uml_image`. Allowed values: `base`, `dark`, `default`, `forest`, `neutral`.
The server prepends `%%{init: {'theme': '<name>'}}%%` when the source has no init/frontmatter theme.

Match the **page background** (MCP prompt **`diagram_theme`**):
- light / white: `default`, `forest`, `neutral`, `base`
- dark / black: `dark`
- B&W / print: `neutral`, `base`, `default`

```mermaid
%%{init: {'theme': 'forest'}}%%
sequenceDiagram
    A->>B: hello
```

## Starter template

```mermaid
sequenceDiagram
    participant User
    participant System

    User->>System: Request
    System-->>User: Response
```

## Example

```mermaid
sequenceDiagram
    participant Browser
    participant Webserver
    participant Processor

    Browser->>Webserver: GET /diagram/svg/base64
    Webserver->>Processor: Convert text to image
    Processor-->>Webserver: Return image
    Webserver-->>Browser: Deliver SVG image

    note over Browser,Webserver: HTTP Request
    note over Webserver,Processor: Internal Processing
```

## Render with uml-mcp

1. Set `diagram_type` to `mermaid` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
