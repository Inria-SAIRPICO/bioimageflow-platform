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
    ) -> None:
        self.event_bus = event_bus
        self.tool_registry = tool_registry
        self.settings = settings
        # When provided, ``settings_provider`` is consulted on each ``start()``
        # so live SettingsStore PATCHes (e.g. flipping ``dev_mode``) take
        # effect on the next run without restarting the app.
        self._settings_provider = settings_provider
        self._environment_manager_provider = environment_manager_provider
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

    # ---- Public properties -------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self.state == "running" or self._starting or self._idle_operation_active

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
                execution_id=str(uuid4()),
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
        return (
            list(previous.requested_nodes)
            if previous.requested_nodes is not None
            else None
        )

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

        if not validation_output.validation.valid:
            raise WorkflowBuildError(validation_output.validation.errors)

        self.context = context
        self.state = "running"
        self.progress = None
        self.last_result = None
        self._node_statuses = {}
        self._current_node_id = None
        for node in build_graph.nodes:
            if not node.enabled:
                self._node_statuses[node.id] = NodeStatus(
                    node_id=node.id,
                    status="disabled",
                    cached=False,
                )

        workflow = validation_output.compilation.workflow
        # The host setting is authoritative for disposable latest outputs.
        workflow.output_view = None
        self._workflow = workflow
        targets: tuple[Any, ...] = ()
        if nodes:
            node_map = dict(workflow.nodes)
            targets = tuple(node_map[nid] for nid in nodes if nid in node_map)

        dev_mode = bool(live_settings.dev_mode)
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
                use_explicit_engine = callable(getattr(workflow, "_make_engine", None))
                engine = self._make_execution_engine(workflow)
                self._attach_environment_status_hook(engine)
                try:
                    if engine is None or not use_explicit_engine:
                        return workflow.compute(*targets, dev_mode=dev_mode)
                    return workflow.compute(
                        *targets,
                        dev_mode=dev_mode,
                        engine=engine,
                    )
                finally:
                    self._materialize_latest_outputs(
                        workflow,
                        live_settings,
                        run_storage_path,
                        context,
                    )

        loop = asyncio.get_running_loop()
        task = loop.create_task(asyncio.to_thread(_run_sync))
        self._run_task = task
        task.add_done_callback(
            lambda completed, run_context=context: self._on_run_done(
                completed,
                run_context,
            )
        )
        return context

    def _materialize_latest_outputs(
        self,
        workflow: Any,
        settings: Settings,
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
                settings,
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
        async with self._preparation_lock:
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

        if self.is_running:
            raise ExecutionConflictError(
                "An execution is already running; stop it before editing the workflow"
            )
        async with self._preparation_lock:
            if self.is_running:
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

    def _make_execution_engine(self, workflow: Any) -> Any | None:
        """Create the engine before execution so its environment lifecycle is observable."""
        make_engine = getattr(workflow, "_make_engine", None)
        if not callable(make_engine):
            return getattr(workflow, "_engine", None)

        engine = make_engine()
        manager = getattr(engine, "_env_manager", None)
        if manager is None or self._environment_manager_provider is None:
            return engine

        shared_manager = self._environment_manager_provider()
        if shared_manager is not None:
            setattr(engine, "_env_manager", shared_manager)
        return engine

    def _attach_environment_status_hook(self, engine: Any) -> None:
        """Publish Wetlands environment lifecycle changes during execution.

        The library owns environment startup inside ``WetlandsEnvManager``.
        Hooking the execution engine's manager keeps the platform UI in sync
        for automatic starts and shutdowns triggered by ``workflow.compute()``.
        """
        manager = getattr(engine, "_env_manager", None)
        get_or_create = getattr(manager, "get_or_create", None)
        if manager is None or not callable(get_or_create):
            return
        if getattr(manager, "_bioimageflow_platform_env_status_hooked", False):
            return

        def _get_or_create_with_status(env_spec: Any, *args: Any, **kwargs: Any) -> Any:
            env_name = getattr(env_spec, "name", None)
            already_running = _wetlands_env_is_running(manager, env_name)
            if isinstance(env_name, str) and env_name:
                self._publish_environment_status(
                    env_name,
                    "running" if already_running else "creating",
                )
            try:
                env = get_or_create(env_spec, *args, **kwargs)
            except Exception:
                if isinstance(env_name, str) and env_name and not already_running:
                    self._publish_environment_status(env_name, "stopped")
                raise
            if isinstance(env_name, str) and env_name:
                self._publish_environment_status(env_name, "running")
            return env

        setattr(manager, "get_or_create", _get_or_create_with_status)
        shutdown_all = getattr(manager, "shutdown_all", None)
        if callable(shutdown_all):

            def _shutdown_all_with_status() -> Any:
                envs = getattr(manager, "_envs", None)
                env_names = list(envs) if isinstance(envs, dict) else []
                try:
                    return shutdown_all()
                finally:
                    for env_name in env_names:
                        self._publish_environment_status(env_name, "stopped")

            setattr(manager, "shutdown_all", _shutdown_all_with_status)
        setattr(manager, "_bioimageflow_platform_env_status_hooked", True)

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
                recovery_action = _environment_reuse_recovery_action(exc)
                if recovery_action is not None:
                    errors[-1]["recovery_action"] = recovery_action
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


def _wetlands_env_is_running(manager: Any, env_name: Any) -> bool:
    if not isinstance(env_name, str) or not env_name:
        return False
    envs = getattr(manager, "_envs", None)
    return isinstance(envs, dict) and env_name in envs


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


def _environment_reuse_recovery_action(exc: BaseException) -> dict[str, str] | None:
    if type(exc).__name__ != "EnvironmentReuseError":
        return None
    message = str(exc)
    if "it was created with a different recipe" not in message:
        return None
    match = re.search(
        r"Environment '(?P<env>[^']+)' already exists at (?P<path>.+?) "
        r"but cannot be reused: it was created with a different recipe\.\n"
        r"Existing hash: (?P<existing>\S+)\n"
        r"Requested hash: (?P<requested>\S+)",
        message,
        flags=re.DOTALL,
    )
    if match is None:
        return None
    return {
        "kind": "delete_environment",
        "env_name": match.group("env"),
        "path": match.group("path"),
        "existing_hash": match.group("existing"),
        "requested_hash": match.group("requested"),
    }


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
    if not validation_output.validation.valid:
        raise WorkflowBuildError(validation_output.validation.errors)
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
    downstream -= directly_cleared
    if downstream:
        plan.workflow.invalidate(list(downstream), cascade=False)

    result: dict[str, NodeStatus] = {}

    # Directly requested nodes → unexecuted.
    for nid in plan.valid_node_ids:
        result[nid] = NodeStatus(node_id=nid, status="unexecuted", cached=False)

    # Downstream nodes → out_of_date.
    for nid in downstream:
        result[nid] = NodeStatus(node_id=nid, status="out_of_date", cached=False)

    return result


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
