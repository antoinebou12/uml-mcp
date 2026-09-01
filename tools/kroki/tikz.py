"""TikZ diagram URL generation, template library, and LaTeX utilities.

Provides TikZ/PGF graphics support via Kroki: URL generation,
standalone document wrapping, library auto-detection, and pre-built templates.
"""

import base64
import logging
import re
from dataclasses import dataclass

from .kroki import LANGUAGE_OUTPUT_SUPPORT, Kroki

logger = logging.getLogger(__name__)

# TikZ supported output formats from Kroki
TIKZ_FORMATS: list[str] = LANGUAGE_OUTPUT_SUPPORT.get(
    "tikz", ["png", "svg", "jpeg", "pdf"]
)

# Overleaf accepts base64-encoded LaTeX via data URI (optional edit URL)
OVERLEAF_BASE = "https://www.overleaf.com/docs"


@dataclass(frozen=True)
class TikZUrls:
    """URLs and code for a TikZ diagram (image, optional editor, source)."""

    image_url: str
    """URL to the rendered diagram (Kroki)."""
    edit_url: str | None
    """URL to open in an online editor (Overleaf) or None if not available."""
    code: str
    """The TikZ/LaTeX source code."""


# Patterns that imply specific TikZ libraries (command/style -> library name)
_LIBRARY_HINTS = [
    (
        re.compile(r"\\node\s*\[[^\]]*?(?:circle|ellipse|diamond|regular polygon)"),
        "shapes",
    ),
    (re.compile(r"\\draw\s*\[[^\]]*?->"), "arrows"),
    (re.compile(r"\\draw\s*\[[^\]]*?<-"), "arrows"),
    (
        re.compile(
            r"below\s*of\s*=|above\s*of\s*=|left\s*of\s*=|right\s*of\s*=|"
            r"below\s*=\s*[^]]*\s+of\s+|above\s*=\s*[^]]*\s+of\s+|"
            r"left\s*=\s*[^]]*\s+of\s+|right\s*=\s*[^]]*\s+of\s+|"
            r"(?:^|[,{\s\[])(?:left|right|above|below)(?:\s+(?:left|right|above|below))*=\s*of\s"
        ),
        "positioning",
    ),
    (re.compile(r"\\pgfmathparse|\\pgfmathsetlength|\\pgfmathresult"), "calc"),
    (re.compile(r"decorate|decoration\s*=\s*\{"), "decorations.pathreplacing"),
    (re.compile(r"pattern\s*=\s*"), "patterns"),
    (re.compile(r"fit\s*=\s*|\\fit"), "fit"),
    (
        re.compile(r"\\begin\s*\{\s*scope\s*\}|\\begin\s*\{\s*axis\s*\}|\\addplot"),
        "pgfplots",
    ),
    (re.compile(r"\\begin\s*\{\s*axis\s*\}|\\addplot|\\pgfplotsset"), "pgfplots"),
    (re.compile(r"mindmap|level\s+\d+\s+concept"), "mindmap"),
    (re.compile(r"\\node\s*\[[^\]]*?state|accepting|initial"), "automata"),
    (re.compile(r"child\s*\{|edge\s+from\s+parent"), "trees"),
    (re.compile(r"arrows\.meta|Arrow|Bracket"), "arrows.meta"),
    (re.compile(r"angle|pic\s*\{\s*angle"), "angles"),
    (re.compile(r'quotes|"\s*[^"]+\s*"'), "quotes"),
    (re.compile(r"backgrounds|scope.*background"), "backgrounds"),
    (
        re.compile(
            r"circuit|\\draw\s*\([^)]*\)\s*(?:to\s*)?(?:resistor|capacitor|inductor)"
        ),
        "circuits",
    ),
    (re.compile(r"3d|canvas\s*=\s*|z\s*=\s*"), "3d"),
]

# Explicit \usetikzlibrary{...} extraction
_USETIKZLIBRARY_RE = re.compile(
    r"\\usetikzlibrary\s*\{([^}]+)\}",
    re.IGNORECASE | re.DOTALL,
)

# Whole-line preamble directives to hoist out of the document body (snippet mode)
_USETIKZLIBRARY_LINE_RE = re.compile(
    r"^\s*\\usetikzlibrary\s*\{[^}]*\}\s*$", re.IGNORECASE
)
_USEPACKAGE_TIKZ_LINE_RE = re.compile(
    r"^\s*\\usepackage\s*\{\s*tikz\s*\}\s*$", re.IGNORECASE
)
_USEPACKAGE_PGFPLOTS_LINE_RE = re.compile(
    r"^\s*\\usepackage\s*\{\s*pgfplots\s*\}\s*$", re.IGNORECASE
)


def _strip_hoistable_preamble_lines(snippet: str) -> tuple[str, bool]:
    """Remove lines that belong in the preamble, not inside \\begin{document}.

    Returns (body, stripped_usepackage_pgfplots).
    """
    lines = snippet.splitlines()
    out: list[str] = []
    stripped_pgfplots = False
    for line in lines:
        if (
            _USETIKZLIBRARY_LINE_RE.match(line)
            or _USEPACKAGE_TIKZ_LINE_RE.match(line)
            or _USEPACKAGE_PGFPLOTS_LINE_RE.match(line)
        ):
            if _USEPACKAGE_PGFPLOTS_LINE_RE.match(line):
                stripped_pgfplots = True
            continue
        out.append(line)
    return "\n".join(out).strip(), stripped_pgfplots


def get_required_libraries(tikz_code: str) -> list[str]:
    """Infer required TikZ libraries from diagram code.

    Scans for \\usetikzlibrary{...} and common commands/styles that imply
    specific libraries. Returns a deduplicated list of library names.

    Args:
        tikz_code: Raw TikZ or full LaTeX document content.

    Returns:
        List of TikZ library names (e.g. ['shapes', 'arrows', 'positioning']).
    """
    seen: set[str] = set()
    libraries: list[str] = []

    # Explicit usetikzlibrary
    for m in _USETIKZLIBRARY_RE.finditer(tikz_code):
        for part in m.group(1).split(","):
            lib = part.strip().strip("\"'")
            if lib and lib not in seen:
                seen.add(lib)
                libraries.append(lib)

    # Hint-based detection
    for pattern, lib in _LIBRARY_HINTS:
        if pattern.search(tikz_code) and lib not in seen:
            seen.add(lib)
            libraries.append(lib)

    return libraries


def wrap_tikz_standalone(
    tikz_code: str,
    libraries: list[str] | None = None,
    *,
    border: str = "2pt",
    extra_packages: list[str] | None = None,
) -> str:
    """Wrap TikZ snippet in a minimal standalone LaTeX document.

    If the code already contains \\documentclass, it is returned unchanged.
    Otherwise wraps in standalone with tikz and optional libraries.

    Args:
        tikz_code: TikZ picture or full document.
        libraries: TikZ libraries to load (default: auto-detect from code).
        border: Standalone border option (e.g. '2pt', '10pt').
        extra_packages: Additional \\usepackage{...} to add (e.g. ['pgfplots']).

    Returns:
        Full LaTeX document string.
    """
    code = tikz_code.strip()
    if "\\documentclass" in code:
        return code

    original = code
    body, stripped_pgfplots_usepackage = _strip_hoistable_preamble_lines(code)
    if not body:
        body = original
        stripped_pgfplots_usepackage = False

    if libraries is None:
        libraries = list(get_required_libraries(original))
        if stripped_pgfplots_usepackage and "pgfplots" not in libraries:
            libraries.append("pgfplots")
    else:
        libraries = list(libraries)

    lib_line = ""
    if libraries:
        lib_line = "\\usetikzlibrary{" + ",".join(libraries) + "}\n"

    pkgs = list(extra_packages) if extra_packages else []

    extra = ""
    for pkg in pkgs:
        extra += f"\\usepackage{{{pkg}}}\n"

    # pgfplots needs to be loaded for \begin{axis} (or stripped \usepackage{pgfplots})
    if "pgfplots" in libraries and "pgfplots" not in pkgs:
        extra = "\\usepackage{pgfplots}\n\\pgfplotsset{compat=1.18}\n" + extra

    return f"""\\documentclass[border={border}]{{standalone}}
\\usepackage{{tikz}}
{extra}{lib_line}\\begin{{document}}
{body}
\\end{{document}}
"""


def generate_tikz_urls(
    tikz_code: str,
    output_format: str = "svg",
    base_url: str = "https://kroki.io",
    *,
    wrap_standalone: bool = True,
    include_edit_url: bool = True,
) -> TikZUrls:
    """Generate Kroki image URL and optional edit URL for a TikZ diagram.

    Args:
        tikz_code: TikZ/LaTeX code (snippet or full document).
        output_format: One of 'svg', 'pdf', 'png', 'jpeg'.
        base_url: Kroki server base URL.
        wrap_standalone: If True, wrap snippet in standalone document when needed.
        include_edit_url: If True, set edit_url to Overleaf data-URI link when possible.

    Returns:
        TikZUrls with image_url, edit_url (or None), and normalized code.

    Raises:
        ValueError: If output_format is not supported for TikZ.
    """
    if output_format not in TIKZ_FORMATS:
        raise ValueError(
            f"Unsupported output format '{output_format}' for TikZ. "
            f"Supported: {', '.join(TIKZ_FORMATS)}"
        )

    if wrap_standalone:
        code = wrap_tikz_standalone(tikz_code)
    else:
        code = tikz_code.strip()

    kroki = Kroki(base_url=base_url)
    image_url = kroki.get_url("tikz", code, output_format)

    edit_url: str | None = None
    if include_edit_url:
        try:
            encoded = base64.urlsafe_b64encode(code.encode("utf-8")).decode("ascii")
            # Overleaf project from template; user can paste snippet. Alternative: data URI.
            edit_url = f"{OVERLEAF_BASE}?snip_uri=data:text/plain;base64,{encoded}"
        except Exception as e:  # noqa: BLE001
            logger.debug("Could not build TikZ edit URL: %s", e)

    return TikZUrls(image_url=image_url, edit_url=edit_url, code=code)


class TikZTemplateLibrary:
    """Pre-built TikZ templates for common diagram patterns."""

    FLOWCHART = r"""
\begin{tikzpicture}[node distance=2cm, auto]
  \node[rectangle, draw] (start) {Start};
  \node[diamond, draw, below of=start, aspect=2] (decision) {Decision?};
  \node[rectangle, draw, below left=1.2cm and 1cm of decision] (yes) {Yes};
  \node[rectangle, draw, below right=1.2cm and 1cm of decision] (no) {No};
  \draw[->] (start) -- (decision);
  \draw[->] (decision) -- node[near start, left] {Y} (yes);
  \draw[->] (decision) -- node[near start, right] {N} (no);
\end{tikzpicture}
"""

    SIMPLE_GRAPH = r"""
\begin{tikzpicture}
  \node[circle, draw] (1) at (0,0) {1};
  \node[circle, draw] (2) at (2,0) {2};
  \node[circle, draw] (3) at (1,1.5) {3};
  \draw (1) -- (2);
  \draw (2) -- (3);
  \draw (3) -- (1);
\end{tikzpicture}
"""

    MATH_PLOT = r"""
\begin{tikzpicture}
  \begin{axis}[xlabel=$x$, ylabel=$f(x)$, grid=major, width=8cm, height=6cm]
    \addplot[blue, thick, domain=-2:2] {x^2};
  \end{axis}
\end{tikzpicture}
"""

    TREE = r"""
\begin{tikzpicture}[level distance=1.2cm, sibling distance=1.5cm, edge from parent path={(\tikzparentnode) -- (\tikzchildnode)}]
  \node[circle, draw] {root}
    child { node[circle, draw] {A} }
    child { node[circle, draw] {B}
      child { node[circle, draw] {C} }
      child { node[circle, draw] {D} }
    };
\end{tikzpicture}
"""

    AUTOMATA = r"""
\begin{tikzpicture}[shorten >=1pt, node distance=2.5cm, auto]
  \node[state, initial] (q0) {$q_0$};
  \node[state, accepting, right of=q0] (q1) {$q_1$};
  \draw[->] (q0) to[loop above] node {0} (q0);
  \draw[->] (q0) to node {1} (q1);
  \draw[->] (q1) to[loop above] node {1} (q1);
  \draw[->] (q1) to node {0} (q0);
\end{tikzpicture}
"""

    GEOMETRY_CIRCLE = r"""
\begin{tikzpicture}
  \draw (0,0) circle (1.5);
  \draw (-1.5,0) -- (1.5,0);
  \draw (0,-1.5) -- (0,1.5);
  \fill (0,0) circle (2pt) node[below right] {O};
\end{tikzpicture}
"""

    MINDMAP_SIMPLE = r"""
\begin{tikzpicture}[mindmap, grow cyclic, every node/.style=concept, concept color=blue!40]
  \node {Root}
    child { node {A} }
    child { node {B} }
    child { node {C} };
\end{tikzpicture}
"""

    CIRCUIT_SIMPLE = r"""
\begin{tikzpicture}[circuit ee IEC]
  \node[bulb] (lamp) at (2,0) {};
  \draw (0,0) to[resistor] (1.5,0) to (lamp) to (2,-1) to (0,-1) to[battery] (0,0);
\end{tikzpicture}
"""

    COORDINATE_GRID = r"""
\begin{tikzpicture}[scale=0.8]
  \draw[step=1, gray, thin] (-2,-2) grid (2,2);
  \draw[thick, ->] (-2,0) -- (2.2,0) node[right] {$x$};
  \draw[thick, ->] (0,-2) -- (0,2.2) node[above] {$y$};
\end{tikzpicture}
"""

    BLOCK_DIAGRAM = r"""
\begin{tikzpicture}[node distance=1.5cm, block/.style={rectangle, draw, minimum width=2cm}]
  \node[block] (A) {Input};
  \node[block, right of=A] (B) {Process};
  \node[block, right of=B] (C) {Output};
  \draw[->] (A) -- (B);
  \draw[->] (B) -- (C);
\end{tikzpicture}
"""

    @classmethod
    def get(cls, name: str) -> str:
        """Return a template by name. Names: flowchart, graph, math_plot, tree, automata, geometry_circle, mindmap_simple, circuit_simple, coordinate_grid, block_diagram."""
        key = name.strip().lower().replace("-", "_")
        templates = {
            "flowchart": cls.FLOWCHART,
            "graph": cls.SIMPLE_GRAPH,
            "math_plot": cls.MATH_PLOT,
            "tree": cls.TREE,
            "automata": cls.AUTOMATA,
            "geometry_circle": cls.GEOMETRY_CIRCLE,
            "mindmap_simple": cls.MINDMAP_SIMPLE,
            "circuit_simple": cls.CIRCUIT_SIMPLE,
            "coordinate_grid": cls.COORDINATE_GRID,
            "block_diagram": cls.BLOCK_DIAGRAM,
        }
        if key not in templates:
            raise ValueError(
                f"Unknown TikZ template: {name}. Choose from: {', '.join(templates)}"
            )
        return templates[key].strip()

    @classmethod
    def list_names(cls) -> list[str]:
        """Return list of available template names."""
        return [
            "flowchart",
            "graph",
            "math_plot",
            "tree",
            "automata",
            "geometry_circle",
            "mindmap_simple",
            "circuit_simple",
            "coordinate_grid",
            "block_diagram",
        ]
