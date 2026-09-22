"""Execution service.

Contains the :class:`ExecutionEventBus` protocol, a :class:`NullEventBus`
no-op implementation, the :class:`ExecutionManager` that drives
``bioimageflow.Workflow.compute`` on a background thread, and the
:func:`clear_node_cache` helper used by the ``/execution/clear``
endpoint.

The manager serializes execution preparation and graph mutations through
one async boundary. An accepted run publishes a distinct ``starting``
status while compilation is offloaded, then changes to ``running`` only
after the compiled snapshot passes its final authority check.
"""

from __future__ import annotations

import asyncio
import ast
import logging
import re
import threading
import time
import traceback
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import uuid4

from bioimageflow_server.models.execution import (
    ExecutionContext,
    ExecutionResult,
    ExecutionStatus,
    ProgressInfo,
)
from bioimageflow_server.models.execution_runtime import ResultExportSnapshot
from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.validation import GraphValidationError, NodeStatus
from bioimageflow_server.services.graph_validator import GraphValidationService
from bioimageflow_server.services.log_context import bind_execution_log_context
from bioimageflow_server.services.tool_registry import ToolRegistryService

logger = logging.getLogger(__name__)

_KNOWN_PROGRESS_STATUSES = {
    "started",
    "row_progress",
    "row_complete",
    "completed",
    "cached",
    "failed",
    "cancelled",
}


# ---- Event bus --------------------------------------------------------------


@runtime_checkable
class ExecutionEventBus(Protocol):
    """Sync interface published by the execution manager.

    Implementations must be safe to call from the background thread
    running ``Workflow.compute``. The WebSocket layer will implement
    this by scheduling async broadcasts via
    ``asyncio.run_coroutine_threadsafe``.
    """

    def publish_progress(
        self,
        node_id: str,
        status: str,
        row: int,
        total_rows: int,
        timestamp: float,
        result_key: str | None = None,
        record_id: str | None = None,
        *,
        context: ExecutionContext,
    ) -> None: ...

    def publish_node_state(
        self,
        node_id: str,
        status: str,
        cached: bool,
        error: str | None = None,
        traceback: str | None = None,
        result_key: str | None = None,
        record_id: str | None = None,
        *,
        context: ExecutionContext,
    ) -> None: ...

    def publish_execution_complete(
        self,
        success: bool,
        errors: list,
        node_statuses: dict,
        *,
        context: ExecutionContext,
    ) -> None: ...

    def publish_log(
        self,
        level: str,
        message: str,
        node_id: str | None,
        timestamp: float,
        *,
        context: ExecutionContext | None = None,
    ) -> None: ...

    def publish_environment_status(self, env_name: str, status: str) -> None: ...


class NullEventBus:
    """No-op event bus used when no transport is attached."""

    def publish_progress(
        self,
        node_id: str,
        status: str,
        row: int,
        total_rows: int,
        timestamp: float,
        result_key: str | None = None,
        record_id: str | None = None,
        *,
        context: ExecutionContext,
    ) -> None:
        return None

    def publish_node_state(
        self,
        node_id: str,
        status: str,
        cached: bool,
        error: str | None = None,
        traceback: str | None = None,
        result_key: str | None = None,
        record_id: str | None = None,
        *,
        context: ExecutionContext,
    ) -> None:
        return None

    def publish_execution_complete(
        self,
        success: bool,
        errors: list,
        node_statuses: dict,
        *,
        context: ExecutionContext,
    ) -> None:
        return None

    def publish_log(
        self,
        level: str,
        message: str,
        node_id: str | None,
        timestamp: float,
        *,
        context: ExecutionContext | None = None,
    ) -> None:
        return None

    def publish_environment_status(self, env_name: str, status: str) -> None:
        return None


# ---- Custom exceptions ------------------------------------------------------


class ExecutionConflictError(RuntimeError):
    """Raised when ``start()`` is called while an execution is already running."""


class ExecutionRetryError(RuntimeError):
    """Raised when a retry does not address the latest failed execution."""


class WorkflowBuildError(RuntimeError):
    """Raised when ``graph_builder.build_workflow`` fails structurally.

    Carries the list of :class:`GraphValidationError` surfaced by the
    builder. The router maps this to HTTP 422.
    """

    def __init__(self, errors: list[GraphValidationError]) -> None:
        super().__init__(f"Failed to build workflow: {len(errors)} error(s)")
        self.errors = errors


def _selected_root_scope(graph: GraphState, nodes: list[str]) -> set[str]:
    """Return requested root nodes and their transitive graph predecessors."""

    root_ids = {node.id for node in graph.nodes}
    unknown = sorted(set(nodes) - root_ids)
    if not nodes or unknown:
        detail = (
            "Run Selected requires at least one requested execution target"
            if not nodes
            else f"Requested execution targets do not exist in the graph: {unknown}"
        )
        raise WorkflowBuildError(
            [
                GraphValidationError(
                    type="parameter_invalid",
                    detail=detail,
                    node=unknown[0] if len(unknown) == 1 else None,
                )
            ]
        )

    predecessors: dict[str, set[str]] = {node_id: set() for node_id in root_ids}
    for edge in graph.edges:
        if edge.source_node in root_ids and edge.target_node in root_ids:
            predecessors[edge.target_node].add(edge.source_node)

    scope = set(nodes)
    pending = list(nodes)
    while pending:
        for predecessor in predecessors[pending.pop()]:
            if predecessor not in scope:
                scope.add(predecessor)
                pending.append(predecessor)
    return scope


def _selected_validation_errors(
    graph: GraphState,
    scope: set[str],
    errors: list[GraphValidationError],
) -> list[GraphValidationError]:
    """Keep errors that are not proven to belong to an unrelated root branch."""

    root_ids = {node.id for node in graph.nodes}
    selected_errors: list[GraphValidationError] = []
    for error in errors:
        if error.node is None:
            selected_errors.append(error)
            continue
        owner = error.node.split("/", 1)[0]
        if owner not in root_ids or owner in scope:
            selected_errors.append(error)
    return selected_errors


# ---- ExecutionManager -------------------------------------------------------


class ExecutionManager:
    """Orchestrates a single graph execution on a background thread."""

    def __init__(
        self,
        event_bus: ExecutionEventBus,
        tool_registry: ToolRegistryService,
        settings: Settings,
        storage_path: Path | None = None,
        settings_provider: Callable[[], Settings] | None = None,
        environment_manager_provider: Callable[[], Any | None] | None = None,
        environment_replacement_authorizer: Callable[[Any], bool] | None = None,
        retained_execution_started: Callable[[ExecutionContext], Awaitable[None]] | None = None,
        managed_result_root: Path | Callable[[str], Path] | None = None,
    ) -> None:
        self.event_bus = event_bus
        self.tool_registry = tool_registry
        self.settings = settings
        # When provided, ``settings_provider`` is consulted on each ``start()``
        # so live SettingsStore PATCHes (e.g. flipping ``dev_mode``) take
        # effect on the next run without restarting the app.
        self._settings_provider = settings_provider
        self._environment_manager_provider = environment_manager_provider
        self._environment_replacement_authorizer = environment_replacement_authorizer
        self._retained_execution_started = retained_execution_started
        self._managed_result_root = managed_result_root
        self.storage_path = storage_path

        self.state: Literal["running", "idle"] = "idle"
        self.progress: ProgressInfo | None = None
        self.last_result: ExecutionResult | None = None
        self.context: ExecutionContext | None = None
        self._node_statuses: dict[str, NodeStatus] = {}
        self._workflow: Any | None = None
        self._run_task: asyncio.Task | None = None
        self._preparation_lock = asyncio.Lock()
        self._starting = False
        self._pending_context: ExecutionContext | None = None
        self._idle_operation_active = False
        # Track the last node_id that emitted a "started" event, used to
        # mark the "currently running" node as unexecuted on cancel if
        # no explicit "cancelled" progress event was received.
        self._current_node_id: str | None = None
        self._retained_progress_events: list[dict[str, Any]] = []
        self._retained_progress_sequence = 0
        self._retained_progress_lock = threading.Lock()
        self._retained_progress_by_execution: dict[str, list[dict[str, Any]]] = {}
        self._retained_statuses: dict[str, str] = {}
        self._workflow_run_contexts: dict[str, Any] = {}
        self._retained_result_exports: dict[str, ResultExportSnapshot] = {}

    # ---- Public properties -------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self.state == "running" or self._starting or self._idle_operation_active

    @property
    def is_execution_active(self) -> bool:
        """Whether an execution has been admitted, excluding mutation reservations."""

        return self.state == "running" or self._starting

    def get_status(self) -> ExecutionStatus:
        if self._starting:
            assert self._pending_context is not None
            return ExecutionStatus(
                state="starting",
                last_result=None,
                progress=None,
                node_statuses={},
                **self._pending_context.model_dump(),
            )
        context = self.context
        context_fields = context.model_dump() if context is not None else {}
        return ExecutionStatus(
            state=self.state,
            last_result=self.last_result,
            progress=self.progress,
            node_statuses=dict(self._node_statuses),
            **context_fields,
        )

    def apply_cache_clear_statuses(self, workflow_id: str, statuses: dict[str, NodeStatus]) -> None:
        """Keep the live status snapshot current without rewriting run history."""

        if self.context is not None and self.context.workflow_id == workflow_id:
            self._node_statuses.update(statuses)

    # ---- Lifecycle ---------------------------------------------------------

    async def start(
        self,
        graph: GraphState,
        nodes: list[str] | None = None,
        storage_path: Path | None = None,
        *,
        workflow_id: str,
        draft_revision: int | None = None,
        ensure_context_current: Callable[[], Awaitable[None]] | None = None,
        reserved_context: ExecutionContext | None = None,
    ) -> ExecutionContext:
        """Kick off a background execution.

        Raises:
            ExecutionConflictError: if an execution is already running.
            WorkflowBuildError: if the graph cannot be built into a
                :class:`bioimageflow.Workflow`.
        """
        graph = graph.model_copy(deep=True)
        nodes = list(nodes) if nodes is not None else None
        if reserved_context is None:
            async with self.reserve_start(
                workflow_id,
                draft_revision,
                requested_nodes=nodes,
            ) as context:
                return await self._start_reserved(
                    context,
                    graph,
                    nodes,
                    storage_path,
                    ensure_context_current,
                )
        if (
            not self._starting
            or self._pending_context != reserved_context
            or reserved_context.workflow_id != workflow_id
            or reserved_context.draft_revision != draft_revision
        ):
            raise RuntimeError("Execution start reservation is not current")
        return await self._start_reserved(
            reserved_context,
            graph,
            nodes,
            storage_path,
            ensure_context_current,
        )

    @asynccontextmanager
    async def reserve_start(
        self,
        workflow_id: str,
        draft_revision: int | None,
        *,
        mode: Literal["normal", "retry", "invalidate_failed", "recompute"] = "normal",
        requested_nodes: list[str] | None = None,
        retry_of_execution_id: str | None = None,
    ) -> AsyncIterator[ExecutionContext]:
        """Reserve the engine before any offloaded Run authority preparation."""

        if self.is_running:
            raise ExecutionConflictError(
                "An execution is already running; stop it before starting a new one"
            )
        async with self._preparation_lock:
            if self.is_running:
                raise ExecutionConflictError(
                    "An execution is already running; stop it before starting a new one"
                )
            effective_nodes = self.resolve_requested_nodes(
                mode=mode,
                workflow_id=workflow_id,
                requested_nodes=requested_nodes,
                retry_of_execution_id=retry_of_execution_id,
            )
            context = ExecutionContext(
                execution_id=f"run_{uuid4().hex}",
                workflow_id=workflow_id,
                draft_revision=draft_revision,
                mode=mode,
                requested_nodes=effective_nodes,
                retry_of_execution_id=retry_of_execution_id,
            )
            self._pending_context = context
            self._starting = True
            try:
                yield context
            finally:
                self._starting = False
                self._pending_context = None

    def resolve_requested_nodes(
        self,
        *,
        mode: Literal["normal", "retry", "invalidate_failed", "recompute"],
        workflow_id: str,
        requested_nodes: list[str] | None,
        retry_of_execution_id: str | None,
    ) -> list[str] | None:
        """Validate intent and recover the original target set for retries."""
        if mode in {"normal", "recompute"}:
            return list(requested_nodes) if requested_nodes is not None else None
        previous = self.context
        if (
            previous is None
            or self.last_result is None
            or self.last_result.success
            or retry_of_execution_id != previous.execution_id
            or workflow_id != previous.workflow_id
        ):
            raise ExecutionRetryError(
                "Retry must reference the latest failed execution for this workflow"
            )
        return list(previous.requested_nodes) if previous.requested_nodes is not None else None

    async def _start_reserved(
        self,
        context: ExecutionContext,
        graph: GraphState,
        nodes: list[str] | None,
        storage_path: Path | None,
        ensure_context_current: Callable[[], Awaitable[None]] | None,
    ) -> ExecutionContext:
        live_settings = self._settings_provider() if self._settings_provider else self.settings
        run_storage_path = storage_path if storage_path is not None else self.storage_path
        build_graph = graph
        on_progress = self._make_progress_callback(context)
        try:
            validation_output = await GraphValidationService(
                self.tool_registry
            ).validate_with_compilation_async(
                build_graph,
                storage_path=run_storage_path,
                on_progress=on_progress,
                dev_mode=bool(live_settings.dev_mode),
                settings=live_settings,
            )
        except Exception as exc:
            if ensure_context_current is not None:
                await ensure_context_current()
            raise WorkflowBuildError(
                [
                    GraphValidationError(
                        type="parameter_invalid",
                        detail=f"Workflow build failed: {exc}",
                    )
                ]
            ) from exc

        if ensure_context_current is not None:
            await ensure_context_current()

        selected_scope = _selected_root_scope(build_graph, nodes) if nodes is not None else None
        validation_errors = validation_output.validation.errors
        if selected_scope is not None:
            validation_errors = _selected_validation_errors(
                build_graph,
                selected_scope,
                validation_errors,
            )
        if validation_errors:
            raise WorkflowBuildError(validation_errors)

        workflow = validation_output.compilation.workflow
        if workflow is None:
            raise WorkflowBuildError(
                [
                    GraphValidationError(
                        type="parameter_invalid",
                        detail="Workflow compilation did not produce an executable workflow",
                    )
                ]
            )
        node_map = dict(workflow.nodes)
        if nodes is not None:
            unresolved = sorted({node_id for node_id in nodes if node_id not in node_map})
            if unresolved:
                raise WorkflowBuildError(
                    [
                        GraphValidationError(
                            type="parameter_invalid",
                            detail=f"Requested execution targets could not be resolved: {unresolved}",
                            node=unresolved[0] if len(unresolved) == 1 else None,
                        )
                    ]
                )

        self.context = context
        self.state = "running"
        self.progress = None
        self.last_result = None
        self._node_statuses = {}
        self._current_node_id = None
        with self._retained_progress_lock:
            self._retained_progress_events = []
            self._retained_progress_sequence = 0
            self._retained_progress_by_execution[context.execution_id] = (
                self._retained_progress_events
            )
        self._retained_statuses[context.execution_id] = "running"
        for node in build_graph.nodes:
            if not node.enabled:
                self._node_statuses[node.id] = NodeStatus(
                    node_id=node.id,
                    status="disabled",
                    cached=False,
                )

        # The platform owns the disposable latest-output projection.
        workflow.output_view = None
        self._workflow = workflow
        targets: tuple[Any, ...] = ()
        if nodes is not None:
            targets = tuple(node_map[nid] for nid in nodes)

        dev_mode = bool(live_settings.dev_mode)
        import bioimageflow

        workflow_run_context = bioimageflow.WorkflowExecutionContext(run_id=context.execution_id)
        self._workflow_run_contexts[context.execution_id] = workflow_run_context
        self._retained_result_exports[context.execution_id] = ResultExportSnapshot()
        target_label = ", ".join(nodes) if nodes else "workflow terminals"
        logger.info("Starting workflow execution for %s", target_label)
        self.event_bus.publish_log(
            "INFO",
            f"Execution started for {target_label}",
            None,
            time.time(),
            context=context,
        )

        def _run_sync() -> Any:
            with bind_execution_log_context(context):
                engine = self._create_execution_engine(workflow)
                self._attach_environment_status_hook(engine)
                try:
                    value = workflow.compute(
                        *targets,
                        dev_mode=dev_mode,
                        engine=engine,
                        run_context=workflow_run_context,
                    )
                finally:
                    self._materialize_latest_outputs(
                        workflow,
                        run_storage_path,
                        context,
                    )
                self._export_managed_result(context, value)
                return value

        loop = asyncio.get_running_loop()
        task = loop.create_task(asyncio.to_thread(_run_sync))
        self._run_task = task
        task.add_done_callback(
            lambda completed, run_context=context: self._on_run_done(
                completed,
                run_context,
            )
        )
        if self._retained_execution_started is not None:
            try:
                await self._retained_execution_started(context)
            except Exception:
                logger.exception(
                    "Could not retain accepted local execution %s", context.execution_id
                )
        return context

    def _managed_result_destination(self, execution_id: str) -> Path:
        root = self._managed_result_root
        if root is None:
            raise RuntimeError("Managed result storage is not configured")
        return root(execution_id) if callable(root) else root / execution_id

    def _export_managed_result(self, context: ExecutionContext, value: Any) -> None:
        if self._managed_result_root is None:
            self._retained_result_exports[context.execution_id] = ResultExportSnapshot(
                state="unavailable",
                error_code="workflow-result-export-error",
                detail="Managed result storage is not configured.",
            )
            self._workflow_run_contexts.pop(context.execution_id, None)
            return
        destination = self._managed_result_destination(context.execution_id)
        run_context = self._workflow_run_contexts[context.execution_id]
        try:
            run_context.export_result(value, destination=destination)
            from bioimageflow_server.services.execution_runtime import (
                _archive_bundle,
                _archive_digest,
            )

            archive = _archive_bundle(destination)
        except Exception as exc:
            code = getattr(exc, "code", "workflow-result-export-error")
            self._retained_result_exports[context.execution_id] = ResultExportSnapshot(
                state="unavailable",
                error_code=code if isinstance(code, str) else "workflow-result-export-error",
                detail=str(exc),
            )
        else:
            self._retained_result_exports[context.execution_id] = ResultExportSnapshot(
                state="available",
                archive_digest=_archive_digest(archive),
            )
        finally:
            self._workflow_run_contexts.pop(context.execution_id, None)
        try:
            from bioimageflow_server.services.execution_runtime import (
                _persist_attached_completion,
            )

            _persist_attached_completion(
                destination,
                state="succeeded",
                result_export=self._retained_result_exports[context.execution_id],
            )
        except Exception as exc:
            current = self._retained_result_exports[context.execution_id]
            self._retained_result_exports[context.execution_id] = ResultExportSnapshot(
                state="unavailable",
                error_code="workflow-result-retention-error",
                detail=f"Could not retain attached completion state: {exc}",
                archive_digest=current.archive_digest,
            )

    def retained_result_export(self, context: ExecutionContext) -> ResultExportSnapshot:
        return self._retained_result_exports.get(
            context.execution_id,
            ResultExportSnapshot(
                state="unavailable",
                error_code="workflow-run-result-unavailable",
                detail="The retained attached result is unavailable.",
            ),
        )

    def export_retained_result(self, context: ExecutionContext, destination: Path) -> Path:
        export = self.retained_result_export(context)
        if export.state != "available":
            raise RuntimeError(export.detail or "The retained attached result is unavailable.")
        from bioimageflow_server.services.execution_runtime import _verified_archive

        return _verified_archive(destination, export)

    def retained_progress(self, *, after_sequence: int = 0) -> list[dict[str, Any]]:
        """Return the engine-neutral public progress retained for the current run."""
        with self._retained_progress_lock:
            return [
                event
                for event in self._retained_progress_events
                if event["sequence"] > after_sequence
            ]

    def retained_progress_for(
        self,
        context: ExecutionContext,
        *,
        after_sequence: int = 0,
    ) -> list[dict[str, Any]]:
        with self._retained_progress_lock:
            return [
                event
                for event in self._retained_progress_by_execution.get(
                    context.execution_id,
                    [],
                )
                if event["sequence"] > after_sequence
            ]

    def retained_status(self, context: ExecutionContext) -> str:
        return self._retained_statuses.get(context.execution_id, "lost")

    def _materialize_latest_outputs(
        self,
        workflow: Any,
        storage_path: Path | None,
        context: ExecutionContext,
    ) -> None:
        """Best-effort human output publication that never changes run success."""
        if storage_path is None:
            return
        from bioimageflow_server.services.output_views import materialize_latest_outputs

        try:
            resolved = materialize_latest_outputs(
                workflow,
                storage_path=storage_path,
            )
            if resolved.warning:
                logger.warning(resolved.warning)
                self.event_bus.publish_log(
                    "WARNING",
                    resolved.warning,
                    None,
                    time.time(),
                    context=context,
                )
        except Exception as exc:
            message = (
                "Workflow computation finished, but latest outputs could not be "
                f"materialized: {exc}"
            )
            logger.warning(message, exc_info=True)
            self.event_bus.publish_log(
                "WARNING",
                message,
                None,
                time.time(),
                context=context,
            )

    async def stop(self) -> None:
        await self._stop_expected(None)

    async def stop_retained(self, context: ExecutionContext) -> None:
        """Stop only when ``context`` is still the manager's current run."""

        await self._stop_expected(context)

    async def _stop_expected(self, expected: ExecutionContext | None) -> None:
        async with self._preparation_lock:
            if expected is not None and self.context != expected:
                return
            if self._workflow is None or self.state != "running":
                return
            self.event_bus.publish_log(
                "INFO",
                "Execution stop requested",
                None,
                time.time(),
                context=self.context,
            )
            try:
                self._workflow.cancel()
            except Exception:  # pragma: no cover — defensive
                logger.exception("Workflow.cancel() raised")

    @asynccontextmanager
    async def exclusive_idle_mutation(self) -> AsyncIterator[None]:
        """Lease the idle engine across a complete graph mutation."""

        if self.is_execution_active:
            raise ExecutionConflictError(
                "An execution is already running; stop it before editing the workflow"
            )
        async with self._preparation_lock:
            if self.is_execution_active:
                raise ExecutionConflictError(
                    "An execution is already running; stop it before editing the workflow"
                )
            self._idle_operation_active = True
            try:
                yield
            finally:
                self._idle_operation_active = False

    # ---- Internals ---------------------------------------------------------

    def _make_progress_callback(self, context: ExecutionContext) -> Callable[[Any], None]:
        """Return the ``on_progress`` callback for this run.

        Closes over ``self`` so it can update the manager's state from
        inside the background thread. Every known ``ProgressEvent.status``
        is mapped to a bus call and/or an entry in ``_node_statuses``.
        Unknown statuses are logged and ignored so a library upgrade
        doesn't turn into a spurious execution failure.
        """

        def _on_progress(event: Any) -> None:
            if self.state != "running" or self.context != context:
                logger.warning(
                    "Dropping progress event outside its active execution %s",
                    context.execution_id,
                )
                return
            node_id = getattr(event, "node_name", None)
            status = getattr(event, "status", None)
            if node_id is None or status is None:
                logger.warning("Dropping malformed progress event: %r", event)
                return
            if status not in _KNOWN_PROGRESS_STATUSES:
                logger.warning(
                    "Unknown progress status %r for node %s; ignoring",
                    status,
                    node_id,
                )
                return

            from bioimageflow_server.services.execution_progress import (
                progress_event_from_attached,
            )

            with self._retained_progress_lock:
                converted = progress_event_from_attached(
                    event,
                    self._retained_progress_sequence + 1,
                )
                self._retained_progress_events.extend(converted)
                self._retained_progress_sequence = converted[-1]["sequence"]

            timestamp = float(getattr(event, "timestamp", 0.0) or 0.0)
            result_key = getattr(event, "result_key", None)
            record_id = getattr(event, "record_id", None)

            if status == "started":
                self._current_node_id = node_id
                self._node_statuses[node_id] = NodeStatus(
                    node_id=node_id,
                    status="running",
                    cached=False,
                    result_key=result_key,
                    record_id=record_id,
                )
                self.event_bus.publish_node_state(
                    node_id,
                    "running",
                    False,
                    None,
                    None,
                    result_key,
                    record_id,
                    context=context,
                )
                self.event_bus.publish_log(
                    "INFO",
                    f"Node {node_id} started",
                    node_id,
                    timestamp,
                    context=context,
                )
                return

            if status == "row_progress":
                current = int(getattr(event, "current", 0) or 0)
                maximum = int(getattr(event, "maximum", 0) or 0)
                self.progress = ProgressInfo(
                    node_id=node_id,
                    row=current,
                    total_rows=maximum,
                    result_key=result_key,
                    record_id=record_id,
                )
                self.event_bus.publish_progress(
                    node_id,
                    "row_progress",
                    current,
                    maximum,
                    timestamp,
                    result_key,
                    record_id,
                    context=context,
                )
                self.event_bus.publish_log(
                    "DEBUG",
                    f"Node {node_id} row progress {current}/{maximum}",
                    node_id,
                    timestamp,
                    context=context,
                )
                return

            if status == "row_complete":
                row = int(getattr(event, "row", 0) or 0)
                total_rows = int(getattr(event, "total_rows", 0) or 0)
                self.progress = ProgressInfo(
                    node_id=node_id,
                    row=row,
                    total_rows=total_rows,
                    result_key=result_key,
                    record_id=record_id,
                )
                self.event_bus.publish_progress(
                    node_id,
                    "row_complete",
                    row,
                    total_rows,
                    timestamp,
                    result_key,
                    record_id,
                    context=context,
                )
                self.event_bus.publish_log(
                    "INFO",
                    f"Node {node_id} completed row {row}/{total_rows}",
                    node_id,
                    timestamp,
                    context=context,
                )
                return

            if status == "completed":
                self._node_statuses[node_id] = NodeStatus(
                    node_id=node_id,
                    status="executed",
                    cached=False,
                    result_key=result_key,
                    record_id=record_id,
                )
                self.event_bus.publish_node_state(
                    node_id,
                    "executed",
                    False,
                    None,
                    None,
                    result_key,
                    record_id,
                    context=context,
                )
                self.event_bus.publish_log(
                    "INFO",
                    f"Node {node_id} completed",
                    node_id,
                    timestamp,
                    context=context,
                )
                return

            if status == "cached":
                self._node_statuses[node_id] = NodeStatus(
                    node_id=node_id,
                    status="executed",
                    cached=True,
                    result_key=result_key,
                    record_id=record_id,
                )
                self.event_bus.publish_node_state(
                    node_id,
                    "executed",
                    True,
                    None,
                    None,
                    result_key,
                    record_id,
                    context=context,
                )
                self.event_bus.publish_log(
                    "INFO",
                    f"Node {node_id} used cached result",
                    node_id,
                    timestamp,
                    context=context,
                )
                return

            if status == "failed":
                message = getattr(event, "message", None)
                tb = getattr(event, "traceback", None)
                self._node_statuses[node_id] = NodeStatus(
                    node_id=node_id,
                    status="failed",
                    cached=False,
                    error=message,
                    traceback=tb,
                    result_key=result_key,
                    record_id=record_id,
                )
                self.event_bus.publish_node_state(
                    node_id,
                    "failed",
                    False,
                    message,
                    tb,
                    result_key,
                    record_id,
                    context=context,
                )
                # Wetlands can announce terminal task failure before the
                # worker exception payload is available. Keep the immediate
                # failed state, but let ``_on_run_done`` publish the single
                # enriched error log instead of emitting a generic duplicate.
                if message or tb:
                    self.event_bus.publish_log(
                        "ERROR",
                        _format_node_failure_message(node_id, message, tb),
                        node_id,
                        timestamp or time.time(),
                        context=context,
                    )
                return

            if status == "cancelled":
                self._node_statuses[node_id] = NodeStatus(
                    node_id=node_id,
                    status="unexecuted",
                    cached=False,
                    result_key=result_key,
                    record_id=record_id,
                )
                self.event_bus.publish_node_state(
                    node_id,
                    "unexecuted",
                    False,
                    None,
                    None,
                    result_key,
                    record_id,
                    context=context,
                )
                return

        return _on_progress

    def _create_execution_engine(self, workflow: Any) -> Any:
        """Create the engine before execution so its environment lifecycle is observable."""
        if (
            workflow.engine_type == "wetlands"
            and self._environment_manager_provider is not None
        ):
            shared_manager = self._environment_manager_provider()
            if shared_manager is not None:
                return workflow.create_engine(
                    resource_lifetime="external",
                    env_manager=shared_manager,
                )
        return workflow.create_engine()

    def _attach_environment_status_hook(self, engine: Any) -> None:
        """Publish Wetlands environment lifecycle changes during execution.

        The library owns environment startup inside ``WetlandsEnvManager``.
        Hooking the execution engine's manager keeps the platform UI in sync
        for automatic starts and shutdowns triggered by ``workflow.compute()``.
        """
        manager = engine.environment_manager
        get_or_create = getattr(manager, "get_or_create", None)
        if manager is None or not callable(get_or_create):
            return
        if getattr(manager, "_bioimageflow_platform_env_status_hook_owner", None) is self:
            return

        original_get_or_create = getattr(
            manager,
            "_bioimageflow_platform_original_get_or_create",
            get_or_create,
        )
        setattr(
            manager,
            "_bioimageflow_platform_original_get_or_create",
            original_get_or_create,
        )

        def _get_or_create_with_status(env_spec: Any, *args: Any, **kwargs: Any) -> Any:
            # The shared manager outlives individual runs, so resolve the context
            # here instead of retaining the run that first installed this hook.
            active_context = self.context if self.state == "running" else None
            env_name = getattr(env_spec, "name", None)
            node_id = self._current_node_id if active_context is not None else None
            caller_preparation = kwargs.get("on_preparation")
            caller_provision_event = kwargs.get("on_provision_event")

            def _on_preparation(preparation: Any) -> None:
                action = getattr(preparation, "action", None)
                if isinstance(env_name, str) and env_name:
                    status = "updating" if action == "updating" else "creating"
                    if action == "reusing":
                        status = "running"
                    self._publish_environment_status(env_name, status)
                if active_context is not None and node_id is not None:
                    phase = {
                        "updating": f"Updating execution environment {env_name}",
                        "creating": f"Creating execution environment {env_name}",
                        "starting": f"Starting execution environment {env_name}",
                    }.get(action)
                    if phase is not None:
                        self._publish_environment_phase(active_context, node_id, phase)
                if callable(caller_preparation):
                    caller_preparation(preparation)

            def _on_provision_event(event: Any) -> None:
                if active_context is not None:
                    self._on_environment_event(event, active_context, node_id, env_name)
                if callable(caller_provision_event):
                    caller_provision_event(event)

            try:
                kwargs["on_preparation"] = _on_preparation
                kwargs["on_provision_event"] = _on_provision_event
                if (
                    self._environment_replacement_authorizer is not None
                    and self._environment_replacement_authorizer(env_spec)
                ):
                    inspect_environment = getattr(manager, "inspect_environment", None)
                    if callable(inspect_environment):
                        recipe_state = inspect_environment(env_spec)
                        if getattr(recipe_state, "value", None) == "stale":
                            kwargs["replace_existing"] = True
                env = original_get_or_create(env_spec, *args, **kwargs)
            except Exception:
                if isinstance(env_name, str) and env_name:
                    self._publish_environment_status(env_name, "failed")
                raise
            if (
                active_context is not None
                and node_id is not None
                and active_context == self.context
                and self.state == "running"
            ):
                self._publish_environment_phase(active_context, node_id, "Executing tool")
            if isinstance(env_name, str) and env_name:
                self._publish_environment_status(env_name, "running")
            return env

        setattr(manager, "get_or_create", _get_or_create_with_status)
        current_shutdown_all = getattr(manager, "shutdown_all", None)
        original_shutdown_all = getattr(
            manager,
            "_bioimageflow_platform_original_shutdown_all",
            current_shutdown_all,
        )
        if callable(original_shutdown_all):
            setattr(
                manager,
                "_bioimageflow_platform_original_shutdown_all",
                original_shutdown_all,
            )

            def _shutdown_all_with_status() -> Any:
                envs = getattr(manager, "_envs", None)
                env_names = list(envs) if isinstance(envs, dict) else []
                try:
                    return original_shutdown_all()
                finally:
                    for env_name in env_names:
                        self._publish_environment_status(env_name, "stopped")

            setattr(manager, "shutdown_all", _shutdown_all_with_status)
        setattr(manager, "_bioimageflow_platform_env_status_hook_owner", self)

    def _on_environment_event(
        self, event: Any, context: ExecutionContext, node_id: str | None, env_name: str | None
    ) -> None:
        if context != self.context or self.state != "running":
            return
        kind = getattr(getattr(event, "kind", None), "value", None)
        message = getattr(event, "message", None)
        if not isinstance(message, str) or not message:
            return
        stage = getattr(event, "stage", None)
        if kind == "output":
            self.event_bus.publish_log("INFO", message, node_id, time.time(), context=context)
        elif kind in {"step", "progress", "state"}:
            self.event_bus.publish_log("INFO", message, node_id, time.time(), context=context)
            if node_id is not None and kind == "step" and stage:
                label = f"Installing {env_name}: {message}"
                self._publish_environment_phase(context, node_id, label)

    def _publish_environment_phase(
        self, context: ExecutionContext, node_id: str, message: str
    ) -> None:
        with self._retained_progress_lock:
            self._retained_progress_sequence += 1
            self._retained_progress_events.append(
                {
                    "sequence": self._retained_progress_sequence,
                    "kind": "phase",
                    "payload": {"node_name": node_id, "message": message},
                }
            )

    def _publish_environment_status(self, env_name: str, status: str) -> None:
        publish = getattr(self.event_bus, "publish_environment_status", None)
        if callable(publish):
            publish(env_name, status)

    def _on_run_done(self, task: asyncio.Task, context: ExecutionContext) -> None:
        """Called on the event loop when the background task finishes."""
        try:
            exc = task.exception()
        except asyncio.CancelledError:  # pragma: no cover — defensive
            exc = None

        success: bool
        errors: list[dict[str, Any]] = []

        if exc is None:
            success = True
        else:
            # Import inside to avoid a top-level dependency on bioimageflow
            # in modules that never execute workflows.
            from bioimageflow.engine import WorkflowCancelledError

            if isinstance(exc, WorkflowCancelledError):
                success = False
                errors.append(
                    {
                        "type": "cancelled",
                        "detail": str(exc),
                    }
                )
                logger.info("Workflow execution cancelled: %s", exc)
                # If a currently-running node never got a terminal event,
                # mark it as unexecuted.
                if (
                    self._current_node_id is not None
                    and self._node_statuses.get(self._current_node_id) is not None
                    and self._node_statuses[self._current_node_id].status == "running"
                ):
                    self._node_statuses[self._current_node_id] = NodeStatus(
                        node_id=self._current_node_id,
                        status="unexecuted",
                        cached=False,
                    )
            else:
                success = False
                local_tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                detail, tb = _format_exception_for_client(exc, local_tb)
                errors.append(
                    {
                        "type": type(exc).__name__,
                        "detail": detail,
                        "traceback": tb,
                    }
                )
                logger.error(
                    "Workflow execution failed: %s",
                    exc,
                    exc_info=(type(exc), exc, exc.__traceback__),
                )
                # Attribute the failure to the currently-running node if
                # no explicit "failed" event was seen.
                target_id = self._current_node_id
                if target_id is None:
                    target_id = _single_failed_node_without_error(self._node_statuses)
                should_publish_error_log = True
                if target_id is not None and target_id in self._node_statuses:
                    current = self._node_statuses[target_id]
                    if current.status == "running":
                        self._node_statuses[target_id] = NodeStatus(
                            node_id=target_id,
                            status="failed",
                            cached=False,
                            error=detail,
                            traceback=tb,
                        )
                        self.event_bus.publish_node_state(
                            target_id,
                            "failed",
                            False,
                            detail,
                            tb,
                            context=context,
                        )
                    elif current.status == "failed" and not current.error:
                        self._node_statuses[target_id] = NodeStatus(
                            node_id=target_id,
                            status="failed",
                            cached=False,
                            error=detail,
                            traceback=tb,
                        )
                        self.event_bus.publish_node_state(
                            target_id,
                            "failed",
                            False,
                            detail,
                            tb,
                            context=context,
                        )
                    elif current.status == "failed":
                        should_publish_error_log = False
                if should_publish_error_log:
                    self.event_bus.publish_log(
                        "ERROR",
                        _format_node_failure_message(target_id, detail, tb)
                        if target_id is not None
                        else _format_workflow_failure_message(detail, tb),
                        target_id,
                        time.time(),
                        context=context,
                    )

        self.last_result = ExecutionResult(
            success=success,
            errors=errors,
            node_statuses=dict(self._node_statuses),
        )
        terminal_status = (
            "succeeded"
            if success
            else "cancelled"
            if any(error.get("type") == "cancelled" for error in errors)
            else "failed"
        )
        if not success:
            result_export = ResultExportSnapshot(
                state="unavailable",
                error_code="workflow-run-result-unavailable",
                detail=f"The attached execution {terminal_status} before producing a result.",
            )
            self._retained_result_exports[context.execution_id] = result_export
            self._workflow_run_contexts.pop(context.execution_id, None)
            if self._managed_result_root is not None:
                try:
                    from bioimageflow_server.services.execution_runtime import (
                        _persist_attached_completion,
                    )

                    _persist_attached_completion(
                        self._managed_result_destination(context.execution_id),
                        state=terminal_status,
                        result_export=result_export,
                    )
                except Exception:
                    logger.exception(
                        "Could not retain terminal attached execution %s",
                        context.execution_id,
                    )
        self._retained_statuses[context.execution_id] = terminal_status
        self.event_bus.publish_execution_complete(
            success,
            errors,
            dict(self._node_statuses),
            context=context,
        )
        if success:
            logger.info("Workflow execution completed successfully")
            self.event_bus.publish_log(
                "INFO",
                "Workflow execution completed successfully",
                None,
                time.time(),
                context=context,
            )

        self.state = "idle"
        self._workflow = None
        self._run_task = None


def _format_node_failure_message(
    node_id: str | None,
    message: str | None,
    tb: str | None,
) -> str:
    detail = message or "Execution failed"
    prefix = f"Node {node_id} failed" if node_id else "Node failed"
    if tb:
        return f"{prefix}: {detail}\n{tb}"
    return f"{prefix}: {detail}"


def _format_workflow_failure_message(message: str, tb: str | None) -> str:
    if tb:
        return f"Workflow execution failed: {message}\n{tb}"
    return f"Workflow execution failed: {message}"


def _single_failed_node_without_error(
    node_statuses: dict[str, NodeStatus],
) -> str | None:
    failed = [
        node_id
        for node_id, status in node_statuses.items()
        if status.status == "failed" and not status.error
    ]
    return failed[0] if len(failed) == 1 else None


def _format_exception_for_client(exc: BaseException, local_tb: str) -> tuple[str, str]:
    """Return a short UI detail plus formatted diagnostics for ``exc``.

    Wetlands wraps worker failures in an exception payload shaped like
    ``{"exception": "...", "traceback": [...]}``. Showing ``str(exc)`` exposes
    that Python dict in the frontend. Instead, keep the payload in the details
    text and make the row/toast message readable.
    """
    payload = _extract_remote_exception_payload(exc)
    if payload is None:
        message = str(exc).strip() or type(exc).__name__
        return _summarize_failure_message(message), local_tb

    remote_message = str(payload.get("exception") or "").strip()
    summary = _summarize_failure_message(remote_message or str(exc))
    remote_tb = _format_remote_traceback(payload.get("traceback"))

    detail_parts: list[str] = []
    if remote_message:
        detail_parts.append(f"Remote error:\n{remote_message}")
    if remote_tb:
        detail_parts.append(f"Remote traceback:\n{remote_tb.rstrip()}")
    if local_tb:
        detail_parts.append(f"Local traceback:\n{local_tb.rstrip()}")
    return summary, "\n\n".join(detail_parts)


def _extract_remote_exception_payload(exc: BaseException) -> dict[str, Any] | None:
    for arg in exc.args:
        if isinstance(arg, dict) and "exception" in arg:
            return arg
        if not isinstance(arg, str):
            continue
        text = arg.strip()
        if not (text.startswith("{") and "exception" in text):
            continue
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            continue
        if isinstance(parsed, dict) and "exception" in parsed:
            return parsed
    return None


def _format_remote_traceback(value: object) -> str:
    if isinstance(value, list):
        return "".join(str(line) for line in value)
    if isinstance(value, str):
        return value
    return ""


def _summarize_failure_message(message: str) -> str:
    command_summary = _summarize_command_failure(message)
    if command_summary is not None:
        return command_summary
    first_line = next((line.strip() for line in message.splitlines() if line.strip()), "")
    return first_line or "Execution failed"


def _summarize_command_failure(message: str) -> str | None:
    match = re.search(
        r"Command '?(\[.*?\])'? (?:died with <Signals\.([A-Z0-9_]+): \d+>|"
        r"returned non-zero exit status (\d+))",
        message,
        flags=re.DOTALL,
    )
    if match is None:
        return None
    try:
        command = ast.literal_eval(match.group(1))
    except (SyntaxError, ValueError):
        command = []
    if not isinstance(command, list) or not command:
        return None

    executable = Path(str(command[0])).name
    input_path = _option_value(command, "-i") or _option_value(command, "--input")
    input_clause = f" while processing {input_path!r}" if input_path else ""

    if match.group(2):
        detail = (
            f"External command {executable!r} crashed with signal {match.group(2)}{input_clause}."
        )
    else:
        detail = (
            f"External command {executable!r} failed with exit status "
            f"{match.group(3)}{input_clause}."
        )

    if input_path and Path(input_path).name.startswith("."):
        detail += " The selected input appears to be a hidden/system file, not image data."
    return detail


def _option_value(command: list[object], option: str) -> str | None:
    for index, value in enumerate(command):
        if value == option and index + 1 < len(command):
            return str(command[index + 1])
    return None


# ---- Cache clearer ----------------------------------------------------------


@dataclass(frozen=True)
class NodeCacheClearPlan:
    """Validated request-local plan awaiting identity-fenced invalidation."""

    workflow: Any
    valid_node_ids: tuple[str, ...]
    downstream_node_ids: frozenset[str]
    storage_path: Path | None
    graph: GraphState
    compilation: Any
    dev_mode: bool
    registry: ToolRegistryService


def prepare_node_cache_clear(
    node_ids: list[str],
    graph: GraphState,
    registry: ToolRegistryService,
    storage_path: Path | None,
    *,
    dev_mode: bool = True,
    settings: Settings | None = None,
) -> NodeCacheClearPlan:
    """Compile and validate an immutable cache-clear request.

    The returned plan has no persistence side effects and can be discarded when
    its workflow identity or storage context changes before commit.
    """
    try:
        validation_output = GraphValidationService(registry).validate_with_compilation(
            graph,
            storage_path=storage_path,
            dev_mode=dev_mode,
            settings=settings,
        )
    except Exception as exc:
        raise WorkflowBuildError(
            [
                GraphValidationError(
                    type="parameter_invalid",
                    detail=f"Workflow build failed: {exc}",
                )
            ]
        ) from exc
    requested_roots = {node_id.split("/", 1)[0] for node_id in node_ids}
    blocking_errors = [
        error
        for error in validation_output.validation.errors
        if error.type != "cache_corrupt"
        or error.node is None
        or error.node.split("/", 1)[0] not in requested_roots
    ]
    if blocking_errors:
        raise WorkflowBuildError(blocking_errors)
    workflow = validation_output.compilation.workflow

    # Filter to valid node IDs known to the workflow.
    known = set(workflow.nodes.keys())
    valid_ids = tuple(nid for nid in node_ids if nid in known)

    # Collect transitive downstream of each requested node.
    downstream: set[str] = set()
    for nid in valid_ids:
        downstream.update(workflow.downstream_of(nid))

    downstream -= set(valid_ids)

    return NodeCacheClearPlan(
        workflow=workflow,
        valid_node_ids=valid_ids,
        downstream_node_ids=frozenset(downstream),
        storage_path=storage_path,
        graph=graph,
        compilation=validation_output.compilation,
        dev_mode=dev_mode,
        registry=registry,
    )


def commit_node_cache_clear(plan: NodeCacheClearPlan) -> dict[str, NodeStatus]:
    """Apply a validated cache-clear plan inside its caller's identity fence."""

    if not plan.valid_node_ids:
        return {}

    directly_cleared = plan.workflow.invalidate(
        list(plan.valid_node_ids),
        cascade=False,
    )
    downstream = set(plan.downstream_node_ids)
    downstream -= {selection.node_name for selection in directly_cleared}
    if downstream:
        plan.workflow.invalidate(list(downstream), cascade=False)

    if plan.storage_path is not None:
        from bioimageflow_server.services.output_views import remove_latest_node_outputs

        remove_latest_node_outputs(plan.storage_path, list(plan.valid_node_ids))

    from bioimageflow_server.services.result_store import ResultStoreService

    results = (
        ResultStoreService(plan.storage_path, plan.registry)
        if plan.storage_path is not None
        else None
    )
    refreshed = GraphValidationService.validation_from_compilation(
        plan.graph,
        plan.compilation,
        dev_mode=plan.dev_mode,
        has_retained_latest=(
            None
            if results is None
            else lambda node_id: (
                results.get_latest_record_dir(
                    node_id,
                    storage_path=plan.storage_path,
                )
                is not None
            )
        ),
    )
    affected = set(plan.valid_node_ids) | downstream
    statuses = {
        node_id: status
        for node_id, status in refreshed.node_statuses.items()
        if node_id in affected
    }
    for node_id in downstream:
        status = statuses.get(node_id)
        if status is not None and status.status == "unexecuted":
            statuses[node_id] = status.model_copy(update={"status": "out_of_date"})
    return statuses


def clear_node_cache(
    node_ids: list[str],
    graph: GraphState,
    registry: ToolRegistryService,
    storage_path: Path | None,
    *,
    dev_mode: bool = True,
    settings: Settings | None = None,
) -> dict[str, NodeStatus]:
    """Compile, validate, and clear cache for synchronous callers."""

    return commit_node_cache_clear(
        prepare_node_cache_clear(
            node_ids,
            graph.model_copy(deep=True),
            registry,
            storage_path,
            dev_mode=dev_mode,
            settings=settings,
        )
    )
