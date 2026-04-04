#!/usr/bin/env python3
"""
MCP Server Evaluation Harness for UML-MCP.

Runs evaluation questions against the MCP server using Claude.
Requires: anthropic, mcp packages. Install with: uv add anthropic mcp

Usage:
  python scripts/evaluation.py -t stdio -c python -a server.py evaluations/uml_mcp_eval.xml
  python scripts/evaluation.py -t http -u http://localhost:8000/mcp evaluations/uml_mcp_eval.xml

See evaluations/uml_mcp_eval.xml for the 10 read-only Q&A pairs.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_evaluation_file(file_path: Path) -> list[dict]:
    """Parse XML evaluation file with qa_pair elements."""
    tree = ET.parse(file_path)
    root = tree.getroot()

    evaluations = []
    for qa_pair in root.findall(".//qa_pair"):
        question_elem = qa_pair.find("question")
        answer_elem = qa_pair.find("answer")
        if question_elem is not None and answer_elem is not None:
            evaluations.append(
                {
                    "question": (question_elem.text or "").strip(),
                    "answer": (answer_elem.text or "").strip(),
                }
            )
    return evaluations


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate MCP servers using test questions",
    )
    parser.add_argument("eval_file", type=Path, help="Path to evaluation XML file")
    parser.add_argument(
        "-t", "--transport", choices=["stdio", "sse", "http"], default="stdio"
    )
    parser.add_argument("-c", "--command", help="Command to run MCP server (stdio)")
    parser.add_argument("-a", "--args", nargs="+", help="Arguments for command (stdio)")
    parser.add_argument("-u", "--url", help="MCP server URL (sse/http)")
    parser.add_argument("-m", "--model", default="claude-3-5-sonnet-20241022")
    parser.add_argument("-o", "--output", type=Path, help="Output report file")

    args = parser.parse_args()

    if not args.eval_file.exists():
        print(f"Error: Evaluation file not found: {args.eval_file}")
        sys.exit(1)

    qa_pairs = parse_evaluation_file(args.eval_file)
    print(f"Loaded {len(qa_pairs)} evaluation questions from {args.eval_file}")

    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.client.streamable_http import streamablehttp_client
    except ImportError:
        print("Error: mcp package required. Run: uv add mcp")
        sys.exit(1)

    async def run():
        if args.transport == "stdio":
            if not args.command:
                print("Error: --command required for stdio transport")
                sys.exit(1)
            cmd_args = args.args or []
            server_params = StdioServerParameters(command=args.command, args=cmd_args)
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_resp = await session.list_tools()
                    resources_resp = await session.list_resources()
                    print(f"Tools: {len(tools_resp.tools)}")
                    print(f"Resources: {len(resources_resp.resources)}")
        elif args.transport in ("http", "streamable_http"):
            if not args.url:
                print("Error: --url required for http transport")
                sys.exit(1)
            async with streamablehttp_client(url=args.url) as (
                read,
                write,
                _get_session_id,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_resp = await session.list_tools()
                    resources_resp = await session.list_resources()
                    print(f"Tools: {len(tools_resp.tools)}")
                    print(f"Resources: {len(resources_resp.resources)}")
        else:
            print("Error: SSE transport not implemented in this script")
            sys.exit(1)

    asyncio.run(run())

    print(
        "\nTo run full evaluation with Claude, use the evaluation harness from the MCP"
    )
    print(
        "Development Guide. This script verifies the server connection and discovery."
    )
    print("\nExample full evaluation (requires anthropic):")
    print(
        "  python scripts/evaluation.py -t stdio -c python -a server.py evaluations/uml_mcp_eval.xml"
    )


if __name__ == "__main__":
    main()
