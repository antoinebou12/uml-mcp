"""Enterprise auth settings: env vars + JSON config file (``MCP_AUTH_CONFIG_FILE``).

Precedence is **defaults < JSON file < environment**. Secrets (client secret,
private key, proxy encryption keys) are accepted from env vars or ``*_FILE``
paths only; putting a secret value directly in the JSON file is rejected so a
ConfigMap never carries credentials.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from functools import lru_cache
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    model_validator,
)

from ..core.env import parse_env_bool, parse_env_list
from . import AuthConfigError, auth_mode_from_env
from .entra import (
    ENTRA_CLOUDS,
    entra_authority_host,
    entra_jwks_uri,
    entra_v1_issuer_template,
    entra_v2_issuer,
    is_guid,
)

Permission = Literal["read", "write", "admin"]

ASYMMETRIC_ALGORITHMS: frozenset[str] = frozenset(
    {
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ES256",
        "ES384",
        "ES512",
        "EdDSA",
    }
)
_MULTI_TENANT_ALIASES = frozenset({"common", "organizations", "consumers"})
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class EntraSettings(BaseModel):
    """Microsoft Entra ID preset (derives issuer, JWKS, audiences, scope prefix)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str
    client_id: str
    app_id_uri: str | None = None
    cloud: Literal["public", "usgov", "china"] = "public"
    token_versions: list[str] = Field(default_factory=lambda: ["2"])
    jwks_appid: bool = False  # append ?appid= for apps with custom signing keys

    @property
    def effective_app_id_uri(self) -> str:
        return (self.app_id_uri or f"api://{self.client_id}").rstrip("/")


class ProxySettings(BaseModel):
    """``entra-proxy`` authorization-server facade settings (secrets redacted)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    client_secret: SecretStr | None = None
    client_certificate_pem: str | None = None
    client_private_key_pem: SecretStr | None = None
    federated_token_file: str | None = None
    encryption_keys: SecretStr | None = None
    allowed_redirect_uris: list[str] = Field(default_factory=list)
    refresh_tokens: bool = True
    refresh_token_max_age_days: int = Field(default=7, ge=1, le=90)
    code_ttl_seconds: int = Field(default=60, ge=10, le=600)
    transaction_ttl_seconds: int = Field(default=600, ge=60, le=3600)

    @property
    def credential_kind(self) -> str | None:
        if self.client_certificate_pem and self.client_private_key_pem:
            return "certificate"
        if self.client_secret is not None:
            return "secret"
        if self.federated_token_file:
            return "workload_identity"
        return None


class AuthSettings(BaseModel):
    """Validated enterprise auth configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["none", "jwt", "entra-proxy"] = "none"
    resource_url: str = ""
    protect_rest: bool = True
    preflight: Literal["warn", "strict", "off"] = "warn"

    algorithms: list[str] = Field(default_factory=lambda: ["RS256"])
    issuers: list[str] = Field(default_factory=list)
    audiences: list[str] = Field(default_factory=list)
    jwks_uri: str | None = None
    public_key_pem: str | None = None
    authorization_servers: list[str] = Field(default_factory=list)
    leeway_seconds: int = Field(default=60, ge=0, le=300)
    jwks_cache_seconds: int = Field(default=3600, ge=60, le=86400)
    token_type: str | None = None
    allowed_client_ids: list[str] = Field(default_factory=list)
    allowed_tenants: list[str] = Field(default_factory=list)

    scope_prefix: str | None = None
    read_scope: str = "mcp.read"
    write_scope: str = "mcp.write"
    scope_strategy: Literal["granular", "default"] = "granular"
    advertise_offline_access: bool = False
    roles_claim: str = "roles"
    reader_roles: list[str] = Field(
        default_factory=lambda: ["MCP.Reader", "MCP.Read.All"]
    )
    writer_roles: list[str] = Field(
        default_factory=lambda: ["MCP.Writer", "MCP.Write.All"]
    )
    admin_roles: list[str] = Field(default_factory=lambda: ["MCP.Admin"])
    require_user_roles: bool = False
    tool_permissions: dict[str, Literal["read", "write"]] = Field(default_factory=dict)
    method_permissions: dict[str, Literal["read", "write"]] = Field(
        default_factory=dict
    )
    max_body_bytes: int = Field(default=0, ge=0)  # 0 = derive from MCP_MAX_CODE_LENGTH

    resource_name: str = "UML-MCP"
    resource_documentation: str | None = None

    entra: EntraSettings | None = None
    proxy: ProxySettings = Field(default_factory=ProxySettings)
    admin_ui: bool = False

    # ------------------------------------------------------------------ derived
    @property
    def enabled(self) -> bool:
        return self.mode != "none"

    @property
    def origin(self) -> str:
        parts = urlsplit(self.resource_url)
        return f"{parts.scheme}://{parts.netloc}"

    @property
    def root_resource(self) -> str:
        return f"{self.origin}/"

    @property
    def prm_url_mcp(self) -> str:
        path = urlsplit(self.resource_url).path.rstrip("/")
        return f"{self.origin}/.well-known/oauth-protected-resource{path}"

    @property
    def prm_url_root(self) -> str:
        return f"{self.origin}/.well-known/oauth-protected-resource"

    @property
    def effective_scope_prefix(self) -> str:
        if self.scope_prefix is not None:
            return self.scope_prefix
        if self.entra is not None and self.mode == "jwt":
            return f"{self.entra.effective_app_id_uri}/"
        return ""

    @property
    def upstream_scope_prefix(self) -> str:
        """Prefix used when talking to Entra (always qualified)."""
        if self.entra is not None:
            return f"{self.entra.effective_app_id_uri}/"
        return self.effective_scope_prefix

    @property
    def effective_issuers(self) -> list[str]:
        issuers = list(self.issuers)
        if self.entra is not None:
            host = entra_authority_host(self.entra.cloud)
            tenants = self._entra_tenants()
            for tid in tenants:
                if "2" in self.entra.token_versions:
                    issuers.append(entra_v2_issuer(host, tid))
                if "1" in self.entra.token_versions:
                    issuers.append(
                        entra_v1_issuer_template(self.entra.cloud).format(tid=tid)
                    )
        return _dedupe(issuers)

    @property
    def effective_audiences(self) -> list[str]:
        audiences = list(self.audiences)
        if self.entra is not None:
            audiences += [self.entra.client_id, self.entra.effective_app_id_uri]
        audiences.append(self.resource_url)
        return _dedupe(audiences)

    @property
    def effective_jwks_uri(self) -> str | None:
        if self.jwks_uri:
            return self.jwks_uri
        if self.entra is not None:
            uri = entra_jwks_uri(
                entra_authority_host(self.entra.cloud), self.entra.tenant_id
            )
            if self.entra.jwks_appid:
                uri = f"{uri}?appid={self.entra.client_id}"
            return uri
        return None

    @property
    def effective_authorization_servers(self) -> list[str]:
        if self.mode == "entra-proxy":
            return [self.origin]
        if self.authorization_servers:
            return list(self.authorization_servers)
        if self.entra is not None:
            return [
                entra_v2_issuer(
                    entra_authority_host(self.entra.cloud), self.entra.tenant_id
                )
            ]
        return list(self.issuers[:1])

    @property
    def effective_allowed_tenants(self) -> list[str]:
        return self._entra_tenants() if self.entra is not None else []

    @property
    def body_limit(self) -> int:
        if self.max_body_bytes:
            return self.max_body_bytes
        code_len = int(os.environ.get("MCP_MAX_CODE_LENGTH", "500000") or 500000)
        return max(1 << 20, 3 * code_len)

    def _entra_tenants(self) -> list[str]:
        assert self.entra is not None
        if self.allowed_tenants:
            return list(self.allowed_tenants)
        return [self.entra.tenant_id]

    # --------------------------------------------------------------- validation
    @model_validator(mode="after")
    def _validate(self) -> AuthSettings:
        if self.mode == "none":
            return self
        errors: list[str] = []
        errors += _validate_url(self.resource_url, "resource_url")
        if self.resource_url and urlsplit(self.resource_url).fragment:
            errors.append("resource_url must not contain a fragment")
        bad = [a for a in self.algorithms if a not in ASYMMETRIC_ALGORITHMS]
        if bad or not self.algorithms:
            errors.append(
                "algorithms must be a non-empty subset of "
                f"{sorted(ASYMMETRIC_ALGORITHMS)} (got {self.algorithms}); "
                "'none' and HMAC (HS*) are never accepted"
            )
        if self.entra is not None:
            if not is_guid(self.entra.client_id):
                errors.append("entra.client_id must be a GUID")
            tid = self.entra.tenant_id.lower()
            if tid in _MULTI_TENANT_ALIASES:
                if not self.allowed_tenants:
                    errors.append(
                        f"entra.tenant_id '{tid}' needs an explicit allowed_tenants "
                        "list (multi-tenant apps must pin trusted tenants)"
                    )
            elif not is_guid(tid):
                errors.append("entra.tenant_id must be a GUID")
            for t in self.allowed_tenants:
                if not is_guid(t):
                    errors.append(f"allowed_tenants entry {t!r} is not a GUID")
            if not self.entra.token_versions or not set(self.entra.token_versions) <= {
                "1",
                "2",
            }:
                errors.append("entra.token_versions must be a subset of ['1', '2']")
            if self.entra.cloud not in ENTRA_CLOUDS:
                errors.append(f"unknown entra.cloud {self.entra.cloud!r}")
        if not self.effective_issuers:
            errors.append("no issuer configured (set MCP_AUTH_ISSUERS or Entra)")
        if not self.effective_jwks_uri and not self.public_key_pem:
            errors.append(
                "no key source (set MCP_AUTH_JWKS_URI, MCP_AUTH_PUBLIC_KEY[_FILE] "
                "or the Entra preset)"
            )
        if self.effective_jwks_uri:
            errors += _validate_url(self.effective_jwks_uri, "jwks_uri")
        for server in self.effective_authorization_servers:
            errors += _validate_url(server, "authorization_servers")
        if self.mode == "entra-proxy":
            if self.entra is None:
                errors.append("entra-proxy mode requires the Entra settings")
            if self.proxy.credential_kind is None:
                errors.append(
                    "entra-proxy mode requires a client credential "
                    "(secret, certificate + private key, or federated token file)"
                )
            if self.proxy.encryption_keys is None:
                errors.append(
                    "entra-proxy mode requires MCP_AUTH_PROXY_ENCRYPTION_KEYS"
                )
            else:
                from .sealing import parse_keys

                try:
                    parse_keys(self.proxy.encryption_keys.get_secret_value())
                except ValueError as exc:
                    errors.append(str(exc))
        if self.scope_strategy == "default" and not self.upstream_scope_prefix:
            errors.append("scope_strategy=default needs a scope prefix / Entra preset")
        if errors:
            raise ValueError("; ".join(errors))
        return self

    # ---------------------------------------------------------------- reporting
    def redacted_dict(self) -> dict[str, Any]:
        """Settings as JSON-safe dict with every secret replaced by a marker."""
        data = self.model_dump(mode="json")
        proxy = data.get("proxy") or {}
        for key in ("client_secret", "client_private_key_pem", "encryption_keys"):
            if proxy.get(key) is not None:
                proxy[key] = "***set***"
        if data.get("public_key_pem"):
            data["public_key_pem"] = "(PEM configured)"
        if proxy.get("client_certificate_pem"):
            proxy["client_certificate_pem"] = "(PEM configured)"
        data["derived"] = {
            "issuers": self.effective_issuers,
            "audiences": self.effective_audiences,
            "jwks_uri": self.effective_jwks_uri,
            "authorization_servers": self.effective_authorization_servers,
            "scope_prefix": self.effective_scope_prefix,
            "prm_url_mcp": self.prm_url_mcp,
            "prm_url_root": self.prm_url_root,
            "credential_kind": self.proxy.credential_kind,
        }
        return data


def _dedupe(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    return seen


def _validate_url(url: str, name: str) -> list[str]:
    if not url:
        return [f"{name} is required when auth is enabled"]
    parts = urlsplit(url)
    if parts.scheme == "https" and parts.netloc:
        return []
    if parts.scheme == "http" and (parts.hostname or "") in _LOOPBACK_HOSTS:
        return []  # loopback http is allowed for local development only
    return [f"{name} must be an https URL (http only for loopback): {url!r}"]


# ---------------------------------------------------------------------- loading

_SECRET_JSON_KEYS = frozenset(
    {"client_secret", "client_private_key_pem", "encryption_keys", "public_key_pem"}
)


def _read_file(path: str, what: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError as exc:
        raise AuthConfigError(f"cannot read {what} file {path!r}: {exc}") from exc


def _load_json(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthConfigError(f"invalid MCP_AUTH_CONFIG_FILE {path!r}: {exc}") from exc
    return _check_file_data(data, "MCP_AUTH_CONFIG_FILE")


def _check_file_data(data: Any, where: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise AuthConfigError(f"{where} must contain an object/mapping")
    proxy = data.get("proxy") if isinstance(data.get("proxy"), dict) else {}
    leaked = sorted(k for k in _SECRET_JSON_KEYS if k in data or k in (proxy or {}))
    if leaked:
        raise AuthConfigError(
            "secrets must not be stored in the JSON config file "
            f"({', '.join(leaked)}); use the matching *_file key or env var"
        )
    return data


def _resolve_file_keys(data: dict[str, Any]) -> dict[str, Any]:
    """Turn ``*_file`` keys from the JSON file into their values."""
    data = dict(data)
    if "public_key_file" in data:
        data["public_key_pem"] = _read_file(data.pop("public_key_file"), "public key")
    proxy = dict(data.get("proxy") or {})
    mapping = {
        "client_secret_file": "client_secret",
        "client_certificate_file": "client_certificate_pem",
        "client_private_key_file": "client_private_key_pem",
        "encryption_keys_file": "encryption_keys",
    }
    for file_key, value_key in mapping.items():
        if file_key in proxy:
            proxy[value_key] = _read_file(proxy.pop(file_key), value_key)
    if proxy or "proxy" in data:
        data["proxy"] = proxy
    return data


_ENV_SCALARS: dict[str, str] = {
    "MCP_AUTH_RESOURCE_URL": "resource_url",
    "MCP_AUTH_PREFLIGHT": "preflight",
    "MCP_AUTH_JWKS_URI": "jwks_uri",
    "MCP_AUTH_TOKEN_TYPE": "token_type",
    "MCP_AUTH_SCOPE_PREFIX": "scope_prefix",
    "MCP_AUTH_READ_SCOPE": "read_scope",
    "MCP_AUTH_WRITE_SCOPE": "write_scope",
    "MCP_AUTH_SCOPE_STRATEGY": "scope_strategy",
    "MCP_AUTH_ROLES_CLAIM": "roles_claim",
    "MCP_AUTH_RESOURCE_NAME": "resource_name",
    "MCP_AUTH_RESOURCE_DOCUMENTATION": "resource_documentation",
}
_ENV_INTS: dict[str, str] = {
    "MCP_AUTH_LEEWAY_SECONDS": "leeway_seconds",
    "MCP_AUTH_JWKS_CACHE_SECONDS": "jwks_cache_seconds",
    "MCP_AUTH_MAX_BODY_BYTES": "max_body_bytes",
}
_ENV_BOOLS: dict[str, str] = {
    "MCP_AUTH_PROTECT_REST": "protect_rest",
    "MCP_AUTH_ADVERTISE_OFFLINE_ACCESS": "advertise_offline_access",
    "MCP_AUTH_REQUIRE_USER_ROLES": "require_user_roles",
    "MCP_ADMIN_UI": "admin_ui",
}
_ENV_LISTS: dict[str, str] = {
    "MCP_AUTH_ALGORITHMS": "algorithms",
    "MCP_AUTH_ISSUERS": "issuers",
    "MCP_AUTH_AUDIENCES": "audiences",
    "MCP_AUTH_AUTHORIZATION_SERVERS": "authorization_servers",
    "MCP_AUTH_ALLOWED_CLIENT_IDS": "allowed_client_ids",
    "MCP_AUTH_ALLOWED_TENANTS": "allowed_tenants",
    "MCP_AUTH_READER_ROLES": "reader_roles",
    "MCP_AUTH_WRITER_ROLES": "writer_roles",
    "MCP_AUTH_ADMIN_ROLES": "admin_roles",
}
_ENV_JSON: dict[str, str] = {
    "MCP_AUTH_TOOL_PERMISSIONS": "tool_permissions",
    "MCP_AUTH_METHOD_PERMISSIONS": "method_permissions",
}
_ENV_ENTRA: dict[str, str] = {
    "MCP_AUTH_ENTRA_TENANT_ID": "tenant_id",
    "MCP_AUTH_ENTRA_CLIENT_ID": "client_id",
    "MCP_AUTH_ENTRA_APP_ID_URI": "app_id_uri",
    "MCP_AUTH_ENTRA_CLOUD": "cloud",
}
_ENV_PROXY_SECRETS: dict[str, str] = {
    "MCP_AUTH_ENTRA_CLIENT_SECRET": "client_secret",
    "MCP_AUTH_ENTRA_CLIENT_CERTIFICATE": "client_certificate_pem",
    "MCP_AUTH_ENTRA_CLIENT_PRIVATE_KEY": "client_private_key_pem",
    "MCP_AUTH_PROXY_ENCRYPTION_KEYS": "encryption_keys",
}


def _env_value(env: Mapping[str, str], name: str, what: str) -> str | None:
    """Return ``$NAME`` or the content of ``$NAME_FILE`` (if either is set)."""
    value = env.get(name)
    if value not in (None, ""):
        return value
    path = env.get(f"{name}_FILE")
    if path:
        return _read_file(path, what)
    return None


def _env_overrides(env: Mapping[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        for name, field in _ENV_SCALARS.items():
            if env.get(name, "") != "":
                out[field] = env[name].strip()
        for name, field in _ENV_INTS.items():
            if env.get(name, "") != "":
                out[field] = int(env[name])
        for name, field in _ENV_BOOLS.items():
            if env.get(name, "") != "":
                out[field] = parse_env_bool(env[name])
        for name, field in _ENV_LISTS.items():
            if env.get(name, "") != "":
                out[field] = parse_env_list(env[name])
        for name, field in _ENV_JSON.items():
            if env.get(name, "") != "":
                out[field] = json.loads(env[name])
    except (ValueError, json.JSONDecodeError) as exc:
        raise AuthConfigError(f"invalid MCP_AUTH_* environment value: {exc}") from exc
    pem = _env_value(env, "MCP_AUTH_PUBLIC_KEY", "public key")
    if pem:
        out["public_key_pem"] = pem
    entra: dict[str, Any] = {
        f: env[n].strip() for n, f in _ENV_ENTRA.items() if env.get(n)
    }
    if env.get("MCP_AUTH_ENTRA_TOKEN_VERSIONS"):
        entra["token_versions"] = parse_env_list(env["MCP_AUTH_ENTRA_TOKEN_VERSIONS"])
    if env.get("MCP_AUTH_ENTRA_JWKS_APPID"):
        entra["jwks_appid"] = parse_env_bool(env["MCP_AUTH_ENTRA_JWKS_APPID"])
    if entra:
        out["entra"] = entra
    proxy: dict[str, Any] = {}
    for name, field in _ENV_PROXY_SECRETS.items():
        value = _env_value(env, name, field)
        if value:
            proxy[field] = value
    fed = env.get("MCP_AUTH_ENTRA_FEDERATED_TOKEN_FILE") or env.get(
        "AZURE_FEDERATED_TOKEN_FILE"
    )
    if fed:
        proxy["federated_token_file"] = fed
    if env.get("MCP_AUTH_PROXY_ALLOWED_REDIRECT_URIS"):
        proxy["allowed_redirect_uris"] = parse_env_list(
            env["MCP_AUTH_PROXY_ALLOWED_REDIRECT_URIS"]
        )
    if env.get("MCP_AUTH_PROXY_REFRESH_TOKENS"):
        proxy["refresh_tokens"] = parse_env_bool(env["MCP_AUTH_PROXY_REFRESH_TOKENS"])
    for name, field in (
        ("MCP_AUTH_PROXY_REFRESH_TOKEN_MAX_AGE_DAYS", "refresh_token_max_age_days"),
        ("MCP_AUTH_PROXY_CODE_TTL_SECONDS", "code_ttl_seconds"),
    ):
        if env.get(name):
            proxy[field] = int(env[name])
    if proxy:
        out["proxy"] = proxy
    return out


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_auth_settings(
    environ: Mapping[str, str] | None = None,
    *,
    file_data: Mapping[str, Any] | None = None,
) -> AuthSettings:
    """Load and validate settings; raise :class:`AuthConfigError` on any problem."""
    env = os.environ if environ is None else environ
    mode = auth_mode_from_env(environ)
    data: dict[str, Any] = {}
    path = (env.get("MCP_AUTH_CONFIG_FILE") or "").strip()
    if path:
        data = _resolve_file_keys(_load_json(path))
    elif file_data is not None:
        data = _resolve_file_keys(_check_file_data(dict(file_data), "auth section"))
    elif environ is None:
        from ..core.settings_file import get_config

        section = get_config().data.get("auth") or {}
        if section:
            data = _resolve_file_keys(
                _check_file_data(dict(section), "uml-mcp.yaml auth")
            )
    data = _merge(data, _env_overrides(env))
    data["mode"] = mode
    try:
        return AuthSettings.model_validate(data)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'settings'}: {err['msg']}"
            for err in exc.errors()
        )
        raise AuthConfigError(
            f"invalid enterprise auth configuration: {details}"
        ) from exc


@lru_cache(maxsize=1)
def get_auth_settings() -> AuthSettings:
    """Process-wide cached settings (call :func:`reset_auth_settings_cache` in tests)."""
    return load_auth_settings()


def reset_auth_settings_cache() -> None:
    get_auth_settings.cache_clear()


__all__ = [
    "ASYMMETRIC_ALGORITHMS",
    "AuthSettings",
    "EntraSettings",
    "Permission",
    "ProxySettings",
    "get_auth_settings",
    "load_auth_settings",
    "reset_auth_settings_cache",
]
