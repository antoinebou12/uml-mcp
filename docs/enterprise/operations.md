---
title: Operations — audit, logging, metrics, rate limits
description: "Run UML-MCP in production: MXCP-style audit trail of every tool, resource and prompt call, log rotation, SIEM shipping, Prometheus metrics and configurable rate limiting."
---

# Operations: audit, logging, metrics, rate limits

Everything on this page is configured in [`uml-mcp.yaml`](../configuration/uml-mcp-yaml.md)
(Helm: the `config:` value) and is **off or quiet by default**. The public Vercel
deployment is unchanged.

## Audit trail

Every MCP **tool**, **resource** and **prompt** execution is recorded, plus REST and
AG-UI calls (`include_http`) and every authentication or authorization denial.
The record format follows [MXCP's auditing model](https://mxcp.dev):

| Field | Meaning |
| --- | --- |
| `timestamp` | UTC, ISO 8601 with milliseconds (`2026-09-25T10:12:03.418Z`) |
| `caller_type` | `http` (Streamable HTTP / REST) or `stdio` |
| `operation_type` | `tool`, `resource`, `prompt` or `http` |
| `operation_name` | Tool, resource URI template or prompt name, or `METHOD /path` |
| `input_data` | Arguments after redaction (see below) |
| `duration_ms` | Execution time |
| `policy_decision` | `allow`, `deny` or `n/a` (auth off) |
| `policy_reason` | Why, e.g. `write permission (scope)`, `insufficient_scope`, `invalid_audience`, `rate_limited` |
| `operation_status` | `success` or `error` |
| `error` | Error message (redacted, truncated), or `null` |
| `user_id` | Verified user: `preferred_username` / `upn` / `email`, else `sub` (null when auth is off) |
| `session_id` | `Mcp-Session-Id`, or `req-<request id>` for stateless calls |
| `request_id` | `X-Request-ID` (echoed on every response; correlate with access logs) |
| `tenant_id`, `client_id` | Entra `tid` and `azp`/`appid` |
| `server_version` | UML-MCP version that handled the call |

Example (JSON Lines):

```json
{"timestamp":"2026-09-25T10:12:03.418Z","caller_type":"http","operation_type":"tool","operation_name":"generate_uml","input_data":{"diagram_type":"sequence","code":{"sha256":"9f2c…","chars":312,"preview":"@startuml\nAlice -> Bob"}},"duration_ms":184.2,"policy_decision":"allow","policy_reason":"write permission (scope)","operation_status":"success","error":null,"user_id":"ada@contoso.com","session_id":"4be1…","request_id":"b7c9…","tenant_id":"1111…","client_id":"aebc6443-996d-45c2-90f0-388ff96faa56","server_version":"1.4.0"}
```

### Redaction (`include_inputs`)

| Mode | Behaviour |
| --- | --- |
| `none` | `input_data` is `null` |
| `redacted` (default) | Keys that look like secrets (`token`, `secret`, `password`, `authorization`, `api_key`, `assertion`, `cookie`, `credential`) become `***`. JWT-looking strings anywhere become `<redacted>`. Diagram source (`code`, `source`, `content`, …) is replaced by `{sha256, chars, preview}` with an 80-char preview. |
| `full` | Values kept, still masked for secrets and JWTs, and truncated at `max_input_chars` (`uml-mcp lint` warns) |

Bearer tokens are never recorded. The auth middleware strips `Authorization`
before the request reaches any handler.

### Sinks and rotation

| Sink | Use |
| --- | --- |
| `file` | Rotating JSONL file, created with mode `0600`. Size-based (`max_bytes`) or time-based (`max_bytes: 0`, `when: midnight`, `interval`), `backup_count` retained, optional gzip (`compress: true`). |
| `stream` | One `{"audit": {...}}` JSON line per record on **stdout** (on **stderr** under stdio, so JSON-RPC stays clean). This is the Kubernetes way: the node's log agent ships it. |
| `memory` | Last `memory_size` records for the admin dashboard's **Activity** tab (per replica) |

A failing sink (disk full, closed pipe) never fails the request. Failures are
counted as `sink_errors` in metrics and logged.

**Retention:** size × `backup_count` bounds disk use on each pod. Long-term retention
belongs in your SIEM.

### Shipping to a SIEM

| Platform | Recipe |
| --- | --- |
| Azure Monitor / Log Analytics | Container Insights collects stdout. Query `ContainerLogV2 \| where LogMessage has '"audit"' \| extend a = parse_json(LogMessage).audit` |
| Splunk | Splunk OpenTelemetry Collector or Connect for Kubernetes; `spath path=audit` |
| Elastic | Filebeat/Elastic Agent `decode_json_fields` on `message`, target `uml_mcp` |
| Files (VMs) | Point `audit.file.path` at `/var/log/uml-mcp/` and let the agent tail `*.jsonl` |

Useful detections:

- `policy_decision == "deny"` grouped by `user_id` and `policy_reason` (probing, mis-scoped clients)
- repeated `invalid_audience` (tokens for another API)
- bursts of `rate_limited`
- `operation_status == "error"` per tool (renderer outages)

## Application logs

`logging.level`, `logging.format: json` (one object per line: `timestamp`, `level`,
`logger`, `message`, `request_id`), per-logger levels, and an optional rotating file.
Under `uvicorn app:app` (Docker/Helm), an explicit `logging:` section is applied at
startup. Uvicorn's access log is off in the chart; the audit trail and
`X-Request-ID` cover it, and query strings with `code=`, `state=` or `access_token=`
are redacted.

## Metrics

`metrics.enabled` (default on) keeps in-process counters, available through the
dashboard and `/admin/api/metrics`:

- calls, errors and denials per operation
- p50/p95 latency from fixed buckets; calls over 30 s report `30000`
- top denial reasons
- rate-limit rejections per scope
- `sink_errors`

To bound cardinality, HTTP paths keep only their first two segments, and
names beyond 200 series are grouped under `other`.

Set `metrics.endpoint: true` to expose `GET /metrics` in Prometheus text format:

```text
uml_mcp_operations_total{type="tool",name="generate_uml",outcome="success"} 42
uml_mcp_rate_limited_total{scope="route:/oauth/token"} 3
uml_mcp_uptime_seconds 8120.4
```

With auth enabled, `/metrics` requires the **`MCP.Admin`** app role. Give the
scraper a client-credentials token, or scrape inside the cluster with auth off
behind a `NetworkPolicy`. Metrics are per replica, so let Prometheus aggregate.

## OpenTelemetry

Set `otel.enabled: true` to send traces to any OTLP collector: Azure Monitor
(via the OpenTelemetry Collector), Grafana Tempo, Jaeger, Datadog or Honeycomb.
You get one server span per HTTP request and one child span per MCP operation.
They carry the audit attributes (never inputs or tokens) and join the caller's
trace through `traceparent`. Configuration: [otel](../configuration/uml-mcp-yaml.md#otel-opentelemetry-traces).

## Rate limits

See [rate_limit](../configuration/uml-mcp-yaml.md#rate_limit):

- token buckets per IP or per principal
- route and per-tool limits
- trusted proxies for `X-Forwarded-For`
- failed-auth throttling
- IETF `RateLimit-*` headers, and 429 with `Retry-After`

Limits are per process. Put global quotas in your ingress or API gateway, and keep
these as a second line of defence.

## Incident checklist

1. **Find the requests.** Filter the dashboard's **Activity** tab, or your SIEM, by
   `user_id`, `client_id` or `request_id`; export JSONL for the ticket.
2. **Contain.**
   - Disable a tool with `tools.disabled` and roll out the config.
   - Tighten `rate_limit.tools`.
   - Remove the user's app-role assignment in Entra.
   - Revoke sessions (`Revoke-MgUserSignInSession`); Conditional Access re-evaluates on refresh.
3. **Keys.** Rotate `MCP_AUTH_PROXY_ENCRYPTION_KEYS` (new key first) to invalidate
   facade refresh tokens.
4. **Verify.**
   - `uml-mcp lint --strict`
   - `uml-mcp config validate`
   - the smoke runner against the deployment, with the token in `MCP_SMOKE_TOKEN` rather than on the command line: `uv run python scripts/run_mcp_smoke.py --url https://mcp.contoso.com/mcp`
   - [`tests/http/entra-auth.http`](https://github.com/antoinebou12/uml-mcp/blob/main/tests/http/entra-auth.http)
