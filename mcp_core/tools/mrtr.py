"""SEP-2322 Multi Round-Trip Request helpers for diagram tools.

When the client advertises form elicitation, tools can return
``InputRequiredResult`` instead of a hard error for missing/unknown
``diagram_type``, background-style ``theme`` values, or large batches.
Clients without elicitation keep ordinary ``{error: ...}`` responses.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
from typing import Any

from mcp_core.core.config import MCP_SETTINGS
from mcp_core.core.diagram_themes import (
    normalize_background,
    themes_for_background,
)

logger = logging.getLogger(__name__)

PICK_TYPE_KEY = "pick_diagram_type"
PICK_THEME_KEY = "pick_theme"
CONFIRM_BATCH_KEY = "confirm_batch"

#: ``theme`` values treated as page backgrounds (see ``diagram_theme`` prompt).
BACKGROUND_THEME_ALIASES = frozenset(
    {"light", "white", "dark", "black", "bw", "print", "mono"}
)


def _request_context() -> Any | None:
    try:
        from fastmcp.server.dependencies import get_context

        return get_context()
    except (ImportError, RuntimeError):
        return None


def client_supports_form_elicitation() -> bool:
    """True when the active client advertised form-mode elicitation."""
    ctx = _request_context()
    if ctx is None:
        return False
    try:
        session = ctx.session
        caps = getattr(session, "client_capabilities", None)
        if caps is None:
            return False
        elic = getattr(caps, "elicitation", None)
        return elic is not None and getattr(elic, "form", None) is not None
    except Exception:  # noqa: BLE001 - outside request / mock session
        return False


def _input_responses() -> dict[str, Any] | None:
    ctx = _request_context()
    if ctx is None:
        return None
    try:
        return ctx.input_responses
    except Exception:  # noqa: BLE001
        return None


def elicit_content(request_key: str) -> dict[str, Any] | None | bool:
    """Return accepted form content, ``False`` if declined/cancelled, else ``None``."""
    responses = _input_responses()
    if not responses or request_key not in responses:
        return None
    result = responses[request_key]
    action = getattr(result, "action", None)
    if action in {"decline", "cancel"}:
        return False
    if action != "accept":
        return None
    content = getattr(result, "content", None)
    return content if isinstance(content, dict) else {}


def is_input_required(value: Any) -> bool:
    try:
        from mcp.types import InputRequiredResult
    except ImportError:
        return False
    return isinstance(value, InputRequiredResult)


def form_elicit(
    *,
    key: str,
    message: str,
    schema: dict[str, Any],
    request_state: str | None = None,
) -> Any:
    """Build an ``InputRequiredResult`` with one form elicitation request."""
    from mcp.types import ElicitRequest, ElicitRequestFormParams, InputRequiredResult

    return InputRequiredResult(
        input_requests={
            key: ElicitRequest(
                params=ElicitRequestFormParams(
                    mode="form",
                    message=message,
                    requested_schema=schema,
                )
            )
        },
        request_state=request_state,
    )


def batch_confirm_min() -> int:
    """Minimum batch size that triggers confirm elicitation; ``0`` disables."""
    raw = os.environ.get("MCP_BATCH_CONFIRM_MIN", "8").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 8


def resolve_diagram_type(diagram_type: str | None) -> str | dict[str, Any] | Any:
    """Return a catalog key, an error dict, or an ``InputRequiredResult``."""
    types = MCP_SETTINGS.diagram_types
    key = (diagram_type or "").strip().lower()
    if key in types:
        return key

    answered = elicit_content(PICK_TYPE_KEY)
    if answered is False:
        return {"error": "Diagram type selection was declined or cancelled."}
    if isinstance(answered, dict):
        picked = str(answered.get("diagram_type") or "").strip().lower()
        if picked in types:
            return picked
        return {"error": f"Unknown diagram_type from elicitation: {picked!r}"}

    names = sorted(types.keys())
    suggestions = difflib.get_close_matches(key, names, n=8, cutoff=0.45) if key else []

    if not client_supports_form_elicitation():
        if not key:
            return {
                "error": "diagram_type is required. Use list_diagram_types or uml://types."
            }
        err: dict[str, Any] = {
            "error": (
                f"Unsupported diagram type: {diagram_type!r}. "
                "Use list_diagram_types or uml://types."
            )
        }
        if suggestions:
            err["suggestions"] = suggestions
        return err

    enum_vals = suggestions or names
    if len(enum_vals) > 80:
        enum_vals = enum_vals[:80]
    msg = (
        f"Unknown diagram_type {diagram_type!r}. Pick a supported type."
        if key
        else "Choose a diagram_type for this render."
    )
    return form_elicit(
        key=PICK_TYPE_KEY,
        message=msg,
        schema={
            "type": "object",
            "properties": {
                "diagram_type": {
                    "type": "string",
                    "title": "Diagram type",
                    "enum": enum_vals,
                }
            },
            "required": ["diagram_type"],
        },
        request_state=json.dumps({"kind": "diagram_type", "given": key}),
    )


def resolve_theme(
    diagram_type: str, theme: str | None
) -> str | None | dict[str, Any] | Any:
    """Resolve ``theme``; elicit when a background alias is passed instead of a theme."""
    if theme is None or not str(theme).strip():
        return None
    raw = str(theme).strip()
    lower = raw.lower()

    answered = elicit_content(PICK_THEME_KEY)
    if answered is False:
        return {"error": "Theme selection was declined or cancelled."}
    if isinstance(answered, dict) and "theme" in answered:
        picked = str(answered.get("theme") or "").strip()
        return picked or None

    if lower not in BACKGROUND_THEME_ALIASES:
        return raw

    bg = normalize_background(lower)
    cfg = MCP_SETTINGS.diagram_types.get(diagram_type)
    backend = (cfg.backend if cfg else "") or "plantuml"
    family = (
        "mermaid" if backend == "mermaid" else "d2" if backend == "d2" else "plantuml"
    )
    options = list(themes_for_background(family, bg))
    if not options:
        return None

    if not client_supports_form_elicitation():
        # Auto-pick first recommended theme when the client cannot elicit.
        return options[0]

    return form_elicit(
        key=PICK_THEME_KEY,
        message=(
            f"Theme {theme!r} looks like a page background. "
            f"Pick a concrete {family} theme for a {bg} background."
        ),
        schema={
            "type": "object",
            "properties": {
                "theme": {
                    "type": "string",
                    "title": "Theme",
                    "enum": options,
                }
            },
            "required": ["theme"],
        },
        request_state=json.dumps(
            {"kind": "theme", "background": bg, "diagram_type": diagram_type}
        ),
    )


def maybe_confirm_batch(items: list[Any]) -> dict[str, Any] | Any | None:
    """Return confirm elicitation, decline error, or ``None`` to proceed."""
    threshold = batch_confirm_min()
    if threshold <= 0 or len(items) < threshold:
        return None

    answered = elicit_content(CONFIRM_BATCH_KEY)
    if answered is False:
        return {"error": "Batch render was declined or cancelled.", "results": []}
    if isinstance(answered, dict):
        if answered.get("confirm") is True:
            return None
        return {"error": "Batch render was not confirmed.", "results": []}

    if not client_supports_form_elicitation():
        return None

    return form_elicit(
        key=CONFIRM_BATCH_KEY,
        message=(
            f"Render {len(items)} diagrams in one batch? "
            f"(Confirm threshold is {threshold}; set MCP_BATCH_CONFIRM_MIN=0 to disable.)"
        ),
        schema={
            "type": "object",
            "properties": {
                "confirm": {
                    "type": "boolean",
                    "title": "Confirm batch render",
                    "description": f"Proceed with {len(items)} diagrams",
                }
            },
            "required": ["confirm"],
        },
        request_state=json.dumps({"kind": "batch", "count": len(items)}),
    )
