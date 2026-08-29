from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from bioimageflow.cluster import ClusterDiagnostic
from bioimageflow_server.models.execution_preflight import ApplyPreparedExecutionRequest
from bioimageflow_server.models.execution_profiles import ExecutionProfileCreate
from bioimageflow_server.services.distributed_execution_integration import (
    PlatformExecutionProfileResolver,
    PlatformPreparedRunRegistrar,
)
from bioimageflow_server.services.execution_preflight import PreparedRunAcceptance
from bioimageflow_server.services.execution_profiles import ExecutionProfileStore
from bioimageflow_server.services.execution_runtime import SubmittedRunAdapter


pytestmark = pytest.mark.anyio


def write_config(path: Path, host: str = "cluster") -> Path:
    path.write_text(
        "from bioimageflow.cluster import RemoteCluster\n"
        f"cluster = RemoteCluster(host={host!r}, root='/shared/bioimageflow')\n",
        encoding="utf-8",
    )
    return path


async def resolved_profile(tmp_path: Path):
    config = write_config(tmp_path / "cluster.py")
    store = ExecutionProfileStore(tmp_path / "profiles.json")
    await store.load()
    record = await store.create(
        ExecutionProfileCreate(name="Cluster", config_path=str(config))
    )
    resolver = PlatformExecutionProfileResolver(
        store,
        local_storage_path=lambda workflow_id: tmp_path / workflow_id / "results",
    )
    return resolver.resolve_target(record.id, "demo", record.revision), resolver


async def test_profile_resolver_loads_exact_digest_and_cluster_identity(tmp_path: Path) -> None:
    profile, _ = await resolved_profile(tmp_path)
    assert profile.cluster.host == "cluster"
    assert str(profile.cluster.root) == "/shared/bioimageflow"
    Path(profile.record.config_path).write_text("cluster = object()\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        PlatformExecutionProfileResolver(
            ExecutionProfileStore(tmp_path / "unused.json"),
            local_storage_path=lambda _workflow_id: tmp_path,
        )._resolve(profile.record, "demo")


class _Coordinator:
    def __init__(self) -> None:
        self.snapshot = None
        self.adapter = None

    async def register(self, snapshot, adapter):
        self.snapshot = snapshot
        self.adapter = adapter
        return snapshot


async def test_registrar_persists_durable_managed_identity(tmp_path: Path) -> None:
    profile, resolver = await resolved_profile(tmp_path)
    handle = SimpleNamespace(
        id="run_" + "1" * 32,
        status="prepared",
        snapshot=lambda: {"state": "prepared"},
    )
    coordinator = _Coordinator()
    registrar = PlatformPreparedRunRegistrar(coordinator, resolver, tmp_path / "exports")
    request = ApplyPreparedExecutionRequest(
        token="token",
        workflow_id="demo",
        draft_revision=2,
        target_id=profile.id,
    )
    snapshot = await registrar.register_prepared_run(
        request,
        PreparedRunAcceptance(handle, profile, SimpleNamespace()),
    )
    assert snapshot.execution_id == handle.id
    assert snapshot.backend == "managed_remote"
    assert snapshot.reconnect == {
        "host": "cluster",
        "root": "/shared/bioimageflow",
        "run_id": handle.id,
    }
    assert isinstance(coordinator.adapter, SubmittedRunAdapter)


async def test_uncertain_submit_retains_exact_run_and_structured_diagnostic(tmp_path: Path) -> None:
    profile, resolver = await resolved_profile(tmp_path)
    diagnostic = ClusterDiagnostic(
        phase="submission",
        category="submission-uncertain",
        message="acknowledgement lost",
        allocation_state="unknown",
        retry_safety="same-attempt-only",
        next_action="attach-preallocated-run",
        identities={"run_id": "run_" + "2" * 32},
    )
    uncertainty = SimpleNamespace(
        run_id="run_" + "2" * 32,
        diagnostic=diagnostic,
        __str__=lambda: "uncertain",
    )
    coordinator = _Coordinator()
    registrar = PlatformPreparedRunRegistrar(coordinator, resolver, tmp_path / "exports")
    request = ApplyPreparedExecutionRequest(
        token="token",
        workflow_id="demo",
        draft_revision=2,
        target_id=profile.id,
    )
    snapshot = await registrar.register_prepared_run(
        request,
        PreparedRunAcceptance(None, profile, SimpleNamespace(), uncertainty),
    )
    assert snapshot.execution_id == uncertainty.run_id
    assert snapshot.state == "prepared"
    assert snapshot.diagnostics[0].category == "submission-uncertain"
    assert snapshot.observation.reachable is False
