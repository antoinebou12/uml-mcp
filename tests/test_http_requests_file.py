"""Sanity checks for tests/http/entra-auth.http (REST Client / JetBrains format)."""

from __future__ import annotations

import re
from pathlib import Path

HTTP = Path(__file__).parent / "http" / "entra-auth.http"


def _requests() -> list[str]:
    blocks = HTTP.read_text(encoding="utf-8").split("\n###")[1:]
    lines = []
    for block in blocks:
        for line in block.splitlines()[1:]:
            if line and not line.startswith(("#", "@")):
                lines.append(line)
                break
    return lines


def test_every_block_has_a_request_line():
    lines = _requests()
    assert len(lines) >= 12
    for line in lines:
        assert re.match(r"^(GET|POST) (\{\{\w+\}\}|https://)\S*$", line), line


def test_variables_are_defined_and_no_secrets():
    text = HTTP.read_text(encoding="utf-8")
    defined = set(re.findall(r"^@(\w+) =", text, re.MULTILINE))
    used = set(re.findall(r"\{\{(\w+)\}\}", text)) - {"appToken"}
    used = {u for u in used if "." not in u}
    assert used <= defined, used - defined
    assert "eyJ" not in text  # never commit a real token
    for expected in (
        "oauth-protected-resource/mcp",
        "client_credentials",
        "code_challenge_method=plain",
        "oauth-authorization-server",
    ):
        assert expected in text
