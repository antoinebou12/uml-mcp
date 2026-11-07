"""Static SVG: a layered tree from the project on the left to its deepest dependency."""

from __future__ import annotations

from collections import Counter
from xml.sax.saxutils import escape

from .layout import PILL_H, ROW, Tree, label

#: theme -> colour tokens. Kind colours stay recognisable in both themes.
PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#f7f8fb",
        "panel": "#ffffff",
        "ink": "#1b2333",
        "muted": "#5d6779",
        "line": "#c3cad6",
        "root": "#1f2a44",
        "root-ink": "#ffffff",
        "runtime": "#2563eb",
        "dev": "#7c3aed",
        "optional": "#0f9488",
        "peer": "#c0267a",
        "dup": "#d97706",
        "badge": "#e9edf3",
        "accent": "#dc2626",
    },
    "dark": {
        "bg": "#0f141c",
        "panel": "#161d29",
        "ink": "#e6ebf3",
        "muted": "#98a3b6",
        "line": "#3a4558",
        "root": "#e6ebf3",
        "root-ink": "#0f141c",
        "runtime": "#60a5fa",
        "dev": "#a78bfa",
        "optional": "#2dd4bf",
        "peer": "#f472b6",
        "dup": "#fbbf24",
        "badge": "#263042",
        "accent": "#f87171",
    },
}

KIND_LABELS = {
    "runtime": "runtime",
    "peer": "peer",
    "optional": "optional",
    "dev": "dev",
}

MARGIN = 24
HEADER = 96


def variables(theme: str) -> str:
    """The colour tokens of one theme as CSS custom properties."""
    return ";".join(f"--{k}:{v}" for k, v in PALETTES[theme].items())


def _rules() -> str:
    s = ".deps-svg "
    kinds = "".join(
        f"{s}.k-{k} .pill{{fill:var(--{k});fill-opacity:.14;stroke:var(--{k})}}"
        f"{s}.k-{k} .dot,{s}.k-{k} .fdot,{s}.lg-{k}{{fill:var(--{k})}}"
        f"{s}.e-{k}{{stroke:var(--{k})}}"
        for k in KIND_LABELS
    )
    return (
        f"{s}text{{font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}}"
        f"{s}.bg{{fill:var(--bg)}}"
        f"{s}.title{{font-size:18px;font-weight:700;fill:var(--ink)}}"
        f"{s}.sub{{font-size:12px;fill:var(--muted)}}"
        f"{s}.warn{{font-size:12px;fill:var(--dup)}}"
        f"{s}.lg{{font-size:11.5px;fill:var(--ink)}}"
        f"{s}.name{{font-size:11.5px;fill:var(--ink)}}"
        f"{s}.lic{{font-size:9.5px;fill:var(--muted)}}"
        f"{s}.badge{{fill:var(--badge)}}"
        f"{s}.pill{{stroke-width:1.2}}"
        f"{s}.edge{{fill:none;stroke-width:1.3;stroke-opacity:.55}}"
        f"{s}.fdot{{stroke:var(--bg);stroke-width:1.5}}"
        f"{s}.flabel{{font-size:10.5px;fill:var(--ink);paint-order:stroke;stroke:var(--bg);"
        "stroke-width:3px;stroke-linejoin:round}"
        f"{kinds}"
        f"{s}.root .pill{{fill:var(--root);fill-opacity:1;stroke:var(--root)}}"
        f"{s}.root .name{{fill:var(--root-ink);font-weight:700}}"
        f"{s}.root .lic{{fill:var(--root-ink);opacity:.8}}"
        f"{s}.root .badge{{fill:var(--root-ink);fill-opacity:.14}}"
        f"{s}.root .fdot{{fill:var(--root)}}"
        f"{s}.dup .pill,{s}.dup .fdot{{stroke:var(--dup);stroke-width:2;stroke-dasharray:4 3}}"
        f"{s}.dupmark{{fill:var(--dup);font-size:11px;font-weight:700}}"
        f"{s}.lg-dup{{fill:none;stroke:var(--dup);stroke-width:2;stroke-dasharray:4 3}}"
        f"{s}.toggle circle{{fill:var(--panel);stroke:var(--line);stroke-width:1.2}}"
        f"{s}.toggle text{{font-size:12px;font-weight:700;fill:var(--muted);text-anchor:middle}}"
        f"{s}.more{{font-size:10px;fill:var(--muted)}}"
        f"{s}.dim{{opacity:.25}}"
        f"{s}.edge.path{{stroke:var(--accent);stroke-opacity:1;stroke-width:2.4}}"
        f"{s}.node.path .pill,{s}.node.path .fdot{{stroke:var(--accent);stroke-width:2}}"
        f"{s}.node.match .pill,{s}.node.match .fdot{{stroke:var(--accent);stroke-width:2.2}}"
        f"{s}.node.sel .pill,{s}.node.sel .fdot{{stroke:var(--accent);stroke-width:3;"
        "stroke-dasharray:none}"
    )


#: Rules shared by the static SVG, the page and its exports; colours come from variables.
RULES = _rules()


def css(theme: str) -> str:
    """A self-contained stylesheet for one theme (static SVG and exports)."""
    return f".deps-svg{{{variables(theme)}}}{RULES}"


def counts(tree: Tree) -> dict[str, int]:
    """Totals for the subtitle and the legend."""
    shown = [tree.graph.packages[pid] for pid in tree.order[1:]]
    kinds = Counter(p.kind for p in shown)
    direct = sum(1 for pid in tree.order[1:] if tree.depth[pid] == 1)
    return {
        "packages": len(shown),
        "direct": direct,
        "transitive": len(shown) - direct,
        "duplicates": len(tree.duplicates),
        **{k: kinds.get(k, 0) for k in KIND_LABELS},
    }


def summary(tree: Tree) -> str:
    c = counts(tree)
    parts = [
        f"{tree.graph.source_kind}",
        f"{c['packages']} package{'s' if c['packages'] != 1 else ''}",
        f"{c['direct']} direct",
    ]
    if tree.graph.has_lock or c["transitive"]:
        parts.append(f"{c['transitive']} transitive")
    if c["duplicates"]:
        parts.append(f"{c['duplicates']} with several versions")
    return " · ".join(parts)


def cap_notice(tree: Tree) -> str:
    if not tree.capped:
        return ""
    return (
        f"Showing {len(tree.order) - 1} of {tree.total - 1} packages, closest to the "
        "project first. Raise plugins.settings.deps.max_nodes to draw more."
    )


def title_of(tree: Tree) -> str:
    graph = tree.graph
    if graph.title:
        return graph.title
    root = graph.packages[graph.root]
    return f"{label(root)} dependencies"


def render(tree: Tree, theme: str) -> str:
    theme = "light" if theme == "light" else "dark"
    packages = tree.graph.packages
    ranges = {(e.source, e.target): e.range for e in tree.edges}
    kinds = {(e.source, e.target): e.kind for e in tree.edges}
    dup_ids = {pid for ids in tree.duplicates.values() for pid in ids}
    rows = max((y for _, y in tree.pos.values()), default=0) / ROW + 1
    width = max(
        560,
        max(tree.pos[pid][0] + tree.widths[pid] for pid in tree.order) + 2 * MARGIN,
    )
    top = HEADER + (18 if tree.capped else 0) + 18 * min(len(tree.graph.notes), 3)
    height = top + rows * ROW + MARGIN
    ox, oy = MARGIN, top + PILL_H / 2

    out: list[str] = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
            f'width="{width:.0f}" height="{height:.0f}" role="img" class="deps-svg {theme}" '
            f'aria-label="{escape(title_of(tree), {chr(34): "&quot;"})}">'
        ),
        f"<style>{css(theme)}</style>",
        f'<rect class="bg" width="{width:.0f}" height="{height:.0f}"/>',
        f'<text class="title" x="{MARGIN}" y="34">{escape(title_of(tree))}</text>',
        f'<text class="sub" x="{MARGIN}" y="54">{escape(summary(tree))}</text>',
    ]
    # legend: kinds that appear, with their counts, then the duplicate marker
    c = counts(tree)
    lx = float(MARGIN)
    for kind, text in KIND_LABELS.items():
        if not c[kind]:
            continue
        out.append(
            f'<circle class="lg-{kind}" cx="{lx + 5:.1f}" cy="76" r="5"/>'
            f'<text class="lg" x="{lx + 15:.1f}" y="80">{text} {c[kind]}</text>'
        )
        lx += 30 + (len(text) + len(str(c[kind]))) * 6.6
    if tree.duplicates:
        out.append(
            f'<rect class="lg-dup" x="{lx:.1f}" y="70" width="22" height="12" rx="6"/>'
            f'<text class="lg" x="{lx + 28:.1f}" y="80">several versions</text>'
        )
    y = HEADER + 4
    if tree.capped:
        out.append(
            f'<text class="warn" x="{MARGIN}" y="{y}">{escape(cap_notice(tree))}</text>'
        )
        y += 18
    for note in tree.graph.notes[:3]:
        out.append(f'<text class="sub" x="{MARGIN}" y="{y}">{escape(note)}</text>')
        y += 18

    out.append(f'<g transform="translate({ox},{oy})">')
    for pid in tree.order[1:]:
        owner = tree.parent[pid]
        assert owner is not None
        x1 = tree.pos[owner][0] + tree.widths[owner]
        y1 = tree.pos[owner][1]
        x2, y2 = tree.pos[pid]
        mid = (x1 + x2) / 2
        out.append(
            f'<path class="edge e-{kinds.get((owner, pid), "runtime")}" '
            f'd="M{x1:.1f},{y1:.1f} C{mid:.1f},{y1:.1f} {mid:.1f},{y2:.1f} {x2:.1f},{y2:.1f}"/>'
        )
    for pid in tree.order:
        package = packages[pid]
        x, yy = tree.pos[pid]
        w = tree.widths[pid]
        owner = tree.parent[pid]
        text = label(package, ranges.get((owner, pid), "") if owner else "")
        classes = ["node", "root" if package.root else f"k-{package.kind}"]
        if pid in dup_ids:
            classes.append("dup")
        tip = [text, package.kind or "project"]
        if package.license:
            tip.append(package.license)
        if pid in dup_ids:
            tip.append("several versions in the tree")
        out.append(
            f'<g class="{" ".join(classes)}" transform="translate({x:.1f},{yy - PILL_H / 2:.1f})">'
            f"<title>{escape(' · '.join(tip))}</title>"
            f'<rect class="pill" width="{w:.1f}" height="{PILL_H}" rx="{PILL_H / 2}"/>'
        )
        if not package.root:
            out.append(f'<circle class="dot" cx="11" cy="{PILL_H / 2}" r="4"/>')
        tx = 20 if not package.root else 11
        shown = text if len(text) <= 46 else text[:45] + "…"
        out.append(
            f'<text class="name" x="{tx}" y="{PILL_H / 2 + 4}">{escape(shown)}</text>'
        )
        if package.license:
            lic = (
                package.license
                if len(package.license) <= 12
                else package.license[:11] + "…"
            )
            bw = 8 + len(lic) * 5.6
            out.append(
                f'<rect class="badge" x="{w - bw - 4:.1f}" y="4" width="{bw:.1f}" '
                f'height="{PILL_H - 8}" rx="{(PILL_H - 8) / 2}"/>'
                f'<text class="lic" x="{w - bw:.1f}" y="{PILL_H / 2 + 3.5}">{escape(lic)}</text>'
            )
        if pid in dup_ids:
            out.append(
                f'<text class="dupmark" x="{w + 4:.1f}" y="{PILL_H / 2 + 4}">×{len(tree.duplicates[package.name.lower()])}</text>'
            )
        out.append("</g>")
    out.append("</g></svg>")
    return "".join(out)
