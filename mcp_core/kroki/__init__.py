"""Kroki operations: health of a Kroki server and a local Docker stack for it."""

from .health import COMPANIONS, probe, wait_until_ready
from .stack import DockerUnavailable, StackError

__all__ = [
    "COMPANIONS",
    "DockerUnavailable",
    "StackError",
    "probe",
    "wait_until_ready",
]
