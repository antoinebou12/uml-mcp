"""Offline eval gate for published prompts, type skills, and uml://recipes."""

from __future__ import annotations

from mcp_core.quality.eval_surface import PUBLISHED_PROMPTS, run_eval


def test_eval_skills_prompts_recipes_is_clean():
    report = run_eval()
    errors = [i for i in report.issues if i.severity == "error"]
    assert not errors, "\n".join(f"{i.area}:{i.target}: {i.message}" for i in errors)
    assert report.counts["prompts_published"] == len(PUBLISHED_PROMPTS)
    assert report.counts["type_skills"] >= 30
    assert report.counts["recipes"] >= 2


def test_eval_counts_match_published_surface():
    report = run_eval()
    assert report.ok
    assert report.counts["errors"] == 0
