---
title: uml-mcp.yaml reference
description: "One configuration file for UML-MCP: discovery, precedence, profiles and every section (server, rendering, tools, rate_limit, logging, audit, metrics, admin, auth)."
---

# `uml-mcp.yaml` — one configuration file

Every setting can still be set with environment variables ([Configuration](../configuration.md)).
`uml-mcp.yaml` puts them in one reviewed, versioned file and adds settings that
have no env var: tool allow-lists, rate-limit policies, log rotation, the audit
trail and metrics.

## Quick start

```bash
uml-mcp config init --profile local        # ~/.config/uml-mcp/config.yaml
uml-mcp config validate                    # exit 1 on any error
uml-mcp config show --sources              # effective values + where each comes from
uml-mcp config path                        # which file is in use
```

Profiles are commented templates shipped in the package:

| Profile | For | Highlights |
| --- | --- | --- |
| `local` | One user, stdio clients (VS Code, Cursor, Claude) | Output dir in `~/uml-mcp/output`, rotating log in `~/.local/state/uml-mcp/`, optional JSONL audit |
| `docker` | Single host HTTP (`docker compose`) | Local Kroki, memory-only, per-IP rate limit, JSON logs, audit to stdout |
| `enterprise` | Kubernetes/Helm + Entra ID | Tool allow-list, per-user rate limit, trusted proxies, JSON logs, audit + `/metrics`, optional OpenTelemetry, `auth.mode: jwt` |

## Discovery and precedence

The first file found wins:

| # | Location |
| --- | --- |
| 1 | `uml-mcp --config <path>` |
| 2 | `UML_MCP_CONFIG=<path>` (`UML_MCP_CONFIG=none` disables discovery) |
| 3 | `./uml-mcp.yaml` (or `.yml`) in the working directory |
| 4 | `$XDG_CONFIG_HOME/uml-mcp/config.yaml` (default `~/.config/uml-mcp/config.yaml`) |
| 5 | `/etc/uml-mcp/config.yaml` |

Values resolve as **defaults < file < environment variables**. The file only fills
env vars that are not already set, so an existing deployment's env vars keep
working and always win. `uml-mcp config show --sources` and the admin dashboard's
**Configuration** tab show the source of each value (`default`, `file:<path>`, `env`).

Unknown sections and unknown keys are errors: the server refuses to start on an
invalid file, so a typo can't silently disable a control.

## Sections

### `server` and `rendering`

These map one-to-one to existing env vars:

| Key | Env var |
| --- | --- |
| `server.allowed_hosts` / `server.allowed_origins` | `MCP_ALLOWED_HOSTS` / `MCP_ALLOWED_ORIGINS` |
| `server.stateless_http` | `FASTMCP_STATELESS_HTTP` |
| `rendering.kroki_server` / `rendering.plantuml_server` | `KROKI_SERVER` / `PLANTUML_SERVER` |
| `rendering.use_local_kroki` / `rendering.use_local_plantuml` | `USE_LOCAL_KROKI` / `USE_LOCAL_PLANTUML` |
| `rendering.url_only` / `rendering.memory_only` / `rendering.read_only` | `MCP_URL_ONLY` / `MCP_MEMORY_ONLY` / `MCP_READ_ONLY` |
| `rendering.diagram_fallback` | `MCP_DIAGRAM_FALLBACK` |
| `rendering.output_dir` (`~` expanded) | `MCP_OUTPUT_DIR` |
| `rendering.max_code_length` / `rendering.max_render_seconds` | `MCP_MAX_CODE_LENGTH` / `MCP_MAX_RENDER_SECONDS` |
| `rendering.batch_max_items` / `rendering.batch_concurrency` | `MCP_BATCH_MAX_ITEMS` / `MCP_BATCH_CONCURRENCY` |

### `tools` — least privilege

```yaml
tools:
  enabled: [list_diagram_types, validate_uml, generate_uml]   # omit for "all"
  disabled: [generate_uml_batch]
```

Disabled tools are **not registered**: they don't appear in `tools/list`, and
calling them returns "unknown tool".

### `rate_limit`

```yaml
rate_limit:
  enabled: true
  key: principal                 # ip | principal (per bearer token / signed-in user)
  trusted_proxies: [10.0.0.0/8]  # X-Forwarded-For is honoured only from these peers
  default: {requests_per_minute: 120, burst: 30}
  routes:                        # longest prefix wins
    /mcp: {requests_per_minute: 300}
    /oauth/token: {requests_per_minute: 30}
  tools:                         # per MCP tool, enforced inside the tool call
    generate_uml_batch: {requests_per_minute: 10}
  auth_failures_per_minute: 30   # 401s per IP before 429 (key: principal)
  exempt_paths: [/health, /status, /.well-known/, /favicon, /admin/assets/]
```

- **Algorithm:** a token bucket. It refills at `requests_per_minute`, and its capacity is `burst` (default: the same value).
- **HTTP 429:** carries `Retry-After`, `RateLimit-Limit`/`-Remaining`/`-Reset` and the legacy `X-RateLimit-*` headers.
- **Tool limits:** a tool call over its limit returns an MCP error result and is audited with `policy_reason: rate_limited`. With `key: principal`, the tool bucket follows the **verified** user, so refreshing the token does not reset it.
- **Principal keying:** `key: principal` keys HTTP limits on the presented bearer token. Each 401 also charges a per-IP bucket (`auth_failures_per_minute`), so sending random tokens can't create fresh buckets.
- **Scope:** limits are per process. Use your ingress or API gateway (NGINX, Azure API Management, Front Door) for global limits.
- **Legacy setting:** `MCP_RATE_LIMIT_PER_MINUTE` still works when `rate_limit.enabled` is false.

### `logging`

```yaml
logging:
  level: INFO                   # DEBUG | INFO | WARNING | ERROR | CRITICAL
  format: json                  # text | json (one JSON object per line)
  loggers: {httpx: WARNING}
  file:
    path: /var/log/uml-mcp/server.log
    max_bytes: 10485760         # size-based rotation; 0 = time-based
    backup_count: 10
    when: midnight              # time-based: S | M | H | D | midnight
    interval: 1
    compress: true              # gzip rotated files
```

Without a `logging` section, behaviour is unchanged: a daily file in `logs/` plus
console output on stderr. Console output always goes to **stderr**, so the stdio
JSON-RPC stream stays clean.

### `audit`

```yaml
audit:
  enabled: true
  sinks: [file, stream, memory]   # JSONL file · JSON lines on stdout · admin dashboard buffer
  file: {path: /var/log/uml-mcp/audit.jsonl, max_bytes: 52428800, backup_count: 20, compress: true}
  include_inputs: redacted        # none | redacted | full
  max_input_chars: 2000
  memory_size: 500
  include_http: true              # also audit REST/AG-UI calls
```

Field list, redaction rules and SIEM shipping: [Operations](../enterprise/operations.md).
Under stdio transport, the `stream` sink writes to stderr.

### `metrics`

```yaml
metrics:
  enabled: true      # in-process counters + latency histograms (admin dashboard)
  endpoint: true     # expose GET /metrics (Prometheus text); MCP.Admin role when auth is on
```

### `otel` — OpenTelemetry traces

```yaml
otel:
  enabled: true
  service_name: uml-mcp
  exporter: otlp                  # otlp (HTTP/protobuf) | console
  endpoint: http://otel-collector:4318   # default: OTEL_EXPORTER_OTLP_ENDPOINT
  sample_ratio: 1.0               # parent-based: callers' sampling decisions win
  include_user: false             # add enduser.id (PII) to spans
  resource_attributes: {deployment.environment: prod}
```

Install the extra first: `pip install "uml-mcp[otel]"` (`uml-mcp lint` reports
CFG010 when it is missing).

- **HTTP spans:** one server span per HTTP request, named `METHOD /first/two`
  segments so span names stay bounded. It joins the caller's trace through W3C
  `traceparent`.
- **Operation spans:** one span per tool, resource and prompt call. It carries the
  audit attributes: `mcp.operation.*`, `mcp.operation_status`, `mcp.policy_decision`,
  `mcp.session_id`, `mcp.request_id` and duration.
- **Never recorded:** inputs and tokens.
- **Existing OTel setup:** the tracer is private, so a host application's global
  OpenTelemetry configuration is left alone.

### `admin`

```yaml
admin:
  allow_local_without_auth: false   # dashboard at http://127.0.0.1:8000/admin without SSO
```

This setting only takes effect while auth is off, and only for loopback socket
peers; everyone else gets 404. Don't enable it behind a reverse proxy on the same
host that doesn't set `X-Forwarded-For`. With enterprise auth, use
`auth.admin_ui: true` and the `MCP.Admin` role instead.

### `auth`

This section takes the same keys as the enterprise JSON file (`MCP_AUTH_CONFIG_FILE`),
documented in [Enterprise configuration](../enterprise/configuration.md).
Secrets are rejected here, just as they are in the JSON file: use env vars or
`*_file` keys that point to mounted secrets.

## Deployment recipes

| Where | How |
| --- | --- |
| Local | `uml-mcp config init --profile local` then `uml-mcp client install --client vscode` ([Local install](../installation-local.md)) |
| Docker | `docker run -v $PWD/uml-mcp.yaml:/etc/uml-mcp/config.yaml:ro …` |
| Compose | uncomment the volume in `docker-compose.enterprise.yml` and set `UML_MCP_CONFIG` |
| Helm | put the sections under `config:` in your values; the chart renders a ConfigMap and sets `UML_MCP_CONFIG` ([Kubernetes](../enterprise/kubernetes.md)) |
| CI | `uml-mcp config validate --config uml-mcp.yaml && uml-mcp lint --strict` |
