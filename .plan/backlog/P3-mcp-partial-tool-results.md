# Partial / streaming tool results (SEP-2998 — watch)

- **Priority:** P3   **Size:** M
- **Stage:** proposal (not Final) — adopt only after SEP lands or FastMCP exposes a stable API

## Why

[SEP-2998](https://plan.modelcontextprotocol.io/seps) (Partial Tool Results / streaming tool-call output) would let `generate_uml_batch` and long `architecture_report` flows emit completed diagrams as they finish, instead of only at the end. Complements existing `notifications/progress` and the future [Tasks extension](P3-mcp-tasks-extension.md).

## Scope (when Final)

- Stream per-index successes from `generate_uml_batch` without growing the five-tool surface.
- Keep non-streaming clients on the current single final result.

## Refs

- SEP-2998 · related: SEP-2632 structured progress content, SEP-2663 Tasks
