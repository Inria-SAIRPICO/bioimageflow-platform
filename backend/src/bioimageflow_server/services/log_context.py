"""Execution context propagated to logs emitted by worker-thread library code."""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from bioimageflow_server.models.execution import ExecutionContext


_ACTIVE_CONTEXT_LOCK = threading.Lock()
_ACTIVE_EXECUTION_CONTEXT: ExecutionContext | None = None
_FACTORY_LOCK = threading.Lock()
_CONTEXT_SNAPSHOT_ATTRIBUTE = "_bioimageflow_execution_log_context_snapshot"
_FACTORY_MARKER_ATTRIBUTE = "_bioimageflow_execution_log_context_factory"


def _is_execution_record(record: logging.LogRecord) -> bool:
    """Return whether a library record belongs to node execution output."""

    if record.name.startswith("bioimageflow.node."):
        return True
    if record.name == "bioimageflow" and record.module == "engine":
        return True
    if record.name != "wetlands" and not record.name.startswith("wetlands."):
        return False
    return (
        getattr(record, "log_source", None) == "execution"
        and isinstance((call_target := getattr(record, "call_target", None)), str)
        and call_target.startswith("worker:")
    )


def _ensure_context_snapshot_factory() -> None:
    """Snapshot the active run when a record is created, before async handoff."""

    with _FACTORY_LOCK:
        previous_factory = logging.getLogRecordFactory()
        if getattr(previous_factory, _FACTORY_MARKER_ATTRIBUTE, False):
            return

        def _context_snapshot_factory(*args: object, **kwargs: object) -> logging.LogRecord:
            record = previous_factory(*args, **kwargs)
            with _ACTIVE_CONTEXT_LOCK:
                context = _ACTIVE_EXECUTION_CONTEXT
            if context is not None:
                setattr(record, _CONTEXT_SNAPSHOT_ATTRIBUTE, context)
            return record

        setattr(_context_snapshot_factory, _FACTORY_MARKER_ATTRIBUTE, True)
        logging.setLogRecordFactory(_context_snapshot_factory)


def execution_log_context_for_record(
    record: logging.LogRecord,
) -> ExecutionContext | None:
    """Resolve source-time provenance without consulting mutable manager state."""

    if not _is_execution_record(record):
        return None

    execution_id = getattr(record, "execution_id", None)
    workflow_id = getattr(record, "workflow_id", None)
    draft_revision = getattr(record, "draft_revision", None)
    if execution_id is not None or workflow_id is not None or draft_revision is not None:
        if not isinstance(execution_id, str) or not isinstance(workflow_id, str):
            return None
        try:
            return ExecutionContext(
                execution_id=execution_id,
                workflow_id=workflow_id,
                draft_revision=draft_revision,
            )
        except ValueError:
            return None

    snapshot = getattr(record, _CONTEXT_SNAPSHOT_ATTRIBUTE, None)
    if isinstance(snapshot, ExecutionContext):
        return snapshot

    return None


@contextmanager
def bind_execution_log_context(context: ExecutionContext) -> Iterator[None]:
    """Bind one execution identity until its execution workers have drained.

    ``ExecutionManager`` holds this boundary around ``workflow.compute()``.
    Execution-lifetime engines stop their workers and join ``ProcessLogger``
    readers before that call returns, while the record factory freezes the
    identity when each record is created. Delayed handler scheduling therefore
    cannot relabel an earlier run's record with a later run's identity.
    """

    global _ACTIVE_EXECUTION_CONTEXT

    _ensure_context_snapshot_factory()
    with _ACTIVE_CONTEXT_LOCK:
        if _ACTIVE_EXECUTION_CONTEXT is not None and _ACTIVE_EXECUTION_CONTEXT != context:
            raise RuntimeError("Another execution log context is already active")
        _ACTIVE_EXECUTION_CONTEXT = context
    try:
        yield
    finally:
        with _ACTIVE_CONTEXT_LOCK:
            if _ACTIVE_EXECUTION_CONTEXT == context:
                _ACTIVE_EXECUTION_CONTEXT = None


__all__ = ["bind_execution_log_context", "execution_log_context_for_record"]
