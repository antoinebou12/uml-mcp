"""Feature catalog shared by the ``uml-mcp setup`` wizard and the web Setup page.

Each feature is a named, documented switch that maps onto ``uml-mcp.yaml``
sections. Profiles pick sensible defaults; users flip features on or off.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from typing import Any

PROFILES = ("local", "docker", "enterprise")


@dataclass(frozen=True)
class Feature:
    key: str
    title: str
    description: str
    category: str  # rendering | observability | security | admin
    apply: str  # live | restart
    enabled: dict[str, Any]  # YAML patch when on
    disabled: dict[str, Any] = field(default_factory=dict)  # YAML patch when off
    defaults: tuple[str, ...] = ()  # profiles where it is on by default

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["defaults"] = list(self.defaults)
        return data


FEATURES: tuple[Feature, ...] = (
    Feature(
        "memory_only",
        "In-memory rendering",
        "Keep rendered diagrams in memory and return URLs/bytes instead of writing files. "
        "Best for servers and containers.",
        "rendering",
        "restart",
        {"rendering": {"memory_only": True}},
        {"rendering": {"memory_only": False}},
        ("docker", "enterprise"),
    ),
    Feature(
        "diagram_fallback",
        "Renderer fallback",
        "When Kroki fails, retry with the PlantUML server or mermaid.ink so users still get "
        "a diagram.",
        "rendering",
        "restart",
        {"rendering": {"diagram_fallback": True}},
        {"rendering": {"diagram_fallback": False}},
        ("local", "docker", "enterprise"),
    ),
    Feature(
        "audit",
        "Audit trail",
        "Record every tool, resource and prompt call (who, what, decision, duration) with "
        "secrets and diagram code redacted. Feeds the Activity page.",
        "observability",
        "live",
        {"audit": {"enabled": True}},  # sinks come from the profile template
        {"audit": {"enabled": False}},
        ("docker", "enterprise"),
    ),
    Feature(
        "json_logs",
        "Structured JSON logs",
        "One JSON object per log line for log collectors (Azure Monitor, Splunk, Elastic).",
        "observability",
        "live",
        {"logging": {"format": "json"}},
        {"logging": {"format": "text"}},
        ("docker", "enterprise"),
    ),
    Feature(
        "metrics_endpoint",
        "Prometheus /metrics",
        "Expose call counts, errors and latency in Prometheus format for scraping.",
        "observability",
        "restart",
        {"metrics": {"enabled": True, "endpoint": True}},
        {"metrics": {"endpoint": False}},
        ("enterprise",),
    ),
    Feature(
        "otel",
        "OpenTelemetry traces",
        "Send one span per request and per MCP call to an OTLP collector. Requires "
        'pip install "uml-mcp[otel]".',
        "observability",
        "live",
        {"otel": {"enabled": True}},
        {"otel": {"enabled": False}},
    ),
    Feature(
        "rate_limit",
        "Rate limiting",
        "Token-bucket limits per client IP or signed-in user, with per-route and per-tool "
        "limits. Protects renderers from bursts.",
        "security",
        "live",
        {
            "rate_limit": {
                "enabled": True,
                "default": {"requests_per_minute": 120, "burst": 30},
            }
        },
        {"rate_limit": {"enabled": False}},
        ("docker", "enterprise"),
    ),
    Feature(
        "local_dashboard",
        "Local dashboard",
        "Serve this admin console at http://127.0.0.1/admin without SSO (loopback only, "
        "setup-token protected for changes).",
        "admin",
        "restart",
        {"admin": {"allow_local_without_auth": True}},
        {"admin": {"allow_local_without_auth": False}},
        ("local",),
    ),
)

FEATURE_KEYS = tuple(f.key for f in FEATURES)


def get_feature(key: str) -> Feature:
    for feature in FEATURES:
        if feature.key == key:
            return feature
    raise KeyError(f"unknown feature {key!r}; choose from {', '.join(FEATURE_KEYS)}")


def default_features(profile: str) -> set[str]:
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}")
    return {f.key for f in FEATURES if profile in f.defaults}


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def build_config(
    profile: str,
    enabled: set[str] | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a ``uml-mcp.yaml`` mapping for a profile + chosen features."""
    import yaml

    from .commands import _template

    defaults = default_features(profile)  # validates the profile first
    base = yaml.safe_load(_template(profile)) or {}
    chosen = defaults if enabled is None else set(enabled)
    unknown = chosen - set(FEATURE_KEYS)
    if unknown:
        raise KeyError(f"unknown feature(s): {', '.join(sorted(unknown))}")
    for feature in FEATURES:
        base = deep_merge(
            base, feature.enabled if feature.key in chosen else feature.disabled
        )
    if overrides:
        base = deep_merge(base, overrides)
    base["version"] = 1
    return base


def enabled_features(data: dict[str, Any]) -> set[str]:
    """Which catalog features a config mapping has switched on."""

    def matches(patch: dict[str, Any], current: dict[str, Any]) -> bool:
        for key, value in patch.items():
            if isinstance(value, dict):
                if not isinstance(current.get(key), dict) or not matches(
                    value, current[key]
                ):
                    return False
            elif current.get(key) != value:
                return False
        return True

    return {f.key for f in FEATURES if matches(_flags_only(f.enabled), data)}


def _flags_only(patch: dict[str, Any]) -> dict[str, Any]:
    """Compare only booleans/strings that identify the feature (not tunables like limits)."""
    out: dict[str, Any] = {}
    for key, value in patch.items():
        if isinstance(value, dict):
            inner = _flags_only(value)
            if inner:
                out[key] = inner
        elif isinstance(value, (bool, str)):
            out[key] = value
    return out


__all__ = [
    "FEATURES",
    "FEATURE_KEYS",
    "PROFILES",
    "Feature",
    "build_config",
    "deep_merge",
    "default_features",
    "enabled_features",
    "get_feature",
]
