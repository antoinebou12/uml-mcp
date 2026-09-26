"""Wait until a Kroki server and its companion renderers can render.

``/health`` only covers Kroki itself; Mermaid, BPMN, Excalidraw and blockdiag run in
companion containers that start later. This renders one real example per companion:

    uv run python scripts/wait_for_kroki.py http://127.0.0.1:8001 --timeout 180
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.kroki.kroki_templates import DiagramExamples

COMPANIONS = ("mermaid", "blockdiag", "bpmn", "excalidraw")


def pending(client: httpx.Client, url: str, types: tuple[str, ...]) -> dict[str, str]:
    """Types that cannot render yet, with the reason."""
    waiting: dict[str, str] = {}
    for dtype in types:
        try:
            response = client.post(
                f"{url}/{dtype}/svg",
                content=DiagramExamples.get_example(dtype).encode(),
                headers={"Content-Type": "text/plain"},
            )
            if response.status_code != 200 or not response.content:
                waiting[dtype] = f"HTTP {response.status_code} {response.text[:80]}"
        except httpx.HTTPError as exc:
            waiting[dtype] = f"{type(exc).__name__}: {exc}"
    return waiting


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
    url = args.url.rstrip("/")
    types = tuple(t for t in args.types.split(",") if t)
    deadline = time.monotonic() + args.timeout
    with httpx.Client(trust_env=False, timeout=30) as client:
        while True:
            waiting = pending(client, url, types)
            if not waiting:
                print(f"Kroki at {url} renders {', '.join(types)}")
                return 0
            if time.monotonic() > deadline:
                for dtype, reason in waiting.items():
                    print(f"not ready: {dtype}: {reason}", file=sys.stderr)
                return 1
            time.sleep(3)


if __name__ == "__main__":
    raise SystemExit(main())
