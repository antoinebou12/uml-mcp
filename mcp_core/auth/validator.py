"""Access-token validation (RFC 9068-style JWTs, Microsoft Entra v1/v2 tokens).

Checks run in a fixed order so that nothing reaches the network before cheap,
local rejections (size, header, algorithm allow-list, issuer pre-check).
Unverified claims are only ever used to *reject* with a precise reason;
acceptance always requires full signature + claim verification.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

import jwt

from . import errors
from .entra import expected_entra_issuer, is_guid
from .jwks import KeyProvider, KeyUnavailableError, UnknownKeyError
from .settings import AuthSettings

MAX_TOKEN_BYTES = 16 * 1024
FORBIDDEN_HEADERS = ("jku", "x5u", "jwk", "crit")


@dataclass(frozen=True)
class Principal:
    """The authenticated caller, derived from a verified token."""

    subject: str
    tenant_id: str | None
    client_id: str | None
    issuer: str
    kind: str  # "delegated" | "app"
    scopes: frozenset[str]
    roles: frozenset[str]
    token_version: str | None
    expires_at: int | None
    permissions: frozenset[str] = field(default_factory=frozenset)

    @property
    def key(self) -> str:
        """Stable, non-reversible owner key (used to bind AG-UI runs)."""
        raw = f"{self.issuer}|{self.tenant_id}|{self.subject}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


def _b64json(segment: str) -> dict[str, Any]:
    padded = segment + "=" * (-len(segment) % 4)
    data = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    if not isinstance(data, dict):
        raise ValueError("segment is not a JSON object")  # noqa: TRY004
    return data


def _scopes_from(claims: dict[str, Any], prefixes: list[str]) -> frozenset[str]:
    raw = claims.get("scp", claims.get("scope"))
    if isinstance(raw, str):
        items = raw.split()
    elif isinstance(raw, list):
        items = [str(s) for s in raw]
    else:
        items = []
    out = set()
    for item in items:
        for prefix in prefixes:
            if prefix and item.startswith(prefix):
                item = item[len(prefix) :]
                break
        out.add(item)
    return frozenset(out)


class TokenValidator:
    """Validate bearer tokens against :class:`AuthSettings`."""

    def __init__(self, settings: AuthSettings, keys: KeyProvider):
        self.settings = settings
        self.keys = keys
        self._issuers = settings.effective_issuers
        self._audiences = settings.effective_audiences

    # ------------------------------------------------------------------- public
    async def validate(self, token: str) -> Principal:
        header, _claims = self._precheck(token)
        alg = header["alg"]
        try:
            key = await self.keys.get_key(header.get("kid"), alg)
        except KeyUnavailableError as exc:
            raise errors.unavailable(
                "jwks_unavailable",
                "The server cannot reach the identity provider signing keys; "
                f"retry later ({exc})",
            ) from exc
        except UnknownKeyError as exc:
            raise errors.invalid_token(
                "unknown_signing_key",
                f"Token signing key is not trusted by this server: {exc}",
            ) from exc
        verified = self._decode(token, key, alg)
        self._post_checks(header, verified)
        return self._principal(verified)

    async def explain(self, token: str) -> list[CheckResult]:
        """Per-check report for the admin token tester (never echoes the token)."""
        results: list[CheckResult] = []
        try:
            principal = await self.validate(token)
        except errors.AuthError as exc:
            results.append(CheckResult(exc.reason, False, exc.description))
            return results
        results.append(CheckResult("signature", True, "verified"))
        results.append(CheckResult("issuer", True, principal.issuer))
        results.append(CheckResult("audience", True, "accepted"))
        results.append(
            CheckResult(
                "permissions",
                bool(principal.permissions),
                ", ".join(sorted(principal.permissions)) or "none",
            )
        )
        return results

    # ------------------------------------------------------------------ helpers
    def _precheck(self, token: str) -> tuple[dict[str, Any], dict[str, Any]]:
        if len(token) > MAX_TOKEN_BYTES:
            raise errors.invalid_request(
                "token_too_large", "Access token exceeds 16 KiB"
            )
        segments = token.split(".")
        if len(segments) != 3 or not all(segments[:2]):
            raise errors.invalid_token(
                "malformed_token",
                "Access token is not a JWS compact JWT (header.payload.signature); "
                "opaque tokens are not supported",
            )
        try:
            header = _b64json(segments[0])
            claims = _b64json(segments[1])
        except (ValueError, UnicodeDecodeError) as exc:
            raise errors.invalid_token(
                "malformed_token", "Access token header or payload is not valid JSON"
            ) from exc
        alg = header.get("alg")
        if not isinstance(alg, str) or alg not in self.settings.algorithms:
            raise errors.invalid_token(
                "unsupported_algorithm",
                f"Token algorithm {alg!r} is not accepted; allowed: "
                f"{', '.join(self.settings.algorithms)}",
            )
        bad = [h for h in FORBIDDEN_HEADERS if h in header]
        if bad:
            raise errors.invalid_token(
                "forbidden_header",
                f"Token header carries {', '.join(bad)}; key references in tokens "
                "are never trusted",
            )
        kid = header.get("kid")
        if kid is not None and (not isinstance(kid, str) or len(kid) > 256):
            raise errors.invalid_token("missing_kid", "Token 'kid' header is invalid")
        if kid is None and self.settings.effective_jwks_uri:
            raise errors.invalid_token(
                "missing_kid", "Token header has no 'kid' to select a JWKS key"
            )
        if self.settings.token_type:
            typ = str(header.get("typ", "")).lower()
            if typ != self.settings.token_type.lower():
                raise errors.invalid_token(
                    "invalid_token_type",
                    f"Token typ {typ!r} is not {self.settings.token_type!r}",
                )
        iss = claims.get("iss")
        if not isinstance(iss, str) or iss not in self._issuers:
            raise errors.invalid_token(
                "invalid_issuer",
                f"Token issuer {str(iss)[:120]!r} is not trusted by this server",
            )
        aud = claims.get("aud")
        auds = aud if isinstance(aud, list) else [aud]
        if not any(isinstance(a, str) and a in self._audiences for a in auds):
            raise errors.invalid_token(
                "invalid_audience",
                f"Token audience {str(aud)[:120]!r} is for another resource; request "
                f"a token for {self._audiences[0]} (tokens for other services such "
                "as Microsoft Graph are rejected)",
                expected_audiences=self._audiences,
            )
        exp = claims.get("exp")
        if not isinstance(exp, (int, float)):
            raise errors.invalid_token("missing_claim", "Token has no 'exp' claim")
        if exp + self.settings.leeway_seconds < time.time():
            raise errors.invalid_token(
                "token_expired", "Access token expired; obtain a new token"
            )
        return header, claims

    def _decode(self, token: str, key: Any, alg: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                key=key,
                algorithms=[alg],
                audience=self._audiences,
                issuer=self._issuers,
                leeway=self.settings.leeway_seconds,
                options={"require": ["exp", "iss", "aud"], "verify_iat": False},
            )
        except jwt.ExpiredSignatureError as exc:
            raise errors.invalid_token(
                "token_expired", "Access token expired; obtain a new token"
            ) from exc
        except jwt.ImmatureSignatureError as exc:
            raise errors.invalid_token(
                "token_not_yet_valid", "Access token is not valid yet (nbf)"
            ) from exc
        except jwt.InvalidAudienceError as exc:
            raise errors.invalid_token(
                "invalid_audience", "Token audience is not accepted"
            ) from exc
        except jwt.InvalidIssuerError as exc:
            raise errors.invalid_token(
                "invalid_issuer", "Token issuer is not trusted"
            ) from exc
        except jwt.MissingRequiredClaimError as exc:
            raise errors.invalid_token(
                "missing_claim", f"Token is missing the '{exc.claim}' claim"
            ) from exc
        except jwt.InvalidSignatureError as exc:
            raise errors.invalid_token(
                "invalid_signature", "Token signature verification failed"
            ) from exc
        except jwt.PyJWTError as exc:
            raise errors.invalid_token(
                "malformed_token",
                f"Token could not be verified: {exc.__class__.__name__}",
            ) from exc

    def _post_checks(self, header: dict[str, Any], claims: dict[str, Any]) -> None:
        s = self.settings
        if "nonce" in claims:
            raise errors.invalid_token(
                "id_token_not_accepted",
                "An ID token was presented; send an access token for this API",
            )
        if s.entra is not None:
            tid = claims.get("tid")
            if not is_guid(tid):
                raise errors.invalid_token(
                    "missing_claim", "Entra token has no valid 'tid' claim"
                )
            tid = str(tid)
            if tid.lower() not in {t.lower() for t in s.effective_allowed_tenants}:
                raise errors.invalid_token(
                    "tenant_not_allowed", f"Tenant {tid} is not allowed"
                )
            ver = str(claims.get("ver", ""))
            wanted = {f"{v}.0" for v in s.entra.token_versions}
            if ver not in wanted:
                raise errors.invalid_token(
                    "token_version_not_allowed",
                    f"Token version {ver!r} is not accepted (expected "
                    f"{', '.join(sorted(wanted))}); set requestedAccessTokenVersion=2 "
                    "on the API app registration",
                )
            if claims.get("iss") != expected_entra_issuer(claims, s.entra.cloud):
                raise errors.invalid_token(
                    "invalid_issuer",
                    "Token issuer does not match its tenant (iss/tid binding)",
                )
            key_issuer = getattr(self.keys, "key_issuer", lambda _k: None)(
                header.get("kid")
            )
            if (
                ver == "2.0"
                and key_issuer
                and "{tenantid}" in key_issuer
                and key_issuer.replace("{tenantid}", tid) != claims["iss"]
            ):
                raise errors.invalid_token(
                    "invalid_issuer", "Signing key issuer does not match token"
                )
        client_id = claims.get("azp") or claims.get("appid") or claims.get("client_id")
        if s.allowed_client_ids and client_id not in s.allowed_client_ids:
            raise errors.invalid_token(
                "client_not_allowed",
                f"Client application {str(client_id)[:64]!r} is not pre-authorized "
                "for this server",
            )

    def _principal(self, claims: dict[str, Any]) -> Principal:
        from .policy import permissions_for

        s = self.settings
        prefixes = [p for p in {s.effective_scope_prefix, s.upstream_scope_prefix} if p]
        scopes = _scopes_from(claims, prefixes)
        raw_roles = claims.get(s.roles_claim, [])
        roles = frozenset(
            str(r) for r in (raw_roles if isinstance(raw_roles, list) else [raw_roles])
        )
        has_scp = "scp" in claims or "scope" in claims
        kind = "delegated" if has_scp else "app"
        principal = Principal(
            subject=str(claims.get("oid") or claims.get("sub") or ""),
            tenant_id=claims.get("tid"),
            client_id=claims.get("azp")
            or claims.get("appid")
            or claims.get("client_id"),
            issuer=str(claims.get("iss")),
            kind=kind,
            scopes=scopes,
            roles=roles,
            token_version=str(claims.get("ver")) if "ver" in claims else None,
            expires_at=int(claims["exp"]) if "exp" in claims else None,
        )
        return dataclasses.replace(
            principal, permissions=frozenset(permissions_for(principal, s))
        )


__all__ = ["CheckResult", "Principal", "TokenValidator"]
