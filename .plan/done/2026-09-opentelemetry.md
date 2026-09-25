# OpenTelemetry traces and metrics (optional)

- **Priority:** P1   **Size:** M
- **Why:** Enterprises already run OTel collectors (Azure Monitor, Grafana, Datadog); spans per MCP call give latency and error visibility across services.
- **Done when:** `otel:` section in uml-mcp.yaml (enabled, service_name, exporter otlp|console, endpoint, headers from env); spans for every tool/resource/prompt/REST call with the audit attributes (no inputs, no tokens); optional extra `uml-mcp[otel]`; no-op when not installed; docs.
