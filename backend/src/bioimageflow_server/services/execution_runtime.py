"""Engine-neutral execution adapters and retained-run coordinator."""

from __future__ import annotations

import asyncio
import inspect
import shutil
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from bioimageflow_server.models.execution_runtime import (
    ExecutionSnapshot,
    ObservationSnapshot,
    utc_now,
)
from bioimageflow_server.services.execution_progress import reduce_progress_events
from bioimageflow_server.services.execution_registry import ExecutionRegistry


@runtime_checkable
class ExecutionRunAdapter(Protocol):
    """Small common surface over attached and submitted BioImageFlow runs."""

    @property
    def status(self) -> str: ...

    def refresh(self) -> None: ...

    def progress(self, *, after_sequence: int = 0) -> list[dict[str, Any]]: ...

    def cancel(self) -> None: ...

    def logs(self) -> str: ...

    def download_result(self, destination: Path) -> Path: ...


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


class SubmittedRunAdapter:
    """Adapter over public WorkflowRun or RemoteWorkflowRun handles."""

    def __init__(self, handle: Any, *, result_exporter: Callable[[Any, Path], Path] | None = None) -> None:
        self.handle = handle
        self._result_exporter = result_exporter

    @property
    def status(self) -> str:
        return str(self.handle.status)

    def refresh(self) -> None:
        self.handle.refresh()

    def progress(self, *, after_sequence: int = 0) -> list[dict[str, Any]]:
        return list(self.handle.progress(after_sequence=after_sequence))

    def cancel(self) -> None:
        self.handle.cancel()

    def logs(self) -> str:
        return str(self.handle.logs())

    def download_result(self, destination: Path) -> Path:
        signature = inspect.signature(self.handle.result)
        if "destination" in signature.parameters:
            self.handle.result(destination=destination)
            archive = Path(shutil.make_archive(str(destination), "zip", destination))
            return archive
        value = self.handle.result()
        if self._result_exporter is None:
            raise RuntimeError("A result exporter is required for attached or submitted-local results")
        return self._result_exporter(value, destination)


class AttachedRunAdapter:
    """Thread-backed adapter for Direct, Wetlands, and attached Parsl compute."""

    def __init__(
        self,
        *,
        compute: Callable[[Callable[[Any], None]], Any],
        cancel: Callable[[], None],
        result_exporter: Callable[[Any, Path], Path],
    ) -> None:
        self._compute = compute
        self._cancel = cancel
        self._result_exporter = result_exporter
        self._status = "starting"
        self._events: list[dict[str, Any]] = []
        self._sequence = 0
        self._event_lock = threading.Lock()
        self._result: Any = None
        self._error: BaseException | None = None
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

    async def _run(self) -> None:
        self._status = "running"
        try:
            self._result = await asyncio.to_thread(self._compute, self._on_progress)
        except Exception as exc:
            self._error = exc
            self._status = "cancelled" if self._status == "cancel_requested" else "failed"
        else:
            self._status = "cancelled" if self._status == "cancel_requested" else "succeeded"

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

    def logs(self) -> str:
        return ""

    def download_result(self, destination: Path) -> Path:
        if self._status != "succeeded":
            if self._error is not None:
                raise RuntimeError("Attached execution did not succeed") from self._error
            raise RuntimeError("Attached execution result is not ready")
        return self._result_exporter(self._result, destination)


RunReconnector = Callable[[ExecutionSnapshot], ExecutionRunAdapter]
RetryFactory = Callable[[ExecutionSnapshot, str | None], tuple[ExecutionSnapshot, ExecutionRunAdapter]]


class ExecutionCoordinator:
    """Own adapters, polling, durable snapshots, and revisioned publication."""

    TERMINAL = {"succeeded", "failed", "cancelled", "lost"}

    def __init__(
        self,
        registry: ExecutionRegistry,
        *,
        reconnector: RunReconnector,
        retry_factory: RetryFactory | None = None,
        publisher: ExecutionSnapshotPublisher | None = None,
        poll_interval: float = 1.0,
    ) -> None:
        self.registry = registry
        self._reconnector = reconnector
        self._retry_factory = retry_factory
        self._publisher = publisher or NullExecutionSnapshotPublisher()
        self._poll_interval = poll_interval
        self._adapters: dict[str, ExecutionRunAdapter] = {}
        self._poll_tasks: dict[str, asyncio.Task[None]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def start(self) -> None:
        """Reconnect all retained non-terminal submitted runs without resubmission."""

        for snapshot in await asyncio.to_thread(self.registry.non_terminal):
            if snapshot.backend in {"direct", "wetlands", "attached_parsl"}:
                lost = snapshot.model_copy(
                    update={"state": "lost", "finished_at": utc_now()}
                )
                persisted = await asyncio.to_thread(
                    self.registry.save,
                    lost,
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
            snapshot,
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
        return await asyncio.to_thread(self.registry.get, execution_id)

    async def cancel(self, execution_id: str) -> ExecutionSnapshot:
        snapshot = await self.get(execution_id)
        if snapshot.terminal or snapshot.state == "cancel_requested":
            return snapshot
        if snapshot.state not in {"prepared", "queued", "starting", "running"}:
            raise RuntimeError(f"Execution cannot be cancelled while {snapshot.state}")
        adapter = self._adapters.get(execution_id)
        if adapter is None:
            adapter = await asyncio.to_thread(self._reconnector, snapshot)
            reconnect_task = self._poll_tasks.pop(execution_id, None)
            if reconnect_task is not None:
                reconnect_task.cancel()
                await asyncio.gather(reconnect_task, return_exceptions=True)
            await self.attach(execution_id, adapter, publish_initial=False)
        await asyncio.to_thread(adapter.cancel)
        return await self._refresh_once(execution_id)

    async def retry(
        self,
        execution_id: str,
        *,
        target_id: str | None = None,
    ) -> ExecutionSnapshot:
        if self._retry_factory is None:
            raise RuntimeError("Retry is not configured")
        source = await self.get(execution_id)
        if not source.terminal:
            raise RuntimeError("Only terminal executions can be retried")
        snapshot, adapter = await asyncio.to_thread(self._retry_factory, source, target_id)
        return await self.register(snapshot, adapter)

    async def download_result(self, execution_id: str, destination: Path) -> Path:
        snapshot = await self.get(execution_id)
        if snapshot.state != "succeeded":
            raise RuntimeError("Execution result is not available")
        adapter = self._adapters.get(execution_id)
        if adapter is None:
            adapter = await asyncio.to_thread(self._reconnector, snapshot)
        return await asyncio.to_thread(adapter.download_result, destination)

    async def logs(self, execution_id: str) -> str:
        snapshot = await self.get(execution_id)
        adapter = self._adapters.get(execution_id)
        if adapter is None:
            adapter = await asyncio.to_thread(self._reconnector, snapshot)
        return await asyncio.to_thread(adapter.logs)

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
                }
                if state in self.TERMINAL and reduced.finished_at is None:
                    update["finished_at"] = utc_now()
                reduced = reduced.model_copy(update=update)
            except Exception as exc:
                return await self._record_observation_failure(snapshot, exc)
            if (
                reduced.state == snapshot.state
                and reduced.jobs == snapshot.jobs
                and reduced.progress_cursor == snapshot.progress_cursor
                and snapshot.observation.reachable
            ):
                return snapshot
            persisted = await asyncio.to_thread(
                self.registry.save,
                reduced,
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
        if not snapshot.observation.reachable and snapshot.observation.error == str(exc):
            return snapshot
        failed = snapshot.model_copy(
            update={
                "observation": ObservationSnapshot(reachable=False, error=str(exc)),
            }
        )
        persisted = await asyncio.to_thread(
            self.registry.save,
            failed,
            expected_revision=snapshot.revision,
        )
        await self._publisher.publish_execution_snapshot(persisted, initial=False)
        return persisted


def open_public_submitted_run(snapshot: ExecutionSnapshot, profile_resolver: Any) -> SubmittedRunAdapter:
    """Reconnect using only public BioImageFlow handles and sanitized profile values."""

    import bioimageflow

    remote_workflow_run = getattr(bioimageflow, "RemoteWorkflowRun")
    workflow_run = getattr(bioimageflow, "WorkflowRun")

    reconnect = snapshot.reconnect or {}
    storage_path = reconnect.get("storage_path")
    run_id = reconnect.get("run_id")
    if not isinstance(storage_path, str) or not isinstance(run_id, str):
        raise ValueError("Submitted execution reconnect metadata is incomplete")
    if snapshot.backend == "submitted_remote":
        profile_payload = snapshot.target_snapshot.get("profile")
        if isinstance(profile_payload, dict):
            from bioimageflow_server.models.execution_profiles import (
                DistributedExecutionProfile,
            )

            record = DistributedExecutionProfile.model_validate(profile_payload)
            if record.id != snapshot.profile_id or record.revision != snapshot.profile_revision:
                raise ValueError("Retained execution profile binding is inconsistent")
            if record.transport is None:
                raise ValueError("Retained remote execution transport is missing")
            transport = record.transport.to_library()
        else:
            # Compatibility for snapshots retained before profile snapshots
            # were embedded in each accepted run.
            profile = profile_resolver.resolve_revision(
                snapshot.profile_id,
                snapshot.profile_revision,
                snapshot.workflow_id,
            )
            transport = profile.transport
        return SubmittedRunAdapter(
            remote_workflow_run.open(transport, storage_path, run_id)
        )
    if snapshot.backend == "submitted_local":
        return SubmittedRunAdapter(workflow_run.open(storage_path, run_id))
    raise ValueError("Attached executions cannot be reconnected after process restart")
