# MCP Apps: interactive diagram viewer

- **Priority:** P3   **Size:** M   **Status:** done (2026-10)

## Shipped

- Viewer toolbar: zoom in/out/reset, Open URL, Playground links.
- App-only tool `rerender_diagram` (`_meta.ui.visibility: ["app"]`) linked to the same UI resource.
- Viewer listens for `ui/notifications/tool-input`, keeps `code`/`diagram_type` from structured results, and calls host `tools/call` → `rerender_diagram` for theme/format changes.
- If the host rejects app `tools/call`, the re-render row hides after the first failure.
