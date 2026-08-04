"""Application adapters for the public BioImageFlow 0.4 execution contracts."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Literal, Mapping, cast
from uuid import uuid4

from bioimageflow_server.models.execution_preflight import (
    ApplyPreparedExecutionRequest,
    ExecutionPreflightRequest,
)
from bioimageflow_server.models.execution import ExecutionContext
from bioimageflow_server.models.execution_profiles import DistributedExecutionProfile
from bioimageflow_server.models.execution_runtime import (
    ExecutionBackend,
    ExecutionSnapshot,
    JobSnapshot,
    JobState,
    RunState,
)
from bioimageflow_server.services.execution_preflight import DistributedPreflightService
from bioimageflow_server.services.execution_preflight import PreparedRunAcceptance
from bioimageflow_server.services.execution import ExecutionManager
from bioimageflow_server.services.execution_profiles import (
    ExecutionProfileNotFoundError,
    ExecutionProfileStore,
)
from bioimageflow_server.services.execution_runtime import (
    AttachedRunAdapter,
    ExecutionCoordinator,
    SubmittedRunAdapter,
    _archive_bundle,
)
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_draft import WorkflowDraftService


def _remote_storage_path(root: str, workflow_id: str) -> str:
    parts = workflow_id.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise ValueError("Workflow ID cannot be mapped to cluster storage")
    return str(PurePosixPath(root).joinpath(*parts, "results"))


class _EmptyManifest:
    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "bioimageflow.prepared_submission_manifest.v2",
            "bundle_digest": "sha256:" + "0" * 64,
            "entries": [],
            "external_sources": [],
        }


@dataclass
class AttachedPreparedRun:
    workflow: Any
    profile: "ResolvedExecutionProfile"
    request: ExecutionPreflightRequest
    distributed_plan: Mapping[str, Any]


class _DeferredPreparedRun:
    """Process-local immutable acceptance object for non-remote targets."""

    expired = False
    manifest = _EmptyManifest()

    def __init__(self, submit: Callable[[], Any]) -> None:
        self._submit = submit
        self._closed = False
        self._submitted = False

    def submit(self, _transport: object) -> Any:
        if self._closed or self._submitted:
            raise RuntimeError("Prepared execution was already consumed")
        self._submitted = True
        return self._submit()

    def close(self) -> None:
        self._closed = True


@dataclass(frozen=True)
class ResolvedExecutionProfile:
    record: DistributedExecutionProfile
    workflow_id: str
    trusted_factories: tuple[str, ...]
    workflow_storage_path: str | Path | None

    @property
    def id(self) -> str:
        return self.record.id

    @property
    def revision(self) -> int:
        return self.record.revision

    @property
    def mode(self) -> str:
        return self.record.mode

    @property
    def transport(self) -> Any | None:
        value = self.record.transport
        return value.to_library() if value is not None else None

    def planning_arguments(self) -> Mapping[str, Any]:
        return {
            "executor_bindings": self.record.library_bindings(),
            "environment_routes": self.record.environment_routes,
            "shared_runtime_root": self.record.shared_runtime_root,
            "storage_mode": "shared_fs",
            "task_policy": self.record.task_policy.to_library(),
        }

    def submission_arguments(self) -> Mapping[str, Any]:
        launch = self.record.launch
        pre_launch = self.record.pre_launch
        return {
            "parsl_config": self.record.parsl_config.to_library(),
            "executor_bindings": self.record.library_bindings(),
            "environment_routes": self.record.environment_routes,
            "shared_runtime_root": self.record.shared_runtime_root,
            "task_policy": self.record.task_policy.to_library(),
            "launch": launch.to_library() if launch is not None else None,
            "pre_launch": pre_launch.to_library() if pre_launch is not None else None,
        }

    def prepare_non_remote(
        self,
        workflow: Any,
        request: ExecutionPreflightRequest,
        distributed_plan: Mapping[str, Any],
    ) -> _DeferredPreparedRun:
        if self.mode == "attached":
            prepared = AttachedPreparedRun(workflow, self, request, distributed_plan)
            return _DeferredPreparedRun(lambda: prepared)

        def submit_local() -> Any:
            import bioimageflow

            handle = bioimageflow.submit_workflow(
                workflow,
                inputs=request.root_inputs,
                targets=request.requested_nodes,
                node_routes=request.node_routes or None,
                **self.submission_arguments(),
            )
            return PreparedRunAcceptance(
                handle=handle,
                profile=self,
                request=request.model_copy(deep=True),
                distributed_plan=dict(distributed_plan),
            )

        return _DeferredPreparedRun(submit_local)


class PlatformExecutionProfileResolver:
    def __init__(
        self,
        store: ExecutionProfileStore,
        *,
        trusted_factories: Callable[[], list[str]],
        local_storage_path: Callable[[str], Path],
    ) -> None:
        self._store = store
        self._trusted_factories = trusted_factories
        self._local_storage_path = local_storage_path

    def resolve_target(
        self,
        target_id: str,
        workflow_id: str,
        profile_revision: int,
    ) -> ResolvedExecutionProfile:
        if target_id == "local":
            raise ValueError("Local execution does not use distributed preflight")
        try:
            profile = self._store.get(target_id)
        except ExecutionProfileNotFoundError as exc:
            raise ValueError("Execution target does not exist") from exc
        if profile.revision != profile_revision:
            raise ValueError(
                "The visible execution profile revision changed; refresh targets and confirm again"
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
        trusted = tuple(self._trusted_factories())
        if not profile.enabled:
            raise ValueError("Execution profile is disabled")
        if profile.parsl_config.factory not in trusted:
            raise ValueError("Execution profile factory is not trusted")
        storage: str | Path
        if profile.mode == "submitted_remote":
            assert profile.remote_workflow_root is not None
            storage = _remote_storage_path(profile.remote_workflow_root, workflow_id)
        else:
            storage = self._local_storage_path(workflow_id)
        return ResolvedExecutionProfile(profile, workflow_id, trusted, storage)


class DraftWorkflowResolver:
    def __init__(
        self,
        drafts: WorkflowDraftService,
        registry: ToolRegistryService,
        settings: Callable[[], Any],
    ) -> None:
        self._drafts = drafts
        self._registry = registry
        self._settings = settings

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
            settings=self._settings(),
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


def _plan_jobs(plan: Mapping[str, Any]) -> dict[str, JobSnapshot]:
    import bioimageflow

    decoded = bioimageflow.DistributedExecutionPlan.from_dict(dict(plan))
    jobs: dict[str, JobSnapshot] = {}
    for node in decoded.nodes:
        state = cast(
            JobState,
            {
                "cached": "cached",
                "skipped": "skipped",
                "prior_selection_miss": "waiting",
                "unexecuted": "waiting",
                "pending_upstream": "waiting",
            }[node.execution_status],
        )
        jobs[node.scoped_node_path] = JobSnapshot(
            scoped_node_path=node.scoped_node_path,
            state=state,
            executor_label=node.selected_executor,
            route_reason=node.route_reason,
            effective_resources=node.resources.to_dict(),
        )
    return jobs


def _target_snapshot(profile: ResolvedExecutionProfile) -> dict[str, Any]:
    # Pre-launch bytes and local source paths are not needed for reconnect and
    # must not be exposed through retained execution API responses.
    sanitized = profile.record.model_copy(update={"pre_launch": None})
    return {
        "name": profile.record.name,
        "mode": profile.mode,
        "profile": sanitized.model_dump(mode="json"),
    }


class PlatformPreparedRunRegistrar:
    def __init__(
        self,
        coordinator: ExecutionCoordinator,
        profiles: PlatformExecutionProfileResolver,
        managed_result_root: Path,
    ) -> None:
        self._coordinator = coordinator
        self._profiles = profiles
        self._managed_result_root = managed_result_root

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
            reconnect={"result_bundle": str(self._managed_result_root / context.execution_id)},
        )
        return await self._coordinator.register(
            snapshot,
            LegacyExecutionManagerAdapter(
                manager,
                context,
                loop,
                self._managed_result_root / context.execution_id,
            ),
        )

    async def register_prepared_run(
        self,
        request: ApplyPreparedExecutionRequest,
        run_handle: object,
    ) -> ExecutionSnapshot:
        if isinstance(run_handle, AttachedPreparedRun):
            return await self._register_attached(request, run_handle)
        if not isinstance(run_handle, PreparedRunAcceptance):
            raise TypeError("Prepared run is missing its accepted profile binding")
        accepted = run_handle
        profile = accepted.profile
        if not isinstance(profile, ResolvedExecutionProfile):
            raise TypeError("Prepared run has an invalid profile binding")
        handle = accepted.handle
        run_id = str(getattr(handle, "id"))
        storage_path = str(profile.workflow_storage_path)
        snapshot = ExecutionSnapshot(
            execution_id=run_id,
            workflow_id=request.workflow_id,
            draft_revision=request.draft_revision,
            command="run_selected" if request.requested_nodes else "run",
            requested_nodes=request.requested_nodes,
            backend=cast(ExecutionBackend, profile.mode),
            target_id=profile.id,
            profile_id=profile.id,
            profile_revision=profile.revision,
            target_snapshot=_target_snapshot(profile),
            state=cast(RunState, str(getattr(handle, "status"))),
            jobs=_plan_jobs(accepted.distributed_plan),
            reconnect={"storage_path": storage_path, "run_id": run_id},
        )
        return await self._coordinator.register(snapshot, SubmittedRunAdapter(handle))

    async def _register_attached(
        self,
        request: ApplyPreparedExecutionRequest,
        prepared: AttachedPreparedRun,
    ) -> ExecutionSnapshot:
        import bioimageflow

        run_id = f"run_{uuid4().hex}"
        context = bioimageflow.WorkflowExecutionContext(run_id=run_id)
        profile = prepared.profile
        managed_destination = self._managed_result_root / run_id

        def compute(progress: Callable[[Any], None]) -> Any:
            prepared.workflow.on_progress = progress
            targets = tuple(prepared.workflow.nodes[node] for node in request.requested_nodes or [])
            with bioimageflow.ParslEngine.from_config_ref(
                profile.record.parsl_config.to_library(),
                executor_bindings=profile.record.library_bindings(),
                trusted_factories=profile.trusted_factories,
                environment_routes=profile.record.environment_routes,
                shared_runtime_root=profile.record.shared_runtime_root,
                task_policy=profile.record.task_policy.to_library(),
            ) as engine:
                return prepared.workflow.compute(
                    *targets,
                    engine=engine,
                    run_context=context,
                )

        def export_result(value: Any, destination: Path) -> Path:
            context.export_result(value, destination=destination)
            return destination

        adapter = AttachedRunAdapter(
            compute=compute,
            cancel=context.request_cancel,
            result_exporter=export_result,
            managed_destination=managed_destination,
        )
        snapshot = ExecutionSnapshot(
            execution_id=run_id,
            workflow_id=request.workflow_id,
            draft_revision=request.draft_revision,
            command="run_selected" if request.requested_nodes else "run",
            requested_nodes=request.requested_nodes,
            backend="attached_parsl",
            target_id=profile.id,
            profile_id=profile.id,
            profile_revision=profile.revision,
            target_snapshot=_target_snapshot(profile),
            state="starting",
            jobs=_plan_jobs(prepared.distributed_plan),
            reconnect={"result_bundle": str(managed_destination)},
        )
        return await self._coordinator.register(snapshot, adapter)


class ExecutionDownloadDestinationResolver:
    def __init__(self, root: Path) -> None:
        self._root = root

    def resolve(self, execution_id: str) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        return self._root / execution_id


class LegacyExecutionManagerAdapter:
    """Expose the regular Direct/Wetlands manager through the retained panel."""

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
        if self._manager.context != self._context:
            return "lost"
        if self._manager.state == "running":
            return "running"
        result = self._manager.last_result
        if result is None:
            return "starting"
        if result.success:
            return "succeeded"
        if any(error.get("type") == "cancelled" for error in result.errors):
            return "cancelled"
        return "failed"

    def refresh(self) -> None:
        return None

    def progress(self, *, after_sequence: int = 0) -> list[dict[str, Any]]:
        return self._manager.retained_progress(after_sequence=after_sequence)

    def cancel(self) -> None:
        future = asyncio.run_coroutine_threadsafe(self._manager.stop(), self._loop)
        future.result()

    def logs(self) -> str:
        return ""

    def download_result(self, destination: Path) -> Path:
        if self._managed_destination.is_dir():
            if destination != self._managed_destination:
                raise RuntimeError("Managed result destination does not match this execution")
            return _archive_bundle(destination)
        return self._manager.export_retained_result(self._context, destination)

    export_result = download_result

    @property
    def result_export(self):
        if self._managed_destination.is_dir():
            from bioimageflow_server.models.execution_runtime import ResultExportSnapshot

            return ResultExportSnapshot(state="available")
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
