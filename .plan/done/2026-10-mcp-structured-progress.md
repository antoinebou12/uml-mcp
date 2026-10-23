# Structured progress content (SEP-2632 — interim)

- **Priority:** P3   **Size:** S   **Status:** done (2026-10) — interim until SEP Final

## Shipped

- `notifications.report_progress(..., data=)` appends a compact JSON trailer to the progress message (`index`, `diagram_type`, `url`, `ok`, …).
- Batch tool passes structured fields on each completion.
- Upgrade to native structured progress when SEP-2632 lands in the SDK.
