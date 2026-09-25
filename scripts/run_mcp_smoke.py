"""Automated version of tests/prompts/chatgpt_mcp_smoke_test.md.

Runs the smoke steps with a real MCP client instead of a chat model:

    # in-process server (no network needed for discovery/validation):
    USE_REAL_FASTMCP=1 MCP_URL_ONLY=true uv run python scripts/run_mcp_smoke.py --offline
    # remote / enterprise server (bearer token from Entra, e.g. az account get-access-token):
    uv run python scripts/run_mcp_smoke.py --url https://mcp.contoso.com/mcp --token "$TOKEN"

Prints one line per step and ends with ``MCP_SMOKE_TEST: PASS`` or
``MCP_SMOKE_TEST: FAIL - <reason>`` (exit code 0 / 1).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SEQUENCE = """sequenceDiagram
  participant Client
  participant Server
  Client->>Server: request
  Server-->>Client: response"""


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


async def run(
    url: str | None, token: str | None, offline: bool
) -> list[tuple[str, str, str]]:
    from fastmcp import Client

    if url:
        client = Client(url, auth=token) if token else Client(url)
    else:
        os.environ.setdefault("USE_REAL_FASTMCP", "1")
        os.environ.setdefault("MOCK_FASTMCP", "0")
        from mcp_core.core.server import get_mcp_server

        client = Client(get_mcp_server())

    steps: list[tuple[str, str, str]] = []

    def record(name: str, ok: bool | None, detail: str) -> None:
        status = "PASS" if ok else ("SKIP" if ok is None else "FAIL")
        steps.append((name, status, detail))
        print(f"[{status}] {name}: {detail}")

    async with client:
        tools = {t.name for t in await client.list_tools()}
        record(
            "tools",
            {"list_diagram_types", "validate_uml"} <= tools
            and bool({"generate_uml", "generate_uml_image"} & tools),
            ", ".join(sorted(tools)),
        )
        prompts = {p.name for p in await client.list_prompts()}
        record("prompts", "architecture_report" in prompts, f"{len(prompts)} prompts")

        types = _structured(
            await client.call_tool("list_diagram_types", {"query": "mermaid"})
        )
        blob = json.dumps(types)
        record(
            "list_diagram_types",
            "mermaid" in blob,
            "goat/umlet present"
            if ("goat" in blob or "umlet" in blob)
            else "mermaid listed",
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
        record(
            "validate_uml", bool(val.get("valid")), str(val.get("errors") or "valid")
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
        record(
            "validate_uml rejects packed", packed.get("valid") is False, "strict mode"
        )

        try:
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
        except Exception as exc:  # noqa: BLE001 - e.g. HTTP 403 insufficient_scope
            record("generate_uml svg", False, f"{type(exc).__name__}: {str(exc)[:160]}")
            return steps
        url_ok = str(gen.get("url", "")).startswith("https://")
        record(
            "generate_uml svg",
            url_ok and bool(gen.get("playground")),
            f"url={gen.get('url', '')[:60]}… playground={'yes' if gen.get('playground') else 'no'}",
        )
        record("no local paths", "output/" not in json.dumps(gen), "no output/*.png")

        if offline:
            record(
                "generate_uml_image", None, "skipped (--offline: needs Kroki egress)"
            )
        else:
            res = await client.call_tool(
                "generate_uml_image",
                {"diagram_type": "mermaid", "code": SEQUENCE, "output_format": "png"},
            )
            has_image = any(getattr(b, "type", "") == "image" for b in res.content)
            record("generate_uml_image", has_image, "inline ImageContent returned")
    return steps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="remote MCP URL (default: in-process server)")
    parser.add_argument(
        "--token",
        default=os.environ.get("MCP_SMOKE_TOKEN"),
        help="bearer token for protected servers (or MCP_SMOKE_TOKEN)",
    )
    parser.add_argument(
        "--offline", action="store_true", help="skip steps needing Kroki"
    )
    args = parser.parse_args(argv)
    steps = asyncio.run(run(args.url, args.token, args.offline))
    failed = [name for name, status, _ in steps if status == "FAIL"]
    print(
        "MCP_SMOKE_TEST: PASS"
        if not failed
        else f"MCP_SMOKE_TEST: FAIL - {', '.join(failed)}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
