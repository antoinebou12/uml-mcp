"""
Local validation for diagram code before render (no network calls).

Reuses GenerateUMLInput for type/format/length rules, then applies light structural checks.
"""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import ValidationError

from ..tools.schemas import GenerateUMLInput

from .config import MCP_SETTINGS
from .diagram_rendering import prepare_diagram_code


def _structural_errors(backend_type: str, prepared_code: str) -> List[str]:
    errors: List[str] = []
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


def _suggestions_for_errors(errors: List[str]) -> List[str]:
    sug: List[str] = []
    for e in errors:
        if "@startuml" in e or "@enduml" in e:
            sug.append(
                "Close every @startuml with @enduml, or use a single unbroken diagram block."
            )
        if "Mermaid" in e:
            sug.append(
                "Start with a diagram keyword such as `graph TD`, `flowchart LR`, or `sequenceDiagram`."
            )
        if "D2" in e:
            sug.append("Define at least one shape or connection (e.g. `a -> b`).")
    return list(dict.fromkeys(sug))


def validate_uml_inputs(
    diagram_type: str,
    code: str,
    output_format: str = "svg",
) -> Dict[str, Any]:
    """
    Validate diagram inputs without calling Kroki or other renderers.

    Returns a dict with valid, errors, suggestions, backend, diagram_type, and prepared_code
    (when schema validation passed).
    """
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
        errs: List[str] = []
        for err in exc.errors():
            loc = err.get("loc", ())
            name = str(loc[0]) if loc else "input"
            errs.append(f"{name}: {err['msg']}")
        return {
            "valid": False,
            "diagram_type": (diagram_type or "").strip().lower() or None,
            "backend": None,
            "errors": errs,
            "suggestions": _suggestions_for_errors(errs),
            "corrected_code": None,
            "prepared_code": None,
        }

    dt_key = validated.diagram_type
    cfg = MCP_SETTINGS.diagram_types[dt_key]
    prepared = prepare_diagram_code(validated.code, cfg.backend, None)
    structural = _structural_errors(cfg.backend, prepared)
    all_errors = structural
    valid = len(all_errors) == 0

    return {
        "valid": valid,
        "diagram_type": dt_key,
        "backend": cfg.backend,
        "errors": all_errors,
        "suggestions": _suggestions_for_errors(all_errors),
        "corrected_code": prepared if prepared != validated.code.strip() else None,
        "prepared_code": prepared,
    }
