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
    "admin",
    "auth",
)


class ConfigFileError(ValueError):
    """Invalid or unreadable configuration file."""


# --------------------------------------------------------------------- models
class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RotationConfig(_Model):
    path: str
    max_bytes: int = Field(default=10 * 1024 * 1024, ge=0)  # 0 => time based
    backup_count: int = Field(default=10, ge=0)
    when: Literal["S", "M", "H", "D", "midnight"] = "midnight"
    interval: int = Field(default=1, ge=1)
    compress: bool = False


class LoggingConfig(_Model):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: Literal["text", "json"] = "text"
    loggers: dict[str, str] = Field(default_factory=dict)
    file: RotationConfig | None = None


AuditSink = Literal["file", "stream", "memory"]


def _default_sinks() -> list[AuditSink]:
    return ["memory"]


class AuditConfig(_Model):
    enabled: bool = False
    sinks: list[AuditSink] = Field(default_factory=_default_sinks)
    file: RotationConfig | None = None
    include_inputs: Literal["none", "redacted", "full"] = "redacted"
    max_input_chars: int = Field(default=2000, ge=0)
    memory_size: int = Field(default=500, ge=10, le=100_000)
    include_http: bool = True


class MetricsConfig(_Model):
    enabled: bool = True
    endpoint: bool = False  # expose /metrics (Prometheus text)


class OtelConfig(_Model):
    """OpenTelemetry traces (``pip install "uml-mcp[otel]"``)."""

    enabled: bool = False
    service_name: str = "uml-mcp"
    exporter: Literal["otlp", "console"] = "otlp"
    endpoint: str | None = (
        None  # default: OTEL_EXPORTER_OTLP_ENDPOINT or localhost:4318
    )
    sample_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    include_user: bool = False  # add enduser.id (PII) to spans
    resource_attributes: dict[str, str] = Field(default_factory=dict)


class LimitConfig(_Model):
    requests_per_minute: int = Field(default=120, ge=1)
    burst: int = Field(default=0, ge=0)  # 0 => same as requests_per_minute


class RateLimitConfig(_Model):
    enabled: bool = False
    default: LimitConfig = Field(default_factory=LimitConfig)
    key: Literal["ip", "principal"] = (
        "ip"  # principal: per bearer token / signed-in user
    )
    # 401s allowed per IP per minute when key=principal (stops bogus-token key spraying)
    auth_failures_per_minute: int = Field(default=30, ge=1)
    trusted_proxies: list[str] = Field(default_factory=list)
    routes: dict[str, LimitConfig] = Field(default_factory=dict)
    tools: dict[str, LimitConfig] = Field(default_factory=dict)
    exempt_paths: list[str] = Field(
        default_factory=lambda: ["/health", "/status", "/.well-known/", "/favicon"]
    )


class ToolsConfig(_Model):
    enabled: list[str] | None = None  # None => all tools
    disabled: list[str] = Field(default_factory=list)


class AdminConfig(_Model):
    allow_local_without_auth: bool = False


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
    unknown = sorted(set(data) - set(SECTIONS) - {"version"})
    if unknown:
        raise ConfigFileError(
            f"{path}: unknown section(s) {', '.join(unknown)}; "
            f"expected {', '.join(SECTIONS)}"
        )
    return data


def parse_app_config(data: Mapping[str, Any], source: str = "config") -> AppConfig:
    body = {k: v for k, v in data.items() if k != "version" and v is not None}
    try:
        return AppConfig.model_validate(body)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        raise ConfigFileError(f"{source}: {details}") from exc


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
    "AppConfig",
    "AuditConfig",
    "ConfigFileError",
    "LoadedConfig",
    "LoggingConfig",
    "MetricsConfig",
    "OtelConfig",
    "RateLimitConfig",
    "RotationConfig",
    "apply_to_environ",
    "candidate_paths",
    "find_config_path",
    "get_app_config",
    "get_config",
    "load_config",
    "parse_app_config",
    "read_config_file",
    "reset_config_cache",
]
