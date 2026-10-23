# Argument completions for diagram_type and theme

- **Priority:** P2   **Size:** S   **Status:** done (2026-10)

## Shipped

- `mcp_core/resources/completions.py` — `completion/complete` for resource-template args (`diagram_type`, `recipe_id`) and prompt `context` tokens (`uml_diagram`, `diagram_theme`).
- MCP completions apply to prompts / resource templates (not tool args); theme catalogs remain available via `theme_names()` for callers.
- Wired from `register_diagram_resources` → `register_completions`.

## Refs

- Spec: completions · resources/templates argument completion
