"""Runtime checks aligned with pyproject requires-python (3.12 <= x < 3.15)."""

from __future__ import annotations

import sys


def test_python_version_supported() -> None:
    v = sys.version_info[:2]
    assert v >= (3, 12), f"expected Python >= 3.12, got {sys.version}"
    assert v < (3, 15), f"expected Python < 3.15, got {sys.version}"


def test_mcp_core_import_smoke() -> None:
    import importlib

    m = importlib.import_module("mcp_core")
    assert m.__spec__ is not None
