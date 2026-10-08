"""Tests for :mod:`bioimageflow_server.services.execution`.

Covers Task B1 (ExecutionEventBus / NullEventBus) and Task B2
(ExecutionManager). The manager is tested against a mocked graph
builder and a stub ``Workflow`` so the tests never touch real tool
environments.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from tests.graph_factory import graph_state

from bioimageflow_server.models.execution import (
    ExecutionContext,
    ExecutionResult,
    ProgressInfo,
)
from bioimageflow_server.models.graph import ColumnEdge, DataFrameEdge, GraphState, ToolNodeState
from bioimageflow_server.models.validation import GraphValidationError, NodeStatus
from bioimageflow_server.services.execution import (
    ExecutionConflictError,
    ExecutionEventBus,
    ExecutionManager,
    _ExecutionEnvironmentManager,
    NullEventBus,
    WorkflowBuildError,
    ExecutionRetryError,
)
from bioimageflow_server.services.workflow_status import aggregate_workflow_statuses


class EnvironmentReuseError(RuntimeError):
    """Compatibility-shaped error used to test sanitized recovery guidance."""


pytestmark = pytest.mark.anyio

_TEST_CONTEXT = ExecutionContext(
    execution_id="exec-test",
    workflow_id="wf-test",
    draft_revision=1,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ---- B1: NullEventBus -------------------------------------------------------


class TestNullEventBus:
    def test_publish_progress_accepts_execution_context(self) -> None:
        bus = NullEventBus()
        bus.publish_progress(
            "n1",
            "row_complete",
            1,
            10,
            123.0,
            context=_TEST_CONTEXT,
        )

    def test_publish_node_state_accepts_execution_context(self) -> None:
        bus = NullEventBus()
        bus.publish_node_state(
            "n1",
            "running",
            False,
            None,
            None,
            context=_TEST_CONTEXT,
        )

    def test_publish_execution_complete_accepts_execution_context(self) -> None:
        bus = NullEventBus()
        bus.publish_execution_complete(True, [], {}, context=_TEST_CONTEXT)

    def test_publish_log_accepts_four_args(self) -> None:
        bus = NullEventBus()
        bus.publish_log("ERROR", "failed", "n1", 123.0)

    def test_null_bus_is_execution_event_bus(self) -> None:
        bus: ExecutionEventBus = NullEventBus()
        assert bus is not None


# ---- B0 spike: verify library imports ---------------------------------------


def test_workflow_cancelled_error_imports_from_engine() -> None:
    from bioimageflow.engine import WorkflowCancelledError  # noqa: F401


# ---- Test fixtures ----------------------------------------------------------


class RecordingEventBus:
    """An ExecutionEventBus that records all calls for assertions."""

    def __init__(self) -> None:
        self.progress_events: list[tuple[str, str, int, int, float]] = []
        self.node_state_events: list[tuple[str, str, bool, str | None, str | None]] = []
        self.progress_identity_events: list[tuple[str, str | None, str | None]] = []
        self.node_state_identity_events: list[tuple[str, str | None, str | None]] = []
        self.complete_events: list[tuple[bool, list, dict]] = []
        self.progress_contexts: list[ExecutionContext] = []
        self.node_state_contexts: list[ExecutionContext] = []
        self.complete_contexts: list[ExecutionContext] = []
        self.log_events: list[tuple[str, str, str | None, float]] = []
        self.log_contexts: list[ExecutionContext | None] = []
        self.environment_events: list[tuple[str, str]] = []

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
        task_current: int | None = None,
        task_maximum: int | None = None,
        context: ExecutionContext,
    ) -> None:
        self.progress_events.append((node_id, status, row, total_rows, timestamp))
        self.progress_identity_events.append((node_id, result_key, record_id))
        self.progress_contexts.append(context)

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
        self.node_state_events.append((node_id, status, cached, error, traceback))
        self.node_state_identity_events.append((node_id, result_key, record_id))
        self.node_state_contexts.append(context)

    def publish_execution_complete(
        self,
        success: bool,
        errors: list,
        node_statuses: dict,
        *,
        context: ExecutionContext,
    ) -> None:
        self.complete_events.append((success, errors, node_statuses))
        self.complete_contexts.append(context)

    def publish_log(
        self,
        level: str,
        message: str,
        node_id: str | None,
        timestamp: float,
        *,
        context: ExecutionContext | None = None,
    ) -> None:
        self.log_events.append((level, message, node_id, timestamp))
        self.log_contexts.append(context)

    def publish_environment_status(self, env_name: str, status: str) -> None:
        self.environment_events.append((env_name, status))


@dataclass
class _ProgressEventStub:
    node_name: str
    status: str
    row: int = 0
    total_rows: int = 0
    message: str | None = None
    traceback: str | None = None
    current: int | None = None
    maximum: int | None = None
    timestamp: float = 0.0
    result_key: str | None = None
    record_id: str | None = None


class _FakeWorkflow:
    """Minimal stand-in for ``bioimageflow.Workflow``."""

    def __init__(
        self,
        on_progress: Any = None,
        events: list | None = None,
        validation_errors: list | None = None,
    ) -> None:
        self.on_progress = on_progress
        self.events = events or []
        self.errors: list = []
        self.nodes: dict = {}
        self.validation_errors = validation_errors or []
        self.raise_exc: BaseException | None = None
        self.compute_calls = 0
        self.cancel_called = False
        self.targets_received: tuple = ()
        self.engine_type = "direct"

    def create_engine(self, **_kwargs: Any) -> Any:
        return type("Engine", (), {"environment_manager": None, "close": lambda self: None})()

    def validate(self) -> list:
        return list(self.validation_errors)

    def plan(self) -> dict:
        return {}

    def compute(
        self,
        *targets: Any,
        engine: Any = None,
        run_context: Any = None,
    ) -> dict[str, Any]:
        self.compute_calls += 1
        self.targets_received = targets
        for ev in self.events:
            if self.on_progress is not None:
                self.on_progress(ev)
        if self.raise_exc is not None:
            raise self.raise_exc
        return {}

    def cancel(self) -> None:
        self.cancel_called = True


class _EnvSpecStub:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeWetlandsManager:
    def __init__(self) -> None:
        self._envs: dict[str, Any] = {}
        self.calls: list[str] = []
        self.replace_existing_calls: list[bool] = []
        self.recipe_state = "current"
        self.raise_exc: BaseException | None = None
        self.generation = 0
        self.submitted_payloads: list[dict[str, Any]] = []
        self.submitted_receipts: list[Any] = []
        self.submitted_grants: list[Any] = []
        self.pools: set[str] = set()
        self.admission_memos: list[Any] = []

    def admit_runtime(self, env_spec: _EnvSpecStub, *, provision: bool,
                      admissions: dict | None = None, replace_stale: bool = False,
                      on_preparation: Any = None, on_provision_event: Any = None,
                      on_removal_event: Any = None) -> Any:
        self.admission_memos.append(admissions)
        key = (env_spec.name, "recipe")
        if admissions is not None and key in admissions:
            receipt = admissions[key]
            if receipt is not None:
                self.validate_runtime_receipt(env_spec, receipt)
            return receipt
        existing = self._envs.get(env_spec.name)
        if not provision and (existing is None or self.recipe_state == "stale"):
            return None
        replace = self.recipe_state == "stale" and replace_stale
        self.calls.append(env_spec.name)
        self.replace_existing_calls.append(replace)
        if self.recipe_state == "stale" and not replace:
            raise EnvironmentReuseError("Stale managed recipe requires replacement")
        if on_preparation is not None:
            on_preparation(SimpleNamespace(action="updating" if replace else "reusing" if existing else "creating"))
        if existing is None or replace:
            if on_provision_event is not None:
                on_provision_event(SimpleNamespace(
                    kind=SimpleNamespace(value="step"), message="Resolving pixi.lock",
                    stage="lock_resolution",
                ))
                on_provision_event(SimpleNamespace(
                    kind=SimpleNamespace(value="output"), message="Downloaded atlas",
                    stage="conda_install",
                ))
            if self.raise_exc is not None:
                raise self.raise_exc
            self.generation += 1
            existing = SimpleNamespace(generation_id=f"generation-{self.generation}")
            self._envs[env_spec.name] = existing
            self.recipe_state = "current"
        if admissions is not None:
            admissions[key] = existing
        return existing

    def validate_runtime_receipt(self, env_spec: _EnvSpecStub, receipt: Any) -> Any:
        current = self._envs[env_spec.name]
        if current.generation_id != receipt.generation_id or self.recipe_state != "current":
            raise RuntimeError("Runtime generation changed after admission")
        return current

    def is_running(self, env_name: str) -> bool:
        return env_name in self.pools

    def submit_processing_task(
        self, env_spec: _EnvSpecStub, payload: dict[str, Any],
        max_workers: int = 1, worker_timeout: float | None = None, *,
        runtime_receipt: Any, shared_memory_grant: Any = None,
    ) -> object:
        try:
            self.validate_runtime_receipt(env_spec, runtime_receipt)
        except BaseException:
            if shared_memory_grant is not None:
                shared_memory_grant.drained()
            raise
        self.pools.add(env_spec.name)
        self.submitted_payloads.append(payload)
        self.submitted_receipts.append(runtime_receipt)
        self.submitted_grants.append(shared_memory_grant)
        return SimpleNamespace(payload=payload)

    def running_environments(self) -> tuple[str, ...]:
        return tuple(self.pools)

    def shutdown_all(self) -> None:
        self.pools.clear()


def _graph_with(nodes: list[tuple[str, bool]] | None = None) -> GraphState:
    if nodes is None:
        nodes = []
    return graph_state(
        nodes=[
            ToolNodeState(
                type="tool",
                id=node_id,
                name=node_id,
                tool_name="tool",
                position=(0.0, 0.0),
                parameters={},
                enabled=enabled,
            )
            for node_id, enabled in nodes
        ],
        edges=[],
    )


def _selected_graph() -> GraphState:
    def child_graph(node_id: str, *, input_port: bool = False, output_port: bool = False) -> dict:
        interface: dict[str, list[dict]] = {"inputs": [], "outputs": []}
        if input_port:
            interface["inputs"] = [
                {
                    "id": "dataframe_in",
                    "name": "DataFrame in",
                    "kind": "dataframe",
                    "targets": [{"node": "internal", "port": {"kind": "positional", "index": 0}}],
                }
            ]
        if output_port:
            interface["outputs"] = [
                {
                    "id": "dataframe_out",
                    "name": "DataFrame out",
                    "source": {"node": "internal", "column": "value"},
                }
            ]
        return graph_state(
            name=f"{node_id}_definition",
            nodes=[
                ToolNodeState(
                    type="tool",
                    id="internal",
                    name="internal",
                    tool_name="tool",
                    position=(0.0, 0.0),
                    parameters={},
                )
            ],
            interface=interface,
        ).model_dump(mode="json", by_alias=True)

    return graph_state(
        nodes=[
            {
                "type": "workflow",
                "id": "upstream",
                "name": "upstream",
                "workflow": child_graph("upstream", output_port=True),
                "bindings": {},
                "position": (0.0, 0.0),
            },
            {
                "type": "workflow",
                "id": "selected",
                "name": "selected",
                "workflow": child_graph("selected", input_port=True),
                "bindings": {},
                "position": (200.0, 0.0),
            },
            {
                "type": "workflow",
                "id": "unrelated",
                "name": "unrelated",
                "workflow": child_graph("unrelated"),
                "bindings": {},
                "position": (100.0, 200.0),
            },
        ],
        edges=[
            DataFrameEdge(
                type="dataframe",
                id="upstream_to_selected",
                source_node="upstream",
                target_node="selected",
                target_input="dataframe_in",
            )
        ],
    )


def test_workflow_boundaries_reflect_executed_descendants() -> None:
    graph = _selected_graph()
    statuses = {
        "upstream/internal": NodeStatus(
            node_id="upstream/internal", status="executed", cached=True
        ),
        "selected/internal": NodeStatus(
            node_id="selected/internal", status="executed", cached=False
        ),
    }

    aggregates = aggregate_workflow_statuses(
        graph,
        statuses,
        selected_leaf_ids=statuses,
    )

    assert aggregates["upstream"].status == "executed"
    assert aggregates["upstream"].cached
    assert aggregates["selected"].status == "executed"
    assert not aggregates["selected"].cached
    assert "unrelated" not in aggregates


def test_validation_projects_workflow_boundary_statuses() -> None:
    from bioimageflow_server.services.graph_builder import BuildOutput
    from bioimageflow_server.services.graph_validator import GraphValidationService

    def plan(status: str) -> SimpleNamespace:
        return SimpleNamespace(
            status=SimpleNamespace(value=status),
            final_result_key=None,
            selected_record_id=None,
        )

    child = SimpleNamespace(nodes={"internal": object()})
    workflow = SimpleNamespace(
        errors=[],
        validate=lambda **_kwargs: [],
        plan=lambda **_kwargs: {
            "upstream/internal": plan("cached"),
            "selected/internal": plan("cached"),
            "unrelated/internal": plan("unexecuted"),
        },
        nodes={name: SimpleNamespace(workflow=child) for name in (
            "upstream", "selected", "unrelated"
        )},
    )

    result = GraphValidationService.validation_from_compilation(
        _selected_graph(), BuildOutput(workflow, [], set())
    )

    assert result.node_statuses["upstream"].status == "executed"
    assert result.node_statuses["selected"].status == "executed"
    assert result.node_statuses["unrelated"].status == "unexecuted"


def test_completed_run_publishes_workflow_boundary_statuses() -> None:
    bus = RecordingEventBus()
    manager = ExecutionManager(bus, MagicMock())
    context = _TEST_CONTEXT.model_copy(
        update={"planned_node_ids": ["upstream/internal", "selected/internal"]}
    )
    manager.context = context
    manager.state = "running"
    manager._active_graph = _selected_graph()
    manager._node_statuses = {
        node_id: NodeStatus(node_id=node_id, status="executed", cached=False)
        for node_id in context.planned_node_ids
    }

    manager._on_run_done(SimpleNamespace(exception=lambda: None), context)

    assert manager.last_result is not None and manager.last_result.success
    assert manager.last_result.node_statuses["upstream"].status == "executed"
    assert manager.last_result.node_statuses["selected"].status == "executed"
    assert "unrelated" not in manager.last_result.node_statuses
    assert ("upstream", "executed", False, None, None) in bus.node_state_events
    assert ("selected", "executed", False, None, None) in bus.node_state_events


def _compiled_workflow_node() -> Any:
    workflow = _FakeWorkflow()
    workflow.nodes = {"internal": object()}
    return type("CompiledWorkflowNode", (), {"workflow": workflow})()


def _install_fake_builder(
    monkeypatch: pytest.MonkeyPatch,
    workflow: _FakeWorkflow | None,
    errors: list | None = None,
    *,
    project_errors: bool = False,
) -> MagicMock:
    """Replace request-local compilation with a fake ``BuildOutput``."""
    from bioimageflow_server.services.graph_builder import BuildOutput
    from bioimageflow_server.services.graph_compiler import GraphCompiler

    original_root_ids: set[str] | None = None

    def _builder(graph, *, storage_path=None, on_progress=None):
        nonlocal original_root_ids
        root_ids = {node.id for node in graph.nodes}
        if original_root_ids is None:
            original_root_ids = root_ids
        # Wire the progress callback into the fake workflow so scripted
        # events are delivered through it.
        if workflow is not None:
            workflow.on_progress = on_progress
        return BuildOutput(
            workflow=workflow,
            errors=[error for error in errors or []
                    if not project_errors or error.node is None
                    or error.node.split("/", 1)[0] not in original_root_ids - root_ids],
            disabled_node_ids=set(),
        )

    mock = MagicMock(side_effect=_builder)
    monkeypatch.setattr(GraphCompiler, "compile", mock)
    return mock


async def _drain(manager: ExecutionManager, timeout: float = 2.0) -> None:
    task = manager._run_task
    if task is None:
        return
    # Wait for the task to finish, swallowing any exception — the manager
    # handles task exceptions in its done_callback.
    deadline = asyncio.get_event_loop().time() + timeout
    while not task.done() and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.01)
    if not task.done():
        pytest.fail("Background task did not finish in time")
    # Let the done_callback run.
    for _ in range(5):
        await asyncio.sleep(0)


def _observed_environment_adapter(
    manager: _FakeWetlandsManager,
    bus: RecordingEventBus,
    *,
    replacement_allowed: bool,
) -> _ExecutionEnvironmentManager:
    execution = ExecutionManager(
        bus,
        MagicMock(),
        environment_replacement_authorizer=lambda _spec: replacement_allowed,
    )

    execution.context = _TEST_CONTEXT
    execution.state = "running"
    return _ExecutionEnvironmentManager(
        manager,
        context=_TEST_CONTEXT,
        current_node_id=lambda: None,
        on_preparation=execution._on_environment_preparation,
        on_provision_event=execution._on_environment_event,
        on_ready=execution._on_environment_ready,
        on_admitted=execution._on_environment_admitted,
        on_failure=execution._on_environment_failure,
        on_stopped=lambda name: execution._publish_environment_status(name, "stopped"),
        replacement_authorizer=execution._environment_replacement_authorizer,
    )


def test_concurrent_submissions_replace_one_stale_generation_before_handoff() -> None:
    """Coordinate both the unguarded race and the guarded path without sleeps."""
    first_inspected = threading.Event()
    second_attempted = threading.Event()
    release_first = threading.Event()

    class ConcurrentManager(_FakeWetlandsManager):
        def __init__(self) -> None:
            super().__init__()
            self.lock = threading.RLock()
            self.task_generations: list[str] = []
            self.retired_generations: list[str] = []

        def admit_runtime(self, env_spec: _EnvSpecStub, **kwargs: Any) -> object:
            if threading.current_thread().name == "e1-first":
                first_inspected.set()
                assert release_first.wait(5)
            with self.lock:
                if self.recipe_state == "stale" and kwargs.get("replace_stale"):
                    self.retired_generations.extend(self.task_generations)
                return super().admit_runtime(env_spec, **kwargs)

        def submit_processing_task(self, env_spec: _EnvSpecStub, payload: dict[str, Any], **kwargs: Any) -> object:
            with self.lock:
                generation = self._envs[env_spec.name].generation_id
                self.task_generations.append(generation)
                return super().submit_processing_task(env_spec, payload, **kwargs)

    class CoordinatedLock:
        """Expose a waiting lock attempt so the controller can release first."""

        def __init__(self) -> None:
            self.lock = threading.RLock()

        def __enter__(self) -> None:
            if threading.current_thread().name == "e1-second":
                second_attempted.set()
            self.lock.acquire()

        def __exit__(self, *_args: Any) -> None:
            self.lock.release()

    manager = ConcurrentManager()
    manager._envs["cellpose-env"] = SimpleNamespace(generation_id="old")
    manager.recipe_state = "stale"
    adapter = _observed_environment_adapter(manager, RecordingEventBus(), replacement_allowed=True)
    # Instrument the guard's acquisition only; inspection, replacement, and
    # submission still exercise the adapter's actual implementation.
    adapter._environment_lock = CoordinatedLock()
    failures: list[BaseException] = []

    def submit(row: int) -> None:
        try:
            spec = _EnvSpecStub("cellpose-env")
            receipt = adapter.admit_runtime(spec, provision=True, admissions={})
            adapter.submit_processing_task(spec, {"row": row}, runtime_receipt=receipt)
        except BaseException as error:
            failures.append(error)

    first = threading.Thread(target=submit, args=(1,), name="e1-first")
    second = threading.Thread(target=submit, args=(2,), name="e1-second")
    first.start()
    try:
        assert first_inspected.wait(5)
        second.start()
        assert second_attempted.wait(5)
    finally:
        release_first.set()
        first.join(5)
        if second.ident is not None:
            second.join(5)

    assert not first.is_alive() and not second.is_alive()
    assert failures == []
    assert sorted(manager.submitted_payloads, key=lambda payload: payload["row"]) == [{"row": 1}, {"row": 2}]
    assert manager.replace_existing_calls == [True, False]
    assert manager.task_generations == ["generation-1", "generation-1"]
    assert manager.retired_generations == []


# ---- B2: ExecutionManager ---------------------------------------------------


def test_cleanup_retains_exact_owners_until_physical_grants_drain() -> None:
    manager = ExecutionManager(RecordingEventBus(), MagicMock())
    state = {"drained": False}
    group = SimpleNamespace(release=MagicMock(side_effect=lambda: SimpleNamespace(
        state="closed" if state["drained"] else "pending",
    )))
    owner = SimpleNamespace(close=MagicMock(side_effect=lambda: SimpleNamespace(
        state="closed" if state["drained"] else "pending", pending_readers=0,
        pending_grants=0 if state["drained"] else 1, pending_files=0,
        pending_leases=0, errors=(),
    )))
    engine = SimpleNamespace(close=MagicMock(side_effect=[RuntimeError("physical close failed"), None]))
    context = SimpleNamespace(result_groups=(group,), shared_memory_context=owner, cleanup_pending=False)
    manager._settle_run_resources("run-owned", context, engine)
    pending = manager._pending_resource_cleanup["run-owned"]
    assert pending.engine is engine and pending.run_context is context and pending.groups == (group,)
    state["drained"] = True
    manager.retry_resource_cleanup()
    assert manager._pending_resource_cleanup == {}
    assert engine.close.call_count == 2
    assert group.release.call_count == 2 and owner.close.call_count == 2


@pytest.mark.parametrize("primary", [None, RuntimeError("science failed")])
def test_cleanup_interruption_preserves_primary_and_independent_cleanup(primary: BaseException | None) -> None:
    manager = ExecutionManager(RecordingEventBus(), MagicMock())
    interruption = KeyboardInterrupt("cleanup interrupted")
    engine = SimpleNamespace(close=MagicMock(side_effect=[interruption, None]))
    group = SimpleNamespace(release=MagicMock(return_value=SimpleNamespace(state="closed")))
    owner = SimpleNamespace(close=MagicMock(return_value=SimpleNamespace(state="closed")))
    context = SimpleNamespace(result_groups=(group,), shared_memory_context=owner, cleanup_pending=False)
    if primary is None:
        with pytest.raises(KeyboardInterrupt) as raised:
            manager._settle_run_resources("run-owned", context, engine)
        assert raised.value is interruption
    else:
        with pytest.raises(RuntimeError) as raised:
            try:
                raise primary
            finally:
                manager._settle_run_resources("run-owned", context, engine, primary=primary)
        assert raised.value is primary
    assert manager._pending_resource_cleanup["run-owned"].engine is engine
    group.release.assert_called_once()
    owner.close.assert_called_once()
    manager.retry_resource_cleanup()
    assert manager._pending_resource_cleanup == {}


class TestExecutionManagerLifecycle:
    async def test_cache_clear_updates_matching_live_status_without_rewriting_run_history(
        self,
    ) -> None:
        em = ExecutionManager(NullEventBus(), MagicMock())
        em.context = ExecutionContext(execution_id="run-1", workflow_id="wf", draft_revision=2)
        executed = NodeStatus(node_id="source", status="executed", cached=True)
        em._node_statuses = {"source": executed}
        em.last_result = ExecutionResult(
            success=True, errors=[], node_statuses={"source": executed}
        )

        cleared = NodeStatus(node_id="source", status="unexecuted", cached=False)
        em.apply_cache_clear_statuses("other", {"source": cleared}, 2)
        assert em.get_status().node_statuses["source"].status == "executed"
        em.apply_cache_clear_statuses("wf", {"source": cleared}, 3)
        assert em.get_status().node_statuses["source"].status == "executed"
        em.apply_cache_clear_statuses("wf", {"source": cleared}, 2)
        assert em.get_status().node_statuses["source"].status == "unexecuted"
        assert em.get_status().last_result.node_statuses["source"].status == "executed"

    async def test_idle_state_initially(self) -> None:
        em = ExecutionManager(NullEventBus(), MagicMock())
        assert em.state == "idle"
        assert em.is_running is False
        assert em.last_result is None
        assert em.progress is None

    async def test_start_sets_running_then_idle_on_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        assert em.state == "running"
        await _drain(em)
        assert em.state == "idle"
        assert em.is_running is False
        assert em.last_result is not None
        assert em.last_result.success is True

    async def test_one_context_is_bound_to_progress_completion_and_terminal_status(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(
            events=[
                _ProgressEventStub("n1", "row_progress", current=1, maximum=2, timestamp=1.0),
                _ProgressEventStub("n1", "completed", timestamp=2.0),
            ]
        )
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())

        context = await em.start(
            _graph_with([("n1", True)]),
            workflow_id="wf_a",
            draft_revision=7,
        )
        await _drain(em)

        assert context.workflow_id == "wf_a"
        assert context.draft_revision == 7
        assert context.execution_id
        assert bus.progress_contexts == [context]
        assert bus.node_state_contexts == [context]
        assert bus.complete_contexts == [context]
        status = em.get_status()
        assert status.execution_id == context.execution_id
        assert status.workflow_id == "wf_a"
        assert status.draft_revision == 7
        assert status.last_result is not None

    async def test_start_and_complete_are_published_as_backend_logs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "completed")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())

        context = await em.start(
            _graph_with([("n1", True)]),
            workflow_id="wf-test",
            draft_revision=3,
        )
        await _drain(em)

        messages = [event[1] for event in bus.log_events]
        assert any("Execution started for workflow terminals" in message for message in messages)
        assert any("Workflow execution completed successfully" in message for message in messages)
        assert bus.log_contexts
        assert all(item == context for item in bus.log_contexts)

    async def test_public_engine_streams_environment_events_across_runs_without_stacking_hooks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _WorkflowWithWetlands(_FakeWorkflow):
            def __init__(self) -> None:
                super().__init__()
                self.engine_type = "wetlands"
                self.create_engine_calls: list[dict[str, Any]] = []
                self.get_or_create_wrappers: list[Any] = []
                self.shutdown_all_wrappers: list[Any] = []

            def create_engine(
                self,
                *,
                resource_lifetime: str = "execution",
                env_manager: Any = None,
            ) -> Any:
                self.create_engine_calls.append(
                    {
                        "resource_lifetime": resource_lifetime,
                        "env_manager": env_manager,
                    }
                )
                return type("Engine", (), {"environment_manager": env_manager, "close": lambda self: None})()

            def compute(
                self,
                *targets: Any,
                engine: Any = None,
                run_context: Any = None,
            ) -> dict[str, Any]:
                manager = engine.environment_manager
                self.get_or_create_wrappers.append(manager.admit_runtime)
                self.shutdown_all_wrappers.append(manager.shutdown_all)
                if self.on_progress is not None:
                    self.on_progress(_ProgressEventStub("n1", "started"))
                receipt = manager.admit_runtime(_EnvSpecStub("atlas"), provision=True, admissions={})
                manager.submit_processing_task(_EnvSpecStub("atlas"), {}, runtime_receipt=receipt)
                return super().compute(*targets)

        bus = RecordingEventBus()
        wf = _WorkflowWithWetlands()
        shared_manager = _FakeWetlandsManager()
        original_admit_runtime = shared_manager.admit_runtime.__func__
        original_shutdown_all = shared_manager.shutdown_all.__func__
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(
            bus,
            MagicMock(),
            environment_manager_provider=lambda: shared_manager,
        )

        first_context = await em.start(
            _graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1
        )
        await _drain(em)
        first_progress = em.retained_progress()

        await em.start(
            _graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1
        )
        await _drain(em)

        assert [call["resource_lifetime"] for call in wf.create_engine_calls] == [
            "external",
            "external",
        ]
        adapters = [call["env_manager"] for call in wf.create_engine_calls]
        assert all(isinstance(adapter, _ExecutionEnvironmentManager) for adapter in adapters)
        assert adapters[0] is not adapters[1]
        assert shared_manager.admit_runtime.__func__ is original_admit_runtime
        assert shared_manager.shutdown_all.__func__ is original_shutdown_all
        assert shared_manager.calls == ["atlas", "atlas"]
        assert bus.environment_events == [
            ("atlas", "creating"), ("atlas", "ready"), ("atlas", "running"),
            ("atlas", "running"), ("atlas", "running"),
        ]
        pixi_logs = [
            context
            for event, context in zip(bus.log_events, bus.log_contexts, strict=True)
            if event[1] == "Downloaded atlas"
        ]
        assert pixi_logs == [first_context]
        assert wf.get_or_create_wrappers[0] is not wf.get_or_create_wrappers[1]
        assert wf.shutdown_all_wrappers[0] is not wf.shutdown_all_wrappers[1]
        assert any(
            event["kind"] == "phase" and "Resolving pixi.lock" in event["payload"]["message"]
            for event in first_progress
        )
        assert not any(
            event["kind"] == "phase" and "Resolving pixi.lock" in event["payload"]["message"]
            for event in em.retained_progress()
        )

    async def test_execution_marks_environment_failed_when_wetlands_start_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _WorkflowWithFailingWetlands(_FakeWorkflow):
            def __init__(self) -> None:
                super().__init__()
                self.engine_type = "wetlands"
                self.manager = _FakeWetlandsManager()
                self.manager.raise_exc = RuntimeError("solve failed")

            def create_engine(self, **kwargs: Any) -> Any:
                return type("Engine", (), {"environment_manager": kwargs["env_manager"], "close": lambda self: None})()

            def compute(
                self,
                *targets: Any,
                engine: Any = None,
                run_context: Any = None,
            ) -> dict[str, Any]:
                engine.environment_manager.admit_runtime(_EnvSpecStub("cellpose-env"), provision=True)
                return {}

        bus = RecordingEventBus()
        wf = _WorkflowWithFailingWetlands()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(
            bus,
            MagicMock(),
            environment_manager_provider=lambda: wf.manager,
        )

        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)

        assert bus.environment_events == [
            ("cellpose-env", "creating"),
            ("cellpose-env", "failed"),
        ]

    async def test_owned_stale_environment_is_replaced_lazily(self) -> None:
        bus = RecordingEventBus()
        manager = _FakeWetlandsManager()
        old = SimpleNamespace(generation_id="old-generation")
        unrelated = SimpleNamespace(generation_id="unrelated-generation")
        manager._envs.update({"cellpose-env": old, "unrelated-env": unrelated})
        manager.recipe_state = "stale"
        adapter = _observed_environment_adapter(manager, bus, replacement_allowed=True)

        replacement = adapter.admit_runtime(_EnvSpecStub("cellpose-env"), provision=True)

        assert replacement is manager._envs["cellpose-env"]
        assert replacement is not old
        assert manager._envs["unrelated-env"] is unrelated
        assert manager.replace_existing_calls == [True]
        assert bus.environment_events == [
            ("cellpose-env", "updating"),
            ("cellpose-env", "ready"),
        ]

        reused = adapter.admit_runtime(_EnvSpecStub("cellpose-env"), provision=True)

        assert reused is replacement
        assert manager._envs["unrelated-env"] is unrelated
        assert manager.replace_existing_calls == [True, False]

    async def test_stale_environment_outside_processing_ownership_is_not_replaced(self) -> None:
        bus = RecordingEventBus()
        manager = _FakeWetlandsManager()
        old = SimpleNamespace(generation_id="external-generation")
        manager._envs["external-env"] = old
        manager.recipe_state = "stale"
        adapter = _observed_environment_adapter(manager, bus, replacement_allowed=False)

        with pytest.raises(EnvironmentReuseError, match="requires replacement"):
            adapter.admit_runtime(_EnvSpecStub("external-env"), provision=True)

        assert manager._envs["external-env"] is old
        assert manager.replace_existing_calls == [False]
        assert bus.environment_events[-1] == ("external-env", "failed")

    async def test_failed_stale_replacement_can_retry_without_publishing_ready(self) -> None:
        bus = RecordingEventBus()
        manager = _FakeWetlandsManager()
        old = SimpleNamespace(generation_id="old-generation")
        manager._envs["cellpose-env"] = old
        manager.recipe_state = "stale"
        manager.raise_exc = RuntimeError("provisioning failed")
        adapter = _observed_environment_adapter(manager, bus, replacement_allowed=True)

        with pytest.raises(RuntimeError, match="provisioning failed"):
            adapter.admit_runtime(_EnvSpecStub("cellpose-env"), provision=True)

        assert manager._envs["cellpose-env"] is old
        assert manager.generation == 0
        assert manager.replace_existing_calls == [True]
        assert bus.environment_events == [
            ("cellpose-env", "updating"),
            ("cellpose-env", "failed"),
        ]

        manager.raise_exc = None
        replacement = adapter.admit_runtime(_EnvSpecStub("cellpose-env"), provision=True)

        assert replacement is manager._envs["cellpose-env"]
        assert replacement is not old
        assert manager.generation == 1
        assert manager.replace_existing_calls == [True, True]
        assert bus.environment_events[-2:] == [
            ("cellpose-env", "updating"),
            ("cellpose-env", "ready"),
        ]

    async def test_processing_submission_uses_receipt_admitted_before_dispatch(self) -> None:
        bus = RecordingEventBus()
        manager = _FakeWetlandsManager()
        manager._envs["cellpose-env"] = SimpleNamespace(generation_id="old")
        manager.recipe_state = "stale"
        adapter = _observed_environment_adapter(manager, bus, replacement_allowed=True)
        spec = _EnvSpecStub("cellpose-env")
        admissions: dict = {}
        receipt = adapter.admit_runtime(spec, provision=True, admissions=admissions)
        assert manager.pools == set()  # Key/cache admission has started no workers.
        assert bus.environment_events[-1] == ("cellpose-env", "ready")
        assert manager.admission_memos == [admissions]
        grant = SimpleNamespace(drained=MagicMock())
        payloads = [{"row": 1}, {"row": 2}]
        tasks = [adapter.submit_processing_task(
            spec, payload, runtime_receipt=receipt, shared_memory_grant=grant,
        ) for payload in payloads]
        assert [task.payload for task in tasks] == payloads
        assert manager.submitted_receipts == [receipt, receipt]
        assert manager.submitted_grants == [grant, grant]
        assert manager.replace_existing_calls == [True]
        assert manager.generation == 1
        assert bus.environment_events.count(("cellpose-env", "updating")) == 1
        bus.environment_events.clear()
        adapter.admit_runtime(spec, provision=True, admissions={})
        assert bus.environment_events == [("cellpose-env", "running")]
        assert manager.submitted_payloads == payloads  # Admission never submits.

    async def test_held_generation_change_refuses_before_any_task(self) -> None:
        manager = _FakeWetlandsManager()
        adapter = _observed_environment_adapter(manager, RecordingEventBus(), replacement_allowed=True)
        spec = _EnvSpecStub("cellpose-env")
        receipt = adapter.admit_runtime(spec, provision=True, admissions={})
        manager._envs[spec.name] = SimpleNamespace(generation_id="substituted")
        grant = SimpleNamespace(drained=MagicMock())
        with pytest.raises(RuntimeError, match="generation changed"):
            adapter.submit_processing_task(spec, {}, runtime_receipt=receipt, shared_memory_grant=grant)
        assert manager.submitted_payloads == []
        assert manager.replace_existing_calls == [False]
        grant.drained.assert_called_once()

    async def test_metadata_only_admission_never_prepares_or_emits_status(self) -> None:
        bus = RecordingEventBus()
        manager = _FakeWetlandsManager()
        adapter = _observed_environment_adapter(manager, bus, replacement_allowed=True)
        assert adapter.admit_runtime(_EnvSpecStub("absent"), provision=False, admissions={}) is None
        assert manager.calls == [] and manager.pools == set()
        assert bus.environment_events == []

    async def test_failed_processing_preparation_never_submits_payload(self) -> None:
        manager = _FakeWetlandsManager()
        manager.recipe_state = "stale"
        manager.raise_exc = RuntimeError("provisioning failed")
        adapter = _observed_environment_adapter(manager, RecordingEventBus(), replacement_allowed=True)
        with pytest.raises(RuntimeError, match="provisioning failed"):
            adapter.admit_runtime(_EnvSpecStub("cellpose-env"), provision=True, admissions={})
        assert manager.submitted_payloads == []

    async def test_start_clears_previous_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        wf = _FakeWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)
        assert em.last_result is not None
        wf2 = _FakeWorkflow()
        _install_fake_builder(monkeypatch, wf2)
        # progress should reset immediately upon next start
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        assert em.progress is None
        await _drain(em)

    async def test_concurrent_start_raises_conflict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _BlockingWorkflow(_FakeWorkflow):
            def __init__(self) -> None:
                super().__init__()
                self.go = threading.Event()

            def compute(
                self,
                *targets: Any,
                engine: Any = None,
                run_context: Any = None,
            ) -> dict[str, Any]:
                self.go.wait(timeout=3.0)
                return {}

        wf = _BlockingWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        with pytest.raises(ExecutionConflictError):
            await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        wf.go.set()
        await _drain(em, timeout=3.0)

    async def test_start_compiles_off_loop_with_explicit_pending_context(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        wf = _FakeWorkflow()
        builder = _install_fake_builder(monkeypatch, wf)
        build = builder.side_effect
        assert callable(build)
        compile_entered = threading.Event()
        release_compile = threading.Event()
        event_loop_thread = threading.get_ident()

        def blocking_build(*args: Any, **kwargs: Any) -> Any:
            assert threading.get_ident() != event_loop_thread
            compile_entered.set()
            assert release_compile.wait(timeout=2)
            return build(*args, **kwargs)

        builder.side_effect = blocking_build
        em = ExecutionManager(RecordingEventBus(), MagicMock())
        prior_context = ExecutionContext(
            execution_id="prior-execution",
            workflow_id="prior-workflow",
            draft_revision=3,
        )
        em.context = prior_context
        prior_result = ExecutionResult(success=True)
        prior_progress = ProgressInfo(
            node_id="prior-node", status="row_complete", row=1, total_rows=1
        )
        prior_node_status = NodeStatus(
            node_id="prior-node",
            status="executed",
            cached=True,
        )
        em.last_result = prior_result
        em.progress = prior_progress
        em._node_statuses = {"prior-node": prior_node_status}
        context_rechecked = False

        async def ensure_context_current() -> None:
            nonlocal context_rechecked
            assert em.state == "idle"
            assert em.context is prior_context
            context_rechecked = True

        start = asyncio.create_task(
            em.start(
                _graph_with([("n1", True)]),
                workflow_id="new-workflow",
                draft_revision=4,
                ensure_context_current=ensure_context_current,
            )
        )
        try:
            async with asyncio.timeout(2):
                while not compile_entered.is_set():
                    await asyncio.sleep(0)

            assert em.is_running is True
            status = em.get_status()
            assert status.state == "starting"
            assert status.execution_id != prior_context.execution_id
            assert status.workflow_id == "new-workflow"
            assert status.draft_revision == 4
            assert status.last_result is None
            assert status.progress is None
            assert status.node_statuses == {}
            assert em.context is prior_context
            assert em.last_result is prior_result
            assert em.progress is prior_progress
            assert em._node_statuses == {"prior-node": prior_node_status}
            with pytest.raises(ExecutionConflictError):
                await em.start(
                    _graph_with([("n2", True)]),
                    workflow_id="other-workflow",
                    draft_revision=1,
                )
            await asyncio.wait_for(asyncio.sleep(0), timeout=0.1)
        finally:
            release_compile.set()

        accepted_context = await start
        assert accepted_context.workflow_id == "new-workflow"
        assert context_rechecked is True
        await _drain(em)

    async def test_rapid_double_start_second_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        wf = _FakeWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        with pytest.raises(ExecutionConflictError):
            await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)

    async def test_idle_mutation_lease_blocks_run_without_reporting_starting(self) -> None:
        em = ExecutionManager(RecordingEventBus(), MagicMock())

        async with em.exclusive_idle_mutation():
            assert em.is_running is True
            status = em.get_status()
            assert status.state == "idle"
            assert status.execution_id is None
            with pytest.raises(ExecutionConflictError):
                await em.start(
                    _graph_with([("n1", True)]),
                    workflow_id="wf-test",
                    draft_revision=1,
                )

        assert em.is_running is False

    async def test_idle_mutation_leases_serialize_without_execution_conflict(self) -> None:
        em = ExecutionManager(RecordingEventBus(), MagicMock())
        first_entered = asyncio.Event()
        release_first = asyncio.Event()
        second_entered = asyncio.Event()

        async def first_mutation() -> None:
            async with em.exclusive_idle_mutation():
                first_entered.set()
                await release_first.wait()

        async def second_mutation() -> None:
            async with em.exclusive_idle_mutation():
                second_entered.set()

        first = asyncio.create_task(first_mutation())
        await first_entered.wait()
        second = asyncio.create_task(second_mutation())
        await asyncio.sleep(0)

        assert second_entered.is_set() is False
        assert second.done() is False

        release_first.set()
        await asyncio.gather(first, second)

        assert second_entered.is_set() is True
        assert em.is_running is False

    async def test_idle_mutation_lease_rejects_an_actual_execution(self) -> None:
        em = ExecutionManager(RecordingEventBus(), MagicMock())
        em.state = "running"

        with pytest.raises(ExecutionConflictError):
            async with em.exclusive_idle_mutation():
                pytest.fail("mutation must not be admitted")

    async def test_run_selected_compiles_the_accepted_graph_without_pruning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow()
        wf.nodes = {node_id: object() for node_id in ["source", "selected"]}
        builder = _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock())
        graph = graph_state(
            nodes=[
                ToolNodeState(
                    type="tool",
                    id=node_id,
                    name=node_id,
                    tool_name="tool",
                    position=(0.0, 0.0),
                    parameters={},
                )
                for node_id in ["source", "selected", "downstream"]
            ],
            edges=[
                ColumnEdge(
                    type="column",
                    id="e1",
                    source_node="source",
                    target_node="selected",
                    source_output="out",
                    target_input="in",
                ),
                ColumnEdge(
                    type="column",
                    id="e2",
                    source_node="selected",
                    target_node="downstream",
                    source_output="out",
                    target_input="in",
                ),
            ],
        )

        context = await em.start(graph, nodes=["selected"], workflow_id="wf-test", draft_revision=1)
        await _drain(em)

        assert context.planned_node_ids == ["source", "selected"]
        assert em.get_status().planned_node_ids == context.planned_node_ids

        built_graph = builder.call_args.args[0]
        assert {node.id for node in built_graph.nodes} == {
            "source",
            "selected",
            "downstream",
        }
        assert [edge.id for edge in built_graph.edges] == ["e1", "e2"]


class TestExecutionManagerProgress:
    async def test_stale_callback_cannot_project_into_a_later_execution(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        first = _FakeWorkflow()
        _install_fake_builder(monkeypatch, first)
        em = ExecutionManager(bus, MagicMock())
        first_context = await em.start(
            _graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1
        )
        await _drain(em)
        assert first.on_progress is not None

        second = _FakeWorkflow()
        _install_fake_builder(monkeypatch, second)
        second_context = await em.start(
            _graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1
        )
        assert second_context.execution_id != first_context.execution_id
        before_status = em.get_status()
        before_retained = em.retained_progress()
        before_progress = list(bus.progress_events)
        before_states = list(bus.node_state_events)
        first.on_progress(_ProgressEventStub("n1", "started"))
        first.on_progress(_ProgressEventStub("n1", "row_complete", row=2, total_rows=3))
        assert em.get_status() == before_status
        assert em.retained_progress() == before_retained
        assert em.retained_progress_for(first_context) == []
        assert bus.progress_events == before_progress
        assert bus.node_state_events == before_states
        await _drain(em)

    async def test_started_publishes_running_and_accumulates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "started")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)
        assert ("n1", "running", False, None, None) in bus.node_state_events
        n1_states = [e for e in bus.node_state_events if e[0] == "n1"]
        assert n1_states[0][1] == "running"
        assert ("INFO", "Node n1 started", "n1", 0.0) in bus.log_events

    async def test_row_progress_updates_progress_ref_no_node_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(
            events=[
                _ProgressEventStub(
                    "n1", "row_progress", row=2, total_rows=5, current=3, maximum=10, timestamp=1.0
                )
            ]
        )
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)
        assert any(
            e[0] == "n1" and e[1] == "row_progress" and e[2] == 2 and e[3] == 5
            for e in bus.progress_events
        )
        assert em.progress == ProgressInfo(
            node_id="n1",
            status="row_progress",
            row=2,
            total_rows=5,
            task_current=3,
            task_maximum=10,
        )
        assert any(
            e[0] == "DEBUG" and e[2] == "n1" and "Node n1 row progress 3/10" in e[1]
            for e in bus.log_events
        )
        assert not any(e[0] == "n1" and e[1] == "row_progress" for e in bus.node_state_events)

    async def test_progress_identity_is_preserved(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(
            events=[
                _ProgressEventStub(
                    "n1",
                    "row_progress",
                    current=3,
                    maximum=10,
                    result_key="rk_123",
                    record_id="rec_456",
                )
            ]
        )
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)

        assert em.progress is not None
        assert em.progress.result_key == "rk_123"
        assert em.progress.record_id == "rec_456"
        assert ("n1", "rk_123", "rec_456") in bus.progress_identity_events

    async def test_row_complete_emits_progress_and_updates_ref(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(
            events=[_ProgressEventStub("n1", "row_complete", row=2, total_rows=5, timestamp=2.0)]
        )
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)
        assert em.progress is not None
        assert em.progress.row == 2
        assert em.progress.total_rows == 5
        assert any(e[1] == "row_complete" and e[2] == 2 and e[3] == 5 for e in bus.progress_events)
        assert any(
            e[0] == "INFO" and e[2] == "n1" and "Node n1 completed row 2/5" in e[1]
            for e in bus.log_events
        )
        assert not any(e[1] == "row_complete" for e in bus.node_state_events)

    async def test_completed_publishes_executed_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(
            events=[
                _ProgressEventStub(
                    "n1",
                    "completed",
                    result_key="rk_done",
                    record_id="rec_done",
                )
            ]
        )
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)
        assert ("n1", "executed", False, None, None) in bus.node_state_events
        assert ("n1", "rk_done", "rec_done") in bus.node_state_identity_events
        assert em._node_statuses["n1"].status == "executed"
        assert em._node_statuses["n1"].cached is False
        assert em._node_statuses["n1"].result_key == "rk_done"
        assert em._node_statuses["n1"].record_id == "rec_done"
        assert ("INFO", "Node n1 completed", "n1", 0.0) in bus.log_events

    async def test_cached_publishes_executed_with_cached_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "cached")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)
        assert ("n1", "executed", True, None, None) in bus.node_state_events
        assert em._node_statuses["n1"].cached is True
        assert ("INFO", "Node n1 used cached result", "n1", 0.0) in bus.log_events

    async def test_failed_publishes_failed_state_with_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(
            events=[_ProgressEventStub("n1", "failed", message="boom")],
        )
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)
        n1_failed = [e for e in bus.node_state_events if e[0] == "n1" and e[1] == "failed"]
        assert n1_failed
        assert em._node_statuses["n1"].status == "failed"
        error_logs = [event for event in bus.log_events if event[0] == "ERROR"]
        assert error_logs
        level, message, node_id, _timestamp = error_logs[-1]
        assert level == "ERROR"
        assert node_id == "n1"
        assert "Node n1 failed: boom" in message

    async def test_failed_progress_publishes_traceback_in_log(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(
            events=[
                _ProgressEventStub(
                    "n1",
                    "failed",
                    message="boom",
                    traceback="Traceback line 1\nTraceback line 2",
                )
            ],
        )
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)

        error_logs = [event for event in bus.log_events if event[0] == "ERROR"]
        assert error_logs
        level, message, node_id, _timestamp = error_logs[-1]
        assert level == "ERROR"
        assert node_id == "n1"
        assert "Traceback line 2" in message

    async def test_cancelled_publishes_unexecuted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "cancelled")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)
        assert ("n1", "unexecuted", False, None, None) in bus.node_state_events
        assert em._node_statuses["n1"].status == "unexecuted"

    async def test_unknown_status_is_logged_and_ignored(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "future_status")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        with caplog.at_level(logging.WARNING):
            await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
            await _drain(em)
        assert em.state == "idle"
        assert not any(e[1] == "future_status" for e in bus.node_state_events)


class TestExecutionManagerResult:
    async def test_success_populates_last_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "completed")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)
        assert em.last_result is not None
        assert em.last_result.success is True
        assert em.last_result.errors == []
        assert "n1" in em.last_result.node_statuses

    async def test_failed_execution_populates_error_and_traceback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow()
        wf.raise_exc = RuntimeError("kaboom")
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)
        assert em.last_result is not None
        assert em.last_result.success is False
        assert em.last_result.errors
        assert "kaboom" in str(em.last_result.errors[0])

    async def test_environment_recipe_mismatch_does_not_offer_manual_deletion(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("cellpose_1", "started")])
        wf.raise_exc = EnvironmentReuseError(
            "Environment 'segmentation-cellpose-v3' already exists at "
            "/Users/amasson/.bioimageflow/wetlands/pixi/workspaces/"
            "segmentation-cellpose-v3/pixi.toml but cannot be reused: "
            "it was created with a different recipe.\n"
            "Existing hash: sha256:12825e7c20f47da18ba92c11cb9179dd2df35fbb6b4f54050c157abbc1a3425f\n"
            "Requested hash: sha256:61bc60ebf72d2fe1c24c29f363954fd68100ece113ccaa80b5beea5605b867ce\n"
            "Use replace_existing=True to recreate the default managed environment, "
            "load(name) to load the existing environment without recipe validation, or choose a different name."
        )
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())

        await em.start(_graph_with([("cellpose_1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)

        assert em.last_result is not None
        assert em.last_result.success is False
        error = em.last_result.errors[0]
        assert error["type"] == "EnvironmentReuseError"
        assert error["detail"].startswith("Environment 'segmentation-cellpose-v3' already exists")
        assert "recovery_action" not in error

    async def test_environment_reuse_error_without_recipe_mismatch_has_no_recovery_action(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow()
        wf.raise_exc = EnvironmentReuseError(
            "Environment 'custom-env' already exists at /somewhere but cannot be reused: "
            "it is loaded from a non-default path.\nRequested hash: sha256:abc"
        )
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())

        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)

        assert em.last_result is not None
        assert em.last_result.success is False
        assert "recovery_action" not in em.last_result.errors[0]

    async def test_wetlands_payload_is_summarized_for_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        command_message = (
            "Command '['atlas', '-ref', '/tmp/blobs.txt', '-i', "
            "'/Users/amasson/Documents/DemoData/FISH/.DS_Store', '-o', "
            "'/tmp/out', '-rad', '59']' died with <Signals.SIGABRT: 6>."
        )
        payload = {
            "exception": command_message,
            "traceback": [
                '  File "/tmp/module_executor.py", line 194, in execution_worker\n',
                "    result = execute_function(message, lock, connection)\n",
            ],
        }
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("atlas_1", "started")])
        wf.raise_exc = RuntimeError(payload)
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())

        await em.start(_graph_with([("atlas_1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)

        assert em.last_result is not None
        assert em.last_result.success is False
        error = em.last_result.errors[0]
        assert error["detail"] == (
            "External command 'atlas' crashed with signal SIGABRT while "
            "processing '/Users/amasson/Documents/DemoData/FISH/.DS_Store'. "
            "The selected input appears to be a hidden/system file, not image data."
        )
        assert "{'exception':" not in error["detail"]
        assert "Remote traceback:" in error["traceback"]
        assert "Local traceback:" in error["traceback"]
        status = em.last_result.node_statuses["atlas_1"]
        assert status.error == error["detail"]
        assert status.traceback == error["traceback"]

    async def test_failed_progress_without_message_is_enriched_from_task_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = {
            "exception": "Implement Chameau2.process_row",
            "traceback": [
                '  File "/tmp/worker.py", line 1, in run_process_row\n',
                '    raise NotImplementedError("Implement Chameau2.process_row")\n',
            ],
        }
        bus = RecordingEventBus()
        wf = _FakeWorkflow(
            events=[
                _ProgressEventStub("chameau2_1", "started"),
                _ProgressEventStub("chameau2_1", "failed"),
            ],
        )
        wf.raise_exc = RuntimeError(payload)
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())

        await em.start(_graph_with([("chameau2_1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)

        assert em.last_result is not None
        status = em.last_result.node_statuses["chameau2_1"]
        assert status.status == "failed"
        assert status.error == "Implement Chameau2.process_row"
        assert status.traceback is not None
        assert "Remote traceback:" in status.traceback
        failed_updates = [
            event
            for event in bus.node_state_events
            if event[0] == "chameau2_1" and event[1] == "failed"
        ]
        assert failed_updates[-1][3] == "Implement Chameau2.process_row"
        error_logs = [event for event in bus.log_events if event[0] == "ERROR"]
        assert len(error_logs) == 1
        assert error_logs[0][2] == "chameau2_1"
        assert "Implement Chameau2.process_row" in error_logs[0][1]
        assert "Remote traceback:" in error_logs[0][1]

    async def test_failed_execution_is_logged(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        import logging

        bus = RecordingEventBus()
        wf = _FakeWorkflow()
        wf.raise_exc = RuntimeError("kaboom")
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        with caplog.at_level(logging.ERROR):
            await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
            await _drain(em)
        assert any("Workflow execution failed: kaboom" in rec.message for rec in caplog.records)
        assert bus.log_events
        level, message, node_id, _timestamp = bus.log_events[-1]
        assert level == "ERROR"
        assert node_id is None
        assert "Workflow execution failed: kaboom" in message

    async def test_workflow_compute_does_not_replace_process_stdout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys

        original_stdout = sys.stdout

        class _ProbeWorkflow(_FakeWorkflow):
            stdout_was_original = False

            def compute(
                self,
                *targets: Any,
                engine: Any = None,
                run_context: Any = None,
            ) -> dict[str, Any]:
                self.stdout_was_original = sys.stdout is original_stdout
                print("stdout line")
                return {}

        bus = RecordingEventBus()
        wf = _ProbeWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)

        assert wf.stdout_was_original is True
        assert not any(event[1] == "stdout line" for event in bus.log_events)

    async def test_failed_progress_with_exception_emits_one_error_log(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(
            events=[
                _ProgressEventStub("n1", "started"),
                _ProgressEventStub("n1", "failed", message="boom"),
            ],
        )
        wf.raise_exc = RuntimeError("boom")
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)
        error_logs = [event for event in bus.log_events if event[0] == "ERROR"]
        assert len(error_logs) == 1
        assert error_logs[0][2] == "n1"

    async def test_execution_complete_event_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "completed")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)
        assert bus.complete_events
        success, errors, node_statuses = bus.complete_events[-1]
        assert success is True
        assert "n1" in node_statuses

    async def test_build_error_raises_workflow_build_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_builder(monkeypatch, None, errors=[MagicMock(detail="bad")])
        em = ExecutionManager(RecordingEventBus(), MagicMock())
        with pytest.raises(WorkflowBuildError):
            await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        assert em.state == "idle"

    async def test_validation_error_rejects_run_before_compute(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bioimageflow.validation import ValidationError

        wf = _FakeWorkflow(
            validation_errors=[
                ValidationError(
                    kind="parameter_invalid",
                    message="Input should be a valid integer",
                    node="n1",
                    field="count",
                )
            ]
        )
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock())
        prior_status = NodeStatus(
            node_id="previous",
            status="executed",
            cached=True,
        )
        prior_result = ExecutionResult(
            success=True,
            errors=[],
            node_statuses={"previous": prior_status},
        )
        prior_progress = ProgressInfo(
            node_id="previous", status="row_complete", row=1, total_rows=1
        )
        em.last_result = prior_result
        em.progress = prior_progress
        em._node_statuses = {"previous": prior_status}
        prior_context = ExecutionContext(
            execution_id="exec-prior",
            workflow_id="wf_prior",
            draft_revision=3,
        )
        em.context = prior_context

        with pytest.raises(WorkflowBuildError) as exc_info:
            await em.start(
                _graph_with([("n1", True)]),
                workflow_id="wf_rejected",
                draft_revision=4,
            )

        assert exc_info.value.errors[0].node == "n1"
        assert exc_info.value.errors[0].field == "count"
        assert wf.compute_calls == 0
        assert em.state == "idle"
        assert em.last_result is prior_result
        assert em.progress is prior_progress
        assert em._node_statuses == {"previous": prior_status}
        assert em.context is prior_context

    async def test_selected_run_ignores_only_unrelated_owned_errors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow()
        wf.nodes = {node_id: _compiled_workflow_node() for node_id in ("upstream", "selected")}
        builder = _install_fake_builder(
            monkeypatch,
            wf,
            errors=[
                GraphValidationError(
                    type="missing_tool",
                    detail="unrelated tool is unavailable",
                    node="unrelated",
                )
            ],
            project_errors=True,
        )
        em = ExecutionManager(RecordingEventBus(), MagicMock())

        context = await em.start(
            _selected_graph(),
            nodes=["selected"],
            workflow_id="wf-test",
            draft_revision=1,
        )
        await _drain(em)

        assert context.planned_node_ids == ["upstream/internal", "selected/internal"]
        assert context.planned_node_names == {
            "upstream/internal": "internal",
            "selected/internal": "internal",
        }

        assert wf.compute_calls == 1
        assert wf.targets_received == (wf.nodes["selected"],)
        assert builder.call_count == 2
        assert {node.id for node in builder.call_args_list[0].args[0].nodes} == {
            "upstream",
            "selected",
            "unrelated",
        }
        projected = builder.call_args_list[1].args[0]
        assert {node.id for node in projected.nodes} == {"upstream", "selected"}
        assert projected.nodes == _selected_graph().nodes[:2]
        assert projected.config == _selected_graph().config
        assert {edge.id for edge in projected.edges} == {"upstream_to_selected"}

    async def test_selected_projection_rechecks_accepted_draft_before_execution(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow()
        wf.nodes = {node_id: _compiled_workflow_node() for node_id in ("upstream", "selected")}
        builder = _install_fake_builder(
            monkeypatch,
            wf,
            errors=[GraphValidationError(
                type="missing_tool", detail="Unrelated unavailable tool", node="unrelated",
            )],
            project_errors=True,
        )
        manager = ExecutionManager(RecordingEventBus(), MagicMock())
        checks = 0

        async def require_current() -> None:
            nonlocal checks
            checks += 1
            if checks == 2:
                raise RuntimeError("Accepted draft changed during selected compilation")

        with pytest.raises(RuntimeError, match="Accepted draft changed"):
            await manager.start(
                _selected_graph(), nodes=["selected"], workflow_id="wf-test",
                draft_revision=1, ensure_context_current=require_current,
            )

        assert builder.call_count == checks == 2
        assert wf.compute_calls == 0
        assert manager.context is None
        assert manager._run_task is None
        assert manager.state == "idle"

    @pytest.mark.parametrize("invalid_node", ["selected", "upstream"])
    async def test_selected_run_rejects_invalid_selected_or_upstream_node_absent_from_workflow(
        self, monkeypatch: pytest.MonkeyPatch, invalid_node: str
    ) -> None:
        wf = _FakeWorkflow()
        wf.nodes = {"unrelated": _compiled_workflow_node()}
        error = GraphValidationError(
            type="missing_tool",
            detail="required tool is unavailable",
            node=invalid_node,
        )
        _install_fake_builder(monkeypatch, wf, errors=[error])
        em = ExecutionManager(RecordingEventBus(), MagicMock())

        with pytest.raises(WorkflowBuildError) as exc_info:
            await em.start(
                _selected_graph(),
                nodes=["selected"],
                workflow_id="wf-test",
                draft_revision=1,
            )

        assert exc_info.value.errors == [error]
        assert wf.compute_calls == 0

    @pytest.mark.parametrize(
        "requested",
        [[], ["unknown"], ["selected", "unknown"]],
    )
    async def test_selected_run_rejects_empty_unknown_and_mixed_targets(
        self, monkeypatch: pytest.MonkeyPatch, requested: list[str]
    ) -> None:
        wf = _FakeWorkflow()
        wf.nodes = {node_id: _compiled_workflow_node() for node_id in ("upstream", "selected")}
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock())

        with pytest.raises(WorkflowBuildError, match="Failed to build workflow"):
            await em.start(
                _selected_graph(),
                nodes=requested,
                workflow_id="wf-test",
                draft_revision=1,
            )

        assert wf.compute_calls == 0

    async def test_selected_run_rejects_requested_target_missing_from_partial_workflow(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow()
        wf.nodes = {"upstream": _compiled_workflow_node()}
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock())

        with pytest.raises(WorkflowBuildError) as exc_info:
            await em.start(
                _selected_graph(),
                nodes=["selected"],
                workflow_id="wf-test",
                draft_revision=1,
            )

        assert exc_info.value.errors[0].node == "selected"
        assert "could not be resolved" in exc_info.value.errors[0].detail
        assert wf.compute_calls == 0

    @pytest.mark.parametrize("node", ["selected/internal", "upstream/internal"])
    async def test_selected_run_rejects_errors_inside_selected_workflow_boundaries(
        self, monkeypatch: pytest.MonkeyPatch, node: str
    ) -> None:
        wf = _FakeWorkflow()
        wf.nodes = {node_id: _compiled_workflow_node() for node_id in ("upstream", "selected")}
        error = GraphValidationError(
            type="parameter_invalid",
            detail="invalid workflow descendant",
            node=node,
        )
        _install_fake_builder(monkeypatch, wf, errors=[error])
        em = ExecutionManager(RecordingEventBus(), MagicMock())

        with pytest.raises(WorkflowBuildError) as exc_info:
            await em.start(
                _selected_graph(),
                nodes=["selected"],
                workflow_id="wf-test",
                draft_revision=1,
            )

        assert exc_info.value.errors == [error]
        assert wf.compute_calls == 0

    async def test_selected_run_ignores_error_inside_unrelated_workflow_boundary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow()
        wf.nodes = {node_id: _compiled_workflow_node() for node_id in ("upstream", "selected")}
        _install_fake_builder(
            monkeypatch,
            wf,
            errors=[
                GraphValidationError(
                    type="parameter_invalid",
                    detail="invalid unrelated descendant",
                    node="unrelated/internal",
                )
            ],
            project_errors=True,
        )
        em = ExecutionManager(RecordingEventBus(), MagicMock())

        await em.start(
            _selected_graph(),
            nodes=["selected"],
            workflow_id="wf-test",
            draft_revision=1,
        )
        await _drain(em)

        assert wf.compute_calls == 1

    @pytest.mark.parametrize("node", [None, "not-a-root/internal"])
    async def test_selected_run_rejects_global_and_unowned_errors(
        self, monkeypatch: pytest.MonkeyPatch, node: str | None
    ) -> None:
        wf = _FakeWorkflow()
        wf.nodes = {node_id: _compiled_workflow_node() for node_id in ("upstream", "selected")}
        error = GraphValidationError(
            type="parameter_invalid",
            detail="unattributable error",
            node=node,
        )
        _install_fake_builder(monkeypatch, wf, errors=[error])
        em = ExecutionManager(RecordingEventBus(), MagicMock())

        with pytest.raises(WorkflowBuildError) as exc_info:
            await em.start(
                _selected_graph(),
                nodes=["selected"],
                workflow_id="wf-test",
                draft_revision=1,
            )

        assert exc_info.value.errors == [error]
        assert wf.compute_calls == 0

    @pytest.mark.parametrize("dangling_endpoint", ["source", "target"])
    async def test_selected_run_preserves_dangling_edge_validation_error(
        self, monkeypatch: pytest.MonkeyPatch, dangling_endpoint: str
    ) -> None:
        graph = _selected_graph()
        edge = DataFrameEdge.model_construct(
            type="dataframe",
            id=f"dangling_{dangling_endpoint}",
            source_node="missing" if dangling_endpoint == "source" else "upstream",
            target_node="missing" if dangling_endpoint == "target" else "selected",
            target_position=0,
            target_input=None,
        )
        graph.edges.append(edge)
        wf = _FakeWorkflow()
        wf.nodes = {node_id: _compiled_workflow_node() for node_id in ("upstream", "selected")}
        error = GraphValidationError(
            type="invalid_edge_id",
            detail=f"Edge has an unknown {dangling_endpoint} endpoint",
            edge_id=edge.id,
        )
        _install_fake_builder(monkeypatch, wf, errors=[error])
        em = ExecutionManager(RecordingEventBus(), MagicMock())

        with pytest.raises(WorkflowBuildError) as exc_info:
            await em.start(
                graph,
                nodes=["selected"],
                workflow_id="wf-test",
                draft_revision=1,
            )

        assert exc_info.value.errors == [error]
        assert wf.compute_calls == 0

    async def test_selected_run_rejects_missing_compiled_workflow_after_filtering(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_builder(
            monkeypatch,
            None,
            errors=[
                GraphValidationError(
                    type="missing_tool",
                    detail="unrelated tool is unavailable",
                    node="unrelated",
                )
            ],
        )
        em = ExecutionManager(RecordingEventBus(), MagicMock())

        with pytest.raises(WorkflowBuildError) as exc_info:
            await em.start(
                _selected_graph(),
                nodes=["selected"],
                workflow_id="wf-test",
                draft_revision=1,
            )

        assert exc_info.value.errors[0].node is None
        assert "did not produce" in exc_info.value.errors[0].detail

    async def test_disabled_nodes_seeded_as_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        wf = _FakeWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock())
        await em.start(
            _graph_with([("n1", True), ("n2", False)]), workflow_id="wf-test", draft_revision=1
        )
        await _drain(em)
        assert em._node_statuses["n2"].status == "disabled"
        assert em._node_statuses["n2"].cached is False

    async def test_cancelled_error_preserves_executed_nodes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bioimageflow.engine import WorkflowCancelledError

        bus = RecordingEventBus()
        wf = _FakeWorkflow(
            events=[
                _ProgressEventStub("n1", "completed"),
                _ProgressEventStub("n2", "cancelled"),
            ],
        )
        wf.raise_exc = WorkflowCancelledError("cancelled")
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        await em.start(
            _graph_with([("n1", True), ("n2", True)]), workflow_id="wf-test", draft_revision=1
        )
        await _drain(em)
        assert em._node_statuses["n1"].status == "executed"
        assert em._node_statuses["n2"].status == "unexecuted"


class TestExecutionManagerStop:
    async def test_close_refuses_queued_idle_mutation(self) -> None:
        manager = ExecutionManager(RecordingEventBus(), MagicMock())
        closing_started, mutation_started = asyncio.Event(), asyncio.Event()
        admitted = False

        async def close() -> None:
            closing_started.set()
            await manager.close()

        async def mutate() -> None:
            nonlocal admitted
            mutation_started.set()
            async with manager.exclusive_idle_mutation():
                admitted = True

        async with manager._preparation_lock:
            closing = asyncio.create_task(close())
            await closing_started.wait()
            mutation = asyncio.create_task(mutate())
            await mutation_started.wait()
            assert not closing.done() and not mutation.done()
        with pytest.raises(ExecutionConflictError, match="shutting down"):
            await mutation
        await closing
        assert not admitted and not manager.is_running
        await manager.close()
        with pytest.raises(ExecutionConflictError, match="shutting down"):
            async with manager.exclusive_idle_mutation():
                admitted = True

    async def test_close_refuses_queued_execution_reservation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        wf = _FakeWorkflow()
        _install_fake_builder(monkeypatch, wf)
        manager = ExecutionManager(RecordingEventBus(), MagicMock())
        closing_started = asyncio.Event()
        reservation_started = asyncio.Event()

        async def close() -> None:
            closing_started.set()
            await manager.close()

        async def start() -> None:
            reservation_started.set()
            await manager.start(_graph_with([("n1", True)]), workflow_id="wf", draft_revision=1)

        # Instrument the admission gate directly: both operations must queue
        # before close sets the terminal fence, with close first in the queue.
        async with manager._preparation_lock:
            closing = asyncio.create_task(close())
            await closing_started.wait()
            reservation = asyncio.create_task(start())
            await reservation_started.wait()
            assert not closing.done() and not reservation.done()
        with pytest.raises(ExecutionConflictError, match="shutting down"):
            await reservation
        await closing
        assert wf.compute_calls == 0
        assert manager._run_task is None and manager.context is None
        await manager.close()  # Cleanup retries do not reopen admission.

    async def test_stop_while_idle_is_noop(self) -> None:
        em = ExecutionManager(RecordingEventBus(), MagicMock())
        await em.stop()  # no error

    async def test_stop_cancels_running_workflow(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from bioimageflow.engine import WorkflowCancelledError

        class _CancellableWorkflow(_FakeWorkflow):
            def __init__(self) -> None:
                super().__init__()
                self._go = threading.Event()

            def compute(
                self,
                *targets: Any,
                engine: Any = None,
                run_context: Any = None,
            ) -> dict[str, Any]:
                self._go.wait(timeout=5.0)
                if self.cancel_called:
                    raise WorkflowCancelledError("cancelled")
                return {}

            def cancel(self) -> None:
                super().cancel()
                self._go.set()

        wf = _CancellableWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await asyncio.sleep(0.01)
        await em.stop()
        assert wf.cancel_called is True
        await _drain(em)
        assert em.state == "idle"

    async def test_stop_request_is_published_as_backend_log(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _CancellableWorkflow(_FakeWorkflow):
            def __init__(self) -> None:
                super().__init__()
                self._go = threading.Event()

            def compute(
                self,
                *targets: Any,
                engine: Any = None,
                run_context: Any = None,
            ) -> dict[str, Any]:
                self._go.wait(timeout=5.0)
                return {}

            def cancel(self) -> None:
                super().cancel()
                self._go.set()

        bus = RecordingEventBus()
        wf = _CancellableWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await asyncio.sleep(0.01)
        await em.stop()
        await _drain(em)

        assert any(
            event[0] == "INFO" and event[1] == "Execution stop requested"
            for event in bus.log_events
        )


class TestExecutionManagerStatus:
    async def test_get_status_idle(self) -> None:
        em = ExecutionManager(RecordingEventBus(), MagicMock())
        status = em.get_status()
        assert status.state == "idle"
        assert status.last_result is None
        assert status.progress is None

    async def test_get_status_after_run_includes_node_statuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "completed")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        await _drain(em)
        status = em.get_status()
        assert status.state == "idle"
        assert status.last_result is not None
        assert hasattr(status, "node_statuses")
        assert "n1" in getattr(status, "node_statuses")


class TestExecutionManagerIsRunning:
    async def test_is_running_true_while_executing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _BlockWorkflow(_FakeWorkflow):
            def __init__(self) -> None:
                super().__init__()
                self.go = threading.Event()

            def compute(
                self,
                *targets: Any,
                engine: Any = None,
                run_context: Any = None,
            ) -> dict[str, Any]:
                self.go.wait(timeout=2.0)
                return {}

        wf = _BlockWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test", draft_revision=1)
        assert em.is_running is True
        wf.go.set()
        await _drain(em)
        assert em.is_running is False


class TestExecutionManagerStoragePath:
    async def test_start_passes_per_run_storage_path_to_builder(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow()
        builder = _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(
            RecordingEventBus(),
            MagicMock(),
            storage_path=None,
        )
        await em.start(
            _graph_with([("n1", True)]),
            storage_path=Path("/tmp/workflows/wf_a"),
            workflow_id="wf-test",
            draft_revision=1,
        )
        await _drain(em)
        assert builder.call_args.kwargs["storage_path"] == Path("/tmp/workflows/wf_a")

    async def test_start_always_compiles_the_request_graph(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow()
        builder = _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(
            RecordingEventBus(),
            MagicMock(),
        )

        await em.start(
            _graph_with([("n1", True)]),
            storage_path=Path("/tmp/workflows/new"),
            workflow_id="wf-test",
            draft_revision=1,
        )
        await _drain(em)

        assert builder.call_args.args[0].nodes[0].id == "n1"
        assert builder.call_args.kwargs["storage_path"] == Path("/tmp/workflows/new")


class TestExecutionRetryIntent:
    def test_retry_reuses_original_targets(self) -> None:
        manager = ExecutionManager(RecordingEventBus(), MagicMock())
        manager.context = ExecutionContext(
            execution_id="failed-run",
            workflow_id="wf-test",
            draft_revision=1,
            requested_nodes=["selected"],
        )
        manager.last_result = ExecutionResult(success=False)

        nodes = manager.resolve_requested_nodes(
            mode="retry",
            workflow_id="wf-test",
            requested_nodes=None,
            retry_of_execution_id="failed-run",
        )

        assert nodes == ["selected"]

    def test_retry_rejects_a_different_or_successful_execution(self) -> None:
        manager = ExecutionManager(RecordingEventBus(), MagicMock())
        manager.context = ExecutionContext(
            execution_id="successful-run",
            workflow_id="wf-test",
            draft_revision=1,
        )
        manager.last_result = ExecutionResult(success=True)

        with pytest.raises(ExecutionRetryError, match="latest failed execution"):
            manager.resolve_requested_nodes(
                mode="retry",
                workflow_id="wf-test",
                requested_nodes=None,
                retry_of_execution_id="successful-run",
            )

    async def test_status_retains_execution_intent_while_idle(self) -> None:
        manager = ExecutionManager(RecordingEventBus(), MagicMock())
        manager.context = ExecutionContext(
            execution_id="failed-run",
            workflow_id="wf-test",
            draft_revision=1,
            requested_nodes=["selected"],
        )
        manager.last_result = ExecutionResult(success=False)
        async with manager.reserve_start(
            "wf-test",
            4,
            mode="invalidate_failed",
            requested_nodes=None,
            retry_of_execution_id="failed-run",
        ) as context:
            manager.context = context
        manager.last_result = ExecutionResult(success=False)

        status = manager.get_status()

        assert status.mode == "invalidate_failed"
        assert status.requested_nodes == ["selected"]
        assert status.retry_of_execution_id == "failed-run"
