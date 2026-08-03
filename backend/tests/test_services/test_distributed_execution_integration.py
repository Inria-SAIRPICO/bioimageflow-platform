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
)
from bioimageflow_server.services.execution_preflight import PreparedRunAcceptance


class _Coordinator:
    def __init__(self) -> None:
        self.registered: list[tuple[Any, Any]] = []

    async def register(self, snapshot: Any, adapter: Any) -> Any:
        self.registered.append((snapshot, adapter))
        return snapshot


@pytest.mark.anyio
async def test_regular_execution_is_registered_for_the_shared_panel() -> None:
    coordinator = _Coordinator()
    registrar = PlatformPreparedRunRegistrar(coordinator, profiles=SimpleNamespace())  # type: ignore[arg-type]
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
async def test_submission_registration_uses_preflight_bound_profile_revision() -> None:
    coordinator = _Coordinator()
    registrar = PlatformPreparedRunRegistrar(
        coordinator,
        profiles=SimpleNamespace(
            resolve_target=lambda *_args: (_ for _ in ()).throw(
                AssertionError("apply must not re-resolve a mutable profile")
            )
        ),  # type: ignore[arg-type]
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
        distributed_plan={"nodes": []},
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


def test_legacy_adapter_maps_cancelled_terminal_result() -> None:
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
        stop=lambda: asyncio.sleep(0),
    )
    loop = asyncio.new_event_loop()
    try:
        from bioimageflow_server.services.distributed_execution_integration import (
            LegacyExecutionManagerAdapter,
        )

        adapter = LegacyExecutionManagerAdapter(manager, context, loop)  # type: ignore[arg-type]
        assert adapter.status == "cancelled"
    finally:
        loop.close()


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
