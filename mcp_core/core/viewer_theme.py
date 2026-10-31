"""Apply explicit viewer theme changes to previously prepared source."""

import json
import re


def apply_viewer_theme(code: str, diagram_type: str, theme: str | None) -> str:
    if not theme:
        return code
    if diagram_type.startswith("d3_"):
        try:
            spec = json.loads(code)
            spec["theme"] = theme
            return json.dumps(spec)
        except (ValueError, TypeError):
            return code
    from .config import MCP_SETTINGS

    info = MCP_SETTINGS.diagram_types.get(diagram_type)
    backend = info.backend if info else diagram_type
    if backend in {"plantuml", "c4plantuml"}:
        return re.sub(r"(?m)^(\s*!theme\s+)\S+", lambda m: m[1] + theme, code)
    if backend == "mermaid":
        code = re.sub(
            r"(['\"]theme['\"]\s*:\s*['\"])[^'\"]+(['\"])",
            lambda m: m[1] + theme + m[2],
            code,
        )
        code = re.sub(r"(?m)^(\s*theme\s*:\s*)[^\n]+", lambda m: m[1] + theme, code)
        if not re.search(r"""["']?theme["']?\s*:""", code):
            code = re.sub(
                r"(%%\{\s*(?:init|initialize)\s*:\s*\{)",
                lambda m: m[1] + f"'theme': '{theme}', ",
                code,
                count=1,
            )
        return code
    if backend == "d2":
        from .diagram_themes import resolve_d2_theme_id

        value = resolve_d2_theme_id(theme)
        if value is not None:
            return re.sub(r"(theme-id\s*:\s*)\d+", lambda m: m[1] + str(value), code)
    return code
