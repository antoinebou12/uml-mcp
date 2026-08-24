"""
Pydantic schemas for MCP tool inputs and outputs.
"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GenerateUMLInput(BaseModel):
    """Input model for generate_uml tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    diagram_type: str = Field(
        ...,
        description="Type of diagram (e.g. class, sequence, activity, mermaid, d2). See uml://types.",
        min_length=1,
    )
    code: str = Field(
        ...,
        description="Diagram code in the format for the chosen type",
        min_length=1,
    )
    output_dir: Optional[str] = Field(
        default=None,
        description="Directory to save the image; omit for URL/base64 only (no file write)",
    )
    output_format: str = Field(
        default="svg",
        description="Output format: svg, png, pdf, jpeg, txt, or base64 (per diagram type; see uml://formats)",
    )
    theme: Optional[str] = Field(
        default=None,
        description="PlantUML theme (only for PlantUML diagram types)",
    )
    scale: float = Field(
        default=1.0,
        ge=0.1,
        description="Scale factor for SVG output (e.g. 2.0 doubles size). Only applied when output_format is svg.",
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
        v = v.lower().strip()
        allowed = ("svg", "png", "pdf", "jpeg", "txt", "base64")
        if v not in allowed:
            raise ValueError(f"output_format must be one of: {', '.join(allowed)}")
        return v

    @model_validator(mode="after")
    def validate_output_format_for_diagram_type(self) -> "GenerateUMLInput":
        from ..core.config import MCP_SETTINGS

        diagram_type = getattr(self, "diagram_type", "").lower()
        output_format = (getattr(self, "output_format", "") or "svg").lower().strip()
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
    def reject_output_dir_when_read_only(self) -> "GenerateUMLInput":
        from ..core.config import MCP_SETTINGS

        if MCP_SETTINGS.read_only and self.output_dir:
            raise ValueError(
                "output_dir is not allowed when MCP_READ_ONLY=true; omit output_dir for URL/base64 only."
            )
        return self


class ValidateUMLInput(BaseModel):
    """Input model for validate_uml tool (subset of generate_uml; no output_dir)."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    diagram_type: str = Field(
        ...,
        description="Type of diagram (e.g. class, sequence, mermaid, d2). See uml://types.",
        min_length=1,
    )
    code: str = Field(
        ...,
        description="Diagram code in the format for the chosen type",
        min_length=1,
    )
    output_format: str = Field(
        default="svg",
        description="Output format: svg, png, pdf, jpeg, txt, or base64 (per diagram type; see uml://formats)",
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
        v = v.lower().strip()
        allowed = ("svg", "png", "pdf", "jpeg", "txt", "base64")
        if v not in allowed:
            raise ValueError(f"output_format must be one of: {', '.join(allowed)}")
        return v

    @model_validator(mode="after")
    def validate_output_format_for_diagram_type(self) -> "ValidateUMLInput":
        from ..core.config import MCP_SETTINGS

        diagram_type = getattr(self, "diagram_type", "").lower()
        output_format = (getattr(self, "output_format", "") or "svg").lower().strip()
        types_map = getattr(MCP_SETTINGS, "diagram_types", {})
        if diagram_type in types_map:
            allowed = types_map[diagram_type].formats
            if output_format not in allowed:
                raise ValueError(
                    f"output_format '{output_format}' not supported for diagram type "
                    f"'{diagram_type}'. Use uml://formats or choose one of: {', '.join(allowed)}"
                )
        return self


class DiagramResult(BaseModel):
    """Structured output for diagram generation tools."""

    code: str
    url: Optional[str] = None
    playground: Optional[str] = None
    local_path: Optional[str] = None
    content_base64: Optional[str] = (
        None  # Image bytes when not writing to file (memory-only)
    )
    error: Optional[str] = None
    source: Optional[str] = None
    attempts: Optional[list] = None
    fallback_used: Optional[bool] = None
    render_ms: Optional[float] = None
    cache_hit: Optional[bool] = None
    mime_type: Optional[str] = None


class ValidationResult(BaseModel):
    """Structured output for validate_uml."""

    valid: bool
    errors: list[str] = []
    warnings: list[str] = []
    suggestions: list[str] = []


class BatchDiagramResult(BaseModel):
    """Structured output for generate_uml_batch."""

    results: list[DiagramResult]


class DiagramTypesOutput(BaseModel):
    """Structured output for list_diagram_types."""

    types: dict[str, Any]
