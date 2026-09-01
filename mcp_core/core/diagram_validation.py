"""Local validation for diagram code before render (no network calls)."""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from ..tools.schemas import GenerateUMLInput
from .config import MCP_SETTINGS
from .diagram_rendering import prepare_diagram_code


def _structural_errors(backend_type: str, prepared_code: str) -> list[str]:
    errors: list[str] = []
    if backend_type == "plantuml":
        n_start = prepared_code.count("@startuml")
        n_end = prepared_code.count("@enduml")
        if n_start != n_end:
            errors.append(
                f"Unbalanced PlantUML: {n_start} @startuml vs {n_end} @enduml "
                "(each diagram block needs a matching @enduml)."
            )
    elif backend_type == "mermaid":
        stripped = prepared_code.strip()
        if len(stripped) < 3:
            errors.append("Mermaid diagram code is too short to be valid.")
    elif backend_type == "d2":
        stripped = prepared_code.strip()
        if len(stripped) < 2:
            errors.append("D2 diagram code is too short to be valid.")
    return errors


_MERMAID_HEAD = re.compile(
    r"^\s*(graph\b|flowchart\b|sequenceDiagram\b|classDiagram\b|stateDiagram\b|"
    r"erDiagram\b|gantt\b|pie\b|gitGraph\b|journey\b|mindmap\b|timeline\b|"
    r"requirementDiagram\b|sankey-beta\b|block-beta\b|C4Context\b|C4Container\b)",
    re.IGNORECASE | re.MULTILINE,
)

_MERMAID_SEQUENCE_DANGLING_ARROW = re.compile(
    r"(?:<<-->>|<<->>|-->>|->>|-->|->|--x|-x|--\)|-\))\s*[+-]?\s*$"
)
_LINE_NUMBER = re.compile(r"\bline\s+(\d+)\b", re.IGNORECASE)


def _strict_mermaid_sequence_errors(prepared_code: str) -> list[str]:
    errors: list[str] = []
    lines = prepared_code.splitlines()
    first_content_seen = False

    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("%%"):
            continue

        if not first_content_seen:
            first_content_seen = True
            if stripped.lower().startswith("sequencediagram"):
                continue
            return errors

        if _MERMAID_SEQUENCE_DANGLING_ARROW.search(stripped):
            errors.append(
                "Mermaid (strict): sequence message on line "
                f"{line_number} has an arrow but no target actor."
            )
            break

    return errors


def _structural_errors_strict_mermaid(prepared_code: str) -> list[str]:
    """Extra checks when strict=True; conservative to limit false positives."""
    errors: list[str] = []
    source = prepared_code.strip()
    if not source:
        errors.append("Mermaid diagram code is empty.")
        return errors
    if not _MERMAID_HEAD.search(source):
        errors.append(
            "Mermaid (strict): start with a diagram keyword such as "
            "`graph TD`, `flowchart LR`, or `sequenceDiagram`."
        )
    if "subgraph" in source.lower() and "end" not in source.lower():
        errors.append(
            "Mermaid (strict): subgraph blocks typically need a matching `end`."
        )
    errors.extend(_strict_mermaid_sequence_errors(source))
    return errors


def _structural_errors_strict_d2(prepared_code: str) -> list[str]:
    errors: list[str] = []
    for line_number, line in enumerate(prepared_code.splitlines(), 1):
        if line.count('"') % 2 != 0:
            errors.append(
                f"D2 (strict): line {line_number} may have an unclosed double quote."
            )
            break
    return errors


def _suggestions_for_errors(errors: list[str]) -> list[str]:
    suggestions: list[str] = []
    for error in errors:
        if "@startuml" in error or "@enduml" in error:
            suggestions.append(
                "Close every @startuml with @enduml, or use a single unbroken diagram block."
            )
        if "Mermaid" in error:
            suggestions.append(
                "Start with a diagram keyword such as `graph TD`, `flowchart LR`, or `sequenceDiagram`."
            )
        if "target actor" in error:
            suggestions.append(
                "Complete sequence messages with a target actor, for example `A->>B: message`."
            )
        if "D2" in error:
            suggestions.append("Define at least one shape or connection (e.g. `a -> b`).")
        if "strict" in error.lower() and "Mermaid" in error:
            suggestions.append(
                "Use a standard Mermaid diagram header on the first line (e.g. graph TD;)."
            )
    return list(dict.fromkeys(suggestions))


def _diagnostic_code(message: str) -> str:
    lower = message.lower()
    if "unsupported diagram type" in lower:
        return "UNSUPPORTED_DIAGRAM_TYPE"
    if "output_format" in lower or "not supported" in lower:
        return "UNSUPPORTED_OUTPUT_FORMAT"
    if "exceeds maximum length" in lower:
        return "SOURCE_TOO_LARGE"
    if "target actor" in lower:
        return "MERMAID_DANGLING_ARROW"
    if "diagram keyword" in lower:
        return "MERMAID_MISSING_HEADER"
    if "subgraph" in lower:
        return "MERMAID_UNCLOSED_SUBGRAPH"
    if "unclosed double quote" in lower:
        return "D2_UNCLOSED_QUOTE"
    if "@startuml" in lower or "@enduml" in lower:
        return "PLANTUML_UNBALANCED_BLOCK"
    if "too short" in lower or "empty" in lower:
        return "SOURCE_TOO_SHORT"
    return "INVALID_DIAGRAM"


def _line_from_message(message: str) -> int | None:
    match = _LINE_NUMBER.search(message)
    return int(match.group(1)) if match else None


def _build_diagnostics(
    errors: list[str], suggestions: list[str]
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for index, message in enumerate(errors):
        suggestion = suggestions[index] if index < len(suggestions) else None
        diagnostics.append(
            {
                "severity": "error",
                "code": _diagnostic_code(message),
                "message": message,
                "line": _line_from_message(message),
                "column": None,
                "suggestion": suggestion,
            }
        )
    return diagnostics


def _normalization_changes(
    original: str, prepared: str, backend: str
) -> list[str]:
    if prepared == original.strip():
        return []
    changes: list[str] = []
    stripped = original.strip()
    if backend == "plantuml":
        if "@startuml" not in stripped:
            changes.append("added @startuml wrapper")
        if "@enduml" not in stripped:
            changes.append("added @enduml wrapper")
    elif backend == "tikz" and "\\documentclass" not in stripped:
        changes.append("wrapped TikZ snippet in a standalone document")
    if not changes:
        changes.append("normalized diagram source")
    return changes


def validate_uml_inputs(
    diagram_type: str,
    code: str,
    output_format: str = "svg",
    strict: bool = False,
) -> dict[str, Any]:
    """Validate diagram inputs locally and return actionable diagnostics."""
    try:
        validated = GenerateUMLInput(
            diagram_type=diagram_type,
            code=code,
            output_dir=None,
            output_format=output_format,
            theme=None,
            scale=1.0,
        )
    except ValidationError as exc:
        errors: list[str] = []
        for error in exc.errors():
            loc = error.get("loc", ())
            name = str(loc[0]) if loc else "input"
            errors.append(f"{name}: {error['msg']}")
        suggestions = _suggestions_for_errors(errors)
        return {
            "valid": False,
            "diagram_type": (diagram_type or "").strip().lower() or None,
            "backend": None,
            "errors": errors,
            "warnings": [],
            "suggestions": suggestions,
            "diagnostics": _build_diagnostics(errors, suggestions),
            "corrected_code": None,
            "prepared_code": None,
            "strict": strict,
            "normalized": False,
            "changes": [],
        }

    dt_key = validated.diagram_type
    cfg = MCP_SETTINGS.diagram_types[dt_key]
    prepared = prepare_diagram_code(validated.code, cfg.backend, None)
    structural = _structural_errors(cfg.backend, prepared)
    extra: list[str] = []
    if strict:
        if cfg.backend == "mermaid":
            extra.extend(_structural_errors_strict_mermaid(prepared))
        elif cfg.backend == "d2":
            extra.extend(_structural_errors_strict_d2(prepared))
    all_errors = structural + extra
    suggestions = _suggestions_for_errors(all_errors)
    changes = _normalization_changes(validated.code, prepared, cfg.backend)

    return {
        "valid": len(all_errors) == 0,
        "diagram_type": dt_key,
        "backend": cfg.backend,
        "errors": all_errors,
        "warnings": [],
        "suggestions": suggestions,
        "diagnostics": _build_diagnostics(all_errors, suggestions),
        "corrected_code": prepared if prepared != validated.code.strip() else None,
        "prepared_code": prepared,
        "strict": strict,
        "normalized": bool(changes),
        "changes": changes,
    }
