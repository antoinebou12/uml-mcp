"""Read, validate, save and reset ``uml-mcp.yaml`` for the admin console.

Saving is atomic (``0600``, timestamped backup). Settings that the running
process can pick up are re-applied immediately (audit, logging, OTel, rate
limits, admin flags); the rest are reported as ``restart_required``.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

from ..core import features
from ..core.settings_file import (
    CONFIG_ENV,
    ENV_MAP,
    META_KEYS,
    AdminConfig,
    AuditConfig,
    ConfigFileError,
    LoggingConfig,
    MetricsConfig,
    OtelConfig,
    PluginsConfig,
    RateLimitConfig,
    RenderingSettings,
    ServerSettings,
    ToolsConfig,
    get_config,
    parse_app_config,
    reset_config_cache,
    write_config_file,
)

#: Editable sections, in UI order: (key, model, title, description, apply, icon).
SECTIONS: tuple[tuple[str, Any, str, str, str, str], ...] = (
    (
        "rendering",
        RenderingSettings,
        "Rendering",
        "Kroki/PlantUML servers, output handling, limits and fallbacks.",
        "restart",
        "image",
    ),
    (
        "server",
        ServerSettings,
        "Server",
        "Allowed hosts and origins for the HTTP transport.",
        "restart",
        "server",
    ),
    (
        "tools",
        ToolsConfig,
        "Tools",
        "Which MCP tools are exposed (least privilege).",
        "restart",
        "wrench",
    ),
    (
        "rate_limit",
        RateLimitConfig,
        "Rate limits",
        "Token buckets per client or user, route and tool.",
        "live",
        "gauge",
    ),
    (
        "audit",
        AuditConfig,
        "Audit trail",
        "MXCP-style record of every call, with redaction and sinks.",
        "live",
        "list-checks",
    ),
    (
        "logging",
        LoggingConfig,
        "Logging",
        "Level, format and rotating log file.",
        "live",
        "scroll-text",
    ),
    (
        "metrics",
        MetricsConfig,
        "Metrics",
        "In-process counters and the Prometheus endpoint.",
        "live",
        "chart-line",
    ),
    (
        "otel",
        OtelConfig,
        "OpenTelemetry",
        "Traces to an OTLP collector.",
        "live",
        "activity",
    ),
    (
        "plugins",
        PluginsConfig,
        "Plugins",
        "Extra renderers and tools from installed packages.",
        "restart",
        "puzzle",
    ),
    (
        "admin",
        AdminConfig,
        "Admin console",
        "Who may use and change this console.",
        "live",
        "shield",
    ),
)
#: Fields whose change needs a restart even though their section is live.
RESTART_FIELDS = {"metrics.endpoint", "admin.allow_local_without_auth"}
LIVE_SECTIONS = {key for key, *_, apply, _icon in SECTIONS if apply == "live"}


class ReadOnlyConfigError(RuntimeError):
    """The configuration file cannot be written (e.g. a Kubernetes ConfigMap)."""


def target_path() -> Path:
    """File the console writes: the discovered file, else the per-user default."""
    loaded = get_config()
    if loaded.path is not None:
        return Path(loaded.path)
    from ..core.commands import _default_user_path

    return _default_user_path()


def writable(path: Path) -> bool:
    if path.exists():
        return os.access(path, os.W_OK) and os.access(path.parent, os.W_OK)
    parent = path.parent
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    return os.access(parent, os.W_OK)


def schema() -> dict[str, Any]:
    return {
        "sections": [
            {
                "key": key,
                "title": title,
                "description": description,
                "apply": apply,
                "icon": icon,
                "schema": model.model_json_schema(),
            }
            for key, model, title, description, apply, icon in SECTIONS
        ],
        "restart_fields": sorted(RESTART_FIELDS),
        "features": [f.as_dict() for f in features.FEATURES],
        "profiles": list(features.PROFILES),
    }


def env_locked() -> dict[str, str]:
    """YAML keys overridden by environment variables the operator set (read-only)."""
    loaded = get_config()
    return {
        f"{section}.{key}": env_name
        for (section, key), env_name in ENV_MAP.items()
        if loaded.source_of(env_name, os.environ) == "env"
    }


def _effective_env_sections() -> dict[str, dict[str, Any]]:
    """Effective values of the env-backed ``server``/``rendering`` sections."""
    from ..core.config import MCP_SETTINGS

    def env_bool(name: str) -> bool | None:
        raw = os.environ.get(name)
        return (
            None if raw is None else raw.strip().lower() in ("1", "true", "yes", "on")
        )

    def env_list(name: str) -> list[str] | None:
        from ..core.env import parse_env_list

        return parse_env_list(os.environ.get(name)) or None

    batch_conc = os.environ.get("MCP_BATCH_CONCURRENCY")
    return {
        "rendering": {
            "kroki_server": MCP_SETTINGS.kroki_server,
            "plantuml_server": MCP_SETTINGS.plantuml_server,
            "use_local_kroki": bool(env_bool("USE_LOCAL_KROKI")),
            "use_local_plantuml": bool(env_bool("USE_LOCAL_PLANTUML")),
            "url_only": MCP_SETTINGS.url_only,
            "memory_only": MCP_SETTINGS.memory_only,
            "read_only": MCP_SETTINGS.read_only,
            "diagram_fallback": MCP_SETTINGS.diagram_fallback_enabled,
            "output_dir": MCP_SETTINGS.output_dir,
            "max_code_length": MCP_SETTINGS.max_code_length,
            "max_render_seconds": MCP_SETTINGS.max_render_seconds,
            "batch_max_items": MCP_SETTINGS.batch_max_items,
            "batch_concurrency": int(batch_conc)
            if batch_conc and batch_conc.isdigit()
            else 4,
        },
        "server": {
            "allowed_hosts": env_list("MCP_ALLOWED_HOSTS"),
            "allowed_origins": env_list("MCP_ALLOWED_ORIGINS"),
            "stateless_http": env_bool("FASTMCP_STATELESS_HTTP"),
        },
    }


def current() -> dict[str, Any]:
    loaded = get_config()
    path = target_path()
    data = copy.deepcopy(loaded.data)
    return {
        "path": str(path),
        "exists": path.exists(),
        "writable": writable(path),
        "data": {k: v for k, v in data.items() if k != "auth"},
        "has_auth_section": "auth" in data,
        "effective": {
            **loaded.app.model_dump(mode="json", exclude={"auth"}),
            **_effective_env_sections(),
        },
        "env_locked": env_locked(),
        "setup": data.get("setup"),
        "setup_complete": bool((data.get("setup") or {}).get("completed_at")),
        "features": sorted(features.enabled_features(data)),
    }


def _flatten(data: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for key, value in data.items():
            out.update(_flatten(value, f"{prefix}.{key}" if prefix else str(key)))
        return out
    return {prefix: data}


def changed_keys(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    a, b = _flatten(old), _flatten(new)
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def validate(data: dict[str, Any]) -> None:
    """Raise ConfigFileError (bad sections) or AuthConfigError (auth/secrets)."""
    parse_app_config(data, "settings")
    auth = data.get("auth") or {}
    if auth:
        from ..auth.settings import load_auth_settings

        env = dict(os.environ)
        env.setdefault("MCP_AUTH_MODE", str(auth.get("mode", "none")))
        if env["MCP_AUTH_MODE"] != "none":
            load_auth_settings(env, file_data=auth)
        else:
            from ..auth.settings import _check_file_data

            _check_file_data(dict(auth), "auth section")


def apply_live(app_config: Any) -> list[str]:
    """Re-apply what the running process can change without a restart."""
    from ..observability.audit import configure_audit, get_audit_logger

    applied = ["rate_limit", "admin"]  # read per request
    stdio = getattr(get_audit_logger(), "stdio", False)
    configure_audit(app_config, stdio=stdio)  # also reconfigures OTel
    applied += ["audit", "otel", "metrics"]
    if get_config().data.get("logging") is not None:
        import logging
        import sys

        from ..observability.logging_setup import configure_logging

        configure_logging(
            app_config.logging, console_handler=logging.StreamHandler(sys.stderr)
        )
        applied.append("logging")
    return applied


def save(new_sections: dict[str, Any], *, actor: str | None = None) -> dict[str, Any]:
    """Merge UI sections into the file (auth and meta keys are preserved)."""
    loaded = get_config()
    old = copy.deepcopy(loaded.data)
    data: dict[str, Any] = {
        k: v for k, v in old.items() if k in META_KEYS or k == "auth"
    }
    data.setdefault("version", 1)
    for key, value in new_sections.items():
        if key in META_KEYS or key == "auth":
            if key == "setup" and isinstance(value, dict):
                data["setup"] = value
            continue
        if value not in (None, {}, []):
            data[key] = value
    validate(data)
    path = target_path()
    if not writable(path):
        raise ReadOnlyConfigError(
            f"{path} is not writable (mounted read-only?); download the YAML and apply "
            "it through your deployment (GitOps / ConfigMap)"
        )
    backup = write_config_file(path, data, force=True)
    if os.environ.get(CONFIG_ENV, "").strip().lower() in (
        "",
        "none",
        "off",
        "false",
        "0",
    ):
        os.environ[CONFIG_ENV] = str(path)  # make sure the reload finds what we wrote
    changes = changed_keys(
        {k: v for k, v in old.items() if k not in META_KEYS},
        {k: v for k, v in data.items() if k not in META_KEYS},
    )
    reset_config_cache()
    app_config = get_config().app
    applied = apply_live(app_config)
    restart = sorted(
        k
        for k in changes
        if k.split(".")[0] not in LIVE_SECTIONS
        or ".".join(k.split(".")[:2]) in RESTART_FIELDS
    )
    from ..observability.audit import record_operation

    record_operation(
        operation_type="admin",
        operation_name="settings.save",
        input_data={"changed": changes, "path": str(path)},
        operation_status="success",
        policy_decision="allow",
        policy_reason=f"admin console{f' ({actor})' if actor else ''}",
    )
    return {
        "saved": str(path),
        "backup": str(backup) if backup else None,
        "changed": changes,
        "applied_live": applied,
        "restart_required": restart,
    }


def reset(
    section: str | None = None, profile: str | None = None, *, actor: str | None = None
) -> dict[str, Any]:
    """Reset one section, or everything, to the profile's defaults."""
    loaded = get_config()
    profile = profile or (loaded.data.get("setup") or {}).get("profile") or "local"
    base = features.build_config(profile)
    if section is None:
        sections = {k: v for k, v in base.items() if k not in META_KEYS and k != "auth"}
        sections["setup"] = {**(loaded.data.get("setup") or {}), "profile": profile}
        # sections absent from the profile are dropped (defaults apply)
        current_data = {
            k: None for k in loaded.data if k not in META_KEYS and k != "auth"
        }
        current_data.update(sections)
        return save(
            {k: v for k, v in current_data.items() if v is not None}, actor=actor
        )
    if section not in {key for key, *_ in SECTIONS}:
        raise ConfigFileError(f"unknown section {section!r}")
    data = {k: v for k, v in loaded.data.items() if k not in META_KEYS and k != "auth"}
    if section in base:
        data[section] = base[section]
    else:
        data.pop(section, None)
    return save(data, actor=actor)


def set_plugin_enabled(
    name: str, enabled: bool, *, actor: str | None = None
) -> dict[str, Any]:
    """Add/remove a plugin in ``plugins.enabled`` (takes effect after a restart)."""
    loaded = get_config()
    data = {k: v for k, v in copy.deepcopy(loaded.data).items() if k not in META_KEYS}
    data.pop("auth", None)
    plugins = dict(data.get("plugins") or {})
    names = [n for n in plugins.get("enabled") or [] if n != name]
    if enabled:
        names.append(name)
    plugins["enabled"] = names
    data["plugins"] = plugins
    return save(data, actor=actor)


__all__ = [
    "SECTIONS",
    "ReadOnlyConfigError",
    "changed_keys",
    "current",
    "reset",
    "save",
    "schema",
    "set_plugin_enabled",
    "target_path",
    "validate",
]
