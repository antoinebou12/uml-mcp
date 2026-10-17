"""The cloud architecture page: every PlantUML example is sound and renders with its icons.

The structural checks always run. Rendering needs a real Kroki, like the other tiered
tests: ``UML_MCP_TEST_KROKI_URL`` for a local one, or ``UML_MCP_TEST_PUBLIC_KROKI=1`` for
https://kroki.io. A wrong include name (``ComputeEngine`` for ``Compute_Engine``) is the
usual way these examples break, and only a real render notices.
"""

from __future__ import annotations

import re

import httpx
import pytest

from tests.fixtures_real import ROOT

DOC = ROOT / "docs/diagrams/cloud-architecture.md"
BLOCKS = re.findall(
    r"```plantuml\n(.*?)\n```", DOC.read_text(encoding="utf-8"), re.DOTALL
)
LIBRARIES = ("awslib", "azure", "gcp", "kubernetes", "C4")


def block_id(block: str) -> str:
    first = re.search(r"!include <([\w/\-]+)>", block)
    return first.group(1) if first else "block"


def test_the_page_has_an_example_for_each_library() -> None:
    includes = " ".join(re.findall(r"!include <([\w/\-]+)>", "\n".join(BLOCKS)))
    for library in LIBRARIES:
        assert f"{library}/" in includes, library


@pytest.mark.parametrize("block", BLOCKS, ids=block_id)
def test_each_example_is_a_complete_plantuml_source(block: str) -> None:
    assert block.startswith("@startuml") and block.rstrip().endswith("@enduml")
    for include in re.findall(r"!include (.+)", block):
        assert re.fullmatch(
            r"<(awslib|azure|gcp|kubernetes|C4)/[\w/\-]+>", include.strip()
        ), include


@pytest.mark.parametrize("block", BLOCKS, ids=block_id)
def test_each_example_renders_on_a_real_kroki(kroki_tier, block: str) -> None:
    if not kroki_tier.real:
        pytest.skip("rendering these needs a real Kroki, not the fake one")
    with httpx.Client(trust_env=kroki_tier.name == "public", timeout=90) as client:
        response = client.post(
            f"{kroki_tier.url}/plantuml/svg",
            content=block.encode(),
            headers={"Content-Type": "text/plain"},
        )
    assert response.status_code == 200, response.text[:300]
    svg = response.text
    assert "<svg" in svg and "cannot include" not in svg
    macro_labels = re.findall(r'^\w+\(\w+, "([^"]+)"', block, re.MULTILINE)
    for label in macro_labels:
        assert label in svg, label
    if "!include <C4/" not in block:  # C4 draws boxes; the icon libraries draw images
        assert "<image" in svg, "no icon was drawn"
