"""Tests for the TikZ module (URL generation, templates, library detection, wrapping)."""

import pytest

from tools.kroki.tikz import (
    TIKZ_FORMATS,
    TikZTemplateLibrary,
    TikZUrls,
    generate_tikz_urls,
    get_required_libraries,
    wrap_tikz_standalone,
)


def test_tikz_url_generation():
    """generate_tikz_urls returns TikZUrls with Kroki image URL for TikZ."""
    code = r"\draw (0,0) circle (1cm);"
    urls = generate_tikz_urls(code, output_format="svg")
    assert isinstance(urls, TikZUrls)
    assert urls.code
    assert "kroki.io" in urls.image_url
    assert "/tikz/svg/" in urls.image_url
    assert (
        urls.edit_url is None
        or "overleaf" in urls.edit_url.lower()
        or "docs" in urls.edit_url
    )


def test_tikz_url_generation_with_standalone_wrapping():
    """generate_tikz_urls wraps snippet in standalone document when wrap_standalone=True."""
    snippet = r"\begin{tikzpicture}\draw (0,0) -- (1,1);\end{tikzpicture}"
    urls = generate_tikz_urls(snippet, output_format="svg", wrap_standalone=True)
    assert "\\documentclass" in urls.code
    assert "\\begin{tikzpicture}" in urls.code
    assert "\\end{document}" in urls.code


def test_tikz_url_generation_full_document_unchanged():
    """generate_tikz_urls leaves full LaTeX document unchanged when wrap_standalone=True."""
    full = r"\documentclass{standalone}\usepackage{tikz}\begin{document}\draw (0,0);\end{document}"
    urls = generate_tikz_urls(full, output_format="svg", wrap_standalone=True)
    assert urls.code.strip() == full.strip()


def test_tikz_template_library():
    """TikZTemplateLibrary.get returns non-empty template for known names."""
    for name in TikZTemplateLibrary.list_names():
        template = TikZTemplateLibrary.get(name)
        assert isinstance(template, str)
        assert len(template) > 0
        assert "tikz" in template.lower() or "tikzpicture" in template


def test_tikz_template_library_unknown_raises():
    """TikZTemplateLibrary.get raises ValueError for unknown template name."""
    with pytest.raises(ValueError, match="Unknown TikZ template"):
        TikZTemplateLibrary.get("nonexistent")


def test_tikz_template_library_list_names():
    """TikZTemplateLibrary.list_names returns expected template names."""
    names = TikZTemplateLibrary.list_names()
    assert "flowchart" in names
    assert "graph" in names
    assert "automata" in names
    assert "math_plot" in names
    assert len(names) >= 10


def test_tikz_library_detection_explicit():
    """get_required_libraries extracts libraries from \\usetikzlibrary{...}."""
    code = r"\usetikzlibrary{shapes, arrows.meta, positioning}"
    libs = get_required_libraries(code)
    assert "shapes" in libs
    assert "arrows.meta" in libs
    assert "positioning" in libs


def test_tikz_library_detection_hints():
    """get_required_libraries infers libraries from common commands."""
    code = r"\node[circle, draw] (a) at (0,0) {}; \draw[->] (a) -- (b);"
    libs = get_required_libraries(code)
    assert "shapes" in libs
    assert "arrows" in libs

    code_pos = r"\node[below=1cm of foo] (x) {};"
    libs_pos = get_required_libraries(code_pos)
    assert "positioning" in libs_pos

    code_modern_of = r"\node[right=of src] (b) {};"
    assert "positioning" in get_required_libraries(code_modern_of)

    code_right_dist_of = r"\node[right=2cm of a] (b) {};"
    assert "positioning" in get_required_libraries(code_right_dist_of)

    code_left_dist_of = r"\node[left=1.5cm of b] (c) {};"
    assert "positioning" in get_required_libraries(code_left_dist_of)

    code_axis = r"\begin{axis}\addplot {x^2};\end{axis}"
    libs_axis = get_required_libraries(code_axis)
    assert "pgfplots" in libs_axis


def test_tikz_library_detection_empty():
    """get_required_libraries returns empty list for code with no libraries."""
    libs = get_required_libraries(r"\draw (0,0) -- (1,1);")
    assert isinstance(libs, list)


def test_tikz_standalone_wrapping():
    """wrap_tikz_standalone wraps snippet and adds document class."""
    snippet = r"\begin{tikzpicture}\draw (0,0) circle (1);\end{tikzpicture}"
    out = wrap_tikz_standalone(snippet)
    assert out.startswith("\\documentclass")
    assert "\\usepackage{tikz}" in out
    assert "\\begin{document}" in out
    assert snippet.strip() in out
    assert out.endswith("\\end{document}\n")


def test_tikz_standalone_wrapping_full_document_unchanged():
    """wrap_tikz_standalone returns unchanged when code has \\documentclass."""
    full = r"\documentclass{article}\usepackage{tikz}\begin{document}x\end{document}"
    out = wrap_tikz_standalone(full)
    assert out == full


def test_wrap_tikz_hoists_usetikzlibrary_into_preamble():
    """\\usetikzlibrary lines must not appear inside \\begin{document} ... \\end{document}."""
    code = (
        r"\usetikzlibrary{positioning,shapes}"
        "\n"
        r"\begin{tikzpicture}\node[draw] (a) {};\node[draw, right=of a] (b) {};\end{tikzpicture}"
    )
    out = wrap_tikz_standalone(code)
    doc_i = out.index("\\begin{document}")
    end_doc_i = out.index("\\end{document}")
    body = out[doc_i:end_doc_i]
    assert r"\usetikzlibrary" not in body
    assert r"\begin{tikzpicture}" in body
    assert r"\usetikzlibrary" in out[:doc_i]


def test_tikz_standalone_wrapping_with_libraries():
    """wrap_tikz_standalone includes requested libraries."""
    snippet = r"\draw (0,0);"
    out = wrap_tikz_standalone(snippet, libraries=["shapes", "arrows"])
    assert "\\usetikzlibrary{shapes,arrows}" in out


def test_tikz_all_formats():
    """generate_tikz_urls accepts all supported TikZ output formats."""
    code = r"\draw (0,0) circle (0.5);"
    for fmt in TIKZ_FORMATS:
        urls = generate_tikz_urls(code, output_format=fmt)
        assert f"/tikz/{fmt}/" in urls.image_url


def test_tikz_unsupported_format_raises():
    """generate_tikz_urls raises ValueError for unsupported format."""
    with pytest.raises(ValueError, match="Unsupported output format"):
        generate_tikz_urls(r"\draw (0,0);", output_format="gif")


def test_tikz_custom_base_url():
    """generate_tikz_urls uses custom Kroki base_url."""
    urls = generate_tikz_urls(
        r"\draw (0,0);",
        output_format="svg",
        base_url="https://custom.kroki.example",
    )
    assert "custom.kroki.example" in urls.image_url


def test_tikz_edit_url_optional():
    """generate_tikz_urls can omit edit_url with include_edit_url=False."""
    urls = generate_tikz_urls(
        r"\draw (0,0);",
        output_format="svg",
        include_edit_url=False,
    )
    assert urls.edit_url is None
