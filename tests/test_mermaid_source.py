"""Mermaid source normalization (fences, escaped newlines, invisible characters, theme).

Each "repaired" case is something real Kroki rejects with HTTP 400 as written; the
"unchanged" cases guard that valid diagrams are never altered.
"""

import pytest

from mcp_core.core.diagram_rendering import prepare_diagram_code
from mcp_core.core.mermaid_source import MERMAID_THEMES, prepare_mermaid_source

FLOW = "graph TD\n  A --> B"


@pytest.mark.parametrize(
    "code",
    [
        FLOW,
        "graph TD; A-->B;",
        'graph TD; A["line1\\nline2"]-->B',  # \n inside a label, not after the header
        "sequenceDiagram\n  Alice->>Bob: hi",
        "---\ntitle: T\n---\ngraph TD\n  A --> B",
        "%%{init: {'theme':'dark'}}%%\ngraph TD\n  A --> B",
        "",
    ],
)
def test_valid_source_is_unchanged(code: str) -> None:
    assert prepare_mermaid_source(code) == code


@pytest.mark.parametrize(
    "fenced",
    [
        "```mermaid\ngraph TD\n  A --> B\n```",
        "```\ngraph TD\n  A --> B\n```",
        "```Mermaid\ngraph TD\n  A --> B\n```\n",
        "  ```mermaid\ngraph TD\n  A --> B\n```  ",
        "```mermaid\r\ngraph TD\n  A --> B\n```",
    ],
)
def test_markdown_fence_is_unwrapped(fenced: str) -> None:
    assert prepare_mermaid_source(fenced) == FLOW


def test_prose_after_the_closing_fence_is_dropped() -> None:
    fenced = "```mermaid\ngraph TD\n  A --> B\n```\nHere is your diagram!"

    assert prepare_mermaid_source(fenced) == FLOW


def test_one_line_fence() -> None:
    assert (
        prepare_mermaid_source("```mermaid graph TD; A-->B;```") == "graph TD; A-->B;"
    )


def test_double_escaped_newlines_become_newlines() -> None:
    assert prepare_mermaid_source("graph TD\\n  A --> B") == FLOW
    assert (
        prepare_mermaid_source(
            "sequenceDiagram\\n  Alice->>Bob: hi\\n  Bob-->>Alice: yo"
        )
        == "sequenceDiagram\n  Alice->>Bob: hi\n  Bob-->>Alice: yo"
    )


def test_escaped_newlines_are_left_alone_when_real_newlines_exist() -> None:
    code = 'graph TD\n  A["a\\nb"] --> B'

    assert prepare_mermaid_source(code) == code


@pytest.mark.parametrize("char", ["\u200b", "\u200c", "\u200d", "\u2060"])
def test_zero_width_characters_are_removed(char: str) -> None:
    """Each of these makes real Mermaid fail with "Lexical error ... Unrecognized text"."""
    assert prepare_mermaid_source(f"graph TD\n  A{char} --> B") == FLOW


@pytest.mark.parametrize("char", ["\ufeff", "\u00a0"])
def test_harmless_invisible_characters_are_left_alone(char: str) -> None:
    """Mermaid accepts a BOM and non-breaking spaces, so the text is not rewritten."""
    code = f"graph TD\n  A[Hello{char}world] --> B"

    assert prepare_mermaid_source(code) == code


def test_preparation_is_idempotent() -> None:
    once = prepare_mermaid_source("```mermaid\ngraph TD\\n A-->B\n```", "dark")

    assert prepare_mermaid_source(once, "dark") == once


@pytest.mark.parametrize("theme", sorted(MERMAID_THEMES))
def test_theme_becomes_an_init_directive(theme: str) -> None:
    out = prepare_mermaid_source(FLOW, theme)

    assert out == f"%%{{init: {{'theme': '{theme}'}}}}%%\n{FLOW}"


def test_theme_is_case_insensitive() -> None:
    assert prepare_mermaid_source(FLOW, " Dark ").startswith(
        "%%{init: {'theme': 'dark'}}%%"
    )


@pytest.mark.parametrize("theme", [None, "", "cerulean", "not-a-theme"])
def test_unknown_or_missing_theme_is_ignored(theme: str | None) -> None:
    """A PlantUML theme name sent for a Mermaid diagram must not break it."""
    assert prepare_mermaid_source(FLOW, theme) == FLOW


def test_authors_own_init_directive_wins() -> None:
    code = "%%{init: {'theme':'forest'}}%%\n" + FLOW

    assert prepare_mermaid_source(code, "dark") == code


def test_theme_goes_after_frontmatter() -> None:
    code = "---\ntitle: My Flow\n---\n" + FLOW

    assert prepare_mermaid_source(code, "dark") == (
        "---\ntitle: My Flow\n---\n%%{init: {'theme': 'dark'}}%%\n" + FLOW
    )


def test_frontmatter_theme_wins() -> None:
    code = "---\nconfig:\n  theme: forest\n---\n" + FLOW

    assert prepare_mermaid_source(code, "dark") == code


def test_prepare_diagram_code_applies_it_for_mermaid_only() -> None:
    fenced = "```mermaid\n" + FLOW + "\n```"

    assert prepare_diagram_code(fenced, "mermaid", "dark") == (
        "%%{init: {'theme': 'dark'}}%%\n" + FLOW
    )
    # Other backends are untouched: a fence is not Mermaid's business there.
    assert prepare_diagram_code(fenced, "graphviz", "dark") == fenced
