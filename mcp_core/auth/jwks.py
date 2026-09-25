"""Signing-key sources: a hardened async JWKS cache and a static PEM key set.

JWKS hardening (DoS / rotation):

* keys cached for ``ttl`` seconds; an unknown ``kid`` forces at most one refetch
  per ``min_refresh_seconds`` (single-flight + short negative cache);
* stale keys keep serving for ``stale_if_error_seconds`` when the IdP is down;
* HTTPS only (loopback http allowed for local dev), no redirects, size caps;
* key type / curve / ``use`` / ``key_ops`` must match the token algorithm.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any, Protocol

import httpx
import jwt
from jwt.algorithms import get_default_algorithms

MAX_JWKS_BYTES = 256 * 1024
MAX_KEYS = 100

_ALG_KTY = {
    "RS": "RSA",
    "PS": "RSA",
    "ES": "EC",
    "Ed": "OKP",
}
_ALG_CRV = {"ES256": "P-256", "ES384": "P-384", "ES512": "P-521"}


class KeyUnavailableError(Exception):
    """Key material could not be fetched (network / IdP outage)."""


class UnknownKeyError(Exception):
    """No key matches the token's ``kid``/algorithm."""


class KeyProvider(Protocol):
    async def get_key(self, kid: str | None, alg: str) -> Any: ...

    def health(self) -> dict[str, Any]: ...


def _key_matches_alg(jwk: dict[str, Any], alg: str) -> bool:
    kty = _ALG_KTY.get(alg[:2])
    if kty is None or jwk.get("kty") != kty:
        return False
    if alg in _ALG_CRV and jwk.get("crv") != _ALG_CRV[alg]:
        return False
    if jwk.get("use") not in (None, "sig"):
        return False
    ops = jwk.get("key_ops")
    if ops is not None and "verify" not in ops:
        return False
    declared = jwk.get("alg")
    return declared in (None, alg)


class StaticKeySet:
    """One or more PEM public keys (``kid`` optional)."""

    def __init__(self, pems: list[str]):
        self._keys: list[Any] = []
        for pem in pems:
            data = pem.encode()
            key = None
            for name, algo in get_default_algorithms().items():
                if name.startswith(("HS", "none")):
                    continue
                try:
                    key = algo.prepare_key(data)
                    break
                except Exception:  # noqa: BLE001, S112 - try the next key family
                    continue
            if key is None:
                raise ValueError("static public key is not a supported PEM key")
            self._keys.append(key)

    async def get_key(self, kid: str | None, alg: str) -> Any:
        algo = get_default_algorithms().get(alg)
        if algo is None:
            raise UnknownKeyError(f"unsupported algorithm {alg}")
        for key in self._keys:
            try:
                algo.prepare_key(key)  # raises when the key family mismatches
            except Exception:  # noqa: BLE001, S112 - key family mismatch
                continue
            return key
        raise UnknownKeyError("no static key matches the token algorithm")

    def health(self) -> dict[str, Any]:
        return {"source": "static", "keys": len(self._keys), "status": "ok"}


class JwksCache:
    """Async, throttled JWKS cache backed by an ``httpx.AsyncClient``."""

    def __init__(
        self,
        uri: str,
        *,
        http: httpx.AsyncClient | None = None,
        ttl: int = 3600,
        min_refresh_seconds: float = 60.0,
        stale_if_error_seconds: float = 86400.0,
        timeout: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.uri = uri
        self._http = http
        self.ttl = ttl
        self.min_refresh_seconds = min_refresh_seconds
        self.stale_if_error_seconds = stale_if_error_seconds
        self.timeout = timeout
        self._clock = clock
        self._keys: dict[str, dict[str, Any]] = {}
        self._fetched_at: float | None = None
        self._last_attempt: float | None = None
        self._last_error: str | None = None
        self._negative: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self.fetch_count = 0

    # ---------------------------------------------------------------- fetching
    async def _fetch(self) -> dict[str, dict[str, Any]]:
        client = self._http or httpx.AsyncClient(timeout=self.timeout)
        try:
            resp = await client.get(
                self.uri,
                headers={"Accept": "application/json"},
                follow_redirects=False,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise KeyUnavailableError(
                f"JWKS fetch failed: {exc.__class__.__name__}"
            ) from exc
        finally:
            if self._http is None:
                await client.aclose()
        self.fetch_count += 1
        if resp.status_code != 200:
            raise KeyUnavailableError(f"JWKS endpoint returned HTTP {resp.status_code}")
        if len(resp.content) > MAX_JWKS_BYTES:
            raise KeyUnavailableError("JWKS document too large")
        try:
            doc = json.loads(resp.content)
        except ValueError as exc:
            raise KeyUnavailableError("JWKS document is not JSON") from exc
        keys = doc.get("keys") if isinstance(doc, dict) else None
        if not isinstance(keys, list):
            raise KeyUnavailableError("JWKS document has no 'keys' array")
        out: dict[str, dict[str, Any]] = {}
        for jwk in keys[:MAX_KEYS]:
            if isinstance(jwk, dict) and isinstance(jwk.get("kid"), str):
                out[jwk["kid"]] = jwk
        return out

    async def refresh(self, *, force: bool = False) -> None:
        async with self._lock:
            now = self._clock()
            fresh = self._fetched_at is not None and now - self._fetched_at < self.ttl
            if fresh and not force:
                return
            if (
                force
                and self._last_attempt is not None
                and now - self._last_attempt < self.min_refresh_seconds
            ):
                return  # throttled: random kids cannot force a fetch storm
            self._last_attempt = now
            try:
                self._keys = await self._fetch()
                self._fetched_at = self._clock()
                self._last_error = None
                self._negative.clear()
            except KeyUnavailableError as exc:
                self._last_error = str(exc)
                stale_ok = (
                    self._fetched_at is not None
                    and now - self._fetched_at < self.stale_if_error_seconds
                )
                if not stale_ok:
                    raise

    async def get_key(self, kid: str | None, alg: str) -> Any:
        if not kid:
            raise UnknownKeyError("token header has no 'kid'")
        now = self._clock()
        if self._fetched_at is None or now - self._fetched_at >= self.ttl:
            await self.refresh()
        jwk = self._keys.get(kid)
        if jwk is None:
            neg = self._negative.get(kid)
            if neg is None or now - neg >= self.min_refresh_seconds:
                await self.refresh(force=True)
                jwk = self._keys.get(kid)
                if jwk is None:
                    self._negative[kid] = self._clock()
        if jwk is None:
            raise UnknownKeyError(f"no signing key with kid '{kid[:64]}'")
        if not _key_matches_alg(jwk, alg):
            raise UnknownKeyError(f"signing key '{kid[:64]}' does not allow {alg}")
        try:
            return jwt.PyJWK(jwk, algorithm=alg).key
        except jwt.PyJWKError as exc:
            raise UnknownKeyError(f"unusable signing key: {exc}") from exc

    def key_issuer(self, kid: str | None) -> str | None:
        jwk = self._keys.get(kid or "")
        issuer = jwk.get("issuer") if jwk else None
        return issuer if isinstance(issuer, str) else None

    def health(self) -> dict[str, Any]:
        age = None if self._fetched_at is None else self._clock() - self._fetched_at
        return {
            "source": "jwks",
            "uri": self.uri,
            "keys": sorted(self._keys),
            "age_seconds": None if age is None else round(age, 1),
            "fetch_count": self.fetch_count,
            "last_error": self._last_error,
            "status": "ok" if self._last_error is None else "degraded",
        }


__all__ = [
    "JwksCache",
    "KeyProvider",
    "KeyUnavailableError",
    "StaticKeySet",
    "UnknownKeyError",
]
