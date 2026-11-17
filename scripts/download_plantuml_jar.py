#!/usr/bin/env python3
"""Download a pinned ``plantuml.jar`` into ``vendor/plantuml/`` (gitignored).

Usage:
    uv run python scripts/download_plantuml_jar.py
    uv run python scripts/download_plantuml_jar.py --force
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "vendor" / "plantuml" / "plantuml.jar"

# PlantUML 1.2025.4 — update tag + sha256 together when bumping.
PLANTUML_TAG = "v1.2025.4"
PLANTUML_URL = (
    "https://github.com/plantuml/plantuml/releases/download/"
    f"{PLANTUML_TAG}/plantuml-{PLANTUML_TAG.lstrip('v')}.jar"
)
# Leave empty to skip digest verification (still fine for local use).
PLANTUML_SHA256 = ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Destination path (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even when the destination already exists",
    )
    args = parser.parse_args()
    out: Path = args.out
    if out.is_file() and not args.force:
        print(f"Already present: {out}")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".partial")
    print(f"Downloading {PLANTUML_URL}")
    urllib.request.urlretrieve(PLANTUML_URL, tmp)
    if PLANTUML_SHA256:
        got = _sha256(tmp)
        if got.lower() != PLANTUML_SHA256.lower():
            tmp.unlink(missing_ok=True)
            print(
                f"SHA-256 mismatch: expected {PLANTUML_SHA256}, got {got}",
                file=sys.stderr,
            )
            return 1
    tmp.replace(out)
    print(f"Wrote {out} ({out.stat().st_size} bytes)")
    print(
        "Set PLANTUML_JAR_PATH to this file, or leave unset to auto-detect vendor/plantuml/plantuml.jar"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
