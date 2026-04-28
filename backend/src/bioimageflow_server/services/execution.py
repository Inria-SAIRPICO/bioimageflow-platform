"""Execution service.

Contains the :class:`ExecutionEventBus` protocol, a :class:`NullEventBus`
no-op implementation, the :class:`ExecutionManager` that drives
``bioimageflow.Workflow.compute`` on a background thread, and the
:func:`clear_node_cache` helper used by the ``/execution/clear``
endpoint.

The manager uses the simple two-state flag ``state in {"idle",
"running"}`` as its concurrency guard. ``start()`` is fire-and-forget,
so an ``asyncio.Lock`` held across ``async with`` would release
immediately. A synchronous check-and-set on the flag before spawning
the background task guarantees at most one execution.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from bioimageflow_server.models.execution import (
    ExecutionResult,
    ExecutionStatus,
    ProgressInfo,
)
from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.validation import GraphValidationError, NodeStatus
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.session_manager import SessionManager
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
        self, node_id: str, status: str, row: int, total_rows: int, timestamp: float
    ) -> None: ...

    def publish_node_state(
        self,
        node_id: str,
        status: str,
        cached: bool,
        error: str | None = None,
        traceback: str | None = None,
    ) -> None: ...

    def publish_execution_complete(
        self, success: bool, errors: list, node_statuses: dict
    ) -> None: ...


class NullEventBus:
    """No-op event bus used when no transport is attached."""

    def publish_progress(
        self, node_id: str, status: str, row: int, total_rows: int, timestamp: float
    ) -> None:
        return None

    def publish_node_state(
        self,
        node_id: str,
        status: str,
        cached: bool,
        error: str | None = None,
        traceback: str | None = None,
    ) -> None:
        return None

    def publish_execution_complete(
        self, success: bool, errors: list, node_statuses: dict
    ) -> None:
        return None


# ---- Custom exceptions ------------------------------------------------------


class ExecutionConflictError(RuntimeError):
    """Raised when ``start()`` is called while an execution is already running."""


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
        session_manager: SessionManager | None = None,
    ) -> None:
        self.event_bus = event_bus
        self.tool_registry = tool_registry
        self.settings = settings
        self.storage_path = storage_path
        self.session_manager = session_manager

        self.state: Literal["running", "idle"] = "idle"
        self.progress: ProgressInfo | None = None
        self.last_result: ExecutionResult | None = None
        self._node_statuses: dict[str, NodeStatus] = {}
        self._workflow: Any | None = None
        self._run_task: asyncio.Task | None = None
        # Track the last node_id that emitted a "started" event, used to
        # mark the "currently running" node as unexecuted on cancel if
        # no explicit "cancelled" progress event was received.
        self._current_node_id: str | None = None

    # ---- Public properties -------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self.state == "running"

    def get_status(self) -> ExecutionStatus:
        status = ExecutionStatus(
            state=self.state,
            last_result=self.last_result,
            progress=self.progress,
        )
        # Expose node_statuses as an attribute so mid-execution reconnects
        # can resync per-node state. The base model doesn't declare this
        # field; attach it as model_extra-compatible by using __setattr__.
        # (Pydantic v2 allows extras via model_config; here we attach on
        # the instance directly.)
        object.__setattr__(status, "node_statuses", dict(self._node_statuses))
        return status

    # ---- Lifecycle ---------------------------------------------------------

    async def start(
        self, graph: GraphState, nodes: list[str] | None = None
    ) -> None:
        """Kick off a background execution.

        Raises:
            ExecutionConflictError: if an execution is already running.
            WorkflowBuildError: if the graph cannot be built into a
                :class:`bioimageflow.Workflow`.
        """
        # Check-and-set the flag in one synchronous section (no await).
        if self.state == "running":
            raise ExecutionConflictError(
                "An execution is already running; stop it before starting a new one"
            )
        self.state = "running"

        # Clear per-run state.
        self.progress = None
        self.last_result = None
        self._node_statuses = {}
        self._current_node_id = None

        # Seed disabled nodes so they appear in the final result.
        for node in graph.nodes:
            if not node.enabled:
                self._node_statuses[node.id] = NodeStatus(
                    node_id=node.id,
                    status="disabled",
                    cached=False,
                )

        on_progress = self._make_progress_callback()

        # Prefer the session's cached workflow — avoids a redundant
        # build_workflow() call when validation already loaded the graph.
        session = (
            self.session_manager.session
            if self.session_manager is not None
            else None
        )
        if session is not None:
            try:
                workflow = session.to_workflow()
                workflow.on_progress = on_progress
            except Exception as exc:
                self.state = "idle"
                raise WorkflowBuildError(
                    [
                        GraphValidationError(
                            type="parameter_invalid",
                            detail=f"Workflow build failed: {exc}",
                        )
                    ]
                ) from exc

            # Check for translation-level errors from the session load.
            translation_errors = (
                self.session_manager.translation_errors
                if self.session_manager is not None
                else []
            )
            build_errors = list(translation_errors)
            if workflow.errors:
                from bioimageflow_server.services.graph_translator import (
                    lib_validation_error_to_graph_error,
                )

                build_errors.extend(
                    lib_validation_error_to_graph_error(e)
                    for e in workflow.errors
                )
            if build_errors:
                self.state = "idle"
                raise WorkflowBuildError(build_errors)
        else:
            try:
                build_result = build_workflow(
                    graph,
                    self.tool_registry,
                    storage_path=self.storage_path,
                    on_progress=on_progress,
                )
            except Exception as exc:
                self.state = "idle"
                raise WorkflowBuildError(
                    [
                        GraphValidationError(
                            type="parameter_invalid",
                            detail=f"Workflow build failed: {exc}",
                        )
                    ]
                ) from exc

            workflow, errors, _disabled = build_result
            if errors:
                self.state = "idle"
                raise WorkflowBuildError(errors)

        self._workflow = workflow

        # Resolve execution targets. If caller passed an explicit subset,
        # look them up on workflow.nodes; otherwise pass none and let
        # the library auto-detect terminal nodes.
        targets: tuple[Any, ...] = ()
        if nodes:
            node_map = dict(workflow.nodes)
            resolved: list[Any] = []
            for nid in nodes:
                if nid in node_map:
                    resolved.append(node_map[nid])
            targets = tuple(resolved)

        dev_mode = bool(self.settings.dev_mode)

        def _run_sync() -> Any:
            return workflow.compute(*targets, dev_mode=dev_mode)

        loop = asyncio.get_event_loop()
        task = loop.create_task(asyncio.to_thread(_run_sync))
        self._run_task = task
        task.add_done_callback(self._on_run_done)

    async def stop(self) -> None:
        if self._workflow is None or self.state != "running":
            return
        try:
            self._workflow.cancel()
        except Exception:  # pragma: no cover — defensive
            logger.exception("Workflow.cancel() raised")

    # ---- Internals ---------------------------------------------------------

    def _make_progress_callback(self) -> Callable[[Any], None]:
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

            if status == "started":
                self._current_node_id = node_id
                self._node_statuses[node_id] = NodeStatus(
                    node_id=node_id, status="running", cached=False
                )
                self.event_bus.publish_node_state(
                    node_id, "running", False, None, None
                )
                return

            if status == "row_progress":
                current = int(getattr(event, "current", 0) or 0)
                maximum = int(getattr(event, "maximum", 0) or 0)
                self.progress = ProgressInfo(
                    node_id=node_id, row=current, total_rows=maximum
                )
                self.event_bus.publish_progress(
                    node_id, "row_progress", current, maximum, timestamp
                )
                return

            if status == "row_complete":
                row = int(getattr(event, "row", 0) or 0)
                total_rows = int(getattr(event, "total_rows", 0) or 0)
                self.progress = ProgressInfo(
                    node_id=node_id, row=row, total_rows=total_rows
                )
                self.event_bus.publish_progress(
                    node_id, "row_complete", row, total_rows, timestamp
                )
                return

            if status == "completed":
                self._node_statuses[node_id] = NodeStatus(
                    node_id=node_id, status="executed", cached=False
                )
                self.event_bus.publish_node_state(
                    node_id, "executed", False, None, None
                )
                return

            if status == "cached":
                self._node_statuses[node_id] = NodeStatus(
                    node_id=node_id, status="executed", cached=True
                )
                self.event_bus.publish_node_state(
                    node_id, "executed", True, None, None
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
                )
                self.event_bus.publish_node_state(
                    node_id, "failed", False, message, tb
                )
                return

            if status == "cancelled":
                self._node_statuses[node_id] = NodeStatus(
                    node_id=node_id, status="unexecuted", cached=False
                )
                self.event_bus.publish_node_state(
                    node_id, "unexecuted", False, None, None
                )
                return

        return _on_progress

    def _on_run_done(self, task: asyncio.Task) -> None:
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
                # If a currently-running node never got a terminal event,
                # mark it as unexecuted.
                if (
                    self._current_node_id is not None
                    and self._node_statuses.get(self._current_node_id)
                    is not None
                    and self._node_statuses[self._current_node_id].status
                    == "running"
                ):
                    self._node_statuses[self._current_node_id] = NodeStatus(
                        node_id=self._current_node_id,
                        status="unexecuted",
                        cached=False,
                    )
            else:
                success = False
                tb = "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                )
                errors.append(
                    {
                        "type": type(exc).__name__,
                        "detail": str(exc),
                        "traceback": tb,
                    }
                )
                # Attribute the failure to the currently-running node if
                # no explicit "failed" event was seen.
                target_id = self._current_node_id
                if target_id is not None and target_id in self._node_statuses:
                    current = self._node_statuses[target_id]
                    if current.status == "running":
                        self._node_statuses[target_id] = NodeStatus(
                            node_id=target_id,
                            status="failed",
                            cached=False,
                            error=str(exc),
                            traceback=tb,
                        )

        self.last_result = ExecutionResult(
            success=success,
            errors=errors,
            node_statuses=dict(self._node_statuses),
        )
        self.event_bus.publish_execution_complete(
            success, errors, dict(self._node_statuses)
        )

        self.state = "idle"
        self._workflow = None
        self._run_task = None


# ---- Cache clearer ----------------------------------------------------------


def clear_node_cache(
    node_ids: list[str],
    graph: GraphState,
    registry: ToolRegistryService,
    storage_path: Path | None,
    session_manager: SessionManager | None = None,
) -> dict[str, NodeStatus]:
    """Clear cache directories for ``node_ids`` and compute downstream impact.

    Uses the session's cached :class:`Workflow` when available to avoid
    building a throwaway workflow. Falls back to :func:`build_workflow`
    otherwise. Returns a dict keyed by node ID. Cleared nodes get
    status ``"unexecuted"``; their transitive downstream receives
    ``"out_of_date"``. Unknown node IDs are silently skipped.
    """
    session = (
        session_manager.session if session_manager is not None else None
    )
    if session is not None:
        workflow = session.to_workflow()
    else:
        workflow, _errors, _disabled = build_workflow(
            graph, registry, storage_path=storage_path,
        )

    # Filter to valid node IDs known to the workflow.
    known = set(workflow.nodes.keys())
    valid_ids = [nid for nid in node_ids if nid in known]
    if not valid_ids:
        return {}

    # Invalidate without cascade first to identify directly cleared nodes.
    directly_cleared = workflow.invalidate(valid_ids, cascade=False)

    # Collect transitive downstream of each requested node.
    downstream: set[str] = set()
    for nid in valid_ids:
        downstream.update(workflow.downstream_of(nid))

    # Invalidate downstream nodes (the direct ones are already cleared).
    downstream -= directly_cleared
    downstream -= set(valid_ids)
    if downstream:
        workflow.invalidate(list(downstream), cascade=False)

    result: dict[str, NodeStatus] = {}

    # Directly requested nodes → unexecuted.
    for nid in valid_ids:
        result[nid] = NodeStatus(node_id=nid, status="unexecuted", cached=False)

    # Downstream nodes → out_of_date.
    for nid in downstream:
        result[nid] = NodeStatus(node_id=nid, status="out_of_date", cached=False)

    return result
