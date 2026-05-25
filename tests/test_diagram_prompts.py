"""
Unit tests for MCP diagram prompts.
"""

from pathlib import Path
from unittest.mock import MagicMock

from mcp_core.prompts.diagram_prompts import (
    _layout_overlap_appendix,
    algorithm_explainer_prompt,
    class_diagram_prompt,
    get_prompt_registry,
    paper_concept_diagram_prompt,
    register_diagram_prompts,
    sequence_diagram_prompt,
    uml_diagram_prompt,
    uml_diagram_with_thinking_prompt,
)
from tools.kroki.kroki_templates import DiagramTemplates


class TestUmlDiagramPrompt:
    """Tests for uml_diagram_prompt."""

    def test_returns_non_empty_string(self):
        """uml_diagram_prompt returns a non-empty string."""
        result = uml_diagram_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_with_empty_context(self):
        """uml_diagram_prompt(context={}) returns prompt with UML guidance."""
        result = uml_diagram_prompt(context={})
        assert "UML" in result
        assert "notation" in result or "syntax" in result or "diagram" in result
        assert "uml://types" in result
        assert "uml://formats" in result
        assert "generate_uml" in result
        assert "output_dir" in result

    def test_with_diagram_type_in_context(self):
        """uml_diagram_prompt adds diagram type when provided in context."""
        result = uml_diagram_prompt(context={"diagram_type": "class"})
        assert "class" in result
        assert "diagram" in result


class TestClassDiagramPrompt:
    """Tests for class_diagram_prompt."""

    def test_returns_string_with_class_guidance(self):
        """class_diagram_prompt returns string containing class diagram guidance."""
        result = class_diagram_prompt(context={"description": "User and Account"})
        assert isinstance(result, str)
        assert "class" in result.lower()
        assert "PlantUML" in result or "@startuml" in result
        assert "`diagram_type` **class**" in result

    def test_includes_visibility_and_relationships(self):
        """class_diagram_prompt mentions visibility and relationships."""
        result = class_diagram_prompt()
        assert "visibility" in result or "+" in result or "-" in result
        assert (
            "relationship" in result
            or "inheritance" in result
            or "association" in result
        )


class TestSequenceDiagramPrompt:
    """Tests for sequence_diagram_prompt."""

    def test_returns_string_with_sequence_guidance(self):
        """sequence_diagram_prompt returns string with sequence diagram content."""
        result = sequence_diagram_prompt(context={"description": "Login flow"})
        assert isinstance(result, str)
        assert "sequence" in result.lower()
        assert "participant" in result or "PlantUML" in result or "@startuml" in result
        assert "`diagram_type` **sequence**" in result


class TestRegisterDiagramPrompts:
    """Tests for register_diagram_prompts."""

    def test_server_prompt_called_for_each_registered_prompt(self):
        """register_diagram_prompts calls server.prompt(name) for each prompt."""
        server = MagicMock()
        server.prompt.return_value = lambda f: f

        registered = register_diagram_prompts(server)

        registry = get_prompt_registry()
        expected_names = list(registry.keys())
        assert len(registered) == len(expected_names)
        assert server.prompt.call_count == len(expected_names)
        for name in expected_names:
            assert name in registered

    def test_registry_contains_uml_and_class_prompts(self):
        """Prompt registry includes uml_diagram and class_diagram."""
        registry = get_prompt_registry()
        assert "uml_diagram" in registry
        assert "class_diagram" in registry
        assert "uml_diagram_with_thinking" in registry
        assert "c4_model" in registry
        assert "wireviz_harness" in registry
        assert "bpmn_executable_process" in registry
        assert "algorithm_explainer" in registry
        assert "paper_concept_diagram" in registry


def _has_overlap_appendix(text: str) -> bool:
    """Helper: confirm the per-backend overlap appendix is present."""
    return (
        "Reduce arrow overlap" in text
        and "flowchart TD" in text
        and "skinparam linetype ortho" in text
        and "direction: right" in text
    )


class TestUmlDiagramWithThinkingPrompt:
    """uml_diagram_with_thinking_prompt now embeds the overlap appendix."""

    def test_includes_overlap_appendix(self):
        result = uml_diagram_with_thinking_prompt()
        assert isinstance(result, str)
        assert _has_overlap_appendix(result)


class TestAlgorithmExplainerPrompt:
    """Tests for algorithm_explainer_prompt."""

    def test_returns_string_with_algorithm_guidance(self):
        result = algorithm_explainer_prompt()
        assert isinstance(result, str)
        assert "algorithm" in result.lower()
        assert "complexity" in result.lower()
        assert "O(n" in result
        assert "generate_uml" in result

    def test_maps_intents_to_diagram_types(self):
        result = algorithm_explainer_prompt()
        for dt in ("**mermaid**", "**activity**", "**state**", "**d2**"):
            assert dt in result, f"Missing diagram_type mapping for {dt}"

    def test_includes_overlap_appendix(self):
        result = algorithm_explainer_prompt()
        assert _has_overlap_appendix(result)

    def test_context_algorithm_name_is_inlined(self):
        result = algorithm_explainer_prompt(context={"algorithm": "quicksort"})
        assert "quicksort" in result


class TestPaperConceptDiagramPrompt:
    """Tests for paper_concept_diagram_prompt."""

    def test_returns_string_with_paper_guidance(self):
        result = paper_concept_diagram_prompt()
        assert isinstance(result, str)
        assert "paper" in result.lower() or "academic" in result.lower()
        assert "citation" in result.lower()
        assert "generate_uml" in result

    def test_includes_clickable_link_snippets_per_backend(self):
        """Mermaid click, PlantUML [[ ]], D2 link:, and Graphviz URL= snippets are present."""
        result = paper_concept_diagram_prompt()
        assert "click " in result and "_blank" in result
        assert "[[https://arxiv.org" in result
        assert 'link: "https://arxiv.org' in result
        assert 'URL="https://arxiv.org' in result

    def test_recommends_svg_for_clickable_links(self):
        result = paper_concept_diagram_prompt()
        assert "svg" in result.lower()
        assert "strip" in result.lower() or "PNG" in result

    def test_warns_against_fabricating_links(self):
        result = paper_concept_diagram_prompt()
        assert "fabricate" in result.lower() or "never" in result.lower()

    def test_includes_overlap_appendix(self):
        result = paper_concept_diagram_prompt()
        assert _has_overlap_appendix(result)

    def test_context_paper_name_is_inlined(self):
        result = paper_concept_diagram_prompt(
            context={"paper": "Attention Is All You Need"}
        )
        assert "Attention Is All You Need" in result


class TestLayoutOverlapAppendix:
    """Direct tests for the shared per-backend overlap helper."""

    def test_has_a_section_heading(self):
        text = _layout_overlap_appendix()
        assert "Reduce arrow overlap" in text

    def test_covers_each_targeted_backend(self):
        """Each of the four backends in scope appears as its own section."""
        text = _layout_overlap_appendix()
        for backend in ("Mermaid", "PlantUML", "D2", "Graphviz"):
            assert backend in text, f"Missing section for {backend}"

    def test_recommends_direction_per_backend(self):
        text = _layout_overlap_appendix()
        # Mermaid direction header
        assert "flowchart TD" in text or "flowchart LR" in text
        # PlantUML non-sequence direction + ortho routing
        assert "left to right direction" in text
        assert "skinparam linetype ortho" in text
        # D2 direction property
        assert "direction: right" in text or "direction: down" in text
        # Graphviz rank direction
        assert "rankdir=" in text

    def test_recommends_directional_arrows_for_plantuml(self):
        text = _layout_overlap_appendix()
        for arrow in ("-down->", "-right->", "-up->", "-left->"):
            assert arrow in text, f"Missing directional arrow {arrow}"

    def test_recommends_grouping_per_backend(self):
        text = _layout_overlap_appendix()
        # Mermaid subgraph, PlantUML together, Graphviz cluster
        assert "subgraph" in text
        assert "together {" in text
        assert "cluster_" in text

    def test_does_not_break_existing_uml_diagram_prompt(self):
        """The appendix must not be appended to the base uml_diagram_prompt."""
        appendix = _layout_overlap_appendix()
        base = uml_diagram_prompt()
        assert appendix not in base


class TestNewPromptsRegistered:
    """Confirm decorator metadata for the two new prompts is correct."""

    def test_algorithm_prompt_metadata(self):
        registry = get_prompt_registry()
        entry = registry["algorithm_explainer"]
        assert entry["category"] == "algorithm"
        assert "algorithm" in entry["description"].lower()
        assert callable(entry["function"])

    def test_paper_prompt_metadata(self):
        registry = get_prompt_registry()
        entry = registry["paper_concept_diagram"]
        assert entry["category"] == "research"
        assert "paper" in entry["description"].lower() or (
            "citation" in entry["description"].lower()
        )
        assert callable(entry["function"])

    def test_new_prompts_registered_with_server(self):
        """register_diagram_prompts forwards the new prompts to FastMCP.prompt()."""
        server = MagicMock()
        server.prompt.return_value = lambda f: f
        registered = register_diagram_prompts(server)
        assert "algorithm_explainer" in registered
        assert "paper_concept_diagram" in registered
        called_names = [call.args[0] for call in server.prompt.call_args_list]
        assert "algorithm_explainer" in called_names
        assert "paper_concept_diagram" in called_names


class TestSkillFilesMentionNewPrompts:
    """Skill copies must list the new prompts and resources."""

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def test_plugin_skill_mentions_new_prompts(self):
        path = (
            self._repo_root()
            / "plugins"
            / "uml-mcp"
            / "skills"
            / "uml-diagrams"
            / "SKILL.md"
        )
        text = path.read_text(encoding="utf-8")
        assert "algorithm_explainer" in text
        assert "paper_concept_diagram" in text
        assert "uml://recipes" in text

    def test_skill_copy_mentions_new_prompts(self):
        path = self._repo_root() / ".skill" / "skills" / "uml-mcp-diagrams" / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        assert "algorithm_explainer" in text
        assert "paper_concept_diagram" in text
        assert "uml://recipes" in text


class TestRecipeTemplateShapes:
    """The shipped recipe templates should be ready-to-render Mermaid blocks."""

    def test_algorithm_flowchart_template_has_required_structure(self):
        """Starts with a Mermaid flowchart header, has labeled nodes, edges, and complexity."""
        template = DiagramTemplates.get_template("algorithm_flowchart")
        head = template.lstrip().splitlines()[0]
        assert head.startswith("flowchart TD"), head
        assert "-->" in template
        assert "O(n" in template
        assert "Start([" in template and "])" in template

    def test_paper_concept_template_has_required_structure(self):
        """Starts with a Mermaid flowchart LR header and has a click directive to arXiv."""
        template = DiagramTemplates.get_template("paper_concept")
        head = template.lstrip().splitlines()[0]
        assert head.startswith("flowchart LR"), head
        assert "-->" in template
        assert "click " in template
        assert "arxiv.org/abs/" in template
        assert "_blank" in template

    def test_unknown_recipe_falls_back_to_default(self):
        """get_template returns the safe fallback string for unknown keys."""
        out = DiagramTemplates.get_template("definitely_not_a_recipe")
        assert "No specific template" in out
