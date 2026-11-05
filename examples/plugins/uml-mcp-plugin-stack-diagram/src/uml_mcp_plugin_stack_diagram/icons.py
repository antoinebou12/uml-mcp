"""A small built-in glyph set (24x24, stroke based) so diagrams need no logo downloads.

Brand logos are trademarks, so none ship here: pass ``icon`` as a base64 image data URI to
use a real logo, or pick a glyph name such as ``database`` or ``cloud``.
"""

from __future__ import annotations

import hashlib
from html import escape

GLYPHS: dict[str, str] = {
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/>',
    "browser": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M7 6.5h.01M10 6.5h.01"/>',
    "mobile": '<rect x="7" y="2.5" width="10" height="19" rx="2"/><path d="M11 18.5h2"/>',
    "monitor": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    "server": '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 16.5h.01"/>',
    "database": '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "cache": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "cloud": '<path d="M7 18a4 4 0 0 1-.6-7.9A6 6 0 0 1 18 11.5 3.5 3.5 0 0 1 17.5 18z"/>',
    "queue": '<rect x="2.5" y="8" width="5" height="8" rx="1"/><rect x="9.5" y="8" width="5" height="8" rx="1"/><rect x="16.5" y="8" width="5" height="8" rx="1"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "shield": '<path d="M12 3 4 6v6c0 4.5 3.2 8 8 9 4.8-1 8-4.5 8-9V6z"/><path d="m9 12 2 2 4-4"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M16 7l3 3"/>',
    "function": '<path d="M8 4c-2 0-3 1-3 3v3c0 1.5-1 2-2 2 1 0 2 .5 2 2v3c0 2 1 3 3 3M16 4c2 0 3 1 3 3v3c0 1.5 1 2 2 2-1 0-2 .5-2 2v3c0 2-1 3-3 3"/>',
    "container": '<path d="M12 2.5 3.5 7v10L12 21.5 20.5 17V7z"/><path d="M3.5 7 12 11.5 20.5 7M12 11.5v10"/>',
    "storage": '<path d="M3 8h18l-1.5 11a2 2 0 0 1-2 1.7H6.5a2 2 0 0 1-2-1.7z"/><path d="M5 4h14l2 4H3z"/>',
    "cdn": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
    "git": '<circle cx="6" cy="5" r="2.2"/><circle cx="6" cy="19" r="2.2"/><circle cx="18" cy="9" r="2.2"/><path d="M6 7.2v9.6M18 11.2c0 4-6 3-11 6"/>',
    "payments": '<rect x="2.5" y="5" width="19" height="14" rx="2"/><path d="M2.5 10h19M6 15h4"/>',
    "ai": '<path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"/>',
    "api": '<path d="m8 8-4 4 4 4M16 8l4 4-4 4M13.5 5l-3 14"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3.5 7 8.5 6 8.5-6"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1"/>',
    "chart": '<path d="M4 20V4M4 20h16M8 16v-4M12 16V8M16 16v-6"/>',
    "bell": '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 21h4"/>',
}

ALIASES = {
    "web": "browser",
    "frontend": "browser",
    "client": "browser",
    "backend": "server",
    "service": "server",
    "vm": "server",
    "postgres": "database",
    "postgresql": "database",
    "mysql": "database",
    "db": "database",
    "sql": "database",
    "redis": "cache",
    "memcached": "cache",
    "kafka": "queue",
    "rabbitmq": "queue",
    "sqs": "queue",
    "bus": "queue",
    "auth": "lock",
    "iam": "key",
    "security": "shield",
    "lambda": "function",
    "worker": "function",
    "k8s": "container",
    "kubernetes": "container",
    "docker": "container",
    "s3": "storage",
    "bucket": "storage",
    "blob": "storage",
    "gateway": "cdn",
    "loadbalancer": "cdn",
    "lb": "cdn",
    "dns": "cdn",
    "stripe": "payments",
    "billing": "payments",
    "github": "git",
    "ci": "git",
    "llm": "ai",
    "model": "ai",
    "email": "mail",
    "monitoring": "chart",
    "metrics": "chart",
    "settings": "gear",
    "cron": "gear",
}

MONOGRAM_TONES = ("blue", "orange", "green", "purple", "red", "teal", "yellow")


def resolve(name: str) -> str | None:
    """The glyph key for a name or alias, or ``None`` when it is not a glyph."""
    key = name.lower()
    key = ALIASES.get(key, key)
    return key if key in GLYPHS else None


def guess(*names: str) -> str | None:
    """A glyph matching the first name that resolves, else ``None``."""
    for name in names:
        for word in name.lower().replace("/", " ").replace("-", " ").split():
            hit = resolve(word)
            if hit:
                return hit
    return None


def glyph_svg(key: str, x: float, y: float, size: float, tone_class: str) -> str:
    scale = size / 24
    return (
        f'<g class="ico {tone_class}" transform="translate({x:.1f} {y:.1f}) scale({scale:.3f})" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{GLYPHS[key]}</g>'
    )


def monogram_tone(name: str) -> str:
    digest = hashlib.sha256(name.encode("utf-8")).digest()[0]
    return MONOGRAM_TONES[digest % len(MONOGRAM_TONES)]


def monogram_svg(name: str, x: float, y: float, size: float) -> str:
    letters = "".join(w[0] for w in name.replace("-", " ").split()[:2]).upper() or "?"
    tone = monogram_tone(name)
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{size:.1f}" height="{size:.1f}" rx="8" class="f-{tone}"/>'
        f'<text x="{x + size / 2:.1f}" y="{y + size / 2 + 5:.1f}" text-anchor="middle" '
        f'class="mono-letter">{escape(letters)}</text>'
    )


def icon_svg(
    icon: str,
    fallback_names: tuple[str, ...],
    x: float,
    y: float,
    size: float,
    tone: str | None,
    label: str | None = None,
) -> str:
    """Markup for a node icon: a data URI image, a glyph, or a monogram badge.

    ``label`` is what the monogram spells (the node's name) when no glyph matches.
    """
    if icon.startswith("data:"):
        return (
            f'<image href="{escape(icon, quote=True)}" x="{x:.1f}" y="{y:.1f}" '
            f'width="{size:.1f}" height="{size:.1f}" preserveAspectRatio="xMidYMid meet"/>'
        )
    key = resolve(icon) if icon else guess(*fallback_names)
    tone_class = f"s-{tone}" if tone else "s-ink"
    if key:
        return glyph_svg(key, x, y, size, tone_class)
    return monogram_svg(
        label or (fallback_names[0] if fallback_names else icon), x, y, size
    )
