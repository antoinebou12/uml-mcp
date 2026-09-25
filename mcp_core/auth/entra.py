"""Microsoft Entra ID specifics (authorities, issuers, well-known client IDs).

References: Microsoft identity platform access tokens (v1 vs v2 ``iss``/``aud``,
``tid`` binding, signing-key issuer check) and "Protected web API: verify scopes
and app roles".
"""

from __future__ import annotations

import re
from typing import Any

ENTRA_CLOUDS: dict[str, dict[str, str]] = {
    "public": {"login": "login.microsoftonline.com", "sts": "sts.windows.net"},
    "usgov": {"login": "login.microsoftonline.us", "sts": "sts.windows.net"},
    "china": {"login": "login.chinacloudapi.cn", "sts": "sts.chinacloudapi.cn"},
}

#: Well-known first-party client application IDs that can be pre-authorized on
#: the API app registration ("Expose an API" -> "Authorized client applications").
KNOWN_CLIENTS: dict[str, str] = {
    "aebc6443-996d-45c2-90f0-388ff96faa56": "Visual Studio Code",
    "04f0c124-f2bc-4f59-8241-bf6df9866bbd": "Visual Studio",
    "04b07795-8ddb-461a-bbee-02f9e1bf7b46": "Azure CLI (admin tooling, optional)",
}
VSCODE_CLIENT_ID = "aebc6443-996d-45c2-90f0-388ff96faa56"
VISUAL_STUDIO_CLIENT_ID = "04f0c124-f2bc-4f59-8241-bf6df9866bbd"
AZURE_CLI_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"

_GUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def is_guid(value: Any) -> bool:
    return isinstance(value, str) and bool(_GUID.match(value))


def entra_authority_host(cloud: str) -> str:
    return ENTRA_CLOUDS[cloud]["login"]


def entra_v2_issuer(host: str, tenant_id: str) -> str:
    return f"https://{host}/{tenant_id}/v2.0"


def entra_v1_issuer_template(cloud: str) -> str:
    return "https://" + ENTRA_CLOUDS[cloud]["sts"] + "/{tid}/"


def entra_jwks_uri(host: str, tenant_id: str) -> str:
    return f"https://{host}/{tenant_id}/discovery/v2.0/keys"


def entra_authorize_endpoint(host: str, tenant_id: str) -> str:
    return f"https://{host}/{tenant_id}/oauth2/v2.0/authorize"


def entra_token_endpoint(host: str, tenant_id: str) -> str:
    return f"https://{host}/{tenant_id}/oauth2/v2.0/token"


def expected_entra_issuer(claims: dict[str, Any], cloud: str) -> str | None:
    """Issuer the token must carry, derived from its own ``tid`` and ``ver``."""
    tid = claims.get("tid")
    if not is_guid(tid):
        return None
    if str(claims.get("ver")) == "1.0":
        return entra_v1_issuer_template(cloud).format(tid=tid)
    return entra_v2_issuer(entra_authority_host(cloud), str(tid))


__all__ = [
    "AZURE_CLI_CLIENT_ID",
    "ENTRA_CLOUDS",
    "KNOWN_CLIENTS",
    "VISUAL_STUDIO_CLIENT_ID",
    "VSCODE_CLIENT_ID",
    "entra_authority_host",
    "entra_authorize_endpoint",
    "entra_jwks_uri",
    "entra_token_endpoint",
    "entra_v1_issuer_template",
    "entra_v2_issuer",
    "expected_entra_issuer",
    "is_guid",
]
