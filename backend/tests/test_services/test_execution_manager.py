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
from typing import Any
from unittest.mock import MagicMock

import pytest

from bioimageflow_server.models.graph import GraphState, NodeState
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.services import execution as execution_module
from bioimageflow_server.services.execution import (
    ExecutionConflictError,
    ExecutionEventBus,
    ExecutionManager,
    NullEventBus,
    WorkflowBuildError,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ---- B1: NullEventBus -------------------------------------------------------


class TestNullEventBus:
    def test_publish_progress_accepts_five_args(self) -> None:
        bus = NullEventBus()
        bus.publish_progress("n1", "row_complete", 1, 10, 123.0)

    def test_publish_node_state_accepts_five_args(self) -> None:
        bus = NullEventBus()
        bus.publish_node_state("n1", "running", False, None, None)

    def test_publish_execution_complete_accepts_three_args(self) -> None:
        bus = NullEventBus()
        bus.publish_execution_complete(True, [], {})

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
        self.complete_events: list[tuple[bool, list, dict]] = []

    def publish_progress(
        self, node_id: str, status: str, row: int, total_rows: int, timestamp: float
    ) -> None:
        self.progress_events.append((node_id, status, row, total_rows, timestamp))

    def publish_node_state(
        self,
        node_id: str,
        status: str,
        cached: bool,
        error: str | None = None,
        traceback: str | None = None,
    ) -> None:
        self.node_state_events.append((node_id, status, cached, error, traceback))

    def publish_execution_complete(
        self, success: bool, errors: list, node_statuses: dict
    ) -> None:
        self.complete_events.append((success, errors, node_statuses))


@dataclass
class _ProgressEventStub:
    node_name: str
    status: str
    row: int = 0
    total_rows: int = 0
    message: str | None = None
    current: int | None = None
    maximum: int | None = None
    timestamp: float = 0.0


class _FakeWorkflow:
    """Minimal stand-in for ``bioimageflow.Workflow``."""

    def __init__(self, on_progress: Any = None, events: list | None = None) -> None:
        self.on_progress = on_progress
        self.events = events or []
        self.raise_exc: BaseException | None = None
        self.compute_calls = 0
        self.cancel_called = False
        self.targets_received: tuple = ()
        self.dev_mode_received: bool | None = None

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
    """Replace ``graph_builder.build_workflow`` with a fake returning ``workflow``."""
    result = MagicMock()
    result.workflow = workflow
    result.errors = errors or []
    result.disabled_node_ids = set()

    def _builder(graph, registry, storage_path=None, on_progress=None):
        # Wire the progress callback into the fake workflow so scripted
        # events are delivered through it.
        if workflow is not None:
            workflow.on_progress = on_progress
        return result

    mock = MagicMock(side_effect=_builder)
    monkeypatch.setattr(execution_module, "build_workflow", mock)
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
        await em.start(_graph_with([("n1", True)]))
        assert em.state == "running"
        await _drain(em)
        assert em.state == "idle"
        assert em.is_running is False
        assert em.last_result is not None
        assert em.last_result.success is True

    async def test_start_clears_previous_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]))
        await _drain(em)
        assert em.last_result is not None
        wf2 = _FakeWorkflow()
        _install_fake_builder(monkeypatch, wf2)
        # progress should reset immediately upon next start
        await em.start(_graph_with([("n1", True)]))
        assert em.progress is None
        await _drain(em)

    async def test_concurrent_start_raises_conflict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
        await em.start(_graph_with([("n1", True)]))
        with pytest.raises(ExecutionConflictError):
            await em.start(_graph_with([("n1", True)]))
        wf.go.set()
        await _drain(em, timeout=3.0)

    async def test_rapid_double_start_second_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]))
        with pytest.raises(ExecutionConflictError):
            await em.start(_graph_with([("n1", True)]))
        await _drain(em)


class TestExecutionManagerProgress:
    async def test_started_publishes_running_and_accumulates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "started")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]))
        await _drain(em)
        assert ("n1", "running", False, None, None) in bus.node_state_events
        n1_states = [e for e in bus.node_state_events if e[0] == "n1"]
        assert n1_states[0][1] == "running"

    async def test_row_progress_updates_progress_ref_no_node_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(
            events=[
                _ProgressEventStub(
                    "n1", "row_progress", current=3, maximum=10, timestamp=1.0
                )
            ]
        )
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]))
        await _drain(em)
        assert any(
            e[0] == "n1" and e[1] == "row_progress" and e[2] == 3 and e[3] == 10
            for e in bus.progress_events
        )
        assert not any(
            e[0] == "n1" and e[1] == "row_progress" for e in bus.node_state_events
        )

    async def test_row_complete_emits_progress_and_updates_ref(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(
            events=[
                _ProgressEventStub(
                    "n1", "row_complete", row=2, total_rows=5, timestamp=2.0
                )
            ]
        )
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]))
        await _drain(em)
        assert em.progress is not None
        assert em.progress.row == 2
        assert em.progress.total_rows == 5
        assert any(
            e[1] == "row_complete" and e[2] == 2 and e[3] == 5
            for e in bus.progress_events
        )
        assert not any(e[1] == "row_complete" for e in bus.node_state_events)

    async def test_completed_publishes_executed_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "completed")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]))
        await _drain(em)
        assert ("n1", "executed", False, None, None) in bus.node_state_events
        assert em._node_statuses["n1"].status == "executed"
        assert em._node_statuses["n1"].cached is False

    async def test_cached_publishes_executed_with_cached_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "cached")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]))
        await _drain(em)
        assert ("n1", "executed", True, None, None) in bus.node_state_events
        assert em._node_statuses["n1"].cached is True

    async def test_failed_publishes_failed_state_with_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(
            events=[_ProgressEventStub("n1", "failed", message="boom")],
        )
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]))
        await _drain(em)
        n1_failed = [e for e in bus.node_state_events if e[0] == "n1" and e[1] == "failed"]
        assert n1_failed
        assert em._node_statuses["n1"].status == "failed"

    async def test_cancelled_publishes_unexecuted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "cancelled")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]))
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
            await em.start(_graph_with([("n1", True)]))
            await _drain(em)
        assert em.state == "idle"
        assert not any(e[1] == "future_status" for e in bus.node_state_events)


class TestExecutionManagerResult:
    async def test_success_populates_last_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "completed")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]))
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
        await em.start(_graph_with([("n1", True)]))
        await _drain(em)
        assert em.last_result is not None
        assert em.last_result.success is False
        assert em.last_result.errors
        assert "kaboom" in str(em.last_result.errors[0])

    async def test_execution_complete_event_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bus = RecordingEventBus()
        wf = _FakeWorkflow(events=[_ProgressEventStub("n1", "completed")])
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(bus, MagicMock(), _settings())
        await em.start(_graph_with([("n1", True)]))
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
            await em.start(_graph_with([("n1", True)]))
        assert em.state == "idle"

    async def test_disabled_nodes_seeded_as_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wf = _FakeWorkflow()
        _install_fake_builder(monkeypatch, wf)
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        await em.start(_graph_with([("n1", True), ("n2", False)]))
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
        await em.start(_graph_with([("n1", True), ("n2", True)]))
        await _drain(em)
        assert em._node_statuses["n1"].status == "executed"
        assert em._node_statuses["n2"].status == "unexecuted"


class TestExecutionManagerStop:
    async def test_stop_while_idle_is_noop(self) -> None:
        em = ExecutionManager(RecordingEventBus(), MagicMock(), _settings())
        await em.stop()  # no error

    async def test_stop_cancels_running_workflow(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
        await em.start(_graph_with([("n1", True)]))
        await asyncio.sleep(0.01)
        await em.stop()
        assert wf.cancel_called is True
        await _drain(em)
        assert em.state == "idle"


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
        await em.start(_graph_with([("n1", True)]))
        await _drain(em)
        status = em.get_status()
        assert status.state == "idle"
        assert status.last_result is not None
        assert hasattr(status, "node_statuses")
        assert "n1" in getattr(status, "node_statuses")


class TestExecutionManagerIsRunning:
    async def test_is_running_true_while_executing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
        await em.start(_graph_with([("n1", True)]))
        assert em.is_running is True
        wf.go.set()
        await _drain(em)
        assert em.is_running is False
