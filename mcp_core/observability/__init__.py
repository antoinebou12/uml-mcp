"""Observability: MXCP-style audit trail, structured logging, metrics, rate limits.

Everything is configured from the ``logging``, ``audit``, ``metrics`` and
``rate_limit`` sections of ``uml-mcp.yaml`` (see :mod:`mcp_core.core.settings_file`).
"""

from .audit import AuditRecord, get_audit_logger, record_operation
from .context import RequestContext, current_context, set_context

__all__ = [
    "AuditRecord",
    "RequestContext",
    "current_context",
    "get_audit_logger",
    "record_operation",
    "set_context",
]
