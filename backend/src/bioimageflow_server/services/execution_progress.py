"""Idempotent reduction of BioImageFlow progress into retained job snapshots."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from bioimageflow_server.models.execution_runtime import (
    ExecutionSnapshot,
    FailureDiagnosticSnapshot,
    JobSnapshot,
    JobState,
    utc_now,
)

_PUBLIC_STATES: dict[str, JobState] = {
    "started": "running",
    "row_progress": "running",
    "row_complete": "running",
    "completed": "succeeded",
    "cached": "cached",
    "failed": "failed",
    "cancelled": "cancelled",
    "skipped": "skipped",
    "blocked": "blocked",
}
_TERMINAL_JOB_STATES = {"cached", "succeeded", "failed", "cancelled", "skipped", "blocked"}


def _event_time(value: Any) -> datetime:
    if type(value) in {int, float}:
        return datetime.fromtimestamp(float(value), timezone.utc)
    return utc_now()


def _diagnostic(payload: Mapping[str, Any]) -> FailureDiagnosticSnapshot:
    return FailureDiagnosticSnapshot.model_validate(
        {key: value for key, value in payload.items() if key != "schema"}
    )


def reduce_progress_events(
    snapshot: ExecutionSnapshot,
    events: Iterable[Mapping[str, Any]],
) -> ExecutionSnapshot:
    """Apply new globally sequenced events once, retaining independent failures."""

    jobs = dict(snapshot.jobs)
    cursor = snapshot.progress_cursor
    changed = False
    ordered = sorted(events, key=lambda event: int(event.get("sequence", -1)))
    for event in ordered:
        sequence = event.get("sequence")
        if type(sequence) is not int or sequence <= cursor:
            continue
        kind = event.get("kind")
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            cursor = sequence
            changed = True
            continue
        if kind == "diagnostic":
            diagnostic = _diagnostic(payload)
            existing = jobs.get(diagnostic.scoped_node_path) or JobSnapshot(
                scoped_node_path=diagnostic.scoped_node_path
            )
            jobs[diagnostic.scoped_node_path] = existing.model_copy(
                update={
                    "state": "failed" if diagnostic.terminal else existing.state,
                    "diagnostic": diagnostic,
                    "finished_at": utc_now() if diagnostic.terminal else existing.finished_at,
                    "updated_at": utc_now(),
                }
            )
        elif kind == "phase":
            node_path = payload.get("node_name")
            message = payload.get("message")
            if isinstance(node_path, str) and node_path and isinstance(message, str):
                existing = jobs.get(node_path) or JobSnapshot(scoped_node_path=node_path)
                jobs[node_path] = existing.model_copy(
                    update={"message": message, "updated_at": utc_now()}
                )
        elif kind == "public":
            node_path = payload.get("node_name")
            if isinstance(node_path, str) and node_path:
                existing = jobs.get(node_path) or JobSnapshot(scoped_node_path=node_path)
                state = _PUBLIC_STATES.get(str(payload.get("status")), existing.state)
                timestamp = _event_time(payload.get("timestamp"))
                updates: dict[str, Any] = {
                    "state": state,
                    "row": max(0, int(payload.get("row") or 0)),
                    "total_rows": max(0, int(payload.get("total_rows") or 0)),
                    "current": payload.get("current"),
                    "maximum": payload.get("maximum"),
                    "message": payload.get("message"),
                    "result_key": payload.get("result_key"),
                    "record_id": payload.get("record_id"),
                    "updated_at": timestamp,
                }
                if state == "running" and existing.started_at is None:
                    updates["started_at"] = timestamp
                if state in _TERMINAL_JOB_STATES:
                    updates["finished_at"] = timestamp
                jobs[node_path] = existing.model_copy(update=updates)
        cursor = sequence
        changed = True
    if not changed:
        return snapshot
    return snapshot.model_copy(update={"jobs": jobs, "progress_cursor": cursor})


def progress_event_from_attached(event: Any, sequence: int) -> list[dict[str, Any]]:
    """Convert a public ProgressEvent without importing optional engines."""

    payload = {
        "schema": "bioimageflow.public_progress.v1",
        "node_name": event.node_name,
        "status": event.status,
        "row": event.row,
        "total_rows": event.total_rows,
        "current": event.current,
        "maximum": event.maximum,
        "message": event.message,
        "timestamp": event.timestamp,
        "result_key": event.result_key,
        "record_id": event.record_id,
    }
    result: list[dict[str, Any]] = []
    diagnostic = getattr(event, "diagnostic", None)
    if diagnostic is not None:
        result.append(
            {
                "sequence": sequence,
                "kind": "diagnostic",
                "payload": diagnostic.to_dict(),
            }
        )
        sequence += 1
    result.append({"sequence": sequence, "kind": "public", "payload": payload})
    return result
