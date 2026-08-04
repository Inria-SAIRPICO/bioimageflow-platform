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
from bioimageflow_server.models.execution_profiles import DistributedExecutionProfile
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
    SubmittedRunAdapter,
    open_public_submitted_run,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
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

    def export_result(self, destination: Path) -> None:
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
    assert observed.observation.error == "offline"


def _retry_plan(parent_id: str, child_id: str, storage: Path) -> Any:
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
        recompute=None,
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
            backend="submitted_local",
            state="failed",
            reconnect={"storage_path": str(tmp_path), "run_id": parent_id},
        )
    )
    plan = _retry_plan(parent_id, child_id, tmp_path)
    handle = _RetryHandle(plan)
    coordinator = ExecutionCoordinator(
        registry,
        reconnector=lambda _snapshot: SubmittedRunAdapter(handle),
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
async def test_startup_resumes_confirmed_plan_before_reconnect(tmp_path: Path) -> None:
    parent_id = f"run_{uuid4().hex}"
    child_id = f"run_{uuid4().hex}"
    registry = ExecutionRegistry(tmp_path)
    registry.save(
        _snapshot(
            execution_id=parent_id,
            backend="submitted_local",
            state="failed",
            reconnect={"storage_path": str(tmp_path), "run_id": parent_id},
        )
    )
    plan = _retry_plan(parent_id, child_id, tmp_path)
    registry.save_retry_plan(plan.to_dict())
    registry.confirm_retry_plan(parent_id, plan.digest)
    handle = _RetryHandle(plan)
    coordinator = ExecutionCoordinator(
        registry,
        reconnector=lambda _snapshot: SubmittedRunAdapter(handle),
        poll_interval=60,
    )

    await coordinator.start()
    await coordinator.close()

    assert len(handle.started) == 1
    assert registry.get(child_id).retry_of_execution_id == parent_id


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
            backend="attached_parsl",
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
async def test_execution_actions_use_each_exact_capability(tmp_path: Path) -> None:
    capabilities = {
        "submitted_local_parsl": {"supported": True, "reason": None},
        "submitted_run_retry": {"supported": False, "reason": "retry disabled"},
        "submitted_recompute": {"supported": True, "reason": None},
        "submitted_result_export": {"supported": True, "reason": None},
    }
    registry = ExecutionRegistry(tmp_path)
    saved = registry.save(
        _snapshot(
            backend="submitted_local",
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

    assert manager.retained_result_export(context).state == "available"
    assert context.execution_id not in manager._workflow_run_contexts
    assert archive.is_file()
