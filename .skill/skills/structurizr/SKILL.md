---
name: structurizr
description: >-
  Writes valid structurizr diagram source for uml-mcp (diagram_type=structurizr). Structurizr C4 and architecture DSL Use when the user asks for structurizr or that notation; then call validate_uml / generate_uml / generate_uml_image.
---

# structurizr diagram (uml-mcp)

**`diagram_type`:** `structurizr`  
**Backend:** `structurizr`  
**Output formats:** png, svg, pdf, txt, base64

Structurizr C4 and architecture DSL

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) for URL-first replies, progressive discovery, and which MCP tool to call. This file is notation only; it does not add an MCP tool.

## Styling

- Views + `autoLayout`; branding via Structurizr themes in the DSL when needed.
- MCP `theme` is not applied for Structurizr.

## Starter template

```structurizr
workspace "My Workspace" "Description" {
    model {
        user = person "User"
        system = softwareSystem "System" "Description"
        user -> system "Uses"
    }
    views {
        systemContext system "Context" {
            include *
            autolayout lr
        }
    }
}
```

## Example

```structurizr
workspace "Example" "Description" {
    model {
        user = person "User"
        app = softwareSystem "App" "A sample system"
        user -> app "Uses"
    }
    views {
        systemContext app "Context" {
            include *
        }
    }
}
```

## Render with uml-mcp

1. Set `diagram_type` to `structurizr` exactly.
2. Call **`validate_uml`** when the source is untrusted (prefer `strict: true` for Mermaid sequence).
3. Call **`generate_uml`**, **`generate_uml_image`** (chat PNG), or **`generate_uml_batch`**.
4. Pass **`theme`** when this skill's Themes section lists supported values.
5. Surface the returned `url` / `playground` (see the workflow skill).

Confirm formats with `uml://formats` or `list_diagram_types` when unsure.
