"""The look of the D3 diagrams, shared by the architecture, topology and force pages.

The grammar is that of a clean engineering diagram: a dotted canvas, compact monospace
cards with a tinted fill, a coloured outline and a small icon, straight slate arrows with a
label that breaks the line behind it, dashed boundaries titled on their border, and a legend
that counts what is drawn. Colour carries meaning: every node belongs to one of seven
categories, and a legend names the ones in use.

All colours are CSS variables on the diagram's root element, so one stylesheet serves the
light theme, the dark theme and ``auto`` (the system setting), and the page can switch theme
without redrawing anything. A standalone SVG embeds this stylesheet; the HTML page carries it
once, in a ``<style>`` element that its Content-Security-Policy pins by hash.
"""

from __future__ import annotations

#: The categories a node can have. Each one has a fill and an outline colour.
CATEGORIES = (
    "frontend",
    "backend",
    "database",
    "cloud",
    "security",
    "messagebus",
    "external",
)

CATEGORY_LABELS = {
    "frontend": "Edge",
    "backend": "Compute",
    "database": "Data",
    "cloud": "Platform",
    "security": "Security",
    "messagebus": "Messaging",
    "external": "External",
}

LIGHT = {
    "bg": "#f4f5f7",
    "panel": "#ffffff",
    "dot": "#d9dee5",
    "text": "#111827",
    "muted": "#5b6474",
    "dim": "#9aa3b2",
    "arrow": "#94a3b8",
    "emphasis": "#059669",
    "async": "#7c3aed",
    "mask": "#ffffff",
    "frontend-fill": "rgba(34, 211, 238, 0.15)",
    "frontend-stroke": "#0891b2",
    "backend-fill": "rgba(52, 211, 153, 0.18)",
    "backend-stroke": "#059669",
    "database-fill": "rgba(167, 139, 250, 0.2)",
    "database-stroke": "#7c3aed",
    "cloud-fill": "rgba(251, 191, 36, 0.18)",
    "cloud-stroke": "#d97706",
    "security-fill": "rgba(251, 113, 133, 0.15)",
    "security-stroke": "#e11d48",
    "messagebus-fill": "rgba(251, 146, 60, 0.15)",
    "messagebus-stroke": "#ea580c",
    "external-fill": "rgba(148, 163, 184, 0.18)",
    "external-stroke": "#64748b",
}

DARK = {
    "bg": "#020617",
    "panel": "#0b1220",
    "dot": "rgba(148, 163, 184, 0.16)",
    "text": "#ffffff",
    "muted": "#94a3b8",
    "dim": "#475569",
    "arrow": "#64748b",
    "emphasis": "#34d399",
    "async": "#a78bfa",
    "mask": "#0f172a",
    "frontend-fill": "rgba(8, 51, 68, 0.4)",
    "frontend-stroke": "#22d3ee",
    "backend-fill": "rgba(6, 78, 59, 0.4)",
    "backend-stroke": "#34d399",
    "database-fill": "rgba(76, 29, 149, 0.4)",
    "database-stroke": "#a78bfa",
    "cloud-fill": "rgba(120, 53, 15, 0.3)",
    "cloud-stroke": "#fbbf24",
    "security-fill": "rgba(136, 19, 55, 0.4)",
    "security-stroke": "#fb7185",
    "messagebus-fill": "rgba(251, 146, 60, 0.3)",
    "messagebus-stroke": "#fb923c",
    "external-fill": "rgba(30, 41, 59, 0.5)",
    "external-stroke": "#94a3b8",
}

#: group type -> (category colour it borrows, border style)
GROUP_STYLES = {
    "boundary": ("security", "dashed"),
    "system": ("external", "solid"),
    "env": ("database", "solid"),
    "region": ("cloud", "dashed"),
    "zone": ("messagebus", "dotted"),
    "vpc": ("backend", "solid"),
    "subnet": ("frontend", "solid"),
    "cluster": ("frontend", "dashed"),
    "account": ("external", "dashed"),
}

#: Brand-ish accents of the providers, for the small provider badge on a node.
PROVIDER_COLORS = {
    "aws": "#ED7100",
    "azure": "#0078D4",
    "gcp": "#4285F4",
    "kubernetes": "#326CE5",
    "onprem": "#64748B",
    "tech": "#475569",
}

MONO = (
    'ui-monospace, "JetBrains Mono", "SF Mono", Menlo, Consolas, '
    '"Liberation Mono", monospace'
)
SANS = (
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", '
    "Arial, sans-serif"
)


def _vars(palette: dict[str, str]) -> str:
    return ";".join(f"--{name}:{value}" for name, value in palette.items())


def diagram_css() -> str:
    """The stylesheet of a diagram, scoped to its root ``svg.d3d`` element."""
    categories = "".join(
        f".d3d .cat-{c}{{--c-fill:var(--{c}-fill);--c-stroke:var(--{c}-stroke)}}"
        for c in CATEGORIES
    )
    categories += "".join(
        f".d3d .g-{c}{{--g-stroke:var(--{c}-stroke)}}" for c in CATEGORIES
    )
    providers = "".join(
        f".d3d .prov-{name}{{fill:{color}}}" for name, color in PROVIDER_COLORS.items()
    )
    return (
        f".d3d{{{_vars(LIGHT)};font-family:{MONO};color:var(--text)}}"
        f".d3d.dark{{{_vars(DARK)}}}"
        f"@media (prefers-color-scheme:dark){{.d3d.auto{{{_vars(DARK)}}}}}"
        + categories
        + providers
        + ".d3d .panel{fill:var(--panel)}"
        ".d3d .dot{fill:var(--dot)}"
        f".d3d .t-heading{{fill:var(--text);font-size:16px;font-weight:700;font-family:{SANS}}}"
        ".d3d .t-title{fill:var(--text);font-size:13px;font-weight:700}"
        ".d3d .t-sub{fill:var(--muted);font-size:10px}"
        ".d3d .t-port{fill:var(--muted);font-size:10px}"
        ".d3d .t-badge{font-size:8px;font-weight:700;letter-spacing:.08em}"
        ".d3d .t-mono{fill:#fff;font-size:9px;font-weight:700;text-anchor:middle}"
        ".d3d .t-edge{fill:var(--muted);font-size:10px;text-anchor:middle;"
        "paint-order:stroke;stroke:var(--mask);stroke-width:7px;stroke-linejoin:round}"
        ".d3d .t-group{fill:var(--g-stroke);font-size:11px;font-weight:700;"
        "paint-order:stroke;stroke:var(--mask);stroke-width:7px;stroke-linejoin:round}"
        ".d3d .t-legend{fill:var(--muted);font-size:11px}"
        ".d3d .t-legend-head{fill:var(--text);font-size:12px;font-weight:700}"
        ".d3d .t-count{fill:var(--dim);font-size:10px}"
        ".d3d .card{fill:var(--c-fill);stroke:var(--c-stroke);stroke-width:2}"
        ".d3d .mask{fill:var(--mask)}"
        ".d3d .glyph{fill:none;stroke:var(--c-stroke);stroke-width:1.8;"
        "stroke-linecap:round;stroke-linejoin:round}"
        ".d3d .port{fill:var(--c-stroke);stroke:var(--mask);stroke-width:1.5}"
        ".d3d .group-box{fill:var(--g-stroke);fill-opacity:.06;stroke:var(--g-stroke);"
        "stroke-width:1.5}"
        ".d3d .group-box.dashed{stroke-dasharray:8 4}"
        ".d3d .group-box.dotted{stroke-dasharray:2 4}"
        ".d3d .edge-line{fill:none;stroke:var(--arrow);stroke-width:1.6}"
        ".d3d .edge.dashed .edge-line{stroke:var(--async);stroke-dasharray:6 4}"
        ".d3d .edge.primary .edge-line{stroke:var(--emphasis);stroke-width:2.2}"
        ".d3d .head{fill:var(--arrow)}"
        ".d3d .head-dashed{fill:var(--async)}"
        ".d3d .head-primary{fill:var(--emphasis)}"
        ".d3d .swatch{fill:var(--c-fill);stroke:var(--c-stroke);stroke-width:1.5}"
        ".d3d .f-mask{fill:var(--mask)}"
        ".d3d .f-node{fill:var(--c-fill);stroke:var(--c-stroke);stroke-width:2}"
        ".d3d .f-link{stroke:var(--arrow);stroke-opacity:.7}"
        ".d3d .t-flabel{fill:var(--text);font-size:11px;paint-order:stroke;"
        "stroke:var(--mask);stroke-width:5px;stroke-linejoin:round;text-anchor:middle}"
        ".d3d .t-llabel{fill:var(--muted);font-size:10px;paint-order:stroke;"
        "stroke:var(--mask);stroke-width:5px;stroke-linejoin:round;text-anchor:middle}"
        # interaction (only the page uses these)
        ".d3d.hl .node:not(.on),.d3d.hl .edge:not(.on),.d3d.hl .f-link:not(.on)"
        "{opacity:.2}"
        ".d3d .edge.on .edge-line{stroke-width:2.8}"
        ".d3d .node.dragging .card,.d3d .node.dragging .f-node{stroke-width:3.2}"
        ".d3d .pinned .f-node{stroke-dasharray:3 2}"
        ".d3d.flow .edge-line{stroke-dasharray:6 8;animation:d3flow 1s linear infinite}"
        ".d3d.flow .edge.dashed .edge-line{stroke-dasharray:4 6}"
        "@keyframes d3flow{to{stroke-dashoffset:-14}}"
        "@media (prefers-reduced-motion:reduce){.d3d.flow .edge-line{animation:none}}"
    )


def static_diagram_css(theme: str) -> str:
    """Resolve palette variables for SVG rasterizers without CSS variable support."""
    import re

    palette = dict(DARK if theme == "dark" else LIGHT)
    palette.update(
        {
            "c-fill": palette["external-fill"],
            "c-stroke": palette["external-stroke"],
            "g-stroke": palette["external-stroke"],
        }
    )
    css = diagram_css().split(".d3d .panel", 1)[1].split(".d3d.hl", 1)[0]
    rules = re.findall(r"([^{}]+)\{([^{}]+)\}", ".d3d .panel" + css)

    def resolve(body: str, values: dict[str, str]) -> str:
        return re.sub(r"var\(--([\w-]+)\)", lambda m: values[m[1]], body)

    out = [f".d3d{{font-family:{MONO};color:{palette['text']}}}"]
    for selector, body in rules:
        out.append(f"{selector}{{{resolve(body, palette)}}}")
        for category in CATEGORIES:
            if "--c-" in body:
                values = {
                    **palette,
                    "c-fill": palette[f"{category}-fill"],
                    "c-stroke": palette[f"{category}-stroke"],
                }
                out.append(
                    f"{selector.replace('.d3d', f'.d3d .cat-{category}')}{{{resolve(body, values)}}}"
                )
            if "--g-" in body:
                values = {**palette, "g-stroke": palette[f"{category}-stroke"]}
                out.append(
                    f"{selector.replace('.d3d', f'.d3d .g-{category}')}{{{resolve(body, values)}}}"
                )
    out.extend(
        f".d3d .prov-{name}{{fill:{color}}}" for name, color in PROVIDER_COLORS.items()
    )
    return "".join(out)


def chrome_css() -> str:
    """The stylesheet of the page around the diagram (toolbar, panel, menus)."""
    light = {
        "page": LIGHT["bg"],
        "panel": LIGHT["panel"],
        "line": "#e5e7eb",
        "ink": LIGHT["text"],
        "soft": LIGHT["muted"],
        "pill": "rgba(255,255,255,.92)",
        "pill-line": "#cbd5e1",
        "button": "#ffffff",
        "primary": "#111827",
        "primary-ink": "#ffffff",
        "accent": "#0891b2",
    }
    dark = {
        "page": DARK["bg"],
        "panel": DARK["panel"],
        "line": "#1e293b",
        "ink": "#e2e8f0",
        "soft": DARK["muted"],
        "pill": "rgba(15,23,42,.8)",
        "pill-line": "#334155",
        "button": "rgba(15,23,42,.9)",
        "primary": "#ffffff",
        "primary-ink": "#0f172a",
        "accent": "#22d3ee",
    }
    return (
        f"html{{{_vars(light)};color-scheme:light}}"
        f"html.dark{{{_vars(dark)};color-scheme:dark}}"
        f"@media (prefers-color-scheme:dark){{html.auto{{{_vars(dark)};color-scheme:dark}}}}"
        "html,body{height:100%;margin:0}"
        f"body{{font:14px/1.4 {SANS};background:var(--page);color:var(--ink);"
        "display:flex;flex-direction:column;padding:14px 18px 18px;box-sizing:border-box;gap:10px}"
        "header{display:flex;align-items:center;gap:12px}"
        "h1{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:700;margin:0;"
        "flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
        "h1:before{content:'';width:11px;height:11px;border-radius:50%;background:var(--accent);"
        "box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 22%,transparent);flex:none}"
        ".bar{display:flex;align-items:center;gap:4px;padding:5px;border-radius:12px;"
        "background:var(--pill);border:1px solid var(--pill-line)}"
        "button,summary{font:inherit;font-size:13px;padding:5px 11px;border:1px solid transparent;"
        "background:transparent;color:var(--ink);border-radius:8px;cursor:pointer;list-style:none}"
        "summary::-webkit-details-marker{display:none}"
        "button:hover,button:focus-visible,summary:hover,summary:focus-visible{"
        "border-color:var(--accent);outline:none}"
        "button[aria-pressed=true]{background:var(--accent);color:var(--primary-ink)}"
        ".menu{position:relative}"
        ".menu summary{background:var(--primary);color:var(--primary-ink);font-weight:600}"
        ".menu .items{position:absolute;right:0;top:calc(100% + 6px);z-index:6;min-width:150px;"
        "display:flex;flex-direction:column;padding:5px;border-radius:12px;background:var(--button);"
        "border:1px solid var(--pill-line);box-shadow:0 8px 24px rgba(15,23,42,.18)}"
        ".menu .items button{text-align:left}"
        "main{flex:1;min-height:0;position:relative;border-radius:16px;overflow:hidden;"
        "background:var(--panel);border:1px solid var(--line)}"
        "svg{display:block;width:100%;height:100%;cursor:grab;touch-action:none}"
        "svg.dragging{cursor:grabbing}"
        ".node{cursor:move}"
        ".zoom{position:absolute;right:14px;bottom:14px;display:flex;align-items:center;gap:2px}"
        ".zoom output{min-width:46px;text-align:center;font:12px ui-monospace,Menlo,Consolas,monospace;"
        "color:var(--soft)}"
        ".hint{position:absolute;left:16px;bottom:12px;font-size:12px;color:var(--soft);"
        "pointer-events:none}"
        "#tip{position:fixed;pointer-events:none;max-width:260px;padding:6px 9px;border-radius:8px;"
        "background:#0f172a;color:#f8fafc;font-size:12px;opacity:0;transition:opacity .1s;z-index:9}"
        "#tip.show{opacity:1}"
    )
