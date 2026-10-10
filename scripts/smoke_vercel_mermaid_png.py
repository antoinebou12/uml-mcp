"""Production smoke: Mermaid PNG via hosted MCP + tools/list contract.

Fails if generate_uml_image is missing from tools/list, or if Mermaid PNG
fallback URLs still use the broken mermaid.ink /png/ path (must be /img/?type=).

It also fetches the links ``generate_uml`` returns (Mermaid PNG, Mermaid SVG,
PlantUML SVG) and requires a real image: URL-only mode used to hand back Kroki links
without contacting Kroki, so a dead Mermaid link was reported as a success.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

import httpx

DEFAULT_MCP_URL = "https://uml-mcp.vercel.app/mcp"
TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
MERMAID_CODE = """sequenceDiagram
  participant Client
  participant Server
  Client->>Server: request
  Server-->>Client: response"""
PLANTUML_CODE = (
    "@startuml\nClient -> Server: request\nServer --> Client: response\n@enduml"
)


def _parse_sse_or_json(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    if text.startswith("{"):
        return json.loads(text)
    datas = [
        line[5:].strip()
        for line in text.splitlines()
        if line.startswith("data:") and line[5:].strip() not in ("", "[DONE]")
    ]
    if not datas:
        raise ValueError(f"Unparseable MCP response: {text[:200]}")
    return json.loads(datas[-1])


def _structured(rpc: dict[str, Any]) -> dict[str, Any]:
    result = rpc.get("result") or {}
    sc = result.get("structuredContent")
    if isinstance(sc, dict):
        return sc
    return {}


def _tool_names(rpc: dict[str, Any]) -> set[str]:
    result = rpc.get("result") or {}
    tools = result.get("tools") or []
    return {str(t.get("name")) for t in tools if isinstance(t, dict)}


def _link_problem(
    client: httpx.Client, label: str, url: str, expect: str, attempts: int = 2
) -> str | None:
    """Fetch ``url`` and return a description of what is wrong, or None if it is a real image."""
    if not url:
        return f"{label}: no url returned"
    problem = ""
    for attempt in range(attempts):
        if attempt:
            time.sleep(2.0)  # one retry for a transient upstream blip
        try:
            response = client.get(url)
        except httpx.HTTPError as exc:
            problem = f"{label}: GET {url[:90]} failed: {exc!r}"
            continue
        body = response.content
        if response.status_code != 200:
            problem = f"{label}: link returned HTTP {response.status_code}: {url[:90]}"
        elif expect == "svg" and b"<svg" not in body[:4096]:
            problem = f"{label}: link did not return an SVG: {url[:90]}"
        elif expect == "png" and not body.startswith(b"\x89PNG"):
            problem = f"{label}: link did not return a PNG: {url[:90]}"
        else:
            return None
    return problem


def _generate_uml_url(
    client: httpx.Client,
    mcp_url: str,
    headers: dict[str, str],
    request_id: int,
    diagram_type: str,
    code: str,
    output_format: str,
) -> str:
    call = client.post(
        mcp_url,
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": "generate_uml",
                "arguments": {
                    "diagram_type": diagram_type,
                    "code": code,
                    "output_format": output_format,
                },
            },
        },
        headers=headers,
    )
    call.raise_for_status()
    return str(_structured(_parse_sse_or_json(call.text)).get("url") or "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mcp-url",
        default=os.environ.get("MCP_URL", DEFAULT_MCP_URL),
        help="Streamable HTTP MCP endpoint (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    mcp_url = args.mcp_url.rstrip("/")
    if not mcp_url.endswith("/mcp"):
        # Allow root URL and append /mcp
        mcp_url = f"{mcp_url}/mcp"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    req_id = 0

    def next_id() -> int:
        nonlocal req_id
        req_id += 1
        return req_id

    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        init = client.post(
            mcp_url,
            json={
                "jsonrpc": "2.0",
                "id": next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "mermaid-png-smoke", "version": "1.0"},
                },
            },
            headers=headers,
        )
        init.raise_for_status()
        sid = init.headers.get("mcp-session-id")
        if sid:
            headers["mcp-session-id"] = sid
        client.post(
            mcp_url,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=headers,
        )

        listed = client.post(
            mcp_url,
            json={
                "jsonrpc": "2.0",
                "id": next_id(),
                "method": "tools/list",
                "params": {},
            },
            headers=headers,
        )
        listed.raise_for_status()
        names = _tool_names(_parse_sse_or_json(listed.text))
        required = {
            "list_diagram_types",
            "generate_uml",
            "generate_uml_image",
            "generate_uml_batch",
            "validate_uml",
        }
        missing = sorted(required - names)
        if missing:
            print(f"SMOKE_FAIL missing tools: {missing}; got={sorted(names)}")
            return 1
        print(f"tools/list OK ({len(names)} tools)")

        # Prefer generate_uml png so we exercise force_fetch + mermaid fallback URL.
        call = client.post(
            mcp_url,
            json={
                "jsonrpc": "2.0",
                "id": next_id(),
                "method": "tools/call",
                "params": {
                    "name": "generate_uml",
                    "arguments": {
                        "diagram_type": "mermaid",
                        "code": MERMAID_CODE,
                        "output_format": "png",
                    },
                },
            },
            headers=headers,
        )
        call.raise_for_status()
        rpc = _parse_sse_or_json(call.text)
        if rpc.get("error"):
            print(f"SMOKE_FAIL tools/call error: {rpc['error']}")
            return 1
        sc = _structured(rpc)
        url = str(sc.get("url") or "")
        text_blob = json.dumps(rpc)
        # Broken legacy mermaid.ink path
        if "mermaid.ink/png/" in url or "mermaid.ink/png/" in text_blob:
            print(f"SMOKE_FAIL legacy mermaid.ink /png/ URL still present: {url[:120]}")
            return 1
        if (
            sc.get("source") == "mermaid_ink"
            and url
            and ("/img/" not in url or "type=png" not in url)
        ):
            print(f"SMOKE_FAIL expected mermaid.ink /img/?type=png, got: {url[:160]}")
            return 1
        if not url and not sc.get("content_base64") and "error" in text_blob.lower():
            print(f"SMOKE_FAIL no url/base64 in result: {text_blob[:400]}")
            return 1
        # Soft check: success path should have url or base64
        if not url and not sc.get("content_base64"):
            # ToolError may have been raised as text-only content
            content = (rpc.get("result") or {}).get("content") or []
            joined = " ".join(
                str(c.get("text", "")) for c in content if isinstance(c, dict)
            )
            if "error" in joined.lower() or "failed" in joined.lower():
                print(f"SMOKE_FAIL render failed: {joined[:300]}")
                return 1
            print(f"SMOKE_FAIL empty artifact: {text_blob[:400]}")
            return 1

        # The links must resolve to real images, not just look right.
        problems: list[str] = []
        if url:
            problems.append(_link_problem(client, "mermaid png", url, "png") or "")
        for label, dtype, code in (
            ("mermaid svg", "mermaid", MERMAID_CODE),
            ("plantuml svg", "plantuml", PLANTUML_CODE),
        ):
            link = _generate_uml_url(
                client, mcp_url, headers, next_id(), dtype, code, "svg"
            )
            problems.append(_link_problem(client, label, link, "svg") or "")
        problems = [p for p in problems if p]
        if problems:
            for problem in problems:
                print(f"SMOKE_FAIL link check: {problem}")
            return 1
        print("link check OK (mermaid png, mermaid svg, plantuml svg resolve)")

        print(
            "SMOKE_PASS",
            f"source={sc.get('source')}",
            f"url_ok={bool(url)}",
            f"base64={bool(sc.get('content_base64'))}",
            f"playground={bool(sc.get('playground'))}",
            f"display_markdown={bool(sc.get('display_markdown'))}",
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
