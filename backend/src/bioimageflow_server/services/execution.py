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
import ast
import logging
import re
import time
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
from bioimageflow_server.services.graph_compiler import GraphCompiler
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
    ) -> None: ...

    def publish_execution_complete(
        self, success: bool, errors: list, node_statuses: dict
    ) -> None: ...

    def publish_log(
        self,
        level: str,
        message: str,
        node_id: str | None,
        timestamp: float,
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
    ) -> None:
        return None

    def publish_execution_complete(
        self, success: bool, errors: list, node_statuses: dict
    ) -> None:
        return None

    def publish_log(
        self,
        level: str,
        message: str,
        node_id: str | None,
        timestamp: float,
    ) -> None:
        return None

    def publish_environment_status(self, env_name: str, status: str) -> None:
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
        settings_provider: Callable[[], Settings] | None = None,
    ) -> None:
        self.event_bus = event_bus
        self.tool_registry = tool_registry
        self.settings = settings
        # When provided, ``settings_provider`` is consulted on each ``start()``
        # so live SettingsStore PATCHes (e.g. flipping ``dev_mode``) take
        # effect on the next run without restarting the app.
        self._settings_provider = settings_provider
        self.storage_path = storage_path

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
        self,
        graph: GraphState,
        nodes: list[str] | None = None,
        storage_path: Path | None = None,
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

        live_settings = (
            self._settings_provider() if self._settings_provider else self.settings
        )
        run_storage_path = storage_path if storage_path is not None else self.storage_path
        build_graph = _execution_subgraph(graph, nodes) if nodes else graph

        # Seed disabled nodes so they appear in the final result.
        for node in build_graph.nodes:
            if not node.enabled:
                self._node_statuses[node.id] = NodeStatus(
                    node_id=node.id,
                    status="disabled",
                    cached=False,
                )

        on_progress = self._make_progress_callback()

        # Execution compiles the graph submitted with this run request; no
        # validation or editor session can alter its meaning.
        try:
            build_result = GraphCompiler(self.tool_registry).compile(
                build_graph,
                storage_path=run_storage_path,
                on_progress=on_progress,
                settings=live_settings,
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
        self._attach_environment_status_hook(workflow)

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

        dev_mode = bool(live_settings.dev_mode)
        target_label = ", ".join(nodes) if nodes else "workflow terminals"
        logger.info("Starting workflow execution for %s", target_label)
        self.event_bus.publish_log(
            "INFO",
            f"Execution started for {target_label}",
            None,
            time.time(),
        )

        def _run_sync() -> Any:
            return workflow.compute(*targets, dev_mode=dev_mode)

        loop = asyncio.get_running_loop()
        task = loop.create_task(asyncio.to_thread(_run_sync))
        self._run_task = task
        task.add_done_callback(self._on_run_done)

    async def stop(self) -> None:
        if self._workflow is None or self.state != "running":
            return
        self.event_bus.publish_log("INFO", "Execution stop requested", None, time.time())
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
                    node_id, "running", False, None, None, result_key, record_id
                )
                self.event_bus.publish_log(
                    "INFO",
                    f"Node {node_id} started",
                    node_id,
                    timestamp,
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
                )
                self.event_bus.publish_log(
                    "DEBUG",
                    f"Node {node_id} row progress {current}/{maximum}",
                    node_id,
                    timestamp,
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
                )
                self.event_bus.publish_log(
                    "INFO",
                    f"Node {node_id} completed row {row}/{total_rows}",
                    node_id,
                    timestamp,
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
                    node_id, "executed", False, None, None, result_key, record_id
                )
                self.event_bus.publish_log(
                    "INFO",
                    f"Node {node_id} completed",
                    node_id,
                    timestamp,
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
                    node_id, "executed", True, None, None, result_key, record_id
                )
                self.event_bus.publish_log(
                    "INFO",
                    f"Node {node_id} used cached result",
                    node_id,
                    timestamp,
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
                    node_id, "failed", False, message, tb, result_key, record_id
                )
                self.event_bus.publish_log(
                    "ERROR",
                    _format_node_failure_message(node_id, message, tb),
                    node_id,
                    timestamp or time.time(),
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
                    node_id, "unexecuted", False, None, None, result_key, record_id
                )
                return

        return _on_progress

    def _attach_environment_status_hook(self, workflow: Any) -> None:
        """Publish Wetlands environment lifecycle changes during execution.

        The library owns environment startup inside ``WetlandsEnvManager``.
        Hooking the per-workflow manager keeps the platform UI in sync for
        automatic starts triggered by ``workflow.compute()``.
        """
        engine = getattr(workflow, "_engine", None)
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
        setattr(manager, "_bioimageflow_platform_env_status_hooked", True)

    def _publish_environment_status(self, env_name: str, status: str) -> None:
        publish = getattr(self.event_bus, "publish_environment_status", None)
        if callable(publish):
            publish(env_name, status)

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
                logger.info("Workflow execution cancelled: %s", exc)
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
                local_tb = "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                )
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
                    target_id = _single_failed_node_without_error(
                        self._node_statuses
                    )
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
                            target_id, "failed", False, detail, tb
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
                            target_id, "failed", False, detail, tb
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
                    )

        self.last_result = ExecutionResult(
            success=success,
            errors=errors,
            node_statuses=dict(self._node_statuses),
        )
        self.event_bus.publish_execution_complete(
            success, errors, dict(self._node_statuses)
        )
        if success:
            logger.info("Workflow execution completed successfully")
            self.event_bus.publish_log(
                "INFO",
                "Workflow execution completed successfully",
                None,
                time.time(),
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
            f"External command {executable!r} crashed with signal "
            f"{match.group(2)}{input_clause}."
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


def _execution_subgraph(graph: GraphState, node_ids: list[str] | None) -> GraphState:
    """Return selected target nodes plus all transitive upstream dependencies."""
    if not node_ids:
        return graph

    requested = set(node_ids)
    known = {node.id for node in graph.nodes}
    executable = requested & known
    if not executable:
        return GraphState(nodes=[], edges=[])

    incoming: dict[str, list[str]] = {}
    for edge in graph.edges:
        incoming.setdefault(edge.target_node, []).append(edge.source_node)

    stack = list(executable)
    while stack:
        node_id = stack.pop()
        for upstream in incoming.get(node_id, []):
            if upstream in known and upstream not in executable:
                executable.add(upstream)
                stack.append(upstream)

    return GraphState(
        nodes=[node for node in graph.nodes if node.id in executable],
        edges=[
            edge
            for edge in graph.edges
            if edge.source_node in executable and edge.target_node in executable
        ],
    )


# ---- Cache clearer ----------------------------------------------------------


def clear_node_cache(
    node_ids: list[str],
    graph: GraphState,
    registry: ToolRegistryService,
    storage_path: Path | None,
) -> dict[str, NodeStatus]:
    """Clear cache directories for ``node_ids`` and compute downstream impact.

    Compiles and validates the complete request graph before performing
    any invalidation. Returns a dict keyed by node ID. Cleared nodes get
    status ``"unexecuted"``; their transitive downstream receives
    ``"out_of_date"``. Unknown node IDs are silently skipped.
    """
    compilation = GraphCompiler(registry).compile(
        graph,
        storage_path=storage_path,
    )
    if compilation.errors:
        raise WorkflowBuildError(compilation.errors)
    workflow = compilation.workflow

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
