"""Stateless sealed blobs for the ``entra-proxy`` facade (AES-256-GCM).

Format: ``v1.<kid>.<b64url(nonce || ciphertext+tag)>``. A per-purpose subkey is
derived with HKDF-SHA256 and the AAD binds purpose, key id and issuer, so a
client_id can never be replayed as an authorization code (or vice versa).

Keys come from ``MCP_AUTH_PROXY_ENCRYPTION_KEYS="kid2:<b64url32>,kid1:<b64url32>"``:
the first key encrypts, every key decrypts (rotation).
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
from collections.abc import Callable
from typing import Any

_KID = re.compile(r"^[A-Za-z0-9_-]{1,16}$")


class SealError(Exception):
    """Blob is malformed, tampered with, expired or sealed for another purpose."""


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _b64e(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def parse_keys(value: str) -> list[tuple[str, bytes]]:
    """Parse ``kid:b64url32`` entries (comma separated). Raises ``ValueError``."""
    keys: list[tuple[str, bytes]] = []
    for entry in [e.strip() for e in value.split(",") if e.strip()]:
        kid, sep, material = entry.partition(":")
        if not sep or not _KID.match(kid):
            raise ValueError(
                "MCP_AUTH_PROXY_ENCRYPTION_KEYS entries must look like "
                "'<kid>:<base64url 32-byte key>'"
            )
        try:
            raw = _b64d(material)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"encryption key {kid!r} is not base64url") from exc
        if len(raw) != 32:
            raise ValueError(f"encryption key {kid!r} must be exactly 32 bytes")
        keys.append((kid, raw))
    if not keys:
        raise ValueError("MCP_AUTH_PROXY_ENCRYPTION_KEYS is empty")
    return keys


def generate_key(kid: str = "k1") -> str:
    """Helper for docs/CLI: a fresh ``kid:key`` entry."""
    return f"{kid}:{_b64e(os.urandom(32))}"


class Sealer:
    def __init__(
        self,
        keys: list[tuple[str, bytes]],
        issuer: str,
        clock: Callable[[], float] = time.time,
    ):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF

        self._issuer = issuer
        self._clock = clock
        self._primary = keys[0][0]
        self._keys = dict(keys)
        self._hkdf = lambda master, purpose: HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"uml-mcp-sealing-v1",
            info=purpose.encode(),
        ).derive(master)

    def _aead(self, kid: str, purpose: str):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        master = self._keys.get(kid)
        if master is None:
            raise SealError("unknown sealing key")
        return AESGCM(self._hkdf(master, purpose))

    def _aad(self, purpose: str, kid: str) -> bytes:
        return f"uml-mcp/v1/{purpose}/{kid}/{self._issuer}".encode()

    def seal(self, purpose: str, payload: dict[str, Any], ttl: int) -> str:
        body = dict(payload)
        body["exp"] = int(self._clock()) + int(ttl)
        nonce = os.urandom(12)
        kid = self._primary
        ct = self._aead(kid, purpose).encrypt(
            nonce,
            json.dumps(body, separators=(",", ":")).encode(),
            self._aad(purpose, kid),
        )
        return f"v1.{kid}.{_b64e(nonce + ct)}"

    def unseal(self, purpose: str, token: str) -> dict[str, Any]:
        from cryptography.exceptions import InvalidTag

        try:
            version, kid, blob = token.split(".", 2)
        except (AttributeError, ValueError) as exc:
            raise SealError("malformed sealed value") from exc
        if version != "v1":
            raise SealError("unsupported sealed value version")
        try:
            raw = _b64d(blob)
        except (ValueError, TypeError) as exc:
            raise SealError("malformed sealed value") from exc
        if len(raw) < 12 + 16:
            raise SealError("malformed sealed value")
        try:
            plain = self._aead(kid, purpose).decrypt(
                raw[:12], raw[12:], self._aad(purpose, kid)
            )
        except InvalidTag as exc:
            raise SealError("sealed value failed authentication") from exc
        data = json.loads(plain)
        if int(data.get("exp", 0)) < self._clock():
            raise SealError("sealed value expired")
        return data


__all__ = ["SealError", "Sealer", "generate_key", "parse_keys"]
