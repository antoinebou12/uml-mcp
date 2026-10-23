# MRTR elicitation for diagram tools (SEP-2322)

- **Priority:** P2   **Size:** M   **Status:** done (2026-10)

## Shipped

- `mcp_core/tools/mrtr.py` — form elicitation via `InputRequiredResult` when the client advertises form elicitation.
- Unknown `diagram_type` → type picker (else error + `suggestions`).
- Background-style `theme` (`light`/`dark`/`bw`) → theme picker (else auto-pick first recommended).
- `generate_uml_batch` confirm when `len(items) >= MCP_BATCH_CONFIRM_MIN` (default 8; `0` disables).
- Wired into `generate_uml`, `generate_uml_image`, `generate_uml_batch`; `_as_mcp_tool_result` passes `InputRequiredResult` through.

## Refs

- SEP-2322 · docs: `docs/api/tools.md`
