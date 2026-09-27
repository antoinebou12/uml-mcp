"""Wait until a Kroki server and its companion renderers can render.

``/health`` only covers Kroki itself; Mermaid, BPMN, Excalidraw and blockdiag run in
companion containers that start later. This renders one real example per companion
(``mcp_core.kroki.health``; the same check as ``uml-mcp kroki status``):

    uv run python scripts/wait_for_kroki.py http://127.0.0.1:8001 --timeout 180
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_core.kroki.health import COMPANIONS, ready, wait_until_ready


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("url", help="Kroki base URL, e.g. http://127.0.0.1:8001")
    parser.add_argument("--timeout", type=float, default=180.0, help="seconds")
    parser.add_argument(
        "--types",
        default=",".join(COMPANIONS),
        help="comma-separated diagram types to render (default: the companions)",
    )
    args = parser.parse_args(argv)
    types = tuple(t for t in args.types.split(",") if t)
    report = wait_until_ready(args.url, args.timeout, types, trust_env=False)
    if ready(report):
        print(
            f"Kroki {report['version'] or ''} at {report['url']} renders {', '.join(types)}"
        )
        return 0
    if report["error"]:
        print(f"not ready: {report['error']}", file=sys.stderr)
    for dtype, check in report["companions"].items():
        if not check["ok"]:
            print(f"not ready: {dtype}: {check['detail']}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
