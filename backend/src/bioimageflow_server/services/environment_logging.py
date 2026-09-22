"""Shared rendering for Wetlands managed-environment operation events."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from bioimageflow_server.services.operation_failures import normalize_operation_text


logger = logging.getLogger("bioimageflow.environment")


@dataclass(frozen=True)
class EnvironmentLogEntry:
    """A Logger-ready representation of one public Wetlands operation event."""

    level: str
    message: str
    timestamp: float


def environment_log_entry(event: Any) -> EnvironmentLogEntry | None:
    """Return a normalized log entry without depending on private Wetlands APIs."""

    kind = getattr(getattr(event, "kind", None), "value", None)
    line = getattr(event, "line", None)
    message = (
        line if kind == "output" and isinstance(line, str) else getattr(event, "message", None)
    )
    if not isinstance(message, str) or not message:
        return None

    state = getattr(getattr(event, "state", None), "value", None)
    if state == "failed":
        level = "ERROR"
    elif kind == "cancellation_requested" or state == "canceled":
        level = "WARNING"
    else:
        # Pixi writes ordinary progress to stderr, so the stream alone must not
        # promote an otherwise informational line to a warning.
        level = "INFO"

    timestamp = getattr(event, "timestamp", None)
    if not isinstance(timestamp, (int, float)):
        timestamp = time.time()
    return EnvironmentLogEntry(
        level=level,
        message=normalize_operation_text(message),
        timestamp=float(timestamp),
    )


def log_environment_operation_event(event: Any, *, owner: str | None = None) -> None:
    """Send one Wetlands operation event through the streamed Logger bridge."""

    entry = environment_log_entry(event)
    if entry is None:
        return
    message = f"{owner}: {entry.message}" if owner else entry.message
    logger.log(getattr(logging, entry.level), message)


__all__ = [
    "EnvironmentLogEntry",
    "environment_log_entry",
    "log_environment_operation_event",
]
