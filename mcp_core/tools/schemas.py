"""Pydantic schemas for MCP tool inputs and outputs."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    field_validator,
    model_validator,
)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


class GenerateUMLInput(BaseModel):
    """Input model for generate_uml tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    diagram_type: str = Field(
        ...,
        description=(
            "Diagram type such as class, sequence, mermaid, d2, or graphviz. "
            "Use list_diagram_types when unsure."
        ),
        min_length=1,
    )
    code: str = Field(
        ...,
        description="Diagram source code in the syntax required by diagram_type.",
        min_length=1,
    )
    output_dir: str | None = Field(
        default=None,
        description=(
            "Local directory to save the rendered file. Omit for URL/base64 output. "
            "Hosted/read-only deployments reject file output."
        ),
    )
    output_format: str = Field(
        default="svg",
        description=(
            "Requested output format: svg, png, pdf, jpeg, txt, or base64 when "
            "supported by the selected diagram type."
        ),
    )
    theme: str | None = Field(
        default=None,
        description="Optional PlantUML theme; ignored by non-PlantUML backends.",
    )
    scale: float = Field(
        default=1.0,
        ge=0.1,
        description=(
            "SVG scale factor. For example, 2.0 doubles SVG dimensions. "
            "Ignored for non-SVG output."
        ),
    )

    @field_validator("diagram_type")
    @classmethod
    def validate_diagram_type(cls, v: str) -> str:
        key = (v or "").strip().lower()
        if not key:
            raise ValueError("diagram_type cannot be empty")
        from ..core.config import MCP_SETTINGS

        if key not in MCP_SETTINGS.diagram_types:
            raise ValueError(
                f"Unsupported diagram type: {v.strip()}. Use uml://types resource for valid types."
            )
        return key

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Diagram code cannot be empty")
        from ..core.config import MCP_SETTINGS

        if len(v) > MCP_SETTINGS.max_code_length:
            raise ValueError(
                f"Diagram code exceeds maximum length of {MCP_SETTINGS.max_code_length} characters"
            )
        return v.strip()

    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        value = v.lower().strip()
        allowed = ("svg", "png", "pdf", "jpeg", "txt", "base64")
        if value not in allowed:
            raise ValueError(f"output_format must be one of: {', '.join(allowed)}")
        return value

    @model_validator(mode="after")
    def validate_output_format_for_diagram_type(self) -> GenerateUMLInput:
        from ..core.config import MCP_SETTINGS

        diagram_type = self.diagram_type.lower()
        output_format = self.output_format.lower().strip()
        types_map = getattr(MCP_SETTINGS, "diagram_types", {})
        if diagram_type in types_map:
            allowed = types_map[diagram_type].formats
            if output_format not in allowed:
                raise ValueError(
                    f"output_format '{output_format}' not supported for diagram type "
                    f"'{diagram_type}'. Use uml://formats or choose one of: {', '.join(allowed)}"
                )
        return self

    @model_validator(mode="after")
    def validate_output_location(self) -> GenerateUMLInput:
        """Reject file writes in hosted mode and sandbox local writes by default."""
        from ..core.config import MCP_SETTINGS

        if not self.output_dir:
            return self

        if MCP_SETTINGS.read_only or MCP_SETTINGS.memory_only:
            raise ValueError(
                "output_dir is not allowed in read-only or memory-only mode; "
                "omit output_dir for URL/base64 output."
            )

        # Existing tests and explicit developer test environments keep their historical
        # arbitrary-path behavior. Normal local runs are sandboxed unless explicitly
        # opted out with MCP_ALLOW_ARBITRARY_OUTPUT_DIR=true.
        allow_arbitrary = _env_bool(
            "MCP_ALLOW_ARBITRARY_OUTPUT_DIR",
            default=_env_bool("TESTING", False),
        )
        if allow_arbitrary:
            return self

        root_raw = os.environ.get("MCP_OUTPUT_ROOT") or MCP_SETTINGS.output_dir
        root = Path(root_raw).expanduser().resolve()
        requested = Path(self.output_dir).expanduser()
        if not requested.is_absolute():
            requested = (Path.cwd() / requested).resolve()
        else:
            requested = requested.resolve()

        try:
            requested.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"output_dir must stay under configured output root '{root}'. "
                "Set MCP_OUTPUT_ROOT to change the sandbox or explicitly opt out with "
                "MCP_ALLOW_ARBITRARY_OUTPUT_DIR=true for trusted local development."
            ) from exc
        return self


class ValidateUMLInput(BaseModel):
    """Input model for validate_uml tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    diagram_type: str = Field(
        ...,
        description="Diagram type to validate. Use list_diagram_types when unsure.",
        min_length=1,
    )
    code: str = Field(
        ...,
        description="Diagram source code to validate locally without rendering.",
        min_length=1,
    )
    output_format: str = Field(
        default="svg",
        description="Output format whose compatibility should be validated.",
    )

    @field_validator("diagram_type")
    @classmethod
    def validate_diagram_type(cls, v: str) -> str:
        key = (v or "").strip().lower()
        if not key:
            raise ValueError("diagram_type cannot be empty")
        from ..core.config import MCP_SETTINGS

        if key not in MCP_SETTINGS.diagram_types:
            raise ValueError(
                f"Unsupported diagram type: {v.strip()}. Use uml://types resource for valid types."
            )
        return key

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Diagram code cannot be empty")
        from ..core.config import MCP_SETTINGS

        if len(v) > MCP_SETTINGS.max_code_length:
            raise ValueError(
                f"Diagram code exceeds maximum length of {MCP_SETTINGS.max_code_length} characters"
            )
        return v.strip()

    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        value = v.lower().strip()
        allowed = ("svg", "png", "pdf", "jpeg", "txt", "base64")
        if value not in allowed:
            raise ValueError(f"output_format must be one of: {', '.join(allowed)}")
        return value

    @model_validator(mode="after")
    def validate_output_format_for_diagram_type(self) -> ValidateUMLInput:
        from ..core.config import MCP_SETTINGS

        diagram_type = self.diagram_type.lower()
        output_format = self.output_format.lower().strip()
        types_map = getattr(MCP_SETTINGS, "diagram_types", {})
        if diagram_type in types_map:
            allowed = types_map[diagram_type].formats
            if output_format not in allowed:
                raise ValueError(
                    f"output_format '{output_format}' not supported for diagram type "
                    f"'{diagram_type}'. Use uml://formats or choose one of: {', '.join(allowed)}"
                )
        return self


class RenderAttempt(BaseModel):
    """One renderer attempt in the generation pipeline."""

    backend: str
    ok: bool | None = None
    status: str | None = None
    duration_ms: float | None = None
    error_summary: str | None = None
    error_code: str | None = None
    retry_count: int = 0


class DiagramError(BaseModel):
    """Machine-readable detail for a failed diagram request."""

    code: str
    message: str
    diagram_type: str | None = None
    backend: str | None = None
    retryable: bool = False
    line: int | None = None
    column: int | None = None
    suggestion: str | None = None


class DiagramResult(BaseModel):
    """Structured output for diagram generation tools."""

    code: str
    success: bool | None = None
    diagram_type: str | None = None
    output_format: str | None = None
    url: str | None = None
    playground: str | None = None
    local_path: str | None = None
    content_base64: str | None = None
    error: str | None = None
    error_detail: DiagramError | None = None
    source: str | None = None
    attempts: list[RenderAttempt] | None = None
    fallback_used: bool | None = None
    render_ms: float | None = None
    cache_hit: bool | None = None
    cache_lookup_ms: float | None = None
    mime_type: str | None = None
    display_markdown: str | None = None


class ValidationDiagnostic(BaseModel):
    """Actionable local validation diagnostic."""

    severity: str
    code: str
    message: str
    line: int | None = None
    column: int | None = None
    suggestion: str | None = None


class ValidationResult(BaseModel):
    """Structured output for validate_uml."""

    valid: bool
    diagram_type: str | None = None
    backend: str | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    diagnostics: list[ValidationDiagnostic] = Field(default_factory=list)
    corrected_code: str | None = None
    prepared_code: str | None = None
    strict: bool = False
    normalized: bool = False
    changes: list[str] = Field(default_factory=list)


class BatchDiagramItem(BaseModel):
    """One indexed item returned by generate_uml_batch."""

    index: int
    code: str | None = None
    success: bool | None = None
    diagram_type: str | None = None
    output_format: str | None = None
    url: str | None = None
    playground: str | None = None
    local_path: str | None = None
    content_base64: str | None = None
    error: str | None = None
    error_detail: DiagramError | None = None
    source: str | None = None
    attempts: list[RenderAttempt] | None = None
    fallback_used: bool | None = None
    render_ms: float | None = None
    cache_hit: bool | None = None
    cache_lookup_ms: float | None = None
    mime_type: str | None = None
    display_markdown: str | None = None


class BatchDiagramResult(BaseModel):
    """Structured output for generate_uml_batch."""

    results: list[BatchDiagramItem] = Field(default_factory=list)
    error: str | None = None


class DiagramTypeInfo(BaseModel):
    """Metadata for one supported diagram type."""

    backend: str
    description: str
    formats: list[str]


class DiagramTypesOutput(RootModel[dict[str, DiagramTypeInfo]]):
    """Dynamic diagram type map returned by list_diagram_types."""


__all__ = [
    "BatchDiagramItem",
    "BatchDiagramResult",
    "DiagramError",
    "DiagramResult",
    "DiagramTypeInfo",
    "DiagramTypesOutput",
    "GenerateUMLInput",
    "RenderAttempt",
    "ValidateUMLInput",
    "ValidationDiagnostic",
    "ValidationResult",
]
