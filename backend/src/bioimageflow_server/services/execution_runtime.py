"""Engine-neutral execution adapters and retained-run coordinator."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import os
import shutil
import threading
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from bioimageflow_server.models.execution_runtime import (
    ClusterDiagnosticValue,
    ExecutionActionAvailability,
    ExecutionActions,
    ExecutionPage,
    ExecutionSnapshot,
    ObservationSnapshot,
    RecomputeSelection,
    RemoteRunObservationSnapshot,
    ResultExportSnapshot,
    RetryInvalidationPresentation,
    RetryPlanPresentation,
    RetryTargetPresentation,
    utc_now,
)
from bioimageflow_server.services.execution_progress import reduce_progress_events
from bioimageflow_server.services.execution_registry import (
    ExecutionNotFoundError,
    ExecutionRegistry,
    RetryPlanNotFoundError,
)


class ExecutionOperationError(RuntimeError):
    """Stable structured failure for retained execution actions."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


@runtime_checkable
class ExecutionRunAdapter(Protocol):
    """Small common surface over attached and submitted BioImageFlow runs."""

    @property
    def status(self) -> str: ...

    def refresh(self) -> None: ...

    def progress(self, *, after_sequence: int = 0) -> list[dict[str, Any]]: ...

    def cancel(self) -> None: ...

    def export_result(self, destination: Path) -> Path: ...

    @property
    def result_export(self) -> ResultExportSnapshot: ...


class ExecutionSnapshotPublisher(Protocol):
    async def publish_execution_snapshot(
        self,
        snapshot: ExecutionSnapshot,
        *,
        initial: bool,
    ) -> None: ...


class NullExecutionSnapshotPublisher:
    async def publish_execution_snapshot(
        self,
        snapshot: ExecutionSnapshot,
        *,
        initial: bool,
    ) -> None:
        return None


def _archive_bundle(bundle: Path) -> Path:
    archive = bundle.with_suffix(".zip")
    archive.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{archive.stem}.", suffix=".zip", dir=archive.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()
    try:
        created = Path(shutil.make_archive(str(temporary.with_suffix("")), "zip", bundle))
        os.replace(created, archive)
    finally:
        if temporary.exists():
            temporary.unlink()
    return archive


def _archive_digest(archive: Path) -> str:
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _verified_archive(bundle: Path, result_export: ResultExportSnapshot) -> Path:
    archive = bundle.with_suffix(".zip")
    expected = result_export.archive_digest
    if expected is None or not archive.is_file() or _archive_digest(archive) != expected:
        raise ExecutionOperationError(
            "workflow-result-integrity-error",
            "The managed result archive failed integrity verification.",
        )
    return archive


def _attached_completion_path(bundle: Path) -> Path:
    return bundle.with_suffix(".completion.json")


def _persist_attached_completion(
    bundle: Path,
    *,
    state: str,
    result_export: ResultExportSnapshot,
) -> None:
    """Atomically retain attached completion before exposing terminal status."""

    path = _attached_completion_path(bundle)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                {
                    "schema_version": 1,
                    "state": state,
                    "result_export": result_export.model_dump(mode="json"),
                },
                stream,
                sort_keys=True,
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()


def _load_attached_completion(
    bundle: Path,
) -> tuple[str, ResultExportSnapshot] | None:
    path = _attached_completion_path(bundle)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return None
    state = payload.get("state")
    if state not in {"succeeded", "failed", "cancelled"}:
        return None
    try:
        result_export = ResultExportSnapshot.model_validate(payload.get("result_export"))
    except (TypeError, ValueError):
        return None
    if state == "succeeded" and result_export.state == "available":
        try:
            _verified_archive(bundle, result_export)
        except ExecutionOperationError as exc:
            result_export = ResultExportSnapshot(
                state="unavailable",
                error_code=exc.code,
                detail=str(exc),
                archive_digest=result_export.archive_digest,
            )
    return state, result_export


class SubmittedRunAdapter:
    """Adapter over public WorkflowRun or RemoteWorkflowRun handles."""

    def __init__(
        self,
        handle: Any,
        *,
        result_export: ResultExportSnapshot | None = None,
    ) -> None:
        self.handle = handle
        self._result_export = result_export or ResultExportSnapshot()

    @property
    def status(self) -> str:
        return str(self.handle.status)

    def refresh(self) -> None:
        self.handle.refresh()

    def progress(self, *, after_sequence: int = 0) -> list[dict[str, Any]]:
        return list(self.handle.progress(after_sequence=after_sequence))

    def cancel(self) -> None:
        self.handle.cancel()

    def snapshot(self) -> dict[str, Any]:
        return RemoteRunObservationSnapshot.from_public_mapping(
            self.handle.snapshot()
        ).as_backend_metadata()

    def diagnostics(self) -> tuple[Any, ...]:
        return tuple(self.handle.diagnostics())

    def export_result(self, destination: Path) -> Path:
        try:
            self.handle.download_result(destination)
        except Exception as exc:
            error = _operation_error(exc, fallback="workflow-result-export-error")
            unavailable = error.code in {
                "workflow-run-result-unavailable",
                "workflow-result-integrity-error",
            }
            self._result_export = ResultExportSnapshot(
                state="unavailable" if unavailable else "pending",
                error_code=error.code,
                detail=str(error),
            )
            raise
        archive = _archive_bundle(destination)
        self._result_export = ResultExportSnapshot(
            state="available",
            archive_digest=_archive_digest(archive),
        )
        return archive

    @property
    def result_export(self) -> ResultExportSnapshot:
        return self._result_export

    def plan_retry(self, recompute: Any | None = None) -> Any:
        return self.handle.plan_retry(recompute)

    def start_retry(self, plan: Any) -> "SubmittedRunAdapter":
        return SubmittedRunAdapter(self.handle.start_retry(plan))


class AttachedRunAdapter:
    """Thread-backed adapter for Direct, Wetlands, and attached Parsl compute."""

    def __init__(
        self,
        *,
        compute: Callable[[Callable[[Any], None]], Any],
        cancel: Callable[[], None],
        result_exporter: Callable[[Any, Path], Path],
        managed_destination: Path,
    ) -> None:
        self._compute = compute
        self._cancel = cancel
        self._result_exporter = result_exporter
        self._managed_destination = managed_destination
        self._status = "starting"
        self._events: list[dict[str, Any]] = []
        self._sequence = 0
        self._event_lock = threading.Lock()
        self._result: Any = None
        self._error: BaseException | None = None
        self._result_export = ResultExportSnapshot()
        self._task: asyncio.Task[None] | None = None

    @property
    def status(self) -> str:
        return self._status

    def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("Attached adapter was already started")
        self._task = asyncio.create_task(self._run(), name="bioimageflow-attached-run")

    def _on_progress(self, event: Any) -> None:
        from bioimageflow_server.services.execution_progress import progress_event_from_attached

        with self._event_lock:
            converted = progress_event_from_attached(event, self._sequence + 1)
            self._events.extend(converted)
            self._sequence = converted[-1]["sequence"]

    def _complete(self, state: str) -> None:
        try:
            _persist_attached_completion(
                self._managed_destination,
                state=state,
                result_export=self._result_export,
            )
        except Exception as exc:
            if state == "succeeded":
                self._result_export = ResultExportSnapshot(
                    state="unavailable",
                    error_code="workflow-result-retention-error",
                    detail=f"Could not retain attached completion state: {exc}",
                    archive_digest=self._result_export.archive_digest,
                )
        finally:
            self._status = state

    async def _run(self) -> None:
        self._status = "running"
        try:
            self._result = await asyncio.to_thread(self._compute, self._on_progress)
        except Exception as exc:
            self._error = exc
            terminal_state = "cancelled" if self._status == "cancel_requested" else "failed"
            self._complete(terminal_state)
        else:
            if self._status == "cancel_requested":
                self._complete("cancelled")
                return
            try:
                self._result_exporter(self._result, self._managed_destination)
                archive = _archive_bundle(self._managed_destination)
            except Exception as exc:
                error = _operation_error(exc, fallback="workflow-result-export-error")
                self._result_export = ResultExportSnapshot(
                    state="unavailable",
                    error_code=error.code,
                    detail=str(error),
                )
                self._complete("succeeded")
            else:
                self._result_export = ResultExportSnapshot(
                    state="available",
                    archive_digest=_archive_digest(archive),
                )
                self._complete("succeeded")
            finally:
                self._result = None

    def refresh(self) -> None:
        return None

    def progress(self, *, after_sequence: int = 0) -> list[dict[str, Any]]:
        with self._event_lock:
            return [event for event in self._events if event["sequence"] > after_sequence]

    def cancel(self) -> None:
        if self._status not in {"starting", "running"}:
            return
        self._status = "cancel_requested"
        self._cancel()

    def export_result(self, destination: Path) -> Path:
        if self._status != "succeeded":
            if self._error is not None:
                raise RuntimeError("Attached execution did not succeed") from self._error
            raise RuntimeError("Attached execution result is not ready")
        if destination != self._managed_destination:
            raise ExecutionOperationError(
                "workflow-run-result-unavailable",
                self._result_export.detail or "The managed attached result is unavailable.",
            )
        return _verified_archive(destination, self._result_export)

    @property
    def result_export(self) -> ResultExportSnapshot:
        return self._result_export


class ManagedResultAdapter:
    """Read-only adapter for a process-independent attached result bundle."""

    def __init__(self, bundle: Path, result_export: ResultExportSnapshot) -> None:
        self._bundle = bundle
        self._result_export = result_export

    @property
    def status(self) -> str:
        return "succeeded"

    def refresh(self) -> None:
        return None

    def progress(self, *, after_sequence: int = 0) -> list[dict[str, Any]]:
        return []

    def cancel(self) -> None:
        return None

    def export_result(self, destination: Path) -> Path:
        if destination != self._bundle:
            raise ExecutionOperationError(
                "workflow-result-destination-conflict",
                "The retained attached result has a different managed destination.",
            )
        return _verified_archive(self._bundle, self._result_export)

    @property
    def result_export(self) -> ResultExportSnapshot:
        try:
            _verified_archive(self._bundle, self._result_export)
        except ExecutionOperationError as exc:
            return ResultExportSnapshot(
                state="unavailable",
                error_code=exc.code,
                detail=str(exc),
                archive_digest=self._result_export.archive_digest,
            )
        return self._result_export


RunReconnector = Callable[[ExecutionSnapshot], ExecutionRunAdapter]
CapabilityProvider = Callable[[], dict[str, dict[str, Any]]]


class ExecutionCoordinator:
    """Own adapters, polling, durable snapshots, and revisioned publication."""

    TERMINAL = {"succeeded", "failed", "cancelled", "lost"}

    def __init__(
        self,
        registry: ExecutionRegistry,
        *,
        reconnector: RunReconnector,
        capability_provider: CapabilityProvider | None = None,
        publisher: ExecutionSnapshotPublisher | None = None,
        poll_interval: float = 1.0,
    ) -> None:
        self.registry = registry
        self._reconnector = reconnector
        self._capability_provider = capability_provider or _public_capabilities
        self._publisher = publisher or NullExecutionSnapshotPublisher()
        self._poll_interval = poll_interval
        self._adapters: dict[str, ExecutionRunAdapter] = {}
        self._poll_tasks: dict[str, asyncio.Task[None]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def start(self) -> None:
        """Reconnect all retained non-terminal submitted runs without resubmission."""

        for parent_execution_id, digest in await asyncio.to_thread(
            self.registry.confirmed_retry_plans
        ):
            try:
                await self.confirm_retry(parent_execution_id, plan_digest=digest)
            except Exception:
                # The exact confirmed plan remains durable. A subsequent explicit
                # confirmation or process restart retries only this same identity.
                continue

        for snapshot in await asyncio.to_thread(self.registry.non_terminal):
            if snapshot.execution_id in self._adapters or snapshot.execution_id in self._poll_tasks:
                continue
            if snapshot.backend in {"direct", "wetlands"}:
                reconnect = snapshot.reconnect or {}
                result_bundle = reconnect.get("result_bundle")
                completion = (
                    _load_attached_completion(Path(result_bundle))
                    if isinstance(result_bundle, str)
                    else None
                )
                if completion is not None:
                    state, result_export = completion
                    recovered = snapshot.model_copy(
                        update={
                            "state": state,
                            "result_export": result_export,
                            "finished_at": utc_now(),
                        }
                    )
                    persisted = await asyncio.to_thread(
                        self.registry.save,
                        self._with_actions(recovered),
                        expected_revision=snapshot.revision,
                    )
                    await self._publisher.publish_execution_snapshot(
                        persisted,
                        initial=False,
                    )
                    continue
            if snapshot.backend in {"direct", "wetlands"}:
                lost = snapshot.model_copy(update={"state": "lost", "finished_at": utc_now()})
                persisted = await asyncio.to_thread(
                    self.registry.save,
                    self._with_actions(lost),
                    expected_revision=snapshot.revision,
                )
                await self._publisher.publish_execution_snapshot(
                    persisted,
                    initial=False,
                )
                continue
            try:
                adapter = await asyncio.to_thread(self._reconnector, snapshot)
            except Exception as exc:
                await self._record_observation_failure(snapshot, exc)
                self._poll_tasks[snapshot.execution_id] = asyncio.create_task(
                    self._reconnect_loop(snapshot.execution_id),
                    name=f"execution-reconnect-{snapshot.execution_id}",
                )
                continue
            await self.attach(snapshot.execution_id, adapter, publish_initial=False)

    async def close(self) -> None:
        tasks = list(self._poll_tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._poll_tasks.clear()

    async def register(
        self,
        snapshot: ExecutionSnapshot,
        adapter: ExecutionRunAdapter,
    ) -> ExecutionSnapshot:
        persisted = await asyncio.to_thread(
            self.registry.save,
            self._with_actions(snapshot),
            expected_revision=-1,
        )
        if isinstance(adapter, AttachedRunAdapter):
            adapter.start()
        await self.attach(persisted.execution_id, adapter, publish_initial=True)
        return persisted

    async def attach(
        self,
        execution_id: str,
        adapter: ExecutionRunAdapter,
        *,
        publish_initial: bool,
    ) -> None:
        if execution_id in self._adapters:
            raise RuntimeError(f"Execution {execution_id!r} already has an adapter")
        self._adapters[execution_id] = adapter
        self._locks.setdefault(execution_id, asyncio.Lock())
        snapshot = await asyncio.to_thread(self.registry.get, execution_id)
        if publish_initial:
            await self._publisher.publish_execution_snapshot(snapshot, initial=True)
        self._poll_tasks[execution_id] = asyncio.create_task(
            self._poll_loop(execution_id),
            name=f"execution-poll-{execution_id}",
        )

    async def get(self, execution_id: str) -> ExecutionSnapshot:
        snapshot = await asyncio.to_thread(self.registry.get, execution_id)
        return self._with_actions(snapshot)

    async def list(
        self,
        *,
        workflow_id: str | None,
        offset: int,
        limit: int,
    ) -> ExecutionPage:
        page = await asyncio.to_thread(
            self.registry.list,
            workflow_id=workflow_id,
            offset=offset,
            limit=limit,
        )
        return page.model_copy(update={"items": [self._with_actions(item) for item in page.items]})

    async def cancel(self, execution_id: str) -> ExecutionSnapshot:
        snapshot = await self.get(execution_id)
        if snapshot.terminal or snapshot.state == "cancel_requested":
            return snapshot
        if snapshot.backend == "managed_remote":
            cancellable = not snapshot.terminal
        else:
            cancellable = snapshot.state in {"prepared", "starting", "running"}
        if not cancellable:
            raise RuntimeError(f"Execution cannot be cancelled while {snapshot.state}")
        adapter = self._adapters.get(execution_id)
        if adapter is None:
            try:
                adapter = await asyncio.to_thread(self._reconnector, snapshot)
            except Exception as exc:
                raise _operation_error(exc, fallback="execution-cancel-failed") from exc
            reconnect_task = self._poll_tasks.pop(execution_id, None)
            if reconnect_task is not None:
                reconnect_task.cancel()
                await asyncio.gather(reconnect_task, return_exceptions=True)
            await self.attach(execution_id, adapter, publish_initial=False)
        try:
            await asyncio.to_thread(adapter.cancel)
        except Exception as exc:
            raise _operation_error(exc, fallback="execution-cancel-failed") from exc
        return await self._refresh_once(execution_id)

    async def plan_retry(
        self,
        execution_id: str,
        *,
        node_paths: tuple[str, ...] | None = None,
        cascade: bool = True,
    ) -> RetryPlanPresentation:
        source = await self.get(execution_id)
        if not source.terminal:
            raise ExecutionOperationError(
                "workflow-run-retry-error",
                "Only terminal executions can be retried.",
            )
        action = source.actions.recompute if node_paths is not None else source.actions.retry
        if not action.available:
            raise ExecutionOperationError(
                "workflow-run-retry-error",
                action.reason or "This execution cannot be retried.",
            )
        async with self._locks.setdefault(execution_id, asyncio.Lock()):
            adapter = self._adapters.get(execution_id)
            if adapter is None:
                try:
                    adapter = await asyncio.to_thread(self._reconnector, source)
                except Exception as exc:
                    raise _operation_error(
                        exc,
                        fallback="workflow-run-retry-error",
                    ) from exc
            if not isinstance(adapter, SubmittedRunAdapter):
                raise ExecutionOperationError(
                    "workflow-run-retry-error",
                    "Only retained submitted runs support immutable retry plans.",
                )
            recompute = None
            if node_paths is not None:
                import bioimageflow

                try:
                    recompute = bioimageflow.RecomputeRequest(
                        node_paths,
                        cascade=cascade,
                    )
                except (TypeError, ValueError) as exc:
                    raise ExecutionOperationError(
                        "invalid-recompute-request",
                        str(exc),
                    ) from exc
            try:
                plan = await asyncio.to_thread(adapter.plan_retry, recompute)
            except Exception as exc:
                raise _operation_error(exc, fallback="workflow-run-retry-error") from exc
            payload = plan.to_dict()
            # Round-trip through the released public parser before retaining any bytes.
            import bioimageflow

            verified = bioimageflow.RunRetryPlan.from_dict(payload)
            await asyncio.to_thread(self.registry.save_retry_plan, verified.to_dict())
        return _retry_presentation(source, verified)

    async def confirm_retry(
        self,
        execution_id: str,
        *,
        plan_digest: str,
    ) -> ExecutionSnapshot:
        source = await self.get(execution_id)
        if not source.terminal:
            raise ExecutionOperationError(
                "workflow-run-retry-error",
                "Only terminal executions can be retried.",
            )
        try:
            payload = await asyncio.to_thread(
                self.registry.get_retry_plan,
                execution_id,
                plan_digest,
            )
        except RetryPlanNotFoundError as exc:
            raise ExecutionOperationError(
                "retry-plan-not-found",
                "The confirmed retry plan is unknown; create a new preview.",
            ) from exc
        import bioimageflow

        try:
            plan = bioimageflow.RunRetryPlan.from_dict(payload)
        except (TypeError, ValueError) as exc:
            raise ExecutionOperationError(
                "retry-plan-integrity-error",
                "The retained retry plan failed integrity verification.",
            ) from exc
        if plan.digest != plan_digest or plan.parent_run_id != execution_id:
            raise ExecutionOperationError(
                "retry-plan-integrity-error",
                "The retained retry plan does not match this confirmation.",
            )
        if plan.conflicting_run_ids:
            raise ExecutionOperationError(
                "workflow-run-retry-error",
                "The retry plan conflicts with an active execution; create a new preview.",
                details={"conflicting_run_ids": list(plan.conflicting_run_ids)},
            )

        async with self._locks.setdefault(execution_id, asyncio.Lock()):
            source = await self.get(execution_id)
            if not source.terminal:
                raise ExecutionOperationError(
                    "workflow-run-retry-error",
                    "Only terminal executions can be retried.",
                )
            action = (
                source.actions.recompute if plan.recompute is not None else source.actions.retry
            )
            if not action.available:
                raise ExecutionOperationError(
                    "workflow-run-retry-error",
                    action.reason or "This execution cannot be retried.",
                )
            plan_state = await asyncio.to_thread(
                self.registry.retry_plan_state,
                execution_id,
                plan_digest,
            )
            if plan_state in {"uncertain", "started"}:
                try:
                    child = await asyncio.to_thread(self.registry.get, plan.retry_run_id)
                except ExecutionNotFoundError as exc:
                    raise ExecutionOperationError(
                        "retry-plan-integrity-error",
                        "The retained retry state is missing its exact child identity.",
                    ) from exc
                if plan_state == "started":
                    return self._with_actions(child)
                attached = self._adapters.get(child.execution_id)
                try:
                    if attached is None:
                        attached = await asyncio.to_thread(self._reconnector, child)
                except Exception as exc:
                    if _diagnostic_category(exc) != "run-not-found":
                        await self._ensure_uncertain_retry_observation(child)
                        return self._with_actions(child)
                    await asyncio.to_thread(
                        self.registry.mark_retry_absent,
                        execution_id,
                        plan_digest,
                    )
                else:
                    recovered = child.model_copy(
                        update={
                            "state": attached.status,
                            "observation": ObservationSnapshot(),
                        }
                    )
                    persisted = await asyncio.to_thread(
                        self.registry.save,
                        self._with_actions(recovered),
                        expected_revision=child.revision,
                    )
                    # The run exists, so the exact retry start is durably complete.
                    await asyncio.to_thread(
                        self.registry.mark_retry_absent,
                        execution_id,
                        plan_digest,
                    )
                    await asyncio.to_thread(
                        self.registry.mark_retry_started,
                        execution_id,
                        plan_digest,
                    )
                    if persisted.execution_id not in self._adapters:
                        await self.attach(
                            persisted.execution_id,
                            attached,
                            publish_initial=True,
                        )
                    return persisted
            await asyncio.to_thread(
                self.registry.confirm_retry_plan,
                execution_id,
                plan_digest,
            )
            child = await self._ensure_retry_child(source, plan)
            # Recovery always observes the exact preallocated child first. Only a
            # definitive public run-not-found diagnostic permits starting this plan.
            try:
                attached_child = await asyncio.to_thread(self._reconnector, child)
            except Exception as attach_exc:
                if _diagnostic_category(attach_exc) != "run-not-found":
                    error = _operation_error(
                        attach_exc,
                        fallback="retry-child-observation-uncertain",
                    )
                    await asyncio.to_thread(
                        self.registry.mark_retry_uncertain,
                        execution_id,
                        plan_digest,
                    )
                    failed_observation = child.model_copy(
                        update={
                            "observation": ObservationSnapshot(
                                reachable=False,
                                error=_observation_error_text(attach_exc),
                            )
                        }
                    )
                    await asyncio.to_thread(
                        self.registry.save,
                        self._with_actions(failed_observation),
                        expected_revision=child.revision,
                    )
                    raise error from attach_exc
            else:
                started = child.model_copy(
                    update={
                        "state": attached_child.status,
                        "observation": ObservationSnapshot(),
                    }
                )
                persisted = await asyncio.to_thread(
                    self.registry.save,
                    self._with_actions(started),
                    expected_revision=child.revision,
                )
                await asyncio.to_thread(
                    self.registry.mark_retry_started,
                    execution_id,
                    plan_digest,
                )
                await self.attach(persisted.execution_id, attached_child, publish_initial=True)
                return persisted
            parent_adapter = self._adapters.get(execution_id)
            if parent_adapter is None:
                try:
                    parent_adapter = await asyncio.to_thread(self._reconnector, source)
                except Exception as exc:
                    raise _operation_error(
                        exc,
                        fallback="workflow-run-retry-error",
                    ) from exc
            if not isinstance(parent_adapter, SubmittedRunAdapter):
                raise ExecutionOperationError(
                    "workflow-run-retry-error",
                    "Only retained submitted runs support immutable retries.",
                )
            try:
                child_adapter = await asyncio.to_thread(parent_adapter.start_retry, plan)
            except Exception as exc:
                error = _operation_error(exc, fallback="workflow-run-retry-error")
                uncertain_codes = {"submission-uncertain", "remote-retry-submission-uncertain"}
                if error.code in uncertain_codes:
                    await asyncio.to_thread(
                        self.registry.mark_retry_uncertain,
                        execution_id,
                        plan_digest,
                    )
                    child = child.model_copy(
                        update={
                            "observation": ObservationSnapshot(
                                reachable=False,
                                error=_observation_error_text(exc),
                            )
                        }
                    )
                    child = await asyncio.to_thread(
                        self.registry.save,
                        self._with_actions(child),
                        expected_revision=child.revision,
                    )
                    await self._publisher.publish_execution_snapshot(child, initial=True)
                    await self._ensure_uncertain_retry_observation(child)
                else:
                    await asyncio.to_thread(
                        self.registry.mark_retry_failed,
                        execution_id,
                        plan_digest,
                        error={
                            "code": error.code,
                            "message": str(error),
                            "details": error.details,
                        },
                    )
                    failed_child = child.model_copy(
                        update={
                            "state": "failed",
                            "finished_at": utc_now(),
                            "backend_metadata": {
                                **child.backend_metadata,
                                "retry_start_failed": {
                                    "code": error.code,
                                    "message": str(error),
                                },
                            },
                        }
                    )
                    failed_child = await asyncio.to_thread(
                        self.registry.save,
                        self._with_actions(failed_child),
                        expected_revision=child.revision,
                    )
                    await self._publisher.publish_execution_snapshot(
                        failed_child,
                        initial=True,
                    )
                raise error from exc
            started = child.model_copy(
                update={
                    "state": child_adapter.status,
                    "observation": ObservationSnapshot(),
                }
            )
            persisted = await asyncio.to_thread(
                self.registry.save,
                self._with_actions(started),
                expected_revision=child.revision,
            )
            await asyncio.to_thread(
                self.registry.mark_retry_started,
                execution_id,
                plan_digest,
            )
            await self.attach(persisted.execution_id, child_adapter, publish_initial=True)
            return persisted

    async def download_result(self, execution_id: str, destination: Path) -> Path:
        snapshot = await self.get(execution_id)
        if snapshot.state != "succeeded":
            raise ExecutionOperationError(
                "workflow-run-result-unavailable",
                "Execution result is not available.",
            )
        if not snapshot.actions.download_results.available:
            raise ExecutionOperationError(
                "workflow-run-result-unavailable",
                snapshot.actions.download_results.reason
                or "Execution result export is unavailable.",
            )
        adapter = _retained_managed_result_adapter(snapshot)
        if adapter is None:
            adapter = self._adapters.get(execution_id)
        if adapter is None:
            try:
                adapter = await asyncio.to_thread(self._reconnector, snapshot)
            except Exception as exc:
                raise _operation_error(
                    exc,
                    fallback="workflow-result-export-error",
                ) from exc
        async with self._locks.setdefault(execution_id, asyncio.Lock()):
            try:
                archive = await asyncio.to_thread(adapter.export_result, destination)
            except Exception as exc:
                await self._persist_result_export(execution_id, adapter.result_export)
                raise _operation_error(exc, fallback="workflow-result-export-error") from exc
            await self._persist_result_export(execution_id, adapter.result_export)
        return archive

    async def plan_cleanup(
        self,
        execution_id: str,
        *,
        older_than_seconds: int = 86_400,
    ) -> tuple[str, dict[str, Any]]:
        snapshot = await self.get(execution_id)
        if not snapshot.actions.cleanup.available:
            raise ExecutionOperationError(
                "cleanup-unavailable",
                snapshot.actions.cleanup.reason or "Managed cleanup is unavailable.",
            )
        cluster = _cluster_from_snapshot(snapshot)
        try:
            plan = await asyncio.to_thread(
                cluster.plan_cleanup,
                namespace="runs",
                run_ids=(execution_id,),
                older_than_seconds=older_than_seconds,
            )
        except Exception as exc:
            raise _operation_error(exc, fallback="cleanup-planning-failed") from exc
        payload = plan.to_dict()
        digest = await asyncio.to_thread(
            self.registry.save_cleanup_plan,
            execution_id,
            payload,
        )
        return digest, payload

    async def apply_cleanup(self, execution_id: str, *, plan_digest: str) -> dict[str, Any]:
        snapshot = await self.get(execution_id)
        if not snapshot.actions.cleanup.available:
            raise ExecutionOperationError(
                "cleanup-unavailable",
                snapshot.actions.cleanup.reason or "Managed cleanup is unavailable.",
            )
        try:
            payload = await asyncio.to_thread(
                self.registry.get_cleanup_plan,
                execution_id,
                plan_digest,
            )
        except ExecutionNotFoundError as exc:
            raise ExecutionOperationError(
                "cleanup-plan-not-found",
                "The confirmed cleanup plan is unknown; create a new preview.",
            ) from exc
        cluster_api = importlib.import_module("bioimageflow.cluster")
        plan = cluster_api.ClusterCleanupPlan.from_dict(payload)
        cluster = _cluster_from_snapshot(snapshot)
        try:
            report = await asyncio.to_thread(cluster.apply_cleanup, plan)
        except Exception as exc:
            raise _operation_error(exc, fallback="cleanup-apply-failed") from exc
        return report.to_dict()

    async def _persist_result_export(
        self,
        execution_id: str,
        result_export: ResultExportSnapshot,
    ) -> None:
        current = await asyncio.to_thread(self.registry.get, execution_id)
        if current.result_export == result_export:
            return
        updated = current.model_copy(update={"result_export": result_export})
        await asyncio.to_thread(
            self.registry.save,
            self._with_actions(updated),
            expected_revision=current.revision,
        )

    async def _ensure_retry_child(self, source: ExecutionSnapshot, plan: Any) -> ExecutionSnapshot:
        try:
            child = await asyncio.to_thread(self.registry.get, plan.retry_run_id)
        except ExecutionNotFoundError:
            invalidated = {item.node_path for item in plan.invalidations}
            jobs = {
                path: job.model_copy(
                    update={
                        "state": (
                            "waiting"
                            if path in invalidated
                            or job.state in {"waiting", "running", "failed", "cancelled", "blocked"}
                            else "skipped"
                            if job.state == "skipped"
                            else "cached"
                        ),
                        "diagnostic": None,
                        "started_at": None,
                        "finished_at": None,
                    }
                )
                for path, job in source.jobs.items()
            }
            child = ExecutionSnapshot(
                execution_id=plan.retry_run_id,
                workflow_id=source.workflow_id,
                draft_revision=source.draft_revision,
                graph_fingerprint=source.graph_fingerprint,
                command="recompute" if plan.recompute is not None else "retry",
                requested_nodes=source.requested_nodes,
                retry_of_execution_id=source.execution_id,
                backend=source.backend,
                target_id=source.target_id,
                profile_id=source.profile_id,
                profile_revision=source.profile_revision,
                target_snapshot=source.target_snapshot,
                state="preparing",
                jobs=jobs,
                reconnect={
                    **(source.reconnect or {}),
                    "run_id": plan.retry_run_id,
                },
                backend_metadata={"retry_plan_digest": plan.digest},
            )
            child = await asyncio.to_thread(
                self.registry.save,
                self._with_actions(child),
                expected_revision=-1,
            )
        else:
            if (
                child.retry_of_execution_id != source.execution_id
                or child.backend_metadata.get("retry_plan_digest") != plan.digest
            ):
                raise ExecutionOperationError(
                    "retry-child-conflict",
                    "The planned child execution identity belongs to another retry.",
                )
        if child.execution_id not in source.child_execution_ids:
            linked = source.model_copy(
                update={
                    "child_execution_ids": [
                        *source.child_execution_ids,
                        child.execution_id,
                    ]
                }
            )
            linked = await asyncio.to_thread(
                self.registry.save,
                self._with_actions(linked),
                expected_revision=source.revision,
            )
            await self._publisher.publish_execution_snapshot(linked, initial=False)
        return child

    async def _ensure_uncertain_retry_observation(
        self,
        child: ExecutionSnapshot,
    ) -> None:
        """Reconnect only the retry plan's exact child without replaying submission."""

        execution_id = child.execution_id
        if execution_id in self._adapters or execution_id in self._poll_tasks:
            return
        try:
            adapter = await asyncio.to_thread(self._reconnector, child)
        except Exception as exc:
            current = await asyncio.to_thread(self.registry.get, execution_id)
            await self._record_observation_failure(current, exc)
            self._poll_tasks[execution_id] = asyncio.create_task(
                self._reconnect_loop(execution_id),
                name=f"execution-reconnect-{execution_id}",
            )
            return
        await self.attach(execution_id, adapter, publish_initial=False)

    def _with_actions(self, snapshot: ExecutionSnapshot) -> ExecutionSnapshot:
        return snapshot.model_copy(
            update={"actions": _execution_actions(snapshot, self._capability_provider())}
        )

    async def _poll_loop(self, execution_id: str) -> None:
        try:
            while True:
                snapshot = await self._refresh_once(execution_id)
                if snapshot.terminal:
                    return
                await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            raise
        finally:
            self._poll_tasks.pop(execution_id, None)

    async def _reconnect_loop(self, execution_id: str) -> None:
        try:
            while True:
                await asyncio.sleep(self._poll_interval)
                snapshot = await self.get(execution_id)
                if snapshot.terminal:
                    return
                try:
                    adapter = await asyncio.to_thread(self._reconnector, snapshot)
                except Exception as exc:
                    await self._record_observation_failure(snapshot, exc)
                    continue
                self._adapters[execution_id] = adapter
                self._locks.setdefault(execution_id, asyncio.Lock())
                await self._poll_loop(execution_id)
                return
        except asyncio.CancelledError:
            raise
        finally:
            current = asyncio.current_task()
            if self._poll_tasks.get(execution_id) is current:
                self._poll_tasks.pop(execution_id, None)

    async def _refresh_once(self, execution_id: str) -> ExecutionSnapshot:
        async with self._locks.setdefault(execution_id, asyncio.Lock()):
            snapshot = await asyncio.to_thread(self.registry.get, execution_id)
            adapter = self._adapters[execution_id]
            try:
                await asyncio.to_thread(adapter.refresh)
                events = await asyncio.to_thread(
                    adapter.progress,
                    after_sequence=snapshot.progress_cursor,
                )
                reduced = reduce_progress_events(snapshot, events)
                state = adapter.status
                update: dict[str, Any] = {
                    "state": state,
                    "observation": ObservationSnapshot(),
                    "result_export": adapter.result_export,
                }
                if isinstance(adapter, SubmittedRunAdapter):
                    update["backend_metadata"] = adapter.snapshot()
                if state in self.TERMINAL and reduced.finished_at is None:
                    update["finished_at"] = utc_now()
                reduced = reduced.model_copy(update=update)
            except Exception as exc:
                return await self._record_observation_failure(snapshot, exc)
            if (
                reduced.state == snapshot.state
                and reduced.jobs == snapshot.jobs
                and reduced.progress_cursor == snapshot.progress_cursor
                and reduced.result_export == snapshot.result_export
                and reduced.backend_metadata == snapshot.backend_metadata
                and reduced.diagnostics == snapshot.diagnostics
                and reduced.finished_at == snapshot.finished_at
                and snapshot.observation.reachable
            ):
                return snapshot
            persisted = await asyncio.to_thread(
                self.registry.save,
                self._with_actions(reduced),
                expected_revision=snapshot.revision,
            )
            await self._publisher.publish_execution_snapshot(persisted, initial=False)
            return persisted

    async def _record_observation_failure(
        self,
        snapshot: ExecutionSnapshot,
        exc: Exception,
    ) -> ExecutionSnapshot:
        # Observation loss never changes the authoritative run state.
        observation_error = _observation_error_text(exc)
        diagnostic = _cluster_diagnostic_value(exc)
        if (
            not snapshot.observation.reachable
            and snapshot.observation.error == observation_error
            and (diagnostic is None or diagnostic in snapshot.diagnostics)
        ):
            return snapshot
        failed = snapshot.model_copy(
            update={
                "observation": ObservationSnapshot(
                    reachable=False,
                    error=observation_error,
                ),
                "diagnostics": [
                    *snapshot.diagnostics,
                    *([diagnostic] if diagnostic is not None else []),
                ],
            }
        )
        persisted = await asyncio.to_thread(
            self.registry.save,
            self._with_actions(failed),
            expected_revision=snapshot.revision,
        )
        await self._publisher.publish_execution_snapshot(persisted, initial=False)
        return persisted


def _public_capabilities() -> dict[str, dict[str, Any]]:
    import bioimageflow

    payload = bioimageflow.get_execution_capabilities().to_dict()
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, dict):
        raise RuntimeError("BioImageFlow returned an invalid execution capability report")
    return capabilities


def _capability(
    capabilities: dict[str, dict[str, Any]],
    key: str,
) -> tuple[bool, str | None]:
    value = capabilities.get(key)
    if not isinstance(value, dict) or type(value.get("supported")) is not bool:
        return False, f"BioImageFlow did not report the {key!r} capability."
    reason = value.get("reason")
    return bool(value["supported"]), reason if isinstance(reason, str) else None


def _availability(available: bool, reason: str | None = None) -> ExecutionActionAvailability:
    return ExecutionActionAvailability(
        available=available,
        reason=None if available else reason or "This action is unavailable.",
    )


def _execution_actions(
    snapshot: ExecutionSnapshot,
    capabilities: dict[str, dict[str, Any]],
) -> ExecutionActions:
    backend_capability = {
        "direct": "direct",
        "wetlands": "wetlands",
        "managed_remote": "remote_cluster_bootstrap",
    }[snapshot.backend]
    backend_supported, backend_reason = _capability(capabilities, backend_capability)
    cancellable = (
        not snapshot.terminal
        if snapshot.backend == "managed_remote"
        else snapshot.state in {"prepared", "starting", "running"}
    )
    cancel_reason = backend_reason if not backend_supported else f"Execution is {snapshot.state}."

    submitted = snapshot.backend == "managed_remote"
    retry_supported, retry_reason = _capability(capabilities, "submitted_run_retry")
    recompute_supported, recompute_reason = _capability(capabilities, "submitted_recompute")
    retry_available = backend_supported and submitted and snapshot.terminal and retry_supported
    recompute_available = (
        backend_supported and submitted and snapshot.terminal and recompute_supported
    )
    if not submitted:
        retry_reason = recompute_reason = "Immutable retry plans require a submitted run."
    elif not snapshot.terminal:
        retry_reason = recompute_reason = f"Execution is {snapshot.state}."
    elif not backend_supported:
        retry_reason = recompute_reason = backend_reason
    if "retry_start_failed" in snapshot.backend_metadata:
        retry_available = recompute_available = False
        retry_reason = recompute_reason = "The confirmed child failed before launch."

    result_capability = "submitted_result_export" if submitted else "attached_result_export"
    result_supported, result_reason = _capability(capabilities, result_capability)
    result_available = (
        backend_supported
        and result_supported
        and snapshot.state == "succeeded"
        and snapshot.result_export.state != "unavailable"
    )
    if snapshot.state != "succeeded":
        result_reason = f"Execution is {snapshot.state}."
    elif not backend_supported:
        result_reason = backend_reason
    elif snapshot.result_export.state == "unavailable":
        result_reason = snapshot.result_export.detail or "Result export is unavailable."
    cleanup_supported, cleanup_reason = _capability(
        capabilities,
        "cluster_cleanup_planning",
    )
    cleanup_available = submitted and snapshot.terminal and cleanup_supported
    if not submitted:
        cleanup_reason = "Managed cleanup applies only to remote cluster runs."
    elif not snapshot.terminal:
        cleanup_reason = f"Execution is {snapshot.state}."
    return ExecutionActions(
        cancel=_availability(backend_supported and cancellable, cancel_reason),
        retry=_availability(retry_available, retry_reason),
        recompute=_availability(recompute_available, recompute_reason),
        download_results=_availability(result_available, result_reason),
        cleanup=_availability(cleanup_available, cleanup_reason),
    )


def _retry_presentation(source: ExecutionSnapshot, plan: Any) -> RetryPlanPresentation:
    recompute = (
        None
        if plan.recompute is None
        else RecomputeSelection(
            node_paths=list(plan.recompute.node_paths),
            cascade=plan.recompute.cascade,
        )
    )
    conflicts = list(plan.conflicting_run_ids)
    return RetryPlanPresentation(
        plan_digest=plan.digest,
        parent_execution_id=plan.parent_run_id,
        child_execution_id=plan.retry_run_id,
        mode="recompute" if recompute is not None else "retry",
        target=RetryTargetPresentation.model_validate(
            {
                "id": source.target_id,
                "label": source.target_snapshot.get("name", source.target_id),
                "mode": source.target_snapshot.get("mode", source.backend),
            }
        ),
        recompute=recompute,
        invalidations=[
            RetryInvalidationPresentation(**item.to_dict()) for item in plan.invalidations
        ],
        conflicting_run_ids=conflicts,
        confirmable=not conflicts,
        disabled_reason=(
            None if not conflicts else "Another execution currently owns the retained storage."
        ),
    )


def _cluster_diagnostic_value(exc: Exception) -> ClusterDiagnosticValue | None:
    diagnostic = getattr(exc, "diagnostic", None)
    if diagnostic is None or not callable(getattr(diagnostic, "to_dict", None)):
        return None
    try:
        return ClusterDiagnosticValue.model_validate(diagnostic.to_dict())
    except (TypeError, ValueError):
        return None


def _diagnostic_category(exc: Exception) -> str | None:
    diagnostic = _cluster_diagnostic_value(exc)
    return None if diagnostic is None else diagnostic.category


def _observation_error_text(exc: Exception) -> str:
    diagnostic = _cluster_diagnostic_value(exc)
    if diagnostic is not None:
        return diagnostic.message
    return "The execution could not be observed."


def _operation_error(exc: Exception, *, fallback: str) -> ExecutionOperationError:
    if isinstance(exc, ExecutionOperationError):
        return exc
    diagnostic = _cluster_diagnostic_value(exc)
    if diagnostic is not None:
        payload = diagnostic.model_dump(mode="json", by_alias=True)
        return ExecutionOperationError(
            diagnostic.category,
            diagnostic.message,
            details={
                "diagnostic": payload,
                "phase": diagnostic.phase,
                "allocation_state": diagnostic.allocation_state,
                "retry_safety": diagnostic.retry_safety,
                "next_action": diagnostic.next_action,
                "identities": dict(diagnostic.identities),
            },
        )
    details_value = getattr(exc, "details", None)
    details = dict(details_value) if isinstance(details_value, dict) else {}
    public_code = getattr(exc, "code", None)
    remote_code = details.get("remote_code")
    code_value = public_code if isinstance(public_code, str) else fallback
    if code_value == "workflow-run-retry-error" and remote_code in {
        "remote-invalid-retry",
        "remote-retry-conflict",
        "remote-retry-submission-uncertain",
    }:
        code_value = remote_code
    code = code_value if isinstance(code_value, str) else fallback
    # Unexpected implementation failures do not carry BioImageFlow's public,
    # sanitized diagnostic contract. Do not reflect arbitrary exception text or
    # detail mappings into API responses and retained execution state.
    if not isinstance(public_code, str):
        return ExecutionOperationError(
            fallback,
            "The managed execution operation failed unexpectedly.",
        )
    return ExecutionOperationError(code, str(exc), details=details)


def open_public_submitted_run(
    snapshot: ExecutionSnapshot,
) -> ExecutionRunAdapter:
    """Reconnect using only public BioImageFlow handles and sanitized profile values."""

    reconnect = snapshot.reconnect or {}
    retained_result = _retained_managed_result_adapter(snapshot)
    if retained_result is not None:
        return retained_result
    if snapshot.backend in {"direct", "wetlands"}:
        result_bundle = reconnect.get("result_bundle")
        if snapshot.state == "succeeded" and isinstance(result_bundle, str):
            return ManagedResultAdapter(Path(result_bundle), snapshot.result_export)
        raise ValueError("Attached executions cannot be reconnected before success")
    host = reconnect.get("host")
    root = reconnect.get("root")
    run_id = reconnect.get("run_id")
    if snapshot.backend == "managed_remote":
        if not all(isinstance(value, str) for value in (host, root, run_id)):
            raise ValueError("Managed execution reconnect metadata is incomplete")
        cluster_api = importlib.import_module("bioimageflow.cluster")
        cluster = cluster_api.RemoteCluster(host=host, root=root)
        return SubmittedRunAdapter(
            cluster.attach(run_id),
            result_export=snapshot.result_export,
        )
    raise ValueError("Execution backend cannot be reconnected")


def _retained_managed_result_adapter(
    snapshot: ExecutionSnapshot,
) -> ManagedResultAdapter | None:
    if snapshot.state != "succeeded" or snapshot.result_export.state != "available":
        return None
    reconnect = snapshot.reconnect or {}
    result_bundle = reconnect.get("result_bundle")
    if not isinstance(result_bundle, str):
        return None
    try:
        _verified_archive(Path(result_bundle), snapshot.result_export)
    except ExecutionOperationError:
        return None
    return ManagedResultAdapter(Path(result_bundle), snapshot.result_export)


def _cluster_from_snapshot(snapshot: ExecutionSnapshot) -> Any:
    reconnect = snapshot.reconnect or {}
    host = reconnect.get("host")
    root = reconnect.get("root")
    if snapshot.backend != "managed_remote" or not all(
        isinstance(value, str) for value in (host, root)
    ):
        raise ExecutionOperationError(
            "cleanup-unavailable",
            "Managed cluster reconnect facts are unavailable.",
        )
    cluster_api = importlib.import_module("bioimageflow.cluster")
    return cluster_api.RemoteCluster(host=host, root=root)
