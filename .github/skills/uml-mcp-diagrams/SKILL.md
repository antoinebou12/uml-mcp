---
name: uml-mcp-diagrams
description: Render and verify UML, C4, Mermaid, D2 and D3 diagrams.
---

# Diagram workflow

Use the server's current catalog before choosing a renderer. Read `uml://types`
and `uml://formats`, or call `list_diagram_types`. Installed plugins extend the
catalog: never conclude D3 is unsupported from a remembered list. If D3 types
are present, render with those types through the normal generation tools.
If absent, explain that this server has not enabled the plugin.

## Choose a focused workflow

Read the relevant guide through `resources/read` when needed:

| Request | Resource | Local skill |
| --- | --- | --- |
| D3, cloud logos, custom plugins | `skill://uml-mcp-guides/d3-plugins/SKILL.md` | `.skill/skills/uml-mcp-d3-plugins/SKILL.md` |
| Complex Mermaid | `skill://uml-mcp-guides/mermaid/SKILL.md` | `.skill/skills/uml-mcp-mermaid/SKILL.md` |
| PlantUML and C4 levels | `skill://uml-mcp-guides/plantuml-c4/SKILL.md` | `.skill/skills/uml-mcp-plantuml-c4/SKILL.md` |
| Several views or format conversions | `skill://uml-mcp-guides/batch/SKILL.md` | `.skill/skills/uml-mcp-batch/SKILL.md` |

MCP `skills/list` exposes this entry point. The four focused skills are available
on demand through the resource template and the agent-skills index. For other
notations, read `uml://templates`, `uml://examples`, or the per-type local skill
at `.skill/skills/<diagram_type>/SKILL.md`.

## Generate and verify

1. Record the components and directed, labelled relationships from the request.
   Preserve their identity across D3, D2, Mermaid and C4 conversions. C4 levels
   change scope deliberately; explain what each level expands.
2. Choose a catalog type matching the source language. Use the configured Kroki
   endpoint first for Kroki types. Naming Mermaid or PlantUML selects notation;
   a different service requires an explicit request or a documented fallback.
3. Use `validate_uml` for unfamiliar or complex source. Mermaid sequences need
   one statement per line; use `strict: true` when appropriate. Validation alone
   does not prove that an image was rendered or its text is readable.
4. Call `generate_uml_image` for a visible preview, `generate_uml` for a link,
   or `generate_uml_batch` for several views. Request `output_format: svg` in
   MCP Apps whenever the catalog supports it. Plain image clients usually need
   PNG; the server can rasterize SVG-only formats. Leave `output_dir` unset
   unless the user asks to write server-side files.
5. Check `error`, `success`, `mime_type`, returned bytes and render attempts.
   Verify the visible preview, labels and links when the host permits inspection.
   A render URL or `valid: true` is not evidence that the client displayed it.
   Report unverified display or inaccessible links plainly; never invent URLs.

Use a readable overview plus detail views when labels become too small. Keep
layout direction consistent, label decision branches and avoid repeated edges.
For large diagrams, the initial result is a bounded preview; the App fetches
full SVGs on demand and provides source, SVG, PNG, standalone HTML and PDF
exports where the renderer supports them. A small PNG preview is not the full
resolution download.

## Present once

In an MCP App host, give a brief confirmation and let the viewer contain the
image, source, links and downloads. Repeat code or images only on request.
For a client without Apps, show one image or a working render link, plus the
returned playground link when available. Use Markdown links for plain clients.
Do not repeat an image as both ImageContent and Markdown. Do not claim files
were downloaded, links opened or previews inspected unless that happened.

Only pass documented diagram arguments. `user_intent` is transport metadata,
not a renderer setting. Keep prose, HTML wrappers and Markdown fences out of
DSL source. If a render fails, correct the specific diagnostic and retry that
item; do not claim the whole batch succeeded.

Available workflow tools: `list_diagram_types`, `validate_uml`, `generate_uml`,
`generate_uml_image`, `generate_uml_batch`. The App can call `rerender_diagram`
and `download_diagram`. More examples: `uml://recipes`, `uml://capabilities`,
`uml://workflow` and `tests/prompts/chatgpt_mcp_smoke_test.md`.

For algorithm explanations, use the `algorithm_explainer` prompt. For papers
and clickable citations, use `paper_concept_diagram`. Both use `uml://recipes`.

When converting to D2, use supported shapes and keep service names as labels.
The observed `shape: key` request failed in Kroki; use a labelled rectangle for
an authentication service, then check the rendered result. Structural validation
alone does not verify every renderer-specific shape or external library.
