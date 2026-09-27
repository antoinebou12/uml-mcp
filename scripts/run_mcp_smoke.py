"""Automated version of tests/prompts/chatgpt_mcp_smoke_test.md.

Runs the smoke steps with a real MCP client instead of a chat model:

    # in-process server (no network needed for discovery/validation):
    USE_REAL_FASTMCP=1 MCP_URL_ONLY=true uv run python scripts/run_mcp_smoke.py --offline
    # a server backed by a local Kroki (docker compose up -d), diagram URLs are http://
    uv run python scripts/run_mcp_smoke.py --url http://127.0.0.1:8000/mcp --allow-http
    # remote / enterprise server (bearer token from Entra, e.g. az account get-access-token):
    uv run python scripts/run_mcp_smoke.py --url https://mcp.contoso.com/mcp --token "$TOKEN"

Rendered output is checked, not just its presence: the SVG must parse and show the
diagram's labels, the PNG must decode with a real size. Prints one line per step and
ends with ``MCP_SMOKE_TEST: PASS|FAIL - <reason>`` and ``MCP_BATCH_TEST: PASS|FAIL``
(exit code 0 only when both pass). ``--json`` writes the step report to a file.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_core.quality.render_check import (
    RenderCheckError,
    check_png,
    check_svg,
)

SEQUENCE = """sequenceDiagram
  participant Client
  participant Server
  Client->>Server: request
  Server-->>Client: response"""

BATCH = [
    ("graph TD; Client-->MCP; MCP-->Kroki; Kroki-->MCP; MCP-->Client;", ("Kroki",)),
    (
        (
            "sequenceDiagram\n  participant A\n  participant B\n"
            "  A->>B: MCP 2026 request\n  B-->>A: Stateless response"
        ),
        ("MCP 2026 request", "Stateless response"),
    ),
]


@dataclass
class Step:
    phase: str
    name: str
    status: str  # PASS | FAIL | SKIP
    detail: str


def _structured(result: Any) -> dict[str, Any]:
    data = getattr(result, "structured_content", None) or getattr(result, "data", None)
    if isinstance(data, dict):
        return data
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            try:
                parsed = json.loads(text)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return {}


def _svg_check(result: dict[str, Any], labels: tuple[str, ...]) -> str | None:
    """None when the result holds an SVG showing ``labels``, else the problem."""
    encoded = result.get("content_base64")
    if not encoded:
        return "no content_base64 (MCP_URL_ONLY?)"
    try:
        check_svg(base64.b64decode(encoded), labels)
    except (RenderCheckError, ValueError) as exc:
        return str(exc)
    return None


class Runner:
    def __init__(self, allow_http: bool) -> None:
        self.steps: list[Step] = []
        self.schemes = ("https://", "http://") if allow_http else ("https://",)

    def record(self, phase: str, name: str, ok: bool | None, detail: str) -> None:
        status = "PASS" if ok else ("SKIP" if ok is None else "FAIL")
        self.steps.append(Step(phase, name, status, detail))
        print(f"[{status}] {phase}/{name}: {detail}")

    def url_ok(self, value: Any) -> bool:
        return str(value or "").startswith(self.schemes)

    def failed(self, phase: str) -> list[str]:
        return [s.name for s in self.steps if s.phase == phase and s.status == "FAIL"]

    async def smoke(self, client: Any, offline: bool) -> None:
        tools = {t.name for t in await client.list_tools()}
        self.record(
            "smoke",
            "tools",
            {"list_diagram_types", "validate_uml"} <= tools
            and bool({"generate_uml", "generate_uml_image"} & tools),
            ", ".join(sorted(tools)),
        )
        prompts = {p.name for p in await client.list_prompts()}
        self.record(
            "smoke", "prompts", "architecture_report" in prompts, f"{len(prompts)}"
        )

        types = _structured(
            await client.call_tool("list_diagram_types", {"query": "mermaid"})
        )
        blob = json.dumps(types)
        drift = "goat/umlet present" if ("goat" in blob or "umlet" in blob) else ""
        self.record(
            "smoke", "list_diagram_types", "mermaid" in blob, drift or "mermaid"
        )

        val = _structured(
            await client.call_tool(
                "validate_uml",
                {
                    "diagram_type": "mermaid",
                    "code": SEQUENCE,
                    "output_format": "svg",
                    "strict": True,
                },
            )
        )
        self.record(
            "smoke",
            "validate_uml",
            bool(val.get("valid")),
            str(val.get("errors") or "valid"),
        )
        packed = _structured(
            await client.call_tool(
                "validate_uml",
                {
                    "diagram_type": "mermaid",
                    "output_format": "svg",
                    "strict": True,
                    "code": "sequenceDiagram; participant A; A->>B: x;",
                },
            )
        )
        self.record(
            "smoke", "validate_uml rejects packed", packed.get("valid") is False, ""
        )
        if not val.get("valid"):
            return  # the prompt only renders after a successful validation

        gen = _structured(
            await client.call_tool(
                "generate_uml",
                {
                    "diagram_type": "mermaid",
                    "code": SEQUENCE,
                    "output_format": "svg",
                    "scale": 1.0,
                },
            )
        )
        self.record(
            "smoke",
            "generate_uml svg",
            self.url_ok(gen.get("url")) and bool(gen.get("playground")),
            f"url={str(gen.get('url', ''))[:60]} playground="
            f"{'yes' if gen.get('playground') else 'no'} {gen.get('error') or ''}",
        )
        if offline:
            self.record("smoke", "svg content", None, "skipped (--offline)")
        else:
            problem = _svg_check(gen, ("Client", "Server", "request", "response"))
            self.record(
                "smoke", "svg content", problem is None, problem or "labels shown"
            )
        self.record(
            "smoke", "no local paths", "output/" not in json.dumps(gen), "no output/"
        )

        if offline:
            self.record("smoke", "inline image", None, "skipped (--offline)")
            return
        if "generate_uml_image" in tools:
            res = await client.call_tool(
                "generate_uml_image",
                {"diagram_type": "mermaid", "code": SEQUENCE, "output_format": "png"},
            )
            images = [b for b in res.content if getattr(b, "type", "") == "image"]
            png = base64.b64decode(images[0].data) if images else b""
            source = "generate_uml_image"
        else:  # the prompt's fallback: raster force-fetch through generate_uml
            out = _structured(
                await client.call_tool(
                    "generate_uml",
                    {
                        "diagram_type": "mermaid",
                        "code": SEQUENCE,
                        "output_format": "png",
                    },
                )
            )
            png = base64.b64decode(out.get("content_base64") or "")
            source = "generate_uml png"
        try:
            width, height = check_png(png)
        except RenderCheckError as exc:
            self.record("smoke", "inline image", False, f"{source}: {exc}")
        else:
            self.record(
                "smoke", "inline image", True, f"{source}: PNG {width}x{height}"
            )

    async def batch(self, client: Any, offline: bool) -> None:
        out = _structured(
            await client.call_tool(
                "generate_uml_batch",
                {
                    "items": [
                        {
                            "diagram_type": "mermaid",
                            "code": code,
                            "output_format": "svg",
                        }
                        for code, _ in BATCH
                    ]
                },
            )
        )
        results = out.get("results") or []
        self.record(
            "batch", "results", len(results) == len(BATCH), f"{len(results)} results"
        )
        for index, (result, (_, labels)) in enumerate(
            zip(results, BATCH, strict=False), 1
        ):
            ok = not result.get("error") and self.url_ok(result.get("url"))
            detail = (
                f"url={'yes' if result.get('url') else 'no'} "
                f"playground={'yes' if result.get('playground') else 'no'}"
            )
            if ok and not offline:
                problem = _svg_check(result, labels)
                ok, detail = problem is None, problem or f"{detail}, labels shown"
            self.record("batch", f"item {index}", ok, result.get("error") or detail)


async def run(
    url: str | None, token: str | None, offline: bool, allow_http: bool = False
) -> Runner:
    from fastmcp import Client

    if url:
        client = Client(url, auth=token, timeout=120) if token else Client(url)
    else:
        os.environ.setdefault("USE_REAL_FASTMCP", "1")
        os.environ.setdefault("MOCK_FASTMCP", "0")
        from mcp_core.core.server import get_mcp_server

        client = Client(get_mcp_server())

    runner = Runner(allow_http)
    async with client:
        for phase in (runner.smoke, runner.batch):
            try:
                await phase(client, offline)
            except Exception as exc:  # noqa: BLE001 - e.g. HTTP 403 insufficient_scope
                runner.record(
                    phase.__name__,
                    "error",
                    False,
                    f"{type(exc).__name__}: {str(exc)[:160]}",
                )
    return runner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--url", help="remote MCP URL (default: in-process server)")
    parser.add_argument(
        "--token",
        default=os.environ.get("MCP_SMOKE_TOKEN"),
        help="bearer token for protected servers (or MCP_SMOKE_TOKEN)",
    )
    parser.add_argument(
        "--offline", action="store_true", help="skip steps needing Kroki"
    )
    parser.add_argument(
        "--allow-http",
        action="store_true",
        help="accept http:// diagram URLs (a local Kroki)",
    )
    parser.add_argument("--json", metavar="PATH", help="write the step report here")
    args = parser.parse_args(argv)
    runner = asyncio.run(run(args.url, args.token, args.offline, args.allow_http))
    lines = []
    for phase, label in (("smoke", "MCP_SMOKE_TEST"), ("batch", "MCP_BATCH_TEST")):
        failed = runner.failed(phase)
        lines.append(
            f"{label}: PASS" if not failed else f"{label}: FAIL - {', '.join(failed)}"
        )
    print("\n".join(lines))
    if args.json:
        report = {"summary": lines, "steps": [asdict(s) for s in runner.steps]}
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if all(line.endswith("PASS") for line in lines) else 1


if __name__ == "__main__":
    raise SystemExit(main())
