"""Normalize Mermaid source before it is sent to Kroki (or mermaid.ink).

Models routinely hand over Mermaid in shapes the parser rejects even though the diagram
itself is fine. Real Kroki (Mermaid 12) answers each of these with HTTP 400:

* wrapped in a markdown fence (``No diagram type detected``);
* a single line whose newlines arrived double-escaped (``graph TD\\n A --> B``);
* a zero-width character (U+200B/C/D, U+2060) pasted in with the text, which fails
  with ``Lexical error ... Unrecognized text`` and cannot be seen to be fixed.

A BOM and non-breaking spaces are accepted by Mermaid, so they are left alone.
Every fix here only touches input that cannot be valid Mermaid as written, so valid
diagrams are never altered. ``theme`` is applied as Mermaid's own ``%%{init}%%``
directive, which Kroki and mermaid.ink both honour.
"""

from __future__ import annotations

import re

#: Themes Mermaid ships with; anything else (e.g. a PlantUML theme name) is ignored.
MERMAID_THEMES = frozenset({"default", "dark", "forest", "neutral", "base"})

_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060"))
# Header word, optional direction (TD, LR, ...), then a literal backslash-n.
_ESCAPED_NEWLINE = re.compile(r"^[A-Za-z][\w-]*(?:[ \t]+[A-Za-z]{1,2})?\\n")
_FRONTMATTER = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*(?:\n|\Z)", re.DOTALL)
_HAS_INIT_DIRECTIVE = re.compile(r"%%\{\s*(?:init|initialize)\b")
_FRONTMATTER_THEME = re.compile(r"^\s*theme\s*:", re.MULTILINE)


def _strip_fence(text: str) -> str:
    """Unwrap a ```mermaid fenced block (and drop prose after the closing fence)."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text
    body = stripped[3:]
    first, newline, rest = body.partition("\n")
    if newline and first.strip().lower() in ("", "mermaid"):
        body = rest
    elif not newline:  # one-liner: ```graph TD; A-->B;```
        body = re.sub(r"^\s*mermaid\s+", "", body, flags=re.IGNORECASE)
    return body.split("\n```", 1)[0].removesuffix("```").strip()


def _apply_theme(text: str, theme: str | None) -> str:
    name = (theme or "").strip().lower()
    if name not in MERMAID_THEMES or _HAS_INIT_DIRECTIVE.search(text):
        return text  # not a Mermaid theme, or the author already chose one
    directive = f"%%{{init: {{'theme': '{name}'}}}}%%\n"
    frontmatter = _FRONTMATTER.match(text)
    if frontmatter is None:
        return directive + text
    if _FRONTMATTER_THEME.search(frontmatter.group(0)):
        return text  # frontmatter config already sets a theme
    return text[: frontmatter.end()] + directive + text[frontmatter.end() :]


def prepare_mermaid_source(code: str, theme: str | None = None) -> str:
    """Return ``code`` ready for a Mermaid renderer; valid input is returned unchanged."""
    text = _strip_fence(code.translate(_ZERO_WIDTH)).strip()
    if "\n" not in text and _ESCAPED_NEWLINE.match(text):
        text = text.replace("\\n", "\n")
    return _apply_theme(text, theme)


def mermaid_theme_from_source(code: str) -> str:
    """Read the effective theme from the source's configuration header."""
    front = _FRONTMATTER.match(code)
    init = re.search(r"%%\{\s*(?:init|initialize)\s*:(.*?)\}%%", code, re.DOTALL)
    config = front[0] if front else (init[1] if init else "")
    match = re.search(
        r"""["']?theme["']?\s*:\s*["']?(default|dark|forest|neutral|base)\b""", config
    )
    return match[1] if match else "default"
