"""Documentation links for the models and tools a step names.

Reuses the D3 plugin's map of official documentation sites (``uml_mcp_plugin_d3.docs``)
when it is installed (it ships in the same distribution); without it, no step gets a link.
Nothing is fetched: the link only opens when a reader clicks it.
"""

from __future__ import annotations

import re
from collections.abc import Callable

try:  # pragma: no cover - the D3 plugin ships with uml-mcp
    from uml_mcp_plugin_d3.docs import docs_url as _docs_url
except ImportError:  # pragma: no cover
    _docs_url = None

docs_url: Callable[[str | None, str, str], str | None] | None = _docs_url

#: model name pattern -> the ``tech:`` key of its provider's API docs
MODEL_FAMILIES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), key)
    for pattern, key in (
        (r"claude|anthropic", "claude"),
        (
            r"^(gpt|o\d|chatgpt|text-embedding|omni-moderation|whisper|dall-e)|openai",
            "openai",
        ),
        (r"gemini|^models/gemini", "gemini"),
        (r"mistral|mixtral|codestral|ministral", "mistral"),
        (r"^command|cohere|^embed-", "cohere"),
    )
)


def model_docs(model: str) -> str | None:
    if not model or docs_url is None:
        return None
    for pattern, key in MODEL_FAMILIES:
        if pattern.search(model.strip()):
            return docs_url(f"tech:{key}", "tech", key)
    return None


def tool_docs(tool: str) -> str | None:
    """A tool named after a known service (``postgres``, ``elasticsearch``, ``aws:s3``)."""
    if not tool or docs_url is None:
        return None
    provider, _, rest = tool.strip().lower().partition(":")
    if rest:
        return docs_url(tool, provider, rest)
    return docs_url(tool, "tech", tool) or model_docs(tool)


def step_docs(kind: str, model: str, tool: str, trace_model: str) -> str | None:
    if kind == "llm":
        return model_docs(model or trace_model) or tool_docs(tool)
    return tool_docs(tool) or model_docs(model)
