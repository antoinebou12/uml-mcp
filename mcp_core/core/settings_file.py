"""Single configuration file (``uml-mcp.yaml``) for server, rendering, tools,
rate limits, logging, audit, metrics, admin and enterprise auth.

Discovery order (first match wins):

1. ``--config`` / explicit path
2. ``UML_MCP_CONFIG`` (set it to ``none`` to disable discovery)
3. ``./uml-mcp.yaml`` (or ``.yml``)
4. ``$XDG_CONFIG_HOME/uml-mcp/config.yaml`` (default ``~/.config/uml-mcp/config.yaml``)
5. ``/etc/uml-mcp/config.yaml``

Precedence is **defaults < file < environment variables**: the file only fills
environment variables that are not already set, so every existing ``MCP_*``
variable keeps working and always wins.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, MutableMapping
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

CONFIG_ENV = "UML_MCP_CONFIG"

#: YAML (section, key) -> environment variable consumed by the existing settings.
ENV_MAP: dict[tuple[str, str], str] = {
    ("server", "allowed_hosts"): "MCP_ALLOWED_HOSTS",
    ("server", "allowed_origins"): "MCP_ALLOWED_ORIGINS",
    ("server", "stateless_http"): "FASTMCP_STATELESS_HTTP",
    ("rendering", "kroki_server"): "KROKI_SERVER",
    ("rendering", "plantuml_server"): "PLANTUML_SERVER",
    ("rendering", "use_local_kroki"): "USE_LOCAL_KROKI",
    ("rendering", "use_local_plantuml"): "USE_LOCAL_PLANTUML",
    ("rendering", "url_only"): "MCP_URL_ONLY",
    ("rendering", "memory_only"): "MCP_MEMORY_ONLY",
    ("rendering", "read_only"): "MCP_READ_ONLY",
    ("rendering", "diagram_fallback"): "MCP_DIAGRAM_FALLBACK",
    ("rendering", "output_dir"): "MCP_OUTPUT_DIR",
    ("rendering", "max_code_length"): "MCP_MAX_CODE_LENGTH",
    ("rendering", "max_render_seconds"): "MCP_MAX_RENDER_SECONDS",
    ("rendering", "batch_max_items"): "MCP_BATCH_MAX_ITEMS",
    ("rendering", "batch_concurrency"): "MCP_BATCH_CONCURRENCY",
}
SECTIONS = (
    "server",
    "rendering",
    "tools",
    "rate_limit",
    "logging",
    "audit",
    "metrics",
    "otel",
    "plugins",
    "admin",
    "auth",
)


#: Top-level keys that describe the file itself (not settings).
META_KEYS = ("version", "setup")


class ConfigFileError(ValueError):
    """Invalid or unreadable configuration file."""


# --------------------------------------------------------------------- models
class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _f(default: Any = ..., description: str = "", **kw: Any) -> Any:
    """``Field`` with a user-facing description (shown by the setup/settings UI)."""
    return Field(default, description=description, **kw)


class RotationConfig(_Model):
    path: str = _f(description="File path (`~` is expanded).")
    max_bytes: int = _f(
        10 * 1024 * 1024, "Rotate at this size in bytes; 0 rotates by time.", ge=0
    )
    backup_count: int = _f(10, "Rotated files to keep.", ge=0)
    when: Literal["S", "M", "H", "D", "midnight"] = _f(
        "midnight", "Time-based rotation unit (when max_bytes is 0)."
    )
    interval: int = _f(1, "Rotate every N units of `when`.", ge=1)
    compress: bool = _f(False, "Gzip rotated files.")


class LoggingConfig(_Model):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = _f(
        "INFO", "Minimum level written to the console and log file."
    )
    format: Literal["text", "json"] = _f(
        "text", "`json` writes one object per line for log collectors."
    )
    loggers: dict[str, str] = _f(
        description="Per-logger levels, e.g. {httpx: WARNING}.", default_factory=dict
    )
    file: RotationConfig | None = _f(
        None, "Rotating log file (default: daily file in logs/)."
    )


AuditSink = Literal["file", "stream", "memory"]


def _default_sinks() -> list[AuditSink]:
    return ["memory"]


class AuditConfig(_Model):
    enabled: bool = _f(
        False, "Record every tool, resource and prompt call (MXCP fields)."
    )
    sinks: list[AuditSink] = _f(
        description="`file` = rotating JSONL, `stream` = JSON on stdout, "
        "`memory` = dashboard Activity page.",
        default_factory=_default_sinks,
    )
    file: RotationConfig | None = _f(None, "JSONL file for the `file` sink.")
    include_inputs: Literal["none", "redacted", "full"] = _f(
        "redacted", "How tool arguments are stored; `redacted` hashes diagram code."
    )
    max_input_chars: int = _f(2000, "Truncate stored strings beyond this length.", ge=0)
    memory_size: int = _f(500, "Records kept for the dashboard.", ge=10, le=100_000)
    include_http: bool = _f(True, "Also audit REST and AG-UI requests.")


class MetricsConfig(_Model):
    enabled: bool = _f(True, "Keep in-process counters and latency histograms.")
    endpoint: bool = _f(False, "Expose GET /metrics in Prometheus text format.")


class OtelConfig(_Model):
    """OpenTelemetry traces (``pip install "uml-mcp[otel]"``)."""

    enabled: bool = _f(False, "Send traces to an OTLP collector.")
    service_name: str = _f("uml-mcp", "service.name resource attribute.")
    exporter: Literal["otlp", "console"] = _f(
        "otlp", "`console` prints spans (debugging)."
    )
    endpoint: str | None = _f(
        None,
        "OTLP/HTTP endpoint; default OTEL_EXPORTER_OTLP_ENDPOINT or localhost:4318.",
    )
    sample_ratio: float = _f(
        1.0, "Fraction of new traces to sample (0-1).", ge=0.0, le=1.0
    )
    include_user: bool = _f(False, "Add enduser.id to spans (personal data).")
    resource_attributes: dict[str, str] = _f(
        description="Extra resource attributes, e.g. deployment.environment.",
        default_factory=dict,
    )


class LimitConfig(_Model):
    requests_per_minute: int = _f(120, "Sustained rate.", ge=1)
    burst: int = _f(0, "Bucket size; 0 means the same as requests_per_minute.", ge=0)


class RateLimitConfig(_Model):
    enabled: bool = _f(False, "Enforce token-bucket rate limits.")
    default: LimitConfig = _f(
        description="Limit for every non-exempt route.", default_factory=LimitConfig
    )
    key: Literal["ip", "principal"] = _f(
        "ip", "Bucket per client IP or per signed-in user (bearer token)."
    )
    auth_failures_per_minute: int = _f(
        30, "401 responses per IP per minute before 429 (key: principal).", ge=1
    )
    trusted_proxies: list[str] = _f(
        description="CIDRs whose X-Forwarded-For is trusted (your ingress).",
        default_factory=list,
    )
    routes: dict[str, LimitConfig] = _f(
        description="Per-route limits; longest prefix wins.", default_factory=dict
    )
    tools: dict[str, LimitConfig] = _f(
        description="Per-MCP-tool limits.", default_factory=dict
    )
    exempt_paths: list[str] = _f(
        description="Never limited (health checks, discovery).",
        default_factory=lambda: [
            "/health",
            "/status",
            "/.well-known/",
            "/favicon",
            "/admin/assets/",
        ],
    )


class ToolsConfig(_Model):
    enabled: list[str] | None = _f(None, "Allow-list of tools; empty means all tools.")
    disabled: list[str] = _f(
        description="Tools removed from the server.", default_factory=list
    )


class PluginsConfig(_Model):
    enabled: list[str] = _f(
        description="Installed plugins to load (explicit allow-list).",
        default_factory=list,
    )
    settings: dict[str, dict[str, Any]] = _f(
        description="Per-plugin settings by name.", default_factory=dict
    )


class AdminConfig(_Model):
    allow_local_without_auth: bool = _f(
        False, "Serve the dashboard to loopback clients when enterprise auth is off."
    )
    allow_write: bool = _f(
        False, "Enterprise: let MCP.Admin users save settings from the dashboard."
    )
    allow_stop: bool = _f(False, "Enterprise: let MCP.Admin users stop the server.")


class ServerSettings(_Model):
    """Typed view of ``server`` (the file section stays a mapping of env-backed keys)."""

    allowed_hosts: list[str] | None = _f(None, "Host headers accepted by /mcp.")
    allowed_origins: list[str] | None = _f(
        None, "Browser origins allowed to call /mcp."
    )
    stateless_http: bool | None = _f(
        None, "Stateless Streamable HTTP (recommended behind load balancers)."
    )


class RenderingSettings(_Model):
    """Typed view of ``rendering``."""

    kroki_server: str | None = _f(None, "Kroki URL used for rendering.")
    plantuml_server: str | None = _f(None, "PlantUML server used as a fallback.")
    use_local_kroki: bool | None = _f(
        None, "Use the Kroki container from docker compose."
    )
    use_local_plantuml: bool | None = _f(None, "Use the PlantUML container.")
    url_only: bool | None = _f(None, "Return URLs only, never image bytes.")
    memory_only: bool | None = _f(None, "Never write files; keep results in memory.")
    read_only: bool | None = _f(None, "Refuse to write output files.")
    diagram_fallback: bool | None = _f(None, "Retry other renderers when Kroki fails.")
    output_dir: str | None = _f(
        None, "Where diagrams are saved when files are allowed."
    )
    max_code_length: int | None = _f(None, "Maximum diagram source length.", ge=1)
    max_render_seconds: float | None = _f(None, "Render timeout in seconds.", gt=0)
    batch_max_items: int | None = _f(None, "Maximum diagrams per batch call.", ge=1)
    batch_concurrency: int | None = _f(None, "Parallel renders per batch.", ge=1)


class AppConfig(_Model):
    """Validated non-auth sections of ``uml-mcp.yaml``."""

    server: dict[str, Any] = Field(default_factory=dict)
    rendering: dict[str, Any] = Field(default_factory=dict)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    otel: OtelConfig = Field(default_factory=OtelConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)
    auth: dict[str, Any] = Field(default_factory=dict)

    def tool_enabled(self, name: str) -> bool:
        if name in self.tools.disabled:
            return False
        return self.tools.enabled is None or name in self.tools.enabled


# ------------------------------------------------------------------ discovery
def candidate_paths(env: Mapping[str, str] | None = None) -> list[Path]:
    env = os.environ if env is None else env
    xdg = env.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return [
        Path("uml-mcp.yaml"),
        Path("uml-mcp.yml"),
        Path(xdg) / "uml-mcp" / "config.yaml",
        Path("/etc/uml-mcp/config.yaml"),
    ]


def find_config_path(
    explicit: str | None = None, env: Mapping[str, str] | None = None
) -> Path | None:
    env = os.environ if env is None else env
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise ConfigFileError(f"config file not found: {path}")
        return path
    configured = (env.get(CONFIG_ENV) or "").strip()
    if configured.lower() in ("none", "off", "false", "0"):
        return None
    if configured:
        path = Path(configured).expanduser()
        if not path.is_file():
            raise ConfigFileError(f"{CONFIG_ENV} points to a missing file: {path}")
        return path
    for path in candidate_paths(env):
        if path.is_file():
            return path
    return None


def read_config_file(path: Path) -> dict[str, Any]:
    import yaml

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigFileError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigFileError(f"{path} must contain a YAML mapping")
    unknown = sorted(set(data) - set(SECTIONS) - set(META_KEYS))
    if unknown:
        raise ConfigFileError(
            f"{path}: unknown section(s) {', '.join(unknown)}; "
            f"expected {', '.join(SECTIONS)}"
        )
    return data


class _TypedViews(BaseModel):
    server: ServerSettings
    rendering: RenderingSettings


def parse_app_config(data: Mapping[str, Any], source: str = "config") -> AppConfig:
    body = {k: v for k, v in data.items() if k not in META_KEYS and v is not None}
    try:
        # Typed views catch typos in the env-backed sections (unknown keys, bad types).
        _TypedViews.model_validate(
            {
                "server": body.get("server") or {},
                "rendering": body.get("rendering") or {},
            }
        )
        return AppConfig.model_validate(body)
    except ValidationError as exc:
        raise ConfigFileError(f"{source}: {format_errors(exc)}") from exc


def format_errors(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
    )


# ------------------------------------------------------------------- writing
def write_config_file(
    path: Path, data: dict[str, Any], *, force: bool = True
) -> Path | None:
    """Write YAML atomically (0600) and keep a timestamped backup; return the backup."""
    import datetime as _dt
    import shutil

    import yaml

    path = path.expanduser()
    backup = None
    if path.exists():
        if not force:
            raise FileExistsError(f"{path} already exists (use --force to overwrite)")
        backup = path.with_name(
            path.name + f".bak-{_dt.datetime.now(_dt.UTC):%Y%m%d%H%M%S%f}"
        )
        shutil.copy2(path, backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    header = "# uml-mcp.yaml, written by uml-mcp (setup wizard or admin console).\n"
    body = header + yaml.safe_dump(data, sort_keys=False)
    fd = os.open(
        tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
    )  # never world-readable
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(body)
    os.chmod(tmp, 0o600)  # also when tmp pre-existed with other bits
    os.replace(tmp, path)
    return backup


# ------------------------------------------------------------------- loading
class LoadedConfig:
    """Result of discovery: path, raw data, validated model, env provenance."""

    def __init__(
        self,
        path: Path | None,
        data: dict[str, Any],
        app: AppConfig,
        applied_env: dict[str, str],
    ):
        self.path = path
        self.data = data
        self.app = app
        self.applied_env = applied_env  # env vars filled from the file

    def source_of(self, env_name: str, environ: Mapping[str, str]) -> str:
        if env_name in self.applied_env:
            return f"file:{self.path}"
        return "env" if env_name in environ else "default"


def _env_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return json.dumps(list(value))
    return str(value)


def apply_to_environ(
    data: Mapping[str, Any], environ: MutableMapping[str, str]
) -> dict[str, str]:
    """Fill env vars from the file without overriding existing ones."""
    applied: dict[str, str] = {}
    for (section, key), env_name in ENV_MAP.items():
        sect = data.get(section) or {}
        if key in sect and sect[key] is not None and env_name not in environ:
            value = _env_value(sect[key])
            if key.endswith("_dir"):
                value = str(Path(value).expanduser())
            environ[env_name] = applied[env_name] = value
    return applied


def load_config(
    explicit: str | None = None,
    environ: MutableMapping[str, str] | None = None,
    *,
    apply_env: bool = True,
) -> LoadedConfig:
    env = os.environ if environ is None else environ
    path = find_config_path(explicit, env)
    data = read_config_file(path) if path else {}
    app = parse_app_config(data, str(path) if path else "defaults")
    applied = apply_to_environ(data, env) if apply_env else {}
    return LoadedConfig(path, data, app, applied)


@lru_cache(maxsize=1)
def get_config() -> LoadedConfig:
    """Process-wide config (discovered once; env vars filled on first call)."""
    return load_config()


def reset_config_cache() -> None:
    get_config.cache_clear()


def get_app_config() -> AppConfig:
    try:
        return get_config().app
    except ConfigFileError:
        raise
    except Exception:  # noqa: BLE001 - never block startup on optional sections
        return AppConfig()


__all__ = [
    "CONFIG_ENV",
    "ENV_MAP",
    "META_KEYS",
    "AppConfig",
    "AuditConfig",
    "ConfigFileError",
    "LoadedConfig",
    "LoggingConfig",
    "MetricsConfig",
    "OtelConfig",
    "PluginsConfig",
    "RateLimitConfig",
    "RenderingSettings",
    "RotationConfig",
    "ServerSettings",
    "apply_to_environ",
    "candidate_paths",
    "find_config_path",
    "get_app_config",
    "get_config",
    "load_config",
    "parse_app_config",
    "read_config_file",
    "reset_config_cache",
    "write_config_file",
]
