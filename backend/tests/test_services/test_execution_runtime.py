from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import bioimageflow
import pytest

from bioimageflow_server.models.execution_runtime import ExecutionSnapshot
from bioimageflow_server.models.execution import ExecutionContext
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.services.execution_progress import reduce_progress_events
from bioimageflow_server.services.execution import ExecutionManager, NullEventBus
from bioimageflow_server.services.execution_registry import (
    ExecutionNotFoundError,
    ExecutionRegistry,
    ExecutionRevisionConflict,
)
from bioimageflow_server.services.execution_runtime import (
    AttachedRunAdapter,
    ExecutionCoordinator,
    ExecutionOperationError,
    ManagedResultAdapter,
    SubmittedRunAdapter,
    _archive_bundle,
    _archive_digest,
    _operation_error,
    open_public_submitted_run,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService


pytestmark = pytest.mark.campaign_excluded(reason="distributed-engine")


def _snapshot(**updates: Any) -> ExecutionSnapshot:
    values = {
        "execution_id": "run_0123456789abcdef0123456789abcdef",
        "workflow_id": "demo",
        "backend": "managed_remote",
        "target_id": "cluster",
        "state": "prepared",
        "reconnect": {
            "host": "cluster.example",
            "root": "/cluster/workflow",
            "run_id": "run_remote",
        },
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


def test_registry_binds_active_execution_and_journals_across_workspace_switch(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    current = [first]
    registry = ExecutionRegistry(lambda: current[0])
    active = registry.save(
        _snapshot(execution_id=f"run_{uuid4().hex}", state="running")
    )

    current[0] = second
    updated = registry.save(
        active.model_copy(update={"state": "cancel_requested"}),
        expected_revision=active.revision,
    )
    plan = _retry_plan(active.execution_id, f"run_{uuid4().hex}", tmp_path)
    registry.save_retry_plan(plan.to_dict())
    newer = registry.save(
        _snapshot(execution_id=f"run_{uuid4().hex}", workflow_id="second")
    )

    assert registry.get(active.execution_id) == updated
    assert (
        first / ".bioimageflow" / "executions" / f"{active.execution_id}.json"
    ).is_file()
    assert (
        first
        / ".bioimageflow"
        / "executions"
        / "retry_plans"
        / f"{plan.digest.removeprefix('sha256:')}.json"
    ).is_file()
    assert (
        second / ".bioimageflow" / "executions" / f"{newer.execution_id}.json"
    ).is_file()
    assert registry.list().items == [newer]


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
    diagnostic = bioimageflow.NodeFailureDiagnostic(
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


def test_remote_reconnect_uses_only_durable_host_root_and_run_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: dict[str, Any] = {}

    class _RemoteCluster:
        def __init__(self, *, host: str, root: str) -> None:
            opened.update(host=host, root=root)

        def attach(self, run_id: str) -> _FakeHandle:
            opened["run_id"] = run_id
            return _FakeHandle()

    import bioimageflow.cluster as cluster_api

    monkeypatch.setattr(cluster_api, "RemoteCluster", _RemoteCluster)
    adapter = open_public_submitted_run(_snapshot())

    assert isinstance(adapter, SubmittedRunAdapter)
    assert opened["host"] == "cluster.example"
    assert opened["root"] == "/cluster/workflow"
    assert opened["run_id"] == "run_remote"


def test_remote_reconnect_rejects_incomplete_attachment_identity() -> None:
    with pytest.raises(ValueError, match="metadata is incomplete"):
        open_public_submitted_run(
            _snapshot(
                reconnect={"host": "cluster.example", "run_id": "run_remote"},
            )
        )


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

    def snapshot(self) -> dict[str, Any]:
        return {"state": self.status}

    def cancel(self) -> None:
        self.cancelled = True
        self.status = "cancel_requested"

    def download_result(self, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "result.txt").write_text("result")


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
    assert observed.observation.error == "The execution could not be observed."


def _retry_plan(
    parent_id: str,
    child_id: str,
    storage: Path,
    *,
    recompute: Any | None = None,
) -> Any:
    return bioimageflow.RunRetryPlan(
        parent_run_id=parent_id,
        retry_run_id=child_id,
        parent_status="failed",
        parent_status_revision=7,
        storage_path=storage.as_posix(),
        retained_submission_digest="sha256:" + "1" * 64,
        retained_material_digest="sha256:" + "2" * 64,
        retained_material_entries=3,
        cache_selection_revision="sha256:" + "3" * 64,
        recompute=recompute,
        invalidations=(),
        conflicting_run_ids=(),
    )


class _RetryHandle(_FakeHandle):
    def __init__(self, plan: Any) -> None:
        super().__init__()
        self.status = "failed"
        self.plan = plan
        self.planned: list[Any] = []
        self.started: list[Any] = []

    def plan_retry(self, recompute: Any = None) -> Any:
        self.planned.append(recompute)
        return self.plan

    def start_retry(self, plan: Any) -> _FakeHandle:
        self.started.append(plan)
        child = _FakeHandle()
        child.status = "queued"
        return child


class _RetryStartError(ExecutionOperationError):
    def __init__(self, code: str) -> None:
        super().__init__(code, code, details={"retryable": False})


class _RunNotFound(bioimageflow.cluster.ClusterOperationError):
    def __init__(self) -> None:
        super().__init__(
            bioimageflow.cluster.ClusterDiagnostic(
                phase="run-observation",
                category="run-not-found",
                message="The exact child run does not exist.",
                allocation_state="none",
                retry_safety="safe",
                next_action="replay-exact-plan",
                identities={},
            )
        )


class _FailingRetryHandle(_RetryHandle):
    def __init__(self, plan: Any, code: str) -> None:
        super().__init__(plan)
        self.code = code

    def start_retry(self, plan: Any) -> _FakeHandle:
        from bioimageflow.cluster import ClusterDiagnostic, ClusterOperationError

        self.started.append(plan)
        raise ClusterOperationError(
            ClusterDiagnostic(
                phase="retry-start",
                category=self.code,
                message="The managed retry could not be started.",
                allocation_state=(
                    "unknown" if self.code == "submission-uncertain" else "none"
                ),
                retry_safety=(
                    "same-attempt-only"
                    if self.code == "submission-uncertain"
                    else "safe"
                ),
                next_action=(
                    "attach-exact-child"
                    if self.code == "submission-uncertain"
                    else "create-new-plan"
                ),
                identities={"run_id": plan.retry_run_id},
            )
        )


class _RecordingPublisher:
    def __init__(self) -> None:
        self.snapshots: list[tuple[ExecutionSnapshot, bool]] = []

    async def publish_execution_snapshot(
        self,
        snapshot: ExecutionSnapshot,
        *,
        initial: bool,
    ) -> None:
        self.snapshots.append((snapshot, initial))


@pytest.mark.anyio
async def test_retry_plan_is_durable_and_confirmation_recovers_exact_child(
    tmp_path: Path,
) -> None:
    parent_id = f"run_{uuid4().hex}"
    child_id = f"run_{uuid4().hex}"
    registry = ExecutionRegistry(tmp_path)
    registry.save(
        _snapshot(
            execution_id=parent_id,
            backend="managed_remote",
            state="failed",
            reconnect={"host": "cluster", "root": "/shared", "run_id": parent_id},
        )
    )
    plan = _retry_plan(parent_id, child_id, tmp_path)
    handle = _RetryHandle(plan)

    def reconnect(snapshot: ExecutionSnapshot) -> SubmittedRunAdapter:
        if snapshot.execution_id == child_id:
            raise _RunNotFound
        return SubmittedRunAdapter(handle)

    coordinator = ExecutionCoordinator(
        registry,
        reconnector=reconnect,
        poll_interval=60,
    )

    presentation = await coordinator.plan_retry(parent_id)

    assert presentation.child_execution_id == child_id
    assert presentation.confirmable
    assert handle.started == []
    with pytest.raises(ExecutionNotFoundError):
        registry.get(child_id)

    child = await coordinator.confirm_retry(
        parent_id,
        plan_digest=presentation.plan_digest,
    )
    repeated = await coordinator.confirm_retry(
        parent_id,
        plan_digest=presentation.plan_digest,
    )
    await coordinator.close()

    assert child.execution_id == child_id
    assert repeated.execution_id == child_id
    assert len(handle.started) == 1
    assert handle.started[0].to_dict() == plan.to_dict()
    assert registry.get(parent_id).child_execution_ids == [child_id]


@pytest.mark.anyio
async def test_retry_confirmation_refreshes_parent_after_waiting_for_run_lock(
    tmp_path: Path,
) -> None:
    parent_id = f"run_{uuid4().hex}"
    child_id = f"run_{uuid4().hex}"
    registry = ExecutionRegistry(tmp_path)
    registry.save(
        _snapshot(
            execution_id=parent_id,
            backend="managed_remote",
            state="failed",
            reconnect={"host": "cluster", "root": "/shared", "run_id": parent_id},
        )
    )
    plan = _retry_plan(parent_id, child_id, tmp_path)
    handle = _RetryHandle(plan)

    def reconnect(snapshot: ExecutionSnapshot) -> SubmittedRunAdapter:
        if snapshot.execution_id == child_id:
            raise _RunNotFound
        return SubmittedRunAdapter(handle)

    coordinator = ExecutionCoordinator(
        registry,
        reconnector=reconnect,
        poll_interval=60,
    )
    presentation = await coordinator.plan_retry(parent_id)
    original_get = coordinator.get
    first_read = asyncio.Event()
    reads = 0

    async def observed_get(execution_id: str) -> ExecutionSnapshot:
        nonlocal reads
        snapshot = await original_get(execution_id)
        reads += 1
        if reads == 1:
            first_read.set()
        return snapshot

    coordinator.get = observed_get  # type: ignore[method-assign]
    lock = coordinator._locks.setdefault(parent_id, asyncio.Lock())
    await lock.acquire()
    confirmation = asyncio.create_task(
        coordinator.confirm_retry(parent_id, plan_digest=presentation.plan_digest)
    )
    await first_read.wait()
    before_export = registry.get(parent_id)
    registry.save(before_export, expected_revision=before_export.revision)
    lock.release()

    child = await confirmation
    await coordinator.close()

    assert child.execution_id == child_id
    assert len(handle.started) == 1
    assert registry.get(parent_id).child_execution_ids == [child_id]


@pytest.mark.anyio
async def test_startup_resumes_confirmed_plan_before_reconnect(tmp_path: Path) -> None:
    parent_id = f"run_{uuid4().hex}"
    child_id = f"run_{uuid4().hex}"
    registry = ExecutionRegistry(tmp_path)
    registry.save(
        _snapshot(
            execution_id=parent_id,
            backend="managed_remote",
            state="failed",
            reconnect={"host": "cluster", "root": "/shared", "run_id": parent_id},
        )
    )
    plan = _retry_plan(parent_id, child_id, tmp_path)
    registry.save_retry_plan(plan.to_dict())
    registry.confirm_retry_plan(parent_id, plan.digest)
    handle = _RetryHandle(plan)

    def reconnect(snapshot: ExecutionSnapshot) -> SubmittedRunAdapter:
        if snapshot.execution_id == child_id:
            raise _RunNotFound
        return SubmittedRunAdapter(handle)

    coordinator = ExecutionCoordinator(
        registry,
        reconnector=reconnect,
        poll_interval=60,
    )

    await coordinator.start()
    await coordinator.close()

    assert len(handle.started) == 1
    assert registry.get(child_id).retry_of_execution_id == parent_id


@pytest.mark.anyio
async def test_startup_keeps_one_reconnect_task_for_unreachable_uncertain_child(
    tmp_path: Path,
) -> None:
    parent_id = f"run_{uuid4().hex}"
    child_id = f"run_{uuid4().hex}"
    registry = ExecutionRegistry(tmp_path)
    registry.save(
        _snapshot(
            execution_id=parent_id,
            state="failed",
            reconnect={"host": "cluster", "root": "/shared", "run_id": parent_id},
        )
    )
    plan = _retry_plan(parent_id, child_id, tmp_path)
    registry.save_retry_plan(plan.to_dict())
    registry.confirm_retry_plan(parent_id, plan.digest)
    parent = _FailingRetryHandle(plan, "submission-uncertain")
    child_attempts = 0

    def reconnect(snapshot: ExecutionSnapshot) -> SubmittedRunAdapter:
        nonlocal child_attempts
        if snapshot.execution_id == child_id:
            child_attempts += 1
            if child_attempts == 1:
                raise _RunNotFound
            raise ConnectionError("unreachable child")
        return SubmittedRunAdapter(parent)

    coordinator = ExecutionCoordinator(registry, reconnector=reconnect, poll_interval=60)

    await coordinator.start()

    assert child_attempts == 2
    assert list(coordinator._poll_tasks) == [child_id]
    task = coordinator._poll_tasks[child_id]
    await coordinator.close()
    assert task.done()
    assert coordinator._poll_tasks == {}


@pytest.mark.anyio
async def test_uncertain_retry_reconnects_exact_child_now_and_never_restarts(
    tmp_path: Path,
) -> None:
    parent_id = f"run_{uuid4().hex}"
    child_id = f"run_{uuid4().hex}"
    registry = ExecutionRegistry(tmp_path)
    registry.save(
        _snapshot(
            execution_id=parent_id,
            backend="managed_remote",
            state="failed",
            reconnect={"host": "cluster", "root": "/shared", "run_id": parent_id},
        )
    )
    plan = _retry_plan(parent_id, child_id, tmp_path)
    parent_handle = _FailingRetryHandle(plan, "submission-uncertain")
    child_handle = _FakeHandle()
    child_handle.status = "queued"
    reconnects: list[str] = []
    child_attach_attempts = 0

    def reconnect(snapshot: ExecutionSnapshot) -> SubmittedRunAdapter:
        nonlocal child_attach_attempts
        reconnects.append(snapshot.execution_id)
        if snapshot.execution_id == child_id:
            child_attach_attempts += 1
            if child_attach_attempts == 1:
                raise _RunNotFound
            return SubmittedRunAdapter(child_handle)
        return SubmittedRunAdapter(parent_handle)

    publisher = _RecordingPublisher()
    coordinator = ExecutionCoordinator(
        registry,
        reconnector=reconnect,
        publisher=publisher,
        poll_interval=60,
    )
    presentation = await coordinator.plan_retry(parent_id)

    with pytest.raises(ExecutionOperationError) as raised:
        await coordinator.confirm_retry(parent_id, plan_digest=presentation.plan_digest)
    repeated = await coordinator.confirm_retry(
        parent_id,
        plan_digest=presentation.plan_digest,
    )
    await coordinator.close()

    restart_reconnects: list[str] = []

    def reconnect_after_restart(snapshot: ExecutionSnapshot) -> SubmittedRunAdapter:
        restart_reconnects.append(snapshot.execution_id)
        return SubmittedRunAdapter(child_handle)

    restarted = ExecutionCoordinator(
        registry,
        reconnector=reconnect_after_restart,
        poll_interval=60,
    )
    await restarted.start()
    await restarted.close()

    assert raised.value.code == "submission-uncertain"
    assert repeated.execution_id == child_id
    assert len(parent_handle.started) == 1
    assert reconnects.count(parent_id) == 2
    assert reconnects.count(child_id) == 2
    assert reconnects[-1] == child_id
    assert restart_reconnects == [child_id]
    assert registry.retry_plan_state(parent_id, plan.digest) == "started"
    assert registry.get(parent_id).child_execution_ids == [child_id]
    assert any(
        snapshot.execution_id == parent_id
        and snapshot.child_execution_ids == [child_id]
        and not initial
        for snapshot, initial in publisher.snapshots
    )
    assert any(
        snapshot.execution_id == child_id and initial for snapshot, initial in publisher.snapshots
    )


@pytest.mark.anyio
async def test_definite_retry_start_failure_retains_terminal_exact_child(
    tmp_path: Path,
) -> None:
    parent_id = f"run_{uuid4().hex}"
    child_id = f"run_{uuid4().hex}"
    registry = ExecutionRegistry(tmp_path)
    registry.save(
        _snapshot(
            execution_id=parent_id,
            backend="managed_remote",
            state="failed",
            reconnect={"host": "cluster", "root": "/shared", "run_id": parent_id},
        )
    )
    plan = _retry_plan(parent_id, child_id, tmp_path)
    handle = _FailingRetryHandle(plan, "route-incompatible")

    def reconnect(snapshot: ExecutionSnapshot) -> SubmittedRunAdapter:
        if snapshot.execution_id == child_id:
            raise _RunNotFound
        return SubmittedRunAdapter(handle)

    coordinator = ExecutionCoordinator(
        registry,
        reconnector=reconnect,
        poll_interval=60,
    )
    presentation = await coordinator.plan_retry(parent_id)

    with pytest.raises(ExecutionOperationError):
        await coordinator.confirm_retry(parent_id, plan_digest=presentation.plan_digest)
    await coordinator.close()

    assert registry.retry_plan_state(parent_id, plan.digest) == "failed"
    assert registry.get(parent_id).child_execution_ids == [child_id]
    child = registry.get(child_id)
    assert child.state == "failed"
    assert child.backend_metadata["retry_start_failed"]["code"] == "route-incompatible"


@pytest.mark.anyio
async def test_recompute_presentation_normalizes_library_tuple_to_json_list(
    tmp_path: Path,
) -> None:
    parent_id = f"run_{uuid4().hex}"
    child_id = f"run_{uuid4().hex}"
    registry = ExecutionRegistry(tmp_path)
    registry.save(
        _snapshot(
            execution_id=parent_id,
            backend="managed_remote",
            state="failed",
            reconnect={"host": "cluster", "root": "/shared", "run_id": parent_id},
        )
    )
    recompute = bioimageflow.RecomputeRequest(("preprocessing/masks",), cascade=False)
    handle = _RetryHandle(_retry_plan(parent_id, child_id, tmp_path, recompute=recompute))
    coordinator = ExecutionCoordinator(
        registry,
        reconnector=lambda _snapshot: SubmittedRunAdapter(handle),
    )

    presentation = await coordinator.plan_retry(
        parent_id,
        node_paths=("preprocessing/masks",),
        cascade=False,
    )

    assert presentation.recompute is not None
    assert presentation.recompute.node_paths == ["preprocessing/masks"]
    assert presentation.recompute.cascade is False
    assert handle.planned[0].node_paths == ("preprocessing/masks",)


@pytest.mark.anyio
async def test_attached_export_failure_preserves_success_and_disables_download(
    tmp_path: Path,
) -> None:
    registry = ExecutionRegistry(tmp_path)
    adapter = AttachedRunAdapter(
        compute=lambda _progress: {"value": 1},
        cancel=lambda: None,
        result_exporter=lambda _value, _destination: (_ for _ in ()).throw(
            RuntimeError("export failed")
        ),
        managed_destination=tmp_path / "bundle",
    )
    coordinator = ExecutionCoordinator(
        registry,
        reconnector=lambda _snapshot: adapter,
        poll_interval=0.01,
    )
    await coordinator.register(
        _snapshot(
            execution_id="run_" + "e" * 32,
            backend="direct",
            state="starting",
            reconnect={"result_bundle": str(tmp_path / "bundle")},
        ),
        adapter,
    )
    await asyncio.sleep(0.05)
    snapshot = await coordinator.get("run_" + "e" * 32)
    await coordinator.close()

    assert snapshot.state == "succeeded"
    assert snapshot.result_export.state == "unavailable"
    assert snapshot.result_export.error_code == "workflow-result-export-error"
    assert not snapshot.actions.download_results.available


@pytest.mark.anyio
async def test_attached_completion_sidecar_recovers_before_coordinator_poll(
    tmp_path: Path,
) -> None:
    execution_id = "run_" + "a" * 32
    bundle = tmp_path / execution_id
    registry = ExecutionRegistry(tmp_path / "registry")
    registry.save(
        _snapshot(
            execution_id=execution_id,
            backend="direct",
            state="running",
            reconnect={"result_bundle": str(bundle)},
        )
    )
    adapter = AttachedRunAdapter(
        compute=lambda _progress: {"value": 1},
        cancel=lambda: None,
        result_exporter=lambda _value, destination: (
            destination.mkdir(parents=True),
            (destination / "result.txt").write_text("result"),
        )[-1],
        managed_destination=bundle,
    )
    adapter.start()
    assert adapter._task is not None
    await adapter._task
    assert registry.get(execution_id).state == "running"

    coordinator = ExecutionCoordinator(
        registry,
        reconnector=lambda _snapshot: (_ for _ in ()).throw(
            AssertionError("completed attached run must recover from its sidecar")
        ),
    )
    await coordinator.start()
    recovered = await coordinator.get(execution_id)
    await coordinator.close()

    assert recovered.state == "succeeded"
    assert recovered.result_export.state == "available"
    assert recovered.result_export.archive_digest == adapter.result_export.archive_digest
    assert recovered.actions.download_results.available


@pytest.mark.anyio
async def test_attached_completion_recovery_detects_archive_tampering(
    tmp_path: Path,
) -> None:
    execution_id = "run_" + "b" * 32
    bundle = tmp_path / execution_id
    registry = ExecutionRegistry(tmp_path / "registry")
    registry.save(
        _snapshot(
            execution_id=execution_id,
            backend="direct",
            state="running",
            reconnect={"result_bundle": str(bundle)},
        )
    )
    adapter = AttachedRunAdapter(
        compute=lambda _progress: {"value": 1},
        cancel=lambda: None,
        result_exporter=lambda _value, destination: (
            destination.mkdir(parents=True),
            (destination / "result.txt").write_text("result"),
        )[-1],
        managed_destination=bundle,
    )
    adapter.start()
    assert adapter._task is not None
    await adapter._task
    bundle.with_suffix(".zip").write_bytes(b"tampered")

    with pytest.raises(ExecutionOperationError) as raised:
        adapter.export_result(bundle)
    coordinator = ExecutionCoordinator(registry, reconnector=lambda _snapshot: adapter)
    await coordinator.start()
    recovered = await coordinator.get(execution_id)
    await coordinator.close()

    assert raised.value.code == "workflow-result-integrity-error"
    assert recovered.state == "succeeded"
    assert recovered.result_export.state == "unavailable"
    assert recovered.result_export.error_code == "workflow-result-integrity-error"
    assert not recovered.actions.download_results.available


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("terminal_state", "backend"),
    [("failed", "direct"), ("cancelled", "wetlands")],
)
async def test_regular_terminal_sidecar_recovers_failure_and_cancellation(
    tmp_path: Path,
    terminal_state: str,
    backend: str,
) -> None:
    from bioimageflow.engine import WorkflowCancelledError

    execution_id = f"run_{uuid4().hex}"
    context = ExecutionContext(execution_id=execution_id, workflow_id="demo")
    manager = ExecutionManager(
        event_bus=NullEventBus(),
        tool_registry=ToolRegistryService(),
        settings=Settings(deployment_mode="desktop"),
        managed_result_root=tmp_path / "results",
    )
    manager.context = context
    manager.state = "running"
    manager._workflow = object()
    manager._workflow_run_contexts[execution_id] = object()

    async def terminate() -> None:
        if terminal_state == "cancelled":
            raise WorkflowCancelledError("cancelled")
        raise RuntimeError("failed")

    task = asyncio.create_task(terminate())
    await asyncio.gather(task, return_exceptions=True)
    manager._on_run_done(task, context)

    assert manager.retained_status(context) == terminal_state
    assert manager.retained_result_export(context).state == "unavailable"
    assert execution_id not in manager._workflow_run_contexts
    bundle = tmp_path / "results" / execution_id
    assert bundle.with_suffix(".completion.json").is_file()

    registry = ExecutionRegistry(tmp_path / "registry")
    registry.save(
        _snapshot(
            execution_id=execution_id,
            backend=backend,
            state="running",
            reconnect={"result_bundle": str(bundle)},
        )
    )
    coordinator = ExecutionCoordinator(
        registry,
        reconnector=lambda _snapshot: (_ for _ in ()).throw(
            AssertionError("terminal regular run must recover from its sidecar")
        ),
    )
    await coordinator.start()
    recovered = await coordinator.get(execution_id)
    await coordinator.close()

    assert recovered.state == terminal_state
    assert recovered.result_export.state == "unavailable"
    assert recovered.finished_at is not None


@pytest.mark.anyio
async def test_startup_lost_conversion_rederives_and_publishes_actions(tmp_path: Path) -> None:
    registry = ExecutionRegistry(tmp_path)
    execution_id = "run_" + "c" * 32
    registry.save(
        _snapshot(
            execution_id=execution_id,
            backend="direct",
            state="running",
            reconnect={"result_bundle": str(tmp_path / execution_id)},
        )
    )
    publisher = _RecordingPublisher()
    coordinator = ExecutionCoordinator(
        registry,
        reconnector=lambda _snapshot: (_ for _ in ()).throw(AssertionError),
        publisher=publisher,
    )

    await coordinator.start()
    lost = registry.get(execution_id)
    await coordinator.close()

    assert lost.state == "lost"
    assert not lost.actions.cancel.available
    assert publisher.snapshots[-1][0] == lost


@pytest.mark.anyio
async def test_managed_queued_execution_can_be_cancelled(tmp_path: Path) -> None:
    registry = ExecutionRegistry(tmp_path)
    handle = _FakeHandle()
    handle.status = "queued"
    saved = registry.save(_snapshot(backend="managed_remote", state="queued"))
    coordinator = ExecutionCoordinator(
        registry,
        reconnector=lambda _snapshot: SubmittedRunAdapter(handle),
    )

    cancelled = await coordinator.cancel(saved.execution_id)
    await coordinator.close()

    assert handle.cancelled
    assert cancelled.state == "cancel_requested"


def test_submitted_export_transient_failure_remains_pending(tmp_path: Path) -> None:
    class _ExportFailureHandle(_FakeHandle):
        def download_result(self, destination: Path) -> None:
            raise _RetryStartError("workflow-result-export-error")

    adapter = SubmittedRunAdapter(_ExportFailureHandle())

    with pytest.raises(_RetryStartError):
        adapter.export_result(tmp_path / "bundle")

    assert adapter.result_export.state == "pending"
    assert adapter.result_export.error_code == "workflow-result-export-error"


def test_submitted_export_unavailable_failure_is_terminal(tmp_path: Path) -> None:
    class _ExportFailureHandle(_FakeHandle):
        def download_result(self, destination: Path) -> None:
            raise _RetryStartError("workflow-run-result-unavailable")

    adapter = SubmittedRunAdapter(_ExportFailureHandle())

    with pytest.raises(_RetryStartError):
        adapter.export_result(tmp_path / "bundle")

    assert adapter.result_export.state == "unavailable"
    assert adapter.result_export.error_code == "workflow-run-result-unavailable"


def test_operation_error_preserves_explicit_platform_operation_error() -> None:
    exc = _RetryStartError("workflow-result-integrity-error")

    converted = _operation_error(exc, fallback="workflow-result-export-error")

    assert converted.code == "workflow-result-integrity-error"
    assert converted.details == {"retryable": False}


def test_operation_error_does_not_trust_arbitrary_code_or_details() -> None:
    class _UntrustedFailure(RuntimeError):
        code = "submission-uncertain"
        details = {"credential": "must-not-escape"}

    converted = _operation_error(
        _UntrustedFailure("credential=must-not-escape"),
        fallback="workflow-result-export-error",
    )

    assert converted.code == "workflow-result-export-error"
    assert str(converted) == "The managed execution operation failed unexpectedly."
    assert converted.details == {}
    assert "must-not-escape" not in repr(converted.details)


def test_operation_error_normalizes_public_cluster_diagnostic_with_identities() -> None:
    from bioimageflow.cluster import ClusterDiagnostic, ClusterOperationError

    exc = ClusterOperationError(
        ClusterDiagnostic(
            phase="retry-start",
            category="submission-uncertain",
            message="The scheduler acknowledgement is uncertain.",
            allocation_state="unknown",
            retry_safety="same-attempt-only",
            next_action="attach-exact-child",
            identities={"run_id": "run_" + "4" * 32, "attempt_id": "attempt-1"},
        )
    )

    converted = _operation_error(exc, fallback="workflow-run-retry-error")

    assert converted.code == "submission-uncertain"
    assert converted.details["phase"] == "retry-start"
    assert converted.details["allocation_state"] == "unknown"
    assert converted.details["retry_safety"] == "same-attempt-only"
    assert converted.details["next_action"] == "attach-exact-child"
    assert converted.details["identities"]["attempt_id"] == "attempt-1"
    assert "scheduler acknowledgement" in str(converted)


def test_submitted_snapshot_projection_drops_unknown_and_sensitive_values() -> None:
    class _ObservationHandle(_FakeHandle):
        def snapshot(self) -> dict[str, Any]:
            return {
                "state": "running",
                "scheduler_job_id": "job-42",
                "unknown": "must-disappear",
                "secret_token": "sensitive-value",
            }

    projected = SubmittedRunAdapter(_ObservationHandle()).snapshot()

    assert projected == {"state": "running", "scheduler_job_id": "job-42"}
    assert "sensitive-value" not in json.dumps(projected)


@pytest.mark.anyio
async def test_cancel_normalizes_public_cluster_operation_error(tmp_path: Path) -> None:
    from bioimageflow.cluster import ClusterDiagnostic, ClusterOperationError

    class _CancelFailure(_FakeHandle):
        def cancel(self) -> None:
            raise ClusterOperationError(
                ClusterDiagnostic(
                    phase="run-cancel",
                    category="ssh-timeout",
                    message="The cluster could not be reached.",
                    allocation_state="orchestrator-submitted",
                    retry_safety="safe",
                    next_action="retry-cancel",
                    identities={"run_id": "run_" + "5" * 32},
                )
            )

    registry = ExecutionRegistry(tmp_path)
    saved = registry.save(_snapshot(state="running"))
    coordinator = ExecutionCoordinator(
        registry,
        reconnector=lambda _snapshot: SubmittedRunAdapter(_CancelFailure()),
    )

    with pytest.raises(ExecutionOperationError) as raised:
        await coordinator.cancel(saved.execution_id)
    await coordinator.close()

    assert raised.value.code == "ssh-timeout"
    assert raised.value.details["identities"]["run_id"] == "run_" + "5" * 32


def _public_reconnect_error(*, phase: str, category: str) -> Exception:
    from bioimageflow.cluster import ClusterDiagnostic, ClusterOperationError

    return ClusterOperationError(
        ClusterDiagnostic(
            phase=phase,
            category=category,
            message="The retained run could not be attached.",
            allocation_state="orchestrator-submitted",
            retry_safety="safe",
            next_action="retry-attachment",
            identities={"run_id": "run_" + "6" * 32},
        )
    )


@pytest.mark.anyio
async def test_retry_planning_normalizes_public_reconnect_diagnostic(tmp_path: Path) -> None:
    registry = ExecutionRegistry(tmp_path)
    saved = registry.save(_snapshot(state="failed"))
    capabilities = {
        "remote_cluster_bootstrap": {"supported": True, "reason": None},
        "submitted_run_retry": {"supported": True, "reason": None},
        "submitted_recompute": {"supported": True, "reason": None},
        "submitted_result_export": {"supported": True, "reason": None},
    }
    coordinator = ExecutionCoordinator(
        registry,
        reconnector=lambda _snapshot: (_ for _ in ()).throw(
            _public_reconnect_error(phase="run-attach", category="gateway-unavailable")
        ),
        capability_provider=lambda: capabilities,
    )

    with pytest.raises(ExecutionOperationError) as raised:
        await coordinator.plan_retry(saved.execution_id)
    await coordinator.close()

    assert raised.value.code == "gateway-unavailable"
    assert raised.value.details["diagnostic"]["next_action"] == "retry-attachment"
    assert raised.value.details["identities"]["run_id"] == "run_" + "6" * 32


@pytest.mark.anyio
async def test_result_download_normalizes_public_reconnect_diagnostic(tmp_path: Path) -> None:
    registry = ExecutionRegistry(tmp_path)
    saved = registry.save(_snapshot(state="succeeded"))
    capabilities = {
        "remote_cluster_bootstrap": {"supported": True, "reason": None},
        "submitted_run_retry": {"supported": True, "reason": None},
        "submitted_recompute": {"supported": True, "reason": None},
        "submitted_result_export": {"supported": True, "reason": None},
    }
    coordinator = ExecutionCoordinator(
        registry,
        reconnector=lambda _snapshot: (_ for _ in ()).throw(
            _public_reconnect_error(phase="run-attach", category="run-not-found")
        ),
        capability_provider=lambda: capabilities,
    )

    with pytest.raises(ExecutionOperationError) as raised:
        await coordinator.download_result(saved.execution_id, tmp_path / "export")
    await coordinator.close()

    assert raised.value.code == "run-not-found"
    assert raised.value.details["diagnostic"]["phase"] == "run-attach"
    assert raised.value.details["identities"]["run_id"] == "run_" + "6" * 32


@pytest.mark.anyio
async def test_retry_start_normalizes_parent_reconnect_diagnostic(tmp_path: Path) -> None:
    registry = ExecutionRegistry(tmp_path)
    parent = registry.save(_snapshot(execution_id=f"run_{uuid4().hex}", state="failed"))
    child_id = f"run_{uuid4().hex}"
    plan = _retry_plan(parent.execution_id, child_id, tmp_path)
    registry.save_retry_plan(plan.to_dict())
    capabilities = {
        "remote_cluster_bootstrap": {"supported": True, "reason": None},
        "submitted_run_retry": {"supported": True, "reason": None},
        "submitted_recompute": {"supported": True, "reason": None},
        "submitted_result_export": {"supported": True, "reason": None},
    }

    def reconnect(snapshot: ExecutionSnapshot) -> SubmittedRunAdapter:
        category = "run-not-found" if snapshot.execution_id == child_id else "gateway-unavailable"
        raise _public_reconnect_error(phase="run-attach", category=category)

    coordinator = ExecutionCoordinator(
        registry,
        reconnector=reconnect,
        capability_provider=lambda: capabilities,
    )

    with pytest.raises(ExecutionOperationError) as raised:
        await coordinator.confirm_retry(parent.execution_id, plan_digest=plan.digest)
    await coordinator.close()

    assert raised.value.code == "gateway-unavailable"
    assert raised.value.details["diagnostic"]["retry_safety"] == "safe"
    assert registry.retry_plan_state(parent.execution_id, plan.digest) == "confirmed"


@pytest.mark.anyio
async def test_cleanup_plan_is_bound_to_one_retained_managed_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bioimageflow.cluster import (
        ClusterCleanupCandidate,
        ClusterCleanupPlan,
        ClusterCleanupReport,
    )
    import bioimageflow.cluster as cluster_api

    execution_id = f"run_{uuid4().hex}"
    planned: list[dict[str, Any]] = []
    applied: list[ClusterCleanupPlan] = []

    class _Cluster:
        def __init__(self, *, host: str, root: str) -> None:
            assert (host, root) == ("cluster", "/shared")

        def plan_cleanup(self, **kwargs: Any) -> ClusterCleanupPlan:
            planned.append(kwargs)
            return ClusterCleanupPlan(
                plan_id="cleanup-1",
                root_revision=7,
                candidates=(
                    ClusterCleanupCandidate(
                        namespace="runs",
                        identity=execution_id,
                        path=f"runs/{execution_id}",
                        size=42,
                    ),
                ),
            )

        def apply_cleanup(self, plan: ClusterCleanupPlan) -> ClusterCleanupReport:
            applied.append(plan)
            return ClusterCleanupReport(plan_id=plan.plan_id, removed=(execution_id,))

    monkeypatch.setattr(cluster_api, "RemoteCluster", _Cluster)
    registry = ExecutionRegistry(tmp_path)
    registry.save(
        _snapshot(
            execution_id=execution_id,
            state="succeeded",
            reconnect={"host": "cluster", "root": "/shared", "run_id": execution_id},
        )
    )
    coordinator = ExecutionCoordinator(
        registry,
        reconnector=lambda _snapshot: SubmittedRunAdapter(_FakeHandle()),
    )

    digest, plan = await coordinator.plan_cleanup(execution_id, older_than_seconds=123)
    report = await coordinator.apply_cleanup(execution_id, plan_digest=digest)

    assert planned == [
        {"namespace": "runs", "run_ids": (execution_id,), "older_than_seconds": 123}
    ]
    assert plan["candidates"][0]["identity"] == execution_id
    assert applied[0].candidates[0].identity == execution_id
    assert report["removed"] == [execution_id]

    plan_path = registry._cleanup_plan_path(execution_id, digest)
    retained = json.loads(plan_path.read_text(encoding="utf-8"))
    retained["plan"]["root_revision"] = 8
    plan_path.write_text(json.dumps(retained), encoding="utf-8")

    with pytest.raises(ExecutionOperationError) as raised:
        await coordinator.apply_cleanup(execution_id, plan_digest=digest)

    assert raised.value.code == "cleanup-plan-integrity-error"
    assert len(applied) == 1


@pytest.mark.anyio
async def test_cleanup_plan_is_verified_before_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import bioimageflow.cluster as cluster_api

    execution_id = f"run_{uuid4().hex}"

    class _MalformedPlan:
        def to_dict(self) -> dict[str, Any]:
            return {
                "schema": "bioimageflow.cluster_cleanup_plan.v1",
                "plan_id": "cleanup-1",
                "root_revision": 1,
                "candidates": [],
                "credential": "must-not-persist",
            }

    class _Cluster:
        def __init__(self, *, host: str, root: str) -> None:
            del host, root

        def plan_cleanup(self, **kwargs: Any) -> _MalformedPlan:
            del kwargs
            return _MalformedPlan()

    monkeypatch.setattr(cluster_api, "RemoteCluster", _Cluster)
    registry = ExecutionRegistry(tmp_path)
    registry.save(
        _snapshot(
            execution_id=execution_id,
            state="succeeded",
            reconnect={"host": "cluster", "root": "/shared", "run_id": execution_id},
        )
    )
    coordinator = ExecutionCoordinator(
        registry,
        reconnector=lambda _snapshot: SubmittedRunAdapter(_FakeHandle()),
    )

    with pytest.raises(ExecutionOperationError) as raised:
        await coordinator.plan_cleanup(execution_id)

    assert raised.value.code == "cleanup-plan-integrity-error"
    assert not (registry.root / "cleanup_plans").exists()


@pytest.mark.anyio
async def test_execution_actions_use_each_exact_capability(tmp_path: Path) -> None:
    capabilities = {
        "remote_cluster_bootstrap": {"supported": True, "reason": None},
        "submitted_run_retry": {"supported": False, "reason": "retry disabled"},
        "submitted_recompute": {"supported": True, "reason": None},
        "submitted_result_export": {"supported": True, "reason": None},
    }
    registry = ExecutionRegistry(tmp_path)
    saved = registry.save(
        _snapshot(
            backend="managed_remote",
            state="succeeded",
        )
    )
    coordinator = ExecutionCoordinator(
        registry,
        reconnector=lambda _snapshot: SubmittedRunAdapter(_FakeHandle()),
        capability_provider=lambda: capabilities,
    )

    snapshot = await coordinator.get(saved.execution_id)

    assert not snapshot.actions.cancel.available
    assert not snapshot.actions.retry.available
    assert snapshot.actions.retry.reason == "retry disabled"
    assert snapshot.actions.recompute.available
    assert snapshot.actions.download_results.available


def test_submitted_adapter_uses_export_result_and_returns_zip(tmp_path: Path) -> None:
    handle = _FakeHandle()
    adapter = SubmittedRunAdapter(handle)

    archive = adapter.export_result(tmp_path / "bundle")

    assert archive.is_file()
    assert adapter.result_export.state == "available"


def test_direct_and_wetlands_managed_export_is_released_and_downloadable(
    tmp_path: Path,
) -> None:
    manager = ExecutionManager(
        event_bus=NullEventBus(),
        tool_registry=ToolRegistryService(),
        settings=Settings(deployment_mode="desktop"),
        managed_result_root=tmp_path,
    )
    context = ExecutionContext(
        execution_id=f"run_{uuid4().hex}",
        workflow_id="demo",
    )

    class _Context:
        def export_result(self, value: Any, *, destination: Path) -> None:
            assert value == {"answer": 42}
            destination.mkdir(parents=True)
            (destination / "result.json").write_text("{}")

    manager._workflow_run_contexts[context.execution_id] = _Context()

    manager._export_managed_result(context, {"answer": 42})
    archive = manager.export_retained_result(context, tmp_path / context.execution_id)
    result_export = manager.retained_result_export(context)

    assert result_export.state == "available"
    assert context.execution_id not in manager._workflow_run_contexts
    assert archive.is_file()
    assert (tmp_path / context.execution_id).with_suffix(".completion.json").is_file()

    archive.write_bytes(b"tampered")
    with pytest.raises(ExecutionOperationError) as manager_error:
        manager.export_retained_result(context, tmp_path / context.execution_id)
    with pytest.raises(ExecutionOperationError) as adapter_error:
        ManagedResultAdapter(
            tmp_path / context.execution_id,
            result_export,
        ).export_result(tmp_path / context.execution_id)

    assert manager_error.value.code == "workflow-result-integrity-error"
    assert adapter_error.value.code == "workflow-result-integrity-error"


@pytest.mark.anyio
async def test_managed_download_reuses_verified_local_bundle_after_remote_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution_id = f"run_{uuid4().hex}"
    bundle = tmp_path / "exports" / execution_id
    bundle.mkdir(parents=True)
    (bundle / "result.txt").write_text("retained")
    archive = _archive_bundle(bundle)
    result_export = {
        "state": "available",
        "archive_digest": _archive_digest(archive),
    }
    registry = ExecutionRegistry(tmp_path / "registry")
    saved = registry.save(
        _snapshot(
            execution_id=execution_id,
            state="succeeded",
            reconnect={
                "host": "cluster",
                "root": "/shared",
                "run_id": execution_id,
                "result_bundle": str(bundle),
            },
            result_export=result_export,
        )
    )

    class _RemovedCluster:
        def __init__(self, *, host: str, root: str) -> None:
            assert (host, root) == ("cluster", "/shared")

        def attach(self, run_id: str) -> object:
            raise AssertionError(f"remote run {run_id} was already cleaned up")

    import bioimageflow.cluster as cluster_api

    monkeypatch.setattr(cluster_api, "RemoteCluster", _RemovedCluster)
    coordinator = ExecutionCoordinator(registry, reconnector=open_public_submitted_run)
    destination = tmp_path / "exports" / execution_id

    downloaded = await coordinator.download_result(execution_id, destination)
    reopened = open_public_submitted_run(saved)
    await coordinator.close()

    assert downloaded == archive
    assert isinstance(reopened, ManagedResultAdapter)
    assert registry.get(execution_id).reconnect["result_bundle"] == str(bundle)
