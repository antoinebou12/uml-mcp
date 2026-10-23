"""Offline eval for published prompts, per-type skills, and uml://recipes.

    uv run python scripts/eval_skills_prompts_recipes.py
    uv run python scripts/eval_skills_prompts_recipes.py --json

Optional visual sheet (needs Kroki/network)::

    uv run python scripts/build_catalog_sheet.py --recipes
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_core.quality.eval_surface import run_eval


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    args = parser.parse_args(argv)
    report = run_eval()
    if args.json:
        print(
            json.dumps(
                {
                    "ok": report.ok,
                    "counts": report.counts,
                    "issues": [
                        {
                            "severity": i.severity,
                            "area": i.area,
                            "target": i.target,
                            "message": i.message,
                        }
                        for i in report.issues
                    ],
                },
                indent=2,
            )
        )
    else:
        for i in report.issues:
            print(f"{i.severity.upper():7} {i.area}:{i.target}: {i.message}")
        print(
            f"prompts={report.counts['prompts_published']} "
            f"type_skills={report.counts['type_skills']} "
            f"recipes={report.counts['recipes']} "
            f"errors={report.counts['errors']} "
            f"warnings={report.counts['warnings']}"
        )
        print("PASS" if report.ok else "FAIL")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
