# MCP Apps: interactive diagram viewer

- **Priority:** P3   **Size:** M   **Status:** done (2026-10)

## Shipped

- Viewer toolbar: zoom in/out/reset, Open URL, Playground links.
- App-only tool `rerender_diagram` (`_meta.ui.visibility: ["app"]`) linked to the same UI resource.
- Viewer listens for `ui/notifications/tool-input`, keeps `code`/`diagram_type` from structured results, and calls host `tools/call` → `rerender_diagram` for theme/format changes.
- Re-render requests time out after 30 seconds and remain retryable after failure. Duplicate clicks are disabled while a request is pending.
- Viewer decodes UTF-8 SVG, removes root event handlers, rejects unsafe links and messages from non-host windows, and exposes accessible status updates.
- Resource metadata includes the dedicated HTTPS origin and ChatGPT description; render tools advertise invocation labels.
