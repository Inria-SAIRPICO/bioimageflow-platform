"""Platform adapters for BioImageFlow's public managed-cluster API."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, cast

from bioimageflow_server.models.execution import ExecutionContext
from bioimageflow_server.models.execution_preflight import ApplyPreparedExecutionRequest
from bioimageflow_server.models.execution_profiles import DistributedExecutionProfile
from bioimageflow_server.models.execution_runtime import (
    ClusterDiagnosticValue,
    ExecutionBackend,
    ExecutionSnapshot,
    ObservationSnapshot,
    RunState,
)
from bioimageflow_server.services.execution import ExecutionManager
from bioimageflow_server.services.execution_preflight import (
    DistributedPreflightService,
    PreparedRunAcceptance,
)
from bioimageflow_server.services.execution_profiles import (
    ExecutionProfileNotFoundError,
    ExecutionProfileStore,
    load_cluster_config,
)
from bioimageflow_server.services.execution_runtime import (
    ExecutionCoordinator,
    ResultExportSnapshot,
    SubmittedRunAdapter,
)
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_draft import WorkflowDraftService


@dataclass(frozen=True)
class ResolvedExecutionProfile:
    record: DistributedExecutionProfile
    workflow_id: str
    workflow_storage_path: Path
    cluster: Any

    @property
    def id(self) -> str:
        return self.record.id

    @property
    def revision(self) -> int:
        return self.record.revision


class PlatformExecutionProfileResolver:
    def __init__(
        self,
        store: ExecutionProfileStore,
        *,
        trusted_factories: Callable[[], list[str]] | None = None,
        local_storage_path: Callable[[str], Path],
    ) -> None:
        del trusted_factories
        self._store = store
        self._local_storage_path = local_storage_path

    def resolve_target(
        self,
        target_id: str,
        workflow_id: str,
        profile_revision: int,
    ) -> ResolvedExecutionProfile:
        if target_id == "local":
            raise ValueError("Local execution does not use managed-cluster preflight")
        try:
            profile = self._store.get(target_id)
        except ExecutionProfileNotFoundError as exc:
            raise ValueError("Execution target does not exist") from exc
        if profile.revision != profile_revision:
            raise ValueError(
                "The visible execution profile revision changed; refresh targets and try again"
            )
        return self._resolve(profile, workflow_id)

    def resolve_revision(
        self,
        profile_id: str | None,
        profile_revision: int | None,
        workflow_id: str,
    ) -> ResolvedExecutionProfile:
        if profile_id is None or profile_revision is None:
            raise ValueError("Execution profile revision is missing")
        profile = self._store.get(profile_id)
        if profile.revision != profile_revision:
            raise ValueError("The retained execution profile revision is unavailable")
        return self._resolve(profile, workflow_id)

    def _resolve(
        self,
        profile: DistributedExecutionProfile,
        workflow_id: str,
    ) -> ResolvedExecutionProfile:
        if not profile.enabled:
            raise ValueError("Execution profile is disabled")
        loaded = load_cluster_config(profile.config_path, expected_digest=profile.config_digest)
        if loaded.cluster.host != profile.cluster_host or str(loaded.cluster.root) != profile.cluster_root:
            raise ValueError("Cluster identity changed; save the profile again before use")
        return ResolvedExecutionProfile(
            profile,
            workflow_id,
            self._local_storage_path(workflow_id),
            loaded.cluster,
        )


class DraftWorkflowResolver:
    def __init__(
        self,
        drafts: WorkflowDraftService,
        registry: ToolRegistryService,
    ) -> None:
        self._drafts = drafts
        self._registry = registry

    def resolve_workflow(
        self,
        workflow_id: str,
        draft_revision: int,
        storage_path: str | Path | None = None,
    ) -> Any:
        authority = self._drafts.get_draft_authority(workflow_id)
        if authority.draft.draft_revision != draft_revision:
            raise ValueError("The accepted workflow draft revision changed")
        target_storage = Path(storage_path) if storage_path is not None else authority.storage_path
        output = build_workflow(
            authority.draft.graph.model_copy(deep=True),
            self._registry,
            storage_path=target_storage,
        )
        if output.errors:
            details = "; ".join(error.detail for error in output.errors[:5])
            raise ValueError(f"Workflow compilation failed: {details}")
        return output.workflow


class AuthorizedUploadResolver:
    def __init__(self, *, deployment_mode: str, datasets_root: Path) -> None:
        self._deployment_mode = deployment_mode
        self._datasets_root = datasets_root

    def resolve_upload(self, value: str) -> Path:
        candidate = Path(value).expanduser().resolve(strict=True)
        if self._deployment_mode == "desktop":
            return candidate
        root = self._datasets_root.resolve(strict=True)
        if not candidate.is_relative_to(root):
            raise ValueError("Web uploads must come from the managed dataset catalog")
        return candidate


def _target_snapshot(profile: ResolvedExecutionProfile) -> dict[str, Any]:
    return {
        "name": profile.record.name,
        "mode": "managed_remote",
        "host": profile.record.cluster_host,
        "root": profile.record.cluster_root,
        "config_digest": profile.record.config_digest,
    }


class DeferredManagedRunAdapter(SubmittedRunAdapter):
    """Attach the exact uncertain run identity lazily; never resubmit."""

    def __init__(self, cluster: Any, run_id: str) -> None:
        self._cluster = cluster
        self._run_id = run_id
        self._delegate: SubmittedRunAdapter | None = None
        super().__init__(None)

    def _attached(self) -> SubmittedRunAdapter:
        if self._delegate is None:
            self._delegate = SubmittedRunAdapter(self._cluster.attach(self._run_id))
        return self._delegate

    @property
    def status(self) -> str:
        return "prepared" if self._delegate is None else self._delegate.status

    def refresh(self) -> None:
        self._attached().refresh()

    def progress(self, *, after_sequence: int = 0) -> list[dict[str, Any]]:
        return self._attached().progress(after_sequence=after_sequence)

    def snapshot(self) -> dict[str, Any]:
        return self._attached().snapshot()

    def diagnostics(self) -> tuple[Any, ...]:
        return self._attached().diagnostics()

    def cancel(self) -> None:
        self._attached().cancel()

    def export_result(self, destination: Path) -> Path:
        return self._attached().export_result(destination)

    @property
    def result_export(self) -> ResultExportSnapshot:
        return ResultExportSnapshot() if self._delegate is None else self._delegate.result_export

    def plan_retry(self, recompute: Any | None = None) -> Any:
        return self._attached().plan_retry(recompute)

    def start_retry(self, plan: Any) -> SubmittedRunAdapter:
        return self._attached().start_retry(plan)


class PlatformPreparedRunRegistrar:
    def __init__(
        self,
        coordinator: ExecutionCoordinator,
        profiles: PlatformExecutionProfileResolver,
        destinations: "ExecutionDownloadDestinationResolver",
    ) -> None:
        self._coordinator = coordinator
        self._profiles = profiles
        self._destinations = destinations

    async def register_local(
        self,
        context: ExecutionContext,
        manager: ExecutionManager,
    ) -> ExecutionSnapshot:
        loop = asyncio.get_running_loop()
        workflow = getattr(manager, "_workflow", None)
        engine_type = getattr(workflow, "engine_type", "direct")
        backend = "wetlands" if engine_type == "wetlands" else "direct"
        command = cast(
            Literal["run", "run_selected", "retry", "invalidate_retry", "recompute"],
            {
                "normal": "run_selected" if context.requested_nodes else "run",
                "retry": "retry",
                "invalidate_failed": "invalidate_retry",
                "recompute": "recompute",
            }[context.mode],
        )
        snapshot = ExecutionSnapshot(
            execution_id=context.execution_id,
            workflow_id=context.workflow_id,
            draft_revision=context.draft_revision,
            command=command,
            requested_nodes=context.requested_nodes,
            retry_of_execution_id=context.retry_of_execution_id,
            backend=cast(ExecutionBackend, backend),
            target_id="local",
            target_snapshot={"name": "Local", "mode": "local"},
            state="running",
            reconnect={"result_bundle": str(self._destinations.resolve(context.execution_id))},
        )
        return await self._coordinator.register(
            snapshot,
            LocalExecutionManagerAdapter(
                manager,
                context,
                loop,
                self._destinations.resolve(context.execution_id),
            ),
        )

    async def register_prepared_run(
        self,
        request: ApplyPreparedExecutionRequest,
        run_handle: object,
    ) -> ExecutionSnapshot:
        if not isinstance(run_handle, PreparedRunAcceptance):
            raise TypeError("Managed run is missing its accepted profile binding")
        profile = run_handle.profile
        if not isinstance(profile, ResolvedExecutionProfile):
            raise TypeError("Managed run has an invalid profile binding")
        uncertainty = run_handle.uncertainty
        handle = run_handle.handle
        if uncertainty is None and handle is None:
            raise TypeError("Managed submission returned neither a handle nor uncertainty")
        run_id = str(uncertainty.run_id if uncertainty is not None else handle.id)
        diagnostics: list[ClusterDiagnosticValue]
        if uncertainty is not None:
            diagnostics = [
                ClusterDiagnosticValue.model_validate(uncertainty.diagnostic.to_dict())
            ]
            state = cast(RunState, "prepared")
            backend_metadata: dict[str, Any] = {}
            observation = ObservationSnapshot(
                reachable=False,
                error=diagnostics[0].message,
            )
            adapter: SubmittedRunAdapter = DeferredManagedRunAdapter(
                profile.cluster,
                run_id,
            )
        else:
            adapter = SubmittedRunAdapter(handle)
            # Persist the returned durable identity before making any observation
            # call that can fail independently of the accepted submission.
            state = cast(RunState, "prepared")
            backend_metadata = {}
            diagnostics = []
            observation = ObservationSnapshot()
        snapshot = ExecutionSnapshot(
            execution_id=run_id,
            workflow_id=request.workflow_id,
            draft_revision=request.draft_revision,
            command="run_selected" if request.requested_nodes else "run",
            requested_nodes=request.requested_nodes,
            backend="managed_remote",
            target_id=profile.id,
            profile_id=profile.id,
            profile_revision=profile.revision,
            target_snapshot=_target_snapshot(profile),
            state=state,
            reconnect={
                "host": profile.record.cluster_host,
                "root": profile.record.cluster_root,
                "run_id": run_id,
                "result_bundle": str(self._destinations.resolve(run_id)),
            },
            backend_metadata=backend_metadata,
            diagnostics=diagnostics,
            observation=observation,
        )
        return await self._coordinator.register(snapshot, adapter)


class ExecutionDownloadDestinationResolver:
    def __init__(self, root: Path | Callable[[], Path]) -> None:
        self._root_provider = root if callable(root) else lambda: root
        self._bindings: dict[str, Path] = {}

    def resolve(self, execution_id: str) -> Path:
        root = self._bindings.setdefault(execution_id, self._root_provider())
        root.mkdir(parents=True, exist_ok=True)
        return root / execution_id


class LocalExecutionManagerAdapter:
    def __init__(
        self,
        manager: ExecutionManager,
        context: ExecutionContext,
        loop: asyncio.AbstractEventLoop,
        managed_destination: Path,
    ) -> None:
        self._manager = manager
        self._context = context
        self._loop = loop
        self._managed_destination = managed_destination

    @property
    def status(self) -> str:
        return self._manager.retained_status(self._context)

    def refresh(self) -> None:
        return None

    def progress(self, *, after_sequence: int = 0) -> list[dict[str, Any]]:
        return self._manager.retained_progress_for(
            self._context,
            after_sequence=after_sequence,
        )

    def cancel(self) -> None:
        future = asyncio.run_coroutine_threadsafe(
            self._manager.stop_retained(self._context),
            self._loop,
        )
        future.result()

    def export_result(self, destination: Path) -> Path:
        if destination != self._managed_destination:
            raise RuntimeError("Managed result destination does not match this execution")
        return self._manager.export_retained_result(self._context, destination)

    @property
    def result_export(self) -> ResultExportSnapshot:
        return self._manager.retained_result_export(self._context)


def create_preflight_service(
    *,
    workflows: DraftWorkflowResolver,
    profiles: PlatformExecutionProfileResolver,
    uploads: AuthorizedUploadResolver,
    tokens: Any,
) -> DistributedPreflightService:
    return DistributedPreflightService(
        workflows=workflows,
        profiles=profiles,
        uploads=uploads,
        tokens=tokens,
    )
