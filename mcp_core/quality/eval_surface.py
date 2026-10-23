"""Offline eval: published prompts, per-type skills, and uml://recipes stay consistent.

Used by ``tests/test_eval_skills_prompts_recipes.py`` and
``scripts/eval_skills_prompts_recipes.py``. Does not call Kroki.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp_core.core.config import DIAGRAM_TYPES
from mcp_core.core.diagram_validation import validate_uml_inputs
from mcp_core.prompts.diagram_prompts import (
    get_prompt_registry,
    get_published_prompt_registry,
)
from mcp_core.resources.diagram_resources import get_diagram_recipes
from mcp_core.resources.diagram_skills import SKILL_URI, DiagramSkillsExtension

ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = ROOT / ".skill" / "skills"
PUBLISHED_PROMPTS = frozenset(
    {
        "uml_diagram",
        "algorithm_explainer",
        "paper_concept_diagram",
        "architecture_report",
        "diagram_theme",
    }
)


@dataclass
class EvalIssue:
    severity: str  # error | warning
    area: str
    target: str
    message: str


@dataclass
class EvalReport:
    issues: list[EvalIssue] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)


def _err(area: str, target: str, message: str) -> EvalIssue:
    return EvalIssue("error", area, target, message)


def _warn(area: str, target: str, message: str) -> EvalIssue:
    return EvalIssue("warning", area, target, message)


def eval_published_prompts() -> list[EvalIssue]:
    issues: list[EvalIssue] = []
    published = get_published_prompt_registry()
    if set(published) != PUBLISHED_PROMPTS:
        issues.append(
            _err(
                "prompt",
                "prompts/list",
                f"expected {sorted(PUBLISHED_PROMPTS)}, got {sorted(published)}",
            )
        )
    for name, info in published.items():
        desc = str(info.get("description") or "")
        if len(desc) > 160:
            issues.append(
                _warn("prompt", name, f"wire description is {len(desc)} chars (>160)")
            )
        body = info["function"]()
        if not isinstance(body, str) or len(body) < 80:
            issues.append(_err("prompt", name, "body too short or not a string"))
            continue
        if "generate_uml" not in body and name != "architecture_report":
            # architecture_report also mentions generate_uml
            pass
        if "generate_uml" not in body:
            issues.append(_err("prompt", name, "body must mention generate_uml"))
        if (
            name == "uml_diagram"
            and "uml://types" not in body
            and "diagram_type" not in body
        ):
            issues.append(_err("prompt", name, "uml_diagram must mention discovery"))
        if name == "algorithm_explainer" and "uml://recipes" not in body:
            issues.append(_warn("prompt", name, "should point at uml://recipes"))
        if name == "paper_concept_diagram" and "svg" not in body.lower():
            issues.append(_err("prompt", name, "must require SVG for clickable links"))
        if name == "diagram_theme":
            lower = body.lower()
            if "theme" not in lower:
                issues.append(_err("prompt", name, "must mention theme"))
            if "black" not in lower and "bw" not in lower and "dark" not in lower:
                issues.append(
                    _err("prompt", name, "must cover dark/black or B&W backgrounds")
                )
    # Helpers stay unpublished
    registry = get_prompt_registry()
    for helper in (
        "class_diagram",
        "uml_diagram_with_thinking",
        "mermaid_sequence_api",
    ):
        if helper in registry and registry[helper].get("publish", True):
            issues.append(_err("prompt", helper, "must have publish=False"))
    return issues


def eval_type_skills() -> list[EvalIssue]:
    issues: list[EvalIssue] = []
    for name in DIAGRAM_TYPES:
        path = SKILLS_ROOT / name / "SKILL.md"
        if not path.is_file():
            issues.append(_err("skill", name, f"missing {path.relative_to(ROOT)}"))
            continue
        text = path.read_text(encoding="utf-8")
        if f"**`diagram_type`:** `{name}`" not in text:
            issues.append(_err("skill", name, "missing diagram_type header"))
        if "generate_uml" not in text:
            issues.append(_err("skill", name, "must mention generate_uml"))
        if "uml-mcp-diagrams" not in text:
            issues.append(_warn("skill", name, "should link the workflow skill"))
    # MCP skills extension still serves one workflow skill
    ext = DiagramSkillsExtension("public")
    if ext.entry["uri"] != SKILL_URI:
        issues.append(_err("skill", "mcp", f"unexpected URI {ext.entry['uri']}"))
    if "generate_uml" not in ext.text:
        issues.append(
            _err("skill", "uml-mcp-diagrams", "workflow skill missing generate_uml")
        )
    return issues


def eval_recipes() -> list[EvalIssue]:
    issues: list[EvalIssue] = []
    recipes: dict[str, Any] = json.loads(get_diagram_recipes())
    if not recipes:
        issues.append(_err("recipe", "uml://recipes", "empty recipes map"))
        return issues
    published = get_published_prompt_registry()
    for key, recipe in recipes.items():
        target = f"recipe:{key}"
        dtype = recipe.get("diagram_type")
        template = recipe.get("template") or ""
        prompt_name = recipe.get("prompt")
        fmt = recipe.get("output_format") or "svg"
        if dtype not in DIAGRAM_TYPES:
            issues.append(_err("recipe", target, f"unknown diagram_type {dtype!r}"))
            continue
        if not isinstance(template, str) or len(template.strip()) < 10:
            issues.append(_err("recipe", target, "template missing or too short"))
            continue
        if prompt_name and prompt_name not in published:
            issues.append(
                _err("recipe", target, f"prompt {prompt_name!r} is not published")
            )
        try:
            result = validate_uml_inputs(dtype, template, fmt, strict=False)
        except Exception as exc:  # noqa: BLE001
            issues.append(_err("recipe", target, f"validate raised: {exc}"))
            continue
        if not result.get("valid", False):
            issues.append(
                _err(
                    "recipe",
                    target,
                    f"template failed validate_uml: {result.get('errors') or result.get('diagnostics')}",
                )
            )
    return issues


def run_eval() -> EvalReport:
    issues = eval_published_prompts() + eval_type_skills() + eval_recipes()
    counts = {
        "prompts_published": len(get_published_prompt_registry()),
        "type_skills": len(DIAGRAM_TYPES),
        "recipes": len(json.loads(get_diagram_recipes())),
        "errors": sum(1 for i in issues if i.severity == "error"),
        "warnings": sum(1 for i in issues if i.severity == "warning"),
    }
    return EvalReport(issues=issues, counts=counts)


__all__ = ["PUBLISHED_PROMPTS", "EvalIssue", "EvalReport", "run_eval"]
