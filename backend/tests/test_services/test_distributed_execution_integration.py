from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bioimageflow_server.models.execution import ExecutionContext, ExecutionResult
from bioimageflow_server.models.execution_preflight import ExecutionPreflightRequest
from bioimageflow_server.services.distributed_execution_integration import (
    AuthorizedUploadResolver,
    PlatformExecutionProfileResolver,
    PlatformPreparedRunRegistrar,
    ResolvedExecutionProfile,
    _plan_jobs,
)
from bioimageflow_server.services.execution_preflight import PreparedRunAcceptance


class _Coordinator:
    def __init__(self) -> None:
        self.registered: list[tuple[Any, Any]] = []

    async def register(self, snapshot: Any, adapter: Any) -> Any:
        self.registered.append((snapshot, adapter))
        return snapshot


def _distributed_plan(*statuses: str) -> dict[str, Any]:
    return {
        "schema": "bioimageflow.distributed_execution_plan.v1",
        "allocates_resources": False,
        "task_policy": {
            "schema": "bioimageflow.parsl.task_policy.v1",
            "row_chunk_size": 1,
            "max_in_flight": 32,
        },
        "nodes": [
            {
                "scoped_node_path": f"node-{index}",
                "execution_status": status,
                "will_dispatch": status not in {"cached", "skipped"},
                "resources": {
                    "cpu": index + 1,
                    "gpu": index % 2,
                    "memory_bytes": 1024 * (index + 1),
                    "gpu_memory_bytes": None,
                    "max_concurrent": 0,
                },
                "compatible_executors": ["workers"],
                "selected_executor": None if status in {"cached", "skipped"} else "workers",
                "route_reason": None,
                "tool_origin": "installed_module",
                "environment_name": "default",
                "environment_identity": "env_" + "1" * 64,
                "storage_mode": "shared_fs",
                "incompatibilities": {"workers": []},
                "diagnostics": [],
            }
            for index, status in enumerate(statuses)
        ],
    }


@pytest.mark.anyio
async def test_regular_execution_is_registered_for_the_shared_panel(tmp_path: Path) -> None:
    coordinator = _Coordinator()
    registrar = PlatformPreparedRunRegistrar(
        coordinator,
        profiles=SimpleNamespace(),  # type: ignore[arg-type]
        managed_result_root=tmp_path,
    )
    context = ExecutionContext(
        execution_id="local-run",
        workflow_id="demo",
        draft_revision=4,
    )
    manager = SimpleNamespace(
        context=context,
        state="running",
        last_result=None,
        _workflow=SimpleNamespace(engine_type="wetlands"),
        retained_progress=lambda **kwargs: [],
        stop=lambda: asyncio.sleep(0),
    )

    snapshot = await registrar.register_local(context, manager)  # type: ignore[arg-type]

    assert snapshot.execution_id == "local-run"
    assert snapshot.backend == "wetlands"
    assert snapshot.target_id == "local"
    assert coordinator.registered[0][0] is snapshot


@pytest.mark.anyio
async def test_submission_registration_uses_preflight_bound_profile_revision(
    tmp_path: Path,
) -> None:
    coordinator = _Coordinator()
    registrar = PlatformPreparedRunRegistrar(
        coordinator,
        profiles=SimpleNamespace(
            resolve_target=lambda *_args: (_ for _ in ()).throw(
                AssertionError("apply must not re-resolve a mutable profile")
            )
        ),  # type: ignore[arg-type]
        managed_result_root=tmp_path,
    )
    record = SimpleNamespace(
        id="profile_" + "1" * 32,
        revision=4,
        name="Confirmed cluster",
        mode="submitted_remote",
    )
    record.model_copy = lambda **_kwargs: SimpleNamespace(
        model_dump=lambda **_options: {
            "id": record.id,
            "revision": record.revision,
        }
    )
    profile = ResolvedExecutionProfile(
        record=record,  # type: ignore[arg-type]
        workflow_id="demo",
        trusted_factories=("site.parsl:config",),
        workflow_storage_path="/cluster/workflows/demo/results",
    )
    preflight_request = ExecutionPreflightRequest(
        workflow_id="demo",
        draft_revision=7,
        target_id=record.id,
        profile_revision=4,
    )
    handle = SimpleNamespace(
        id="run_" + "2" * 32,
        status="queued",
        refresh=lambda: None,
        progress=lambda **_kwargs: [],
        cancel=lambda: None,
        logs=lambda: "",
    )
    accepted = PreparedRunAcceptance(
        handle=handle,
        profile=profile,
        request=preflight_request,
        distributed_plan=_distributed_plan("cached", "unexecuted"),
    )

    snapshot = await registrar.register_prepared_run(
        SimpleNamespace(
            workflow_id="demo",
            draft_revision=7,
            target_id=record.id,
            requested_nodes=None,
        ),  # type: ignore[arg-type]
        accepted,
    )

    assert snapshot.profile_revision == 4
    assert snapshot.target_snapshot["name"] == "Confirmed cluster"
    assert snapshot.target_snapshot["mode"] == "submitted_remote"
    assert snapshot.reconnect == {
        "storage_path": "/cluster/workflows/demo/results",
        "run_id": handle.id,
    }
    assert snapshot.jobs["node-0"].state == "cached"
    assert snapshot.jobs["node-1"].state == "waiting"
    assert snapshot.jobs["node-1"].effective_resources == {
        "cpu": 2,
        "gpu": 1,
        "memory_bytes": 2048,
        "gpu_memory_bytes": None,
        "max_concurrent": 0,
    }


def test_legacy_adapter_maps_cancelled_terminal_result(tmp_path: Path) -> None:
    context = ExecutionContext(execution_id="local-run", workflow_id="demo")
    manager = SimpleNamespace(
        context=context,
        state="idle",
        last_result=ExecutionResult(
            success=False,
            errors=[{"type": "cancelled", "detail": "cancelled"}],
        ),
        _workflow=SimpleNamespace(engine_type="direct"),
        retained_progress=lambda **kwargs: [],
        retained_progress_for=lambda _context, **kwargs: [],
        retained_status=lambda _context: "cancelled",
        stop=lambda: asyncio.sleep(0),
    )
    loop = asyncio.new_event_loop()
    try:
        from bioimageflow_server.services.distributed_execution_integration import (
            LegacyExecutionManagerAdapter,
        )

        adapter = LegacyExecutionManagerAdapter(  # type: ignore[arg-type]
            manager,
            context,
            loop,
            tmp_path / "bundle",
        )
        assert adapter.status == "cancelled"
    finally:
        loop.close()


def test_legacy_adapter_reads_status_and_progress_for_its_exact_run(tmp_path: Path) -> None:
    first = ExecutionContext(execution_id="first-run", workflow_id="demo")
    second = ExecutionContext(execution_id="second-run", workflow_id="demo")
    progress_by_run = {
        first.execution_id: [{"sequence": 1, "kind": "public", "payload": {}}],
        second.execution_id: [{"sequence": 2, "kind": "public", "payload": {}}],
    }
    statuses = {first.execution_id: "succeeded", second.execution_id: "running"}
    manager = SimpleNamespace(
        context=second,
        state="running",
        last_result=None,
        retained_status=lambda context: statuses[context.execution_id],
        retained_progress_for=lambda context, after_sequence=0: [
            event
            for event in progress_by_run[context.execution_id]
            if event["sequence"] > after_sequence
        ],
        stop=lambda: asyncio.sleep(0),
    )
    loop = asyncio.new_event_loop()
    try:
        from bioimageflow_server.services.distributed_execution_integration import (
            LegacyExecutionManagerAdapter,
        )

        adapter = LegacyExecutionManagerAdapter(  # type: ignore[arg-type]
            manager,
            first,
            loop,
            tmp_path / "first-run",
        )

        assert adapter.status == "succeeded"
        assert adapter.progress(after_sequence=0) == progress_by_run[first.execution_id]
        assert adapter.progress(after_sequence=1) == []
    finally:
        loop.close()


def test_distributed_plan_jobs_decode_every_execution_status_strictly() -> None:
    jobs = _plan_jobs(
        _distributed_plan(
            "cached",
            "skipped",
            "prior_selection_miss",
            "unexecuted",
            "pending_upstream",
        )
    )

    assert [jobs[f"node-{index}"].state for index in range(5)] == [
        "cached",
        "skipped",
        "waiting",
        "waiting",
        "waiting",
    ]
    malformed = _distributed_plan("cached")
    malformed["nodes"][0]["status"] = malformed["nodes"][0].pop("execution_status")
    with pytest.raises(ValueError, match="Invalid DistributedNodePlan payload"):
        _plan_jobs(malformed)


def test_web_uploads_are_confined_to_managed_datasets(tmp_path: Path) -> None:
    root = tmp_path / "datasets"
    root.mkdir()
    dataset = root / "image.tif"
    dataset.write_bytes(b"image")
    outside = tmp_path / "outside.tif"
    outside.write_bytes(b"outside")
    resolver = AuthorizedUploadResolver(deployment_mode="webapp", datasets_root=root)

    assert resolver.resolve_upload(str(dataset)) == dataset
    with pytest.raises(ValueError, match="managed dataset catalog"):
        resolver.resolve_upload(str(outside))


def test_remote_profile_derives_workflow_scoped_cluster_storage() -> None:
    profile = SimpleNamespace(
        id="profile_" + "1" * 32,
        revision=2,
        enabled=True,
        mode="submitted_remote",
        remote_workflow_root="/cluster/workflows",
        parsl_config=SimpleNamespace(factory="site.parsl:config"),
    )
    resolver = PlatformExecutionProfileResolver(
        SimpleNamespace(get=lambda profile_id: profile),  # type: ignore[arg-type]
        trusted_factories=lambda: ["site.parsl:config"],
        local_storage_path=lambda workflow_id: Path("/local") / workflow_id,
    )

    resolved = resolver.resolve_target(profile.id, "project/demo", 2)

    assert resolved.workflow_storage_path == "/cluster/workflows/project/demo/results"

    with pytest.raises(ValueError, match="visible execution profile revision changed"):
        resolver.resolve_target(profile.id, "project/demo", 1)
