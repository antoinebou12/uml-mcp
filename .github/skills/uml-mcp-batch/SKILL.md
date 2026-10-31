---
name: uml-mcp-batch
description: Render and verify diagram batches and consistent multi-format architecture conversions, including four C4 levels.
---

# Diagram batches

Follow `skill://uml-mcp-diagrams/SKILL.md`. Build one inventory of named
components, boundaries and directed labelled edges before converting formats.
Keep IDs stable where possible. Compare each source against that inventory;
record deliberate scope changes between C4 levels. Discover all requested types
and formats, then read the appropriate focused skill.

Call `generate_uml_batch` with an `items` array. Each item uses the documented
`generate_uml` fields: `diagram_type`, `code`, `output_format`, optional `theme`
and `scale`. Keep transport fields such as `user_intent` out of items.

```json
{"items":[{"diagram_type":"mermaid","output_format":"svg","code":"flowchart LR
  web[Frontend] -->|HTTPS| api[Backend]"},{"diagram_type":"d2","output_format":"svg","code":"direction: right
web: Frontend
api: Backend
web -> api: HTTPS"}]}
```

Validate complex or unfamiliar sources before the batch. Validation checks
syntax, while rendering checks the actual backend; neither proves that the host
has displayed a readable preview. For four C4 levels, use context/container/
component libraries and ordinary UML for code detail, as the C4 guide explains.

Inspect every returned index for errors, MIME type, bytes or a usable render
link. Check each gallery entry, including labels and fit, when the host supports
visual inspection. Partial success remains partial success. Retry failed items
individually with corrected source and preserve successful results. Never call
all items successful based only on HTTP status or `valid: true`.

Prefer SVG per item for Apps. Initial thumbnails share a response-size budget;
selecting an item retrieves full vectors on demand. Do not treat a tiny thumbnail
or a Link placeholder as proof of a full-resolution image. If full retrieval
fails, report the affected item and offer its fresh link only if returned.

In an App host, confirm how many items rendered and identify failures briefly;
avoid duplicating every diagram, URL and source in chat. For plain clients,
provide a compact list of named, returned render/playground links and one image
per requested view where supported. Do not reuse URLs from earlier failed runs.
