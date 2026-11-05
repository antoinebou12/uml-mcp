"""Bundled brand marks; no runtime requests to icon CDNs.

The SVGs come from @lobehub/icons-static-svg 1.101.0 (MIT, see ``assets/brands``). A node
shows one when its provider has a mark (AWS, Google Cloud, Azure) or when it names a
software service that has one (``tech:github``, ``tech:gemini``...). Everything else keeps
its monogram tile or category glyph.
"""

import re
from functools import lru_cache
from pathlib import Path

#: provider -> logo file (without ``.svg``)
PROVIDER_LOGOS = {
    "aws": "aws-color",
    "gcp": "googlecloud-color",
    "azure": "azure-color",
}

#: software name (as in ``tech:<name>``) -> logo file
TECH_LOGOS = {
    "openai": "openai",
    "chatgpt": "openai",
    "anthropic": "claude-color",
    "claude": "claude-color",
    "github": "github",
    "copilot": "githubcopilot",
    "vercel": "vercel",
    "cloudflare": "cloudflare-color",
    "azure": "azure-color",
    "microsoft": "microsoft-color",
    "gemini": "gemini-color",
    "mistral": "mistral-color",
    "ollama": "ollama",
    "huggingface": "huggingface-color",
    "langchain": "langchain-color",
    "meta": "meta-color",
    "llama": "meta-color",
    "nvidia": "nvidia-color",
    "deepseek": "deepseek-color",
    "cursor": "cursor",
    "mcp": "mcp",
    "bedrock": "bedrock-color",
    "vertexai": "vertexai-color",
    "perplexity": "perplexity-color",
    "cohere": "cohere-color",
    "groq": "groq",
    "n8n": "n8n-color",
    "notion": "notion",
    # display names, which is what a node carries once its service is resolved
    "githubcopilot": "githubcopilot",
    "microsoftazure": "azure-color",
    "mistralai": "mistral-color",
    "amazonbedrock": "bedrock-color",
    "modelcontextprotocol": "mcp",
}


def logo_key(provider: str, name: str) -> str | None:
    """The logo file for a node, or ``None`` when it has no bundled mark."""
    if provider == "tech":
        return TECH_LOGOS.get(name.lower().replace(" ", ""))
    return PROVIDER_LOGOS.get(provider)


@lru_cache(maxsize=64)
def brand_svg(provider: str, name: str) -> str:
    key = logo_key(provider, name)
    if not key:
        return ""
    svg = (Path(__file__).parent / "assets" / "brands" / f"{key}.svg").read_text(
        encoding="utf-8"
    )

    svg = re.sub(r'\sstyle="[^"]*"', "", svg)

    def root(match):
        attrs = re.sub(r'\s(?:width|height|class)="[^"]*"', "", match[1])
        return (
            '<svg class="brand-logo" x="10" y="6" width="20" height="20"' + attrs + ">"
        )

    return re.sub(r"<svg([^>]*)>", root, svg, count=1)
