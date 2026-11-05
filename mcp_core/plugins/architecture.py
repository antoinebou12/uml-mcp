"""Portable, explicitly positioned architecture diagrams."""

from __future__ import annotations

import html
import json
import math
from itertools import pairwise
from typing import ClassVar

from .api import DiagramTypeSpec, RenderOutput
from .architecture_assets import validate_icon

EXAMPLE = json.dumps(
    {
        "title": "Application architecture",
        "theme": "dark",
        "width": 1000,
        "height": 540,
        "nodes": [
            {"id": "user", "name": "User", "role": "browser", "cx": 112, "top": 120},
            {
                "id": "app",
                "name": "Application",
                "role": "frontend",
                "cx": 342,
                "top": 120,
            },
            {"id": "api", "name": "API", "role": "backend", "cx": 487, "top": 120},
        ],
        "groups": [{"name": "Hosting", "nodes": ["app", "api"]}],
        "edges": [
            {"source": "user", "target": "app", "label": "HTTPS"},
            {"source": "app", "target": "api", "label": "RPC"},
        ],
    }
)


def _number(value):
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
    ):
        raise ValueError("Coordinates must be finite numbers")
    return value


def parse(code):
    try:
        spec = json.loads(code)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Source must be JSON: {exc.msg} at line {exc.lineno}"
        ) from exc
    if not isinstance(spec, dict):
        raise TypeError("Source must be a JSON object with nodes")
    width, height = spec.setdefault("width", 1000), spec.setdefault("height", 540)
    if not 200 <= _number(width) <= 10000 or not 200 <= _number(height) <= 10000:
        raise ValueError("Canvas dimensions must be between 200 and 10000")
    nodes = spec.get("nodes", [])
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 100:
        raise ValueError("Provide between 1 and 100 nodes")
    ids = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise TypeError("Each node must be an object with id, name, cx and top")
        if not isinstance(node.get("id"), str) or node["id"] in ids:
            raise ValueError("Node ids must be unique strings")
        ids.add(node["id"])
        if not isinstance(node.get("name"), str):
            raise TypeError(f"Node {node['id']} needs a name")
        if "cx" not in node or "top" not in node:
            raise ValueError(f"Node {node['id']} needs cx and top coordinates")
        cx, top = _number(node["cx"]), _number(node["top"])
        if cx < 66 or cx + 66 > width or top < 0 or top + 100 > height:
            raise ValueError(f"Node {node['id']} lies outside the canvas")
        icon = node.get("icon", "")
        if icon:
            validate_icon(icon)
    for i, a in enumerate(nodes):
        for b in nodes[i + 1 :]:
            if abs(a["cx"] - b["cx"]) < 140 and abs(a["top"] - b["top"]) < 140:
                raise ValueError(f"Nodes {a['id']} and {b['id']} need more spacing")
    for edge in spec.get("edges", []):
        if (
            not isinstance(edge, dict)
            or edge.get("source") not in ids
            or edge.get("target") not in ids
            or edge["source"] == edge["target"]
        ):
            raise ValueError("Edges need distinct existing source and target ids")
    for group in spec.get("groups", []):
        members = group.get("nodes") if isinstance(group, dict) else None
        if not isinstance(members, list) or not members:
            raise ValueError("Each group needs a name and a non-empty nodes list")
        unknown = [key for key in members if key not in ids]
        if unknown:
            raise ValueError(
                f"Group {group.get('name', '')} lists unknown nodes: {unknown}"
            )
    return spec


def _scene(spec):
    nodes = {n["id"]: n for n in spec["nodes"]}
    groups = []
    for group in spec.get("groups", []):
        members = [nodes[key] for key in group["nodes"]]
        left = min(n["cx"] for n in members) - 90
        top = min(n["top"] for n in members) - 60
        right = max(n["cx"] for n in members) + 90
        bottom = max(n["top"] for n in members) + 150
        if left < 0 or top < 0 or right > spec["width"] or bottom > spec["height"]:
            raise ValueError("Group padding extends outside canvas")
        groups.append((group, left, top, right - left, bottom - top))
    edges = []
    for edge in spec.get("edges", []):
        a, b = nodes[edge["source"]], nodes[edge["target"]]
        if a["top"] == b["top"]:
            direction = 1 if b["cx"] > a["cx"] else -1
            points = [
                (a["cx"] + 36 * direction, a["top"] + 30),
                (b["cx"] - 36 * direction, b["top"] + 30),
            ]
        elif a["cx"] == b["cx"]:
            down = b["top"] > a["top"]
            points = [
                (a["cx"], a["top"] + (106 if down else -6)),
                (b["cx"], b["top"] + (-6 if down else 106)),
            ]
        else:
            down = b["top"] > a["top"]
            start = (a["cx"], a["top"] + (106 if down else -6))
            end = (b["cx"], b["top"] + (-6 if down else 106))
            band = b["top"] - 25 if down else a["top"] - 25
            points = [start, (start[0], band), (end[0], band), end]
        if "via" in edge:
            via = edge["via"]
            if not isinstance(via, list) or len(via) > 20:
                raise ValueError("via must be a list of at most 20 coordinate pairs")
            if any(not isinstance(p, list) or len(p) != 2 for p in via):
                raise ValueError("Each via point must contain x and y")
            points = [
                points[0],
                *[(_number(p[0]), _number(p[1])) for p in via],
                points[-1],
            ]
        for x, y in points:
            if not 0 <= x <= spec["width"] or not 0 <= y <= spec["height"]:
                raise ValueError("Edge route leaves the canvas")
        for (x1, y1), (x2, y2) in pairwise(points):
            if x1 != x2 and y1 != y2:
                raise ValueError("Edge routes must be orthogonal")
        for other in nodes.values():
            for (x1, y1), (x2, y2) in pairwise(points):
                # At tile mid-height only the tile occupies space; below it,
                # protect the full 132px label box, including endpoint labels.
                half_width = 30 if y1 == y2 == other["top"] + 30 else 66
                if (
                    min(x1, x2) < other["cx"] + half_width
                    and max(x1, x2) > other["cx"] - half_width
                    and min(y1, y2) < other["top"] + 100
                    and max(y1, y2) > other["top"]
                ):
                    raise ValueError(
                        f"An edge crosses node {other['id']}; choose a clear via corridor"
                    )
        edges.append((edge, points))
    return groups, edges


class ArchitectureRenderer:
    name = "architecture"
    diagram_types: ClassVar[dict[str, DiagramTypeSpec]] = {
        "architecture": DiagramTypeSpec(
            "Positioned architecture tiles, vendor groups and labelled edges. JSON input; portable HTML or React TSX.",
            ("html", "tsx"),
            example=EXAMPLE,
            template=EXAMPLE,
            security_profile="sandboxed",
        )
    }

    def validate(self, diagram_type, code):
        try:
            _scene(parse(code))
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            return [str(exc)]
        return []

    def render(self, diagram_type, code, output_format):
        spec = parse(code)
        groups, edges = _scene(spec)
        dark = spec.get("theme") == "dark"
        paper, ink, rule, accent = (
            ("#0e1216", "#e6e9ee", "#242a31", "#4996ff")
            if dark
            else ("#fafbfc", "#252b35", "#e7eaef", "#2670de")
        )
        # One markup source keeps geometry identical in both packages.
        chunks = []
        esc = lambda value: html.escape(str(value), quote=True)
        for group, left, top, width, height in groups:
            chunks.append(
                f'<div style="position:absolute;left:{left}px;top:{top}px;width:{width}px;height:{height}px;border:1px solid #687482;border-radius:12px;background:#8888880a"><span style="position:absolute;left:12px;top:12px">{esc(group.get("name", ""))}</span></div>'
            )
        svg = [
            f'<svg width="{spec["width"]}" height="{spec["height"]}" viewBox="0 0 {spec["width"]} {spec["height"]}" style="position:absolute;inset:0"><defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="context-stroke"/></marker></defs>'
        ]
        for edge, points in edges:
            (x1, y1), (x2, y2) = points[0], points[1]
            path = "M" + " L".join(f"{x} {y}" for x, y in points)
            color = accent if not edge.get("neutral") else "#969da6"
            dash = ' stroke-dasharray="4 5"' if edge.get("dashed") else ""
            svg.append(
                f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.5" marker-end="url(#ar)"{dash}/>'
            )
            x, y = ((x1 + x2) / 2, y1 - 8) if y1 == y2 else (x1 + 10, (y1 + y2) / 2)
            svg.append(
                f'<text x="{x}" y="{y}" fill="{color}" text-anchor="middle" style="font:11px ui-monospace,monospace;paint-order:stroke;stroke:{paper};stroke-width:5px">{esc(edge.get("label", ""))}</text>'
            )
        chunks.append("".join(svg) + "</svg>")
        for node in spec["nodes"]:
            icon = (
                f'<img src="{esc(node["icon"])}" width="36" height="36" alt=""/>'
                if node.get("icon")
                else esc(node["name"][:1])
            )
            chunks.append(
                f'<div style="position:absolute;left:{node["cx"] - 66}px;top:{node["top"]}px;width:132px;text-align:center"><div style="width:60px;height:60px;margin:auto;background:white;color:#303744;border:1px solid #687482;border-radius:12px;display:flex;align-items:center;justify-content:center">{icon}</div><div style="margin-top:8px;font-size:13px"><span style="background:{paper}">{esc(node["name"])}</span></div><div style="margin-top:4px;font:10px ui-monospace,monospace;color:#929aa6"><span style="background:{paper}">{esc(node.get("role", ""))}</span></div></div>'
            )
        body = (
            f'<div style="overflow-x:auto;border:1px solid {rule};border-radius:10px"><div style="position:relative;width:{spec["width"]}px;height:{spec["height"]}px;background-color:{paper};color:{ink};font-family:system-ui,sans-serif;background-image:linear-gradient({rule} 1px,transparent 1px),linear-gradient(90deg,{rule} 1px,transparent 1px);background-size:24px 24px">'
            + "".join(chunks)
            + "</div></div>"
        )
        if output_format == "html":
            return RenderOutput(
                (
                    f'<!doctype html><html lang="en"><meta charset="utf-8"><title>{esc(spec.get("title", "Architecture"))}</title><body style="margin:0">'
                    + body
                    + "</body></html>"
                ).encode(),
                "text/html",
            )
        if output_format == "tsx":
            # HTML is converted to literal JSX with typed inline style objects.
            import re

            def style(match):
                values = {}
                for declaration in match[1].split(";"):
                    if not declaration:
                        continue
                    key, value = declaration.split(":", 1)
                    key = re.sub(r"-([a-z])", lambda m: m[1].upper(), key)
                    values[key] = value
                return "style={" + json.dumps(values) + "}"

            jsx = re.sub(r'style="([^"]*)"', style, body)
            for before, after in {
                "stroke-width": "strokeWidth",
                "marker-end": "markerEnd",
                "stroke-dasharray": "strokeDasharray",
                "text-anchor": "textAnchor",
            }.items():
                jsx = jsx.replace(before, after)
            jsx = re.sub(
                r">([^<]+)<",
                lambda m: ">{" + json.dumps(html.unescape(m[1])) + "}<",
                jsx,
            )
            return RenderOutput(
                (
                    "// Load Geist and JetBrains Mono in your app to restore the reference typography.\nexport default function ArchDiagram() { return ("
                    + jsx
                    + "); }\n"
                ).encode(),
                "text/tsx",
            )
        raise ValueError("architecture supports html and tsx")
