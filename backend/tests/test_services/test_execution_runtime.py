from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import bioimageflow

from bioimageflow_server.models.execution_runtime import ExecutionSnapshot
from bioimageflow_server.models.execution_profiles import DistributedExecutionProfile
from bioimageflow_server.services.execution_progress import reduce_progress_events
from bioimageflow_server.services.execution_registry import (
    ExecutionRegistry,
    ExecutionRevisionConflict,
)
from bioimageflow_server.services.execution_runtime import (
    ExecutionCoordinator,
    SubmittedRunAdapter,
    open_public_submitted_run,
)
from tests.test_services.test_execution_profiles import profile_fields


def _snapshot(**updates: Any) -> ExecutionSnapshot:
    values = {
        "execution_id": "run_0123456789abcdef0123456789abcdef",
        "workflow_id": "demo",
        "backend": "submitted_remote",
        "target_id": "cluster",
        "state": "prepared",
        "reconnect": {"storage_path": "/cluster/workflow", "run_id": "run_remote"},
    }
    values.update(updates)
    return ExecutionSnapshot(**values)


def test_registry_atomically_revisions_lists_and_reloads(tmp_path: Path) -> None:
    registry = ExecutionRegistry(tmp_path)
    created = registry.save(_snapshot())
    updated = registry.save(
        created.model_copy(update={"state": "running"}),
        expected_revision=created.revision,
    )

    assert created.revision == 0
    assert updated.revision == 1
    assert registry.get(created.execution_id).state == "running"
    assert registry.list(workflow_id="demo").items == [updated]
    assert not list(registry.root.glob("*.tmp"))
    persisted = json.loads((registry.root / f"{created.execution_id}.json").read_text())
    assert persisted["revision"] == 1

    with pytest.raises(ExecutionRevisionConflict):
        registry.save(updated, expected_revision=0)


def test_progress_reducer_is_idempotent_and_keeps_parallel_diagnostics() -> None:
    events = [
        {
            "sequence": 1,
            "kind": "public",
            "payload": {
                "node_name": "segment/a",
                "status": "row_progress",
                "row": 2,
                "total_rows": 5,
                "timestamp": 10.0,
                "current": 2,
                "maximum": 5,
            },
        },
        {
            "sequence": 2,
            "kind": "diagnostic",
            "payload": {
                "schema": "bioimageflow.node_failure.v1",
                "scoped_node_path": "segment/a",
                "category": "execution",
                "exception_type": "ValueError",
                "message": "a failed",
                "traceback": "trace a",
                "attempt_id": "attempt-a",
                "retry_status": "terminal",
                "terminal": True,
            },
        },
        {
            "sequence": 3,
            "kind": "diagnostic",
            "payload": {
                "schema": "bioimageflow.node_failure.v1",
                "scoped_node_path": "measure/b",
                "category": "execution",
                "exception_type": "RuntimeError",
                "message": "b failed",
                "traceback": None,
                "attempt_id": "attempt-b",
                "retry_status": "terminal",
                "terminal": True,
            },
        },
    ]
    reduced = reduce_progress_events(_snapshot(state="running"), events)
    replayed = reduce_progress_events(reduced, events)

    assert reduced.progress_cursor == 3
    assert reduced.jobs["segment/a"].row == 2
    assert reduced.jobs["segment/a"].diagnostic.message == "a failed"
    assert reduced.jobs["measure/b"].diagnostic.message == "b failed"
    assert replayed == reduced


def test_reducer_accepts_public_bioimageflow_diagnostic_value() -> None:
    diagnostic_type = getattr(bioimageflow, "NodeFailureDiagnostic", None)
    if diagnostic_type is None:
        pytest.skip("BioImageFlow 0.4 public diagnostic value is not installed in this worktree")
    diagnostic = diagnostic_type(
        scoped_node_path="nested/tool",
        category="execution",
        exception_type="RuntimeError",
        message="failed",
        attempt_id="attempt-1",
    )
    reduced = reduce_progress_events(
        _snapshot(state="running"),
        [{"sequence": 1, "kind": "diagnostic", "payload": diagnostic.to_dict()}],
    )
    assert reduced.jobs["nested/tool"].diagnostic.attempt_id == "attempt-1"


def test_remote_reconnect_uses_retained_profile_revision_after_profile_edit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fields = profile_fields(
        mode="submitted_remote",
        launch={
            "backend": "psij",
            "executor": "slurm",
            "walltime_seconds": 3600,
            "cpu_cores": 1,
        },
        transport={
            "host": "confirmed-cluster",
            "staging_root": "/cluster/staging",
            "remote_executable": "/usr/bin/bioimageflow-cluster-agent",
            "connect_timeout": 15.0,
        },
        remote_workflow_root="/cluster/workflows",
    )
    record = DistributedExecutionProfile(
        **fields.model_dump(mode="python"),
        id="profile_" + "1" * 32,
        revision=4,
    )
    opened: dict[str, Any] = {}

    class _RemoteRun:
        @staticmethod
        def open(transport: Any, storage_path: str, run_id: str) -> _FakeHandle:
            opened.update(
                transport=transport,
                storage_path=storage_path,
                run_id=run_id,
            )
            return _FakeHandle()

    monkeypatch.setattr(bioimageflow, "RemoteWorkflowRun", _RemoteRun)
    snapshot = _snapshot(
        profile_id=record.id,
        profile_revision=record.revision,
        target_snapshot={
            "name": record.name,
            "mode": record.mode,
            "profile": record.model_copy(update={"pre_launch": None}).model_dump(mode="json"),
        },
    )
    resolver = type(
        "ChangedProfileStore",
        (),
        {
            "resolve_revision": staticmethod(
                lambda *_args: (_ for _ in ()).throw(
                    AssertionError("reconnect must not read the edited profile")
                )
            )
        },
    )()

    adapter = open_public_submitted_run(snapshot, resolver)

    assert isinstance(adapter, SubmittedRunAdapter)
    assert opened["storage_path"] == "/cluster/workflow"
    assert opened["run_id"] == "run_remote"
    assert opened["transport"].host == "confirmed-cluster"


class _FakeHandle:
    def __init__(self, *, fail_refresh: bool = False) -> None:
        self.status = "running"
        self.fail_refresh = fail_refresh
        self.cancelled = False

    def refresh(self) -> None:
        if self.fail_refresh:
            raise ConnectionError("offline")

    def progress(self, *, after_sequence: int = 0) -> list[dict[str, Any]]:
        return []

    def cancel(self) -> None:
        self.cancelled = True
        self.status = "cancel_requested"

    def logs(self) -> str:
        return "output"

    def result(self, *, destination: Path) -> None:
        destination.write_text("result")


@pytest.mark.anyio
async def test_coordinator_reconnects_without_resubmission_and_cancels(tmp_path: Path) -> None:
    registry = ExecutionRegistry(tmp_path)
    saved = registry.save(_snapshot())
    handle = _FakeHandle()
    reconnects: list[str] = []

    def reconnect(snapshot: ExecutionSnapshot) -> SubmittedRunAdapter:
        reconnects.append(snapshot.execution_id)
        return SubmittedRunAdapter(handle)

    coordinator = ExecutionCoordinator(registry, reconnector=reconnect, poll_interval=60)
    await coordinator.start()
    cancelled = await coordinator.cancel(saved.execution_id)
    await coordinator.close()

    assert reconnects == [saved.execution_id]
    assert handle.cancelled
    assert cancelled.state == "cancel_requested"


@pytest.mark.anyio
async def test_observation_failure_does_not_fail_authoritative_run(tmp_path: Path) -> None:
    registry = ExecutionRegistry(tmp_path)
    saved = registry.save(_snapshot(state="running"))
    handle = _FakeHandle(fail_refresh=True)
    coordinator = ExecutionCoordinator(
        registry,
        reconnector=lambda snapshot: SubmittedRunAdapter(handle),
        poll_interval=60,
    )
    await coordinator.attach(saved.execution_id, SubmittedRunAdapter(handle), publish_initial=False)
    observed = await coordinator.cancel(saved.execution_id)
    await coordinator.close()

    assert observed.state == "running"
    assert not observed.observation.reachable
    assert observed.observation.error == "offline"
