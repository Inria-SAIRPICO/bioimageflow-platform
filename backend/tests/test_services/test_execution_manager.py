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
from typing import Any
from unittest.mock import MagicMock

import pytest
from wetlands.exceptions import EnvironmentReuseError

from bioimageflow_server.models.execution import (
    ExecutionContext,
    ExecutionResult,
    ProgressInfo,
)
from bioimageflow_server.models.graph import ColumnRefEdge, GraphState, NodeState
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.validation import NodeStatus
from bioimageflow_server.services.execution import (
    ExecutionConflictError,
    ExecutionEventBus,
    ExecutionManager,
    NullEventBus,
    WorkflowBuildError,
)

pytestmark = pytest.mark.anyio

_TEST_CONTEXT = ExecutionContext(
    execution_id="exec-test",
    workflow_id="wf-test",
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
        self.validation_errors = validation_errors or []
        self.raise_exc: BaseException | None = None
        self.compute_calls = 0
        self.cancel_called = False
        self.targets_received: tuple = ()
        self.dev_mode_received: bool | None = None

    def validate(self, *, dev_mode: bool = True) -> list:
        return list(self.validation_errors)

    def plan(self, *, dev_mode: bool = True) -> dict:
        return {}

    def compute(self, *targets: Any, dev_mode: bool = False) -> dict[str, Any]:
        self.compute_calls += 1
        self.targets_received = targets
        self.dev_mode_received = dev_mode
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
        self._envs: dict[str, object] = {}
        self.calls: list[str] = []
        self.raise_exc: BaseException | None = None

    def get_or_create(self, env_spec: _EnvSpecStub) -> object:
        self.calls.append(env_spec.name)
        if self.raise_exc is not None:
            raise self.raise_exc
        env = object()
        self._envs[env_spec.name] = env
        return env

    def shutdown_all(self) -> None:
        self._envs.clear()


def _settings(dev_mode: bool = True) -> Settings:
    return Settings(
        deployment_mode="desktop",
        output_data_folder="/tmp/bif",
        dev_mode=dev_mode,
    )


def _graph_with(nodes: list[tuple[str, bool]] | None = None) -> GraphState:
    if nodes is None:
        nodes = []
    return GraphState(
        nodes=[
            NodeState(
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


def _install_fake_builder(
    monkeypatch: pytest.MonkeyPatch,
    workflow: _FakeWorkflow | None,
    errors: list | None = None,
) -> MagicMock:
    """Replace request-local compilation with a fake ``BuildOutput``."""
    from bioimageflow_server.services.graph_builder import BuildOutput
    from bioimageflow_server.services.graph_compiler import GraphCompiler

    def _builder(graph, *, storage_path=None, on_progress=None, settings=None):
        # Wire the progress callback into the fake workflow so scripted
        # events are delivered through it.
        if workflow is not None:
            workflow.on_progress = on_progress
        return BuildOutput(
            workflow=workflow,
            errors=errors or [],
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


# ---- B2: ExecutionManager ---------------------------------------------------


class TestExecutionManagerLifecycle:
    async def test_idle_state_initially(self) -> None:
        em = ExecutionManager(NullEventBus(), MagicMock(), _settings())
        assert em.state == "idle"
        assert em.is_running is False
        assert em.last_result is None
        assert em.progress is None

    async def test_start_sets_running_then_idle_on_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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
        em = ExecutionManager(bus, MagicMock(), _settings())

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
        em = ExecutionManager(bus, MagicMock(), _settings())

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

    async def test_execution_publishes_environment_status_from_wetlands_start(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _WorkflowWithWetlands(_FakeWorkflow):
            def __init__(self) -> None:
                super().__init__()
                self.private_manager = _FakeWetlandsManager()

            def _make_engine(self) -> Any:
                return type("Engine", (), {"_env_manager": self.private_manager})()

            def compute(
                self,
                *targets: Any,
                dev_mode: bool = False,
                engine: Any = None,
            ) -> dict[str, Any]:
                try:
                    engine._env_manager.get_or_create(_EnvSpecStub("cellpose-env"))
                    return super().compute(*targets, dev_mode=dev_mode)
                finally:
                    engine._env_manager.shutdown_all()

        bus = RecordingEventBus()
        wf = _WorkflowWithWetlands()
        shared_manager = _FakeWetlandsManager()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(
            bus,
            MagicMock(),
            _settings(),
            environment_manager_provider=lambda: shared_manager,
        )

        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
        await _drain(em)

        assert wf.private_manager.calls == []
        assert shared_manager.calls == ["cellpose-env"]
        assert bus.environment_events == [
            ("cellpose-env", "creating"),
            ("cellpose-env", "running"),
            ("cellpose-env", "stopped"),
        ]

    async def test_execution_marks_environment_stopped_when_wetlands_start_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _WorkflowWithFailingWetlands(_FakeWorkflow):
            def __init__(self) -> None:
                super().__init__()
                self.manager = _FakeWetlandsManager()
                self.manager.raise_exc = RuntimeError("solve failed")
                self._engine = type("Engine", (), {"_env_manager": self.manager})()

            def compute(self, *targets: Any, dev_mode: bool = False) -> dict[str, Any]:
                self._engine._env_manager.get_or_create(_EnvSpecStub("cellpose-env"))
                return {}

        bus = RecordingEventBus()
        wf = _WorkflowWithFailingWetlands()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock(), _settings())

        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
        await _drain(em)

        assert bus.environment_events == [
            ("cellpose-env", "creating"),
            ("cellpose-env", "stopped"),
        ]

    async def test_start_clears_previous_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        wf = _FakeWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
        await _drain(em)
        assert em.last_result is not None
        wf2 = _FakeWorkflow()
        _install_fake_builder(monkeypatch, wf2)
        # progress should reset immediately upon next start
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
        assert em.progress is None
        await _drain(em)

    async def test_concurrent_start_raises_conflict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _BlockingWorkflow(_FakeWorkflow):
            def __init__(self) -> None:
                super().__init__()
                self.go = threading.Event()

            def compute(self, *targets: Any, dev_mode: bool = False) -> dict[str, Any]:
                self.go.wait(timeout=3.0)
                return {}

        wf = _BlockingWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
        with pytest.raises(ExecutionConflictError):
            await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        prior_context = ExecutionContext(
            execution_id="prior-execution",
            workflow_id="prior-workflow",
            draft_revision=3,
        )
        em.context = prior_context
        prior_result = ExecutionResult(success=True)
        prior_progress = ProgressInfo(node_id="prior-node", row=1, total_rows=1)
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
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
        with pytest.raises(ExecutionConflictError):
            await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
        await _drain(em)

    async def test_idle_mutation_lease_blocks_run_without_reporting_starting(self) -> None:
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())

        async with em.exclusive_idle_mutation():
            assert em.is_running is True
            status = em.get_status()
            assert status.state == "idle"
            assert status.execution_id is None
            with pytest.raises(ExecutionConflictError):
                await em.start(
                    _graph_with([("n1", True)]),
                    workflow_id="wf-test",
                )

        assert em.is_running is False

    async def test_run_selected_builds_only_selected_nodes_and_upstream(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow()
        wf.nodes = {node_id: object() for node_id in ["source", "selected"]}
        builder = _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        graph = GraphState(
            nodes=[
                NodeState(
                    id=node_id,
                    name=node_id,
                    tool_name="tool",
                    position=(0.0, 0.0),
                    parameters={},
                )
                for node_id in ["source", "selected", "downstream"]
            ],
            edges=[
                ColumnRefEdge(
                    id="e1",
                    source_node="source",
                    target_node="selected",
                    source_output="out",
                    target_input="in",
                ),
                ColumnRefEdge(
                    id="e2",
                    source_node="selected",
                    target_node="downstream",
                    source_output="out",
                    target_input="in",
                ),
            ],
        )

        await em.start(graph, nodes=["selected"], workflow_id="wf-test")
        await _drain(em)

        built_graph = builder.call_args.args[0]
        assert {node.id for node in built_graph.nodes} == {"source", "selected"}
        assert [edge.id for edge in built_graph.edges] == ["e1"]


class TestExecutionManagerProgress:
    async def test_started_publishes_running_and_accumulates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "started")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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
            events=[_ProgressEventStub("n1", "row_progress", current=3, maximum=10, timestamp=1.0)]
        )
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
        await _drain(em)
        assert any(
            e[0] == "n1" and e[1] == "row_progress" and e[2] == 3 and e[3] == 10
            for e in bus.progress_events
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
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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
        em = ExecutionManager(bus, MagicMock(), _settings())
        with caplog.at_level(logging.WARNING):
            await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
            await _drain(em)
        assert em.state == "idle"
        assert not any(e[1] == "future_status" for e in bus.node_state_events)


class TestExecutionManagerResult:
    async def test_success_populates_last_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "completed")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
        await _drain(em)
        assert em.last_result is not None
        assert em.last_result.success is False
        assert em.last_result.errors
        assert "kaboom" in str(em.last_result.errors[0])

    async def test_environment_recipe_mismatch_adds_recovery_action(
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
        em = ExecutionManager(bus, MagicMock(), _settings())

        await em.start(_graph_with([("cellpose_1", True)]), workflow_id="wf-test")
        await _drain(em)

        assert em.last_result is not None
        assert em.last_result.success is False
        error = em.last_result.errors[0]
        assert error["type"] == "EnvironmentReuseError"
        assert error["detail"].startswith("Environment 'segmentation-cellpose-v3' already exists")
        assert error["recovery_action"] == {
            "kind": "delete_environment",
            "env_name": "segmentation-cellpose-v3",
            "path": "/Users/amasson/.bioimageflow/wetlands/pixi/workspaces/segmentation-cellpose-v3/pixi.toml",
            "existing_hash": "sha256:12825e7c20f47da18ba92c11cb9179dd2df35fbb6b4f54050c157abbc1a3425f",
            "requested_hash": "sha256:61bc60ebf72d2fe1c24c29f363954fd68100ece113ccaa80b5beea5605b867ce",
        }

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
        em = ExecutionManager(bus, MagicMock(), _settings())

        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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
        em = ExecutionManager(bus, MagicMock(), _settings())

        await em.start(_graph_with([("atlas_1", True)]), workflow_id="wf-test")
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
        em = ExecutionManager(bus, MagicMock(), _settings())

        await em.start(_graph_with([("chameau2_1", True)]), workflow_id="wf-test")
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
        em = ExecutionManager(bus, MagicMock(), _settings())
        with caplog.at_level(logging.ERROR):
            await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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

            def compute(self, *targets: Any, dev_mode: bool = False) -> dict[str, Any]:
                self.stdout_was_original = sys.stdout is original_stdout
                print("stdout line")
                return {}

        bus = RecordingEventBus()
        wf = _ProbeWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
        await _drain(em)
        error_logs = [event for event in bus.log_events if event[0] == "ERROR"]
        assert len(error_logs) == 1
        assert error_logs[0][2] == "n1"

    async def test_execution_complete_event_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "completed")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
        await _drain(em)
        assert bus.complete_events
        success, errors, node_statuses = bus.complete_events[-1]
        assert success is True
        assert "n1" in node_statuses

    async def test_build_error_raises_workflow_build_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_builder(monkeypatch, None, errors=[MagicMock(detail="bad")])
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        with pytest.raises(WorkflowBuildError):
            await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
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
        prior_progress = ProgressInfo(node_id="previous", row=1, total_rows=1)
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

    async def test_disabled_nodes_seeded_as_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        wf = _FakeWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        await em.start(_graph_with([("n1", True), ("n2", False)]), workflow_id="wf-test")
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
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True), ("n2", True)]), workflow_id="wf-test")
        await _drain(em)
        assert em._node_statuses["n1"].status == "executed"
        assert em._node_statuses["n2"].status == "unexecuted"


class TestExecutionManagerStop:
    async def test_stop_while_idle_is_noop(self) -> None:
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        await em.stop()  # no error

    async def test_stop_cancels_running_workflow(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from bioimageflow.engine import WorkflowCancelledError

        class _CancellableWorkflow(_FakeWorkflow):
            def __init__(self) -> None:
                super().__init__()
                self._go = threading.Event()

            def compute(self, *targets: Any, dev_mode: bool = False) -> dict[str, Any]:
                self._go.wait(timeout=5.0)
                if self.cancel_called:
                    raise WorkflowCancelledError("cancelled")
                return {}

            def cancel(self) -> None:
                super().cancel()
                self._go.set()

        wf = _CancellableWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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

            def compute(self, *targets: Any, dev_mode: bool = False) -> dict[str, Any]:
                self._go.wait(timeout=5.0)
                return {}

            def cancel(self) -> None:
                super().cancel()
                self._go.set()

        bus = RecordingEventBus()
        wf = _CancellableWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
        await asyncio.sleep(0.01)
        await em.stop()
        await _drain(em)

        assert any(
            event[0] == "INFO" and event[1] == "Execution stop requested"
            for event in bus.log_events
        )


class TestExecutionManagerStatus:
    async def test_get_status_idle(self) -> None:
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        status = em.get_status()
        assert status.state == "idle"
        assert status.last_result is None
        assert status.progress is None

    async def test_get_status_after_run_includes_node_statuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "completed")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
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

            def compute(self, *targets: Any, dev_mode: bool = False) -> dict[str, Any]:
                self.go.wait(timeout=2.0)
                return {}

        wf = _BlockWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
        assert em.is_running is True
        wf.go.set()
        await _drain(em)
        assert em.is_running is False


class TestExecutionManagerSettingsProvider:
    async def test_provider_overrides_snapshot_dev_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow()
        _install_fake_builder(monkeypatch, wf)
        # Snapshot says dev_mode=True; live provider returns False.
        em = ExecutionManager(
            RecordingEventBus(),
            MagicMock(),
            _settings(dev_mode=True),
            settings_provider=lambda: _settings(dev_mode=False),
        )
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
        await _drain(em)
        assert wf.compute_calls == 1
        assert wf.dev_mode_received is False

    async def test_no_provider_uses_snapshot(self, monkeypatch: pytest.MonkeyPatch) -> None:
        wf = _FakeWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings(dev_mode=True))
        await em.start(_graph_with([("n1", True)]), workflow_id="wf-test")
        await _drain(em)
        assert wf.compute_calls == 1
        assert wf.dev_mode_received is True


class TestExecutionManagerStoragePath:
    async def test_start_passes_per_run_storage_path_to_builder(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow()
        builder = _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(
            RecordingEventBus(),
            MagicMock(),
            _settings(),
            storage_path=None,
        )
        await em.start(
            _graph_with([("n1", True)]),
            storage_path=Path("/tmp/workflows/wf_a"),
            workflow_id="wf-test",
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
            _settings(),
        )

        await em.start(
            _graph_with([("n1", True)]),
            storage_path=Path("/tmp/workflows/new"),
            workflow_id="wf-test",
        )
        await _drain(em)

        assert builder.call_args.args[0].nodes[0].id == "n1"
        assert builder.call_args.kwargs["storage_path"] == Path("/tmp/workflows/new")
