"""Tests for the WebSocket logging bridge."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _StubManager:
    """Stub ConnectionManager exposing only what the bridge needs."""

    def __init__(self) -> None:
        self.broadcast_calls: list[tuple[Any, ...]] = []

    async def broadcast_log(
        self,
        level: str,
        message: str,
        node_id: str | None,
        timestamp: float,
        *,
        context: Any | None = None,
    ) -> None:
        self.broadcast_calls.append((level, message, node_id, timestamp, context))


def _remove_handler(logger_name: str, handler: logging.Handler) -> None:
    logger = logging.getLogger(logger_name)
    if handler in logger.handlers:
        logger.removeHandler(handler)


async def test_extracts_node_id_from_logger_name() -> None:
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    loop = asyncio.get_running_loop()
    handler = WebSocketLogHandler(mgr, loop=loop)

    record = logging.getLogger("bioimageflow.node.segmenter_1").makeRecord(
        "bioimageflow.node.segmenter_1",
        logging.INFO,
        "f",
        10,
        "msg",
        None,
        None,
    )
    handler.emit(record)

    # Give the scheduled coroutine a chance to run
    for _ in range(20):
        await asyncio.sleep(0.01)
        if mgr.broadcast_calls:
            break

    assert len(mgr.broadcast_calls) == 1
    level, message, node_id, _, _ = mgr.broadcast_calls[0]
    assert level == "INFO"
    assert message == "msg"
    assert node_id == "segmenter_1"


async def test_node_id_none_for_non_node_logger() -> None:
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    loop = asyncio.get_running_loop()
    handler = WebSocketLogHandler(mgr, loop=loop)

    record = logging.getLogger("bioimageflow.engine").makeRecord(
        "bioimageflow.engine",
        logging.WARNING,
        "f",
        10,
        "engine msg",
        None,
        None,
    )
    handler.emit(record)

    for _ in range(20):
        await asyncio.sleep(0.01)
        if mgr.broadcast_calls:
            break

    assert mgr.broadcast_calls[0][2] is None
    assert mgr.broadcast_calls[0][0] == "WARNING"


async def test_execution_context_is_attached_only_while_bound() -> None:
    from bioimageflow_server.models.execution import ExecutionContext
    from bioimageflow_server.services.log_context import bind_execution_log_context
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    handler = WebSocketLogHandler(mgr, loop=asyncio.get_running_loop())
    context = ExecutionContext(
        execution_id="exec-a",
        workflow_id="workflow-a",
        draft_revision=4,
    )
    logger = logging.getLogger("bioimageflow.node.shared")

    with bind_execution_log_context(context):
        handler.emit(logger.makeRecord(logger.name, logging.INFO, "f", 1, "bound", None, None))
    handler.emit(logger.makeRecord(logger.name, logging.INFO, "f", 2, "global", None, None))

    for _ in range(20):
        await asyncio.sleep(0.01)
        if len(mgr.broadcast_calls) == 2:
            break

    assert mgr.broadcast_calls[0][4] == context
    assert mgr.broadcast_calls[1][4] is None


async def test_bound_execution_context_reaches_engine_worker_threads() -> None:
    from bioimageflow_server.models.execution import ExecutionContext
    from bioimageflow_server.services.log_context import bind_execution_log_context
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    handler = WebSocketLogHandler(mgr, loop=asyncio.get_running_loop())
    context = ExecutionContext(
        execution_id="exec-threaded",
        workflow_id="workflow-threaded",
        draft_revision=2,
    )
    logger = logging.getLogger("bioimageflow.node.shared")

    with bind_execution_log_context(context):
        worker = threading.Thread(
            target=lambda: handler.emit(
                logger.makeRecord(logger.name, logging.INFO, "f", 1, "threaded", None, None)
            )
        )
        worker.start()
        worker.join(timeout=1.0)

    for _ in range(20):
        await asyncio.sleep(0.01)
        if mgr.broadcast_calls:
            break

    assert mgr.broadcast_calls[0][4] == context


async def test_wetlands_environment_log_stays_global_during_execution() -> None:
    from bioimageflow_server.models.execution import ExecutionContext
    from bioimageflow_server.services.log_context import bind_execution_log_context
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    handler = WebSocketLogHandler(mgr, loop=asyncio.get_running_loop())
    context = ExecutionContext(
        execution_id="exec-a",
        workflow_id="workflow-a",
        draft_revision=1,
    )
    logger = logging.getLogger("wetlands.environment")
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        "f",
        1,
        "environment ready",
        None,
        None,
        extra={"log_source": "environment", "env_name": "tool-env"},
    )

    with bind_execution_log_context(context):
        handler.emit(record)

    for _ in range(20):
        await asyncio.sleep(0.01)
        if mgr.broadcast_calls:
            break

    assert mgr.broadcast_calls[0][4] is None


@pytest.mark.parametrize(
    ("logger_name", "message"),
    [
        ("bioimageflow", "environment created"),
        ("bioimageflow.engine", "engine lifecycle event"),
        ("bioimageflow.registry", "tool registered"),
    ],
)
async def test_bare_bioimageflow_logs_stay_global_during_execution(
    logger_name: str,
    message: str,
) -> None:
    from bioimageflow_server.models.execution import ExecutionContext
    from bioimageflow_server.services.log_context import bind_execution_log_context
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    handler = WebSocketLogHandler(mgr, loop=asyncio.get_running_loop())
    context = ExecutionContext(
        execution_id="exec-a",
        workflow_id="workflow-a",
        draft_revision=1,
    )
    logger = logging.getLogger(logger_name)

    with bind_execution_log_context(context):
        handler.emit(logger.makeRecord(logger.name, logging.INFO, "f", 1, message, None, None))

    for _ in range(20):
        await asyncio.sleep(0.01)
        if mgr.broadcast_calls:
            break

    assert mgr.broadcast_calls[0][4] is None


async def test_bioimageflow_engine_diagnostic_carries_bound_execution_context() -> None:
    from bioimageflow_server.models.execution import ExecutionContext
    from bioimageflow_server.services.log_context import bind_execution_log_context
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    handler = WebSocketLogHandler(mgr, loop=asyncio.get_running_loop())
    context = ExecutionContext(
        execution_id="exec-engine",
        workflow_id="workflow-engine",
        draft_revision=3,
    )
    logger = logging.getLogger("bioimageflow")

    with bind_execution_log_context(context):
        record = logger.makeRecord(
            logger.name,
            logging.INFO,
            "/package/bioimageflow/engine.py",
            809,
            "Skipping node 'disabled' (disabled or upstream disabled)",
            None,
            None,
        )
        handler.emit(record)

    for _ in range(20):
        await asyncio.sleep(0.01)
        if mgr.broadcast_calls:
            break

    assert mgr.broadcast_calls[0][4] == context


async def test_wetlands_record_without_execution_metadata_stays_global() -> None:
    from bioimageflow_server.models.execution import ExecutionContext
    from bioimageflow_server.services.log_context import bind_execution_log_context
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    handler = WebSocketLogHandler(mgr, loop=asyncio.get_running_loop())
    context = ExecutionContext(
        execution_id="exec-a",
        workflow_id="workflow-a",
        draft_revision=1,
    )
    logger = logging.getLogger("wetlands.worker")

    with bind_execution_log_context(context):
        record = logger.makeRecord(
            logger.name,
            logging.INFO,
            "f",
            1,
            "bare worker lifecycle output",
            None,
            None,
        )
        handler.emit(record)

    for _ in range(20):
        await asyncio.sleep(0.01)
        if mgr.broadcast_calls:
            break

    assert mgr.broadcast_calls[0][4] is None


async def test_thumbnail_worker_log_stays_global_during_execution() -> None:
    from bioimageflow_server.models.execution import ExecutionContext
    from bioimageflow_server.services.log_context import bind_execution_log_context
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    handler = WebSocketLogHandler(mgr, loop=asyncio.get_running_loop())
    context = ExecutionContext(
        execution_id="exec-a",
        workflow_id="workflow-a",
        draft_revision=1,
    )
    logger = logging.getLogger("wetlands.execution")
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        "f",
        1,
        "thumbnail generated",
        None,
        None,
        extra={
            "log_source": "execution",
            "call_target": "thumbnail_generator:generate_thumbnail",
        },
    )

    with bind_execution_log_context(context):
        handler.emit(record)

    for _ in range(20):
        await asyncio.sleep(0.01)
        if mgr.broadcast_calls:
            break

    assert mgr.broadcast_calls[0][4] is None


async def test_record_provenance_cannot_be_relabelled_by_a_later_execution() -> None:
    from bioimageflow_server.models.execution import ExecutionContext
    from bioimageflow_server.services.log_context import bind_execution_log_context
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    handler = WebSocketLogHandler(mgr, loop=asyncio.get_running_loop())
    context_a = ExecutionContext(execution_id="exec-a", workflow_id="a", draft_revision=1)
    context_b = ExecutionContext(execution_id="exec-b", workflow_id="b", draft_revision=2)
    logger = logging.getLogger("wetlands.execution")
    with bind_execution_log_context(context_a):
        delayed_a = logger.makeRecord(
            logger.name,
            logging.INFO,
            "f",
            1,
            "late A",
            None,
            None,
            extra={
                "log_source": "execution",
                "call_target": "worker:run_process_row",
            },
        )

    with bind_execution_log_context(context_b):
        handler.emit(delayed_a)

    for _ in range(20):
        await asyncio.sleep(0.01)
        if mgr.broadcast_calls:
            break

    assert mgr.broadcast_calls[0][4] == context_a


async def test_unattributed_worker_record_is_not_claimed_by_a_later_execution() -> None:
    from bioimageflow_server.models.execution import ExecutionContext
    from bioimageflow_server.services.log_context import bind_execution_log_context
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    handler = WebSocketLogHandler(mgr, loop=asyncio.get_running_loop())
    context_b = ExecutionContext(execution_id="exec-b", workflow_id="b", draft_revision=2)
    logger = logging.getLogger("wetlands.execution")
    unattributed = logger.makeRecord(
        logger.name,
        logging.INFO,
        "f",
        1,
        "late unattributed output",
        None,
        None,
        extra={
            "log_source": "execution",
            "call_target": "worker:run_process_row",
        },
    )

    with bind_execution_log_context(context_b):
        handler.emit(unattributed)

    for _ in range(20):
        await asyncio.sleep(0.01)
        if mgr.broadcast_calls:
            break

    assert mgr.broadcast_calls[0][4] is None


async def test_handler_passes_timestamp_from_record() -> None:
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    loop = asyncio.get_running_loop()
    handler = WebSocketLogHandler(mgr, loop=loop)

    record = logging.getLogger("bioimageflow.node.x").makeRecord(
        "bioimageflow.node.x", logging.INFO, "f", 1, "m", None, None
    )
    record.created = 42.0
    handler.emit(record)

    for _ in range(20):
        await asyncio.sleep(0.01)
        if mgr.broadcast_calls:
            break

    assert mgr.broadcast_calls[0][3] == 42.0


async def test_handler_does_not_crash_when_loop_closed() -> None:
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    loop = asyncio.new_event_loop()
    loop.close()

    mgr = _StubManager()
    handler = WebSocketLogHandler(mgr, loop=loop)

    record = logging.getLogger("bioimageflow.node.x").makeRecord(
        "bioimageflow.node.x", logging.INFO, "f", 1, "m", None, None
    )
    # Should not raise
    handler.emit(record)


async def test_attach_to_bioimageflow_logger() -> None:
    from bioimageflow_server.ws.logging_bridge import (
        attach_ws_log_handler,
    )

    mgr = _StubManager()
    loop = asyncio.get_running_loop()

    bioimageflow_logger = logging.getLogger("bioimageflow")
    saved_level = bioimageflow_logger.level
    bioimageflow_logger.setLevel(logging.NOTSET)
    handler = attach_ws_log_handler(mgr, loop)
    try:
        assert handler in bioimageflow_logger.handlers
        assert handler.level == logging.DEBUG
        # Default-lowered to DEBUG when level was NOTSET so subscribers
        # see every record (filtering happens at subscription level).
        assert bioimageflow_logger.level == logging.DEBUG
        # Propagation preserved (spec: keep terminal logging)
        assert bioimageflow_logger.propagate is True
    finally:
        _remove_handler("bioimageflow", handler)
        _remove_handler("wetlands", handler)
        bioimageflow_logger.setLevel(saved_level)


async def test_attach_preserves_explicit_logger_level() -> None:
    """When the deployer has pinned a level on bioimageflow.node, the bridge
    must not override it — doing so would silently increase log volume going
    to other handlers (terminal/file) attached to the same logger."""
    from bioimageflow_server.ws.logging_bridge import attach_ws_log_handler

    mgr = _StubManager()
    loop = asyncio.get_running_loop()
    bioimageflow_logger = logging.getLogger("bioimageflow")
    saved_level = bioimageflow_logger.level
    bioimageflow_logger.setLevel(logging.WARNING)
    try:
        handler = attach_ws_log_handler(mgr, loop)
        try:
            assert bioimageflow_logger.level == logging.WARNING
        finally:
            _remove_handler("bioimageflow", handler)
            _remove_handler("wetlands", handler)
    finally:
        bioimageflow_logger.setLevel(saved_level)


async def test_emit_via_logger_triggers_broadcast() -> None:
    """Logging through a bioimageflow.node.* logger reaches broadcast_log."""
    from bioimageflow_server.ws.logging_bridge import attach_ws_log_handler

    mgr = _StubManager()
    loop = asyncio.get_running_loop()
    handler = attach_ws_log_handler(mgr, loop)
    try:
        logging.getLogger("bioimageflow.node.test_node").info("hello")

        for _ in range(20):
            await asyncio.sleep(0.01)
            if mgr.broadcast_calls:
                break

        assert len(mgr.broadcast_calls) == 1
        level, message, node_id, _, _ = mgr.broadcast_calls[0]
        assert level == "INFO"
        assert message == "hello"
        assert node_id == "test_node"
    finally:
        _remove_handler("bioimageflow", handler)
        _remove_handler("wetlands", handler)


async def test_emit_framework_logger_triggers_broadcast_with_null_node() -> None:
    """Framework-level bioimageflow records reach broadcast_log with no node id."""
    from bioimageflow_server.ws.logging_bridge import attach_ws_log_handler

    mgr = _StubManager()
    loop = asyncio.get_running_loop()
    handler = attach_ws_log_handler(mgr, loop)
    try:
        logging.getLogger("bioimageflow").warning("framework warning")

        for _ in range(20):
            await asyncio.sleep(0.01)
            if mgr.broadcast_calls:
                break

        assert len(mgr.broadcast_calls) == 1
        level, message, node_id, _, _ = mgr.broadcast_calls[0]
        assert level == "WARNING"
        assert message == "framework warning"
        assert node_id is None
    finally:
        _remove_handler("bioimageflow", handler)
        _remove_handler("wetlands", handler)


async def test_emit_wetlands_logger_triggers_broadcast_with_null_node() -> None:
    """Wetlands environment/process records should reach the frontend logger."""
    from bioimageflow_server.ws.logging_bridge import attach_ws_log_handler

    mgr = _StubManager()
    loop = asyncio.get_running_loop()
    handler = attach_ws_log_handler(mgr, loop)
    try:
        logging.getLogger("wetlands.environment").info("env ready")

        for _ in range(20):
            await asyncio.sleep(0.01)
            if mgr.broadcast_calls:
                break

        assert len(mgr.broadcast_calls) == 1
        level, message, node_id, _, _ = mgr.broadcast_calls[0]
        assert level == "INFO"
        assert message == "env ready"
        assert node_id is None
    finally:
        _remove_handler("bioimageflow", handler)
        _remove_handler("wetlands", handler)


async def test_wetlands_execute_context_scopes_following_output_to_node() -> None:
    """Wetlands stdout/stderr records following an Execute line stay node-scoped."""
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    loop = asyncio.get_running_loop()
    handler = WebSocketLogHandler(mgr, loop=loop)

    execute_record = logging.getLogger("wetlands.worker").makeRecord(
        "wetlands.worker",
        logging.INFO,
        "f",
        1,
        "Execute worker.run(({'run_dir': 'bif_data/workflows/w/data/atlas_1/run'},))",
        None,
        None,
    )
    stdout_record = logging.getLogger("wetlands.worker").makeRecord(
        "wetlands.worker",
        logging.INFO,
        "f",
        2,
        "Running Atlas spot detection...",
        None,
        None,
    )
    handler.emit(execute_record)
    handler.emit(stdout_record)

    for _ in range(20):
        await asyncio.sleep(0.01)
        if len(mgr.broadcast_calls) >= 2:
            break

    assert [call[2] for call in mgr.broadcast_calls] == ["atlas_1", "atlas_1"]


async def test_wetlands_execute_path_preserves_nested_node_scope() -> None:
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    handler = WebSocketLogHandler(mgr, loop=asyncio.get_running_loop())
    logger = logging.getLogger("wetlands.worker")
    handler.emit(
        logger.makeRecord(
            logger.name,
            logging.INFO,
            "f",
            1,
            "Execute worker.run(({'run_dir': 'bif_data/workflows/w/data/outer/inner/run'},))",
            None,
            None,
        )
    )

    for _ in range(20):
        await asyncio.sleep(0.01)
        if mgr.broadcast_calls:
            break

    assert mgr.broadcast_calls[0][2] == "outer/inner"


async def test_wetlands_node_fallback_does_not_cross_execution_identity() -> None:
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    handler = WebSocketLogHandler(mgr, loop=asyncio.get_running_loop())
    logger = logging.getLogger("wetlands.worker")
    context_a = {
        "log_source": "execution",
        "call_target": "worker:run_process_row",
        "execution_id": "exec-a",
        "workflow_id": "a",
        "draft_revision": 1,
    }
    context_b = {
        "log_source": "execution",
        "call_target": "worker:run_process_row",
        "execution_id": "exec-b",
        "workflow_id": "b",
        "draft_revision": 1,
    }
    handler.emit(
        logger.makeRecord(
            logger.name,
            logging.INFO,
            "f",
            1,
            "Execute worker.run(({'run_dir': 'bif_data/workflows/a/data/shared/run'},))",
            None,
            None,
            extra=context_a,
        )
    )
    handler.emit(
        logger.makeRecord(
            logger.name,
            logging.INFO,
            "f",
            2,
            "output without a node path",
            None,
            None,
            extra=context_b,
        )
    )

    for _ in range(20):
        await asyncio.sleep(0.01)
        if len(mgr.broadcast_calls) == 2:
            break

    assert [call[2] for call in mgr.broadcast_calls] == ["shared", None]


async def test_wetlands_exit_clears_fallback_node_scope() -> None:
    """A terminal record on a different Wetlands channel must clear node scope."""
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    loop = asyncio.get_running_loop()
    handler = WebSocketLogHandler(mgr, loop=loop)

    records = [
        logging.getLogger("wetlands.worker").makeRecord(
            "wetlands.worker",
            logging.INFO,
            "f",
            1,
            "INFO:123:main:Execute worker.run(({'run_dir': 'bif_data/workflows/w/data/atlas_1/run'},))",
            None,
            None,
        ),
        logging.getLogger("wetlands.worker").makeRecord(
            "wetlands.worker",
            logging.INFO,
            "f",
            2,
            "INFO:123:stdout:exit",
            None,
            None,
        ),
        logging.getLogger("wetlands.worker").makeRecord(
            "wetlands.worker",
            logging.INFO,
            "f",
            3,
            "INFO:123:stdout:unrelated environment output",
            None,
            None,
        ),
    ]
    for record in records:
        handler.emit(record)

    for _ in range(20):
        await asyncio.sleep(0.01)
        if len(mgr.broadcast_calls) >= 3:
            break

    assert [call[2] for call in mgr.broadcast_calls] == ["atlas_1", "atlas_1", None]


async def test_exception_traceback_is_in_broadcast_message() -> None:
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    loop = asyncio.get_running_loop()
    handler = WebSocketLogHandler(mgr, loop=loop)
    logging.getLogger("bioimageflow").addHandler(handler)
    try:
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            logging.getLogger("bioimageflow.node.x").exception("node exploded")

        for _ in range(20):
            await asyncio.sleep(0.01)
            if mgr.broadcast_calls:
                break

        assert mgr.broadcast_calls
        assert "Traceback" in mgr.broadcast_calls[0][1]
        assert "RuntimeError" in mgr.broadcast_calls[0][1]
    finally:
        _remove_handler("bioimageflow", handler)
        _remove_handler("wetlands", handler)


async def test_node_logs_are_not_duplicated_by_framework_handler() -> None:
    """A node record propagating to bioimageflow is emitted once."""
    from bioimageflow_server.ws.logging_bridge import attach_ws_log_handler

    mgr = _StubManager()
    loop = asyncio.get_running_loop()
    handler = attach_ws_log_handler(mgr, loop)
    try:
        logging.getLogger("bioimageflow.node.segmenter_1").error("node failed")

        for _ in range(20):
            await asyncio.sleep(0.01)
            if mgr.broadcast_calls:
                break

        assert len(mgr.broadcast_calls) == 1
        assert mgr.broadcast_calls[0][0] == "ERROR"
        assert mgr.broadcast_calls[0][1] == "node failed"
        assert mgr.broadcast_calls[0][2] == "segmenter_1"
    finally:
        _remove_handler("bioimageflow", handler)
        _remove_handler("wetlands", handler)


async def test_emit_from_background_thread() -> None:
    """Emitting from a non-event-loop thread still schedules on stored loop."""
    from bioimageflow_server.ws.logging_bridge import WebSocketLogHandler

    mgr = _StubManager()
    loop = asyncio.get_running_loop()
    handler = WebSocketLogHandler(mgr, loop=loop)

    done = threading.Event()

    def _worker() -> None:
        record = logging.getLogger("bioimageflow.node.x").makeRecord(
            "bioimageflow.node.x",
            logging.INFO,
            "f",
            1,
            "from-thread",
            None,
            None,
        )
        handler.emit(record)
        done.set()

    t = threading.Thread(target=_worker)
    t.start()
    await asyncio.get_running_loop().run_in_executor(None, done.wait, 1.0)
    t.join(timeout=1.0)
    assert done.is_set()

    for _ in range(30):
        await asyncio.sleep(0.01)
        if mgr.broadcast_calls:
            break

    assert len(mgr.broadcast_calls) == 1
    assert mgr.broadcast_calls[0][1] == "from-thread"


async def test_recursion_guard_prevents_infinite_loop() -> None:
    """If broadcast_log itself logs, the guard prevents re-entry."""
    from bioimageflow_server.ws.logging_bridge import attach_ws_log_handler

    emit_count = {"n": 0}

    class _RecursiveStub:
        async def broadcast_log(
            self,
            level: str,
            message: str,
            node_id: str | None,
            timestamp: float,
            *,
            context: Any | None = None,
        ) -> None:
            emit_count["n"] += 1
            # Simulate a downstream failure that logs via a node logger.
            logging.getLogger("bioimageflow.node.recursion_trap").error("failure inside broadcast")

    mgr = _RecursiveStub()
    loop = asyncio.get_running_loop()
    handler = attach_ws_log_handler(mgr, loop)
    try:
        logging.getLogger("bioimageflow.node.x").info("initial")

        for _ in range(30):
            await asyncio.sleep(0.01)
            if emit_count["n"] >= 1:
                break

        # Exactly one emit: the recursion guard short-circuits the re-entry.
        # (Coroutine scheduling is async but the guard applies inside emit(),
        # so only the outer emit reaches broadcast_log in the same call stack.)
        assert emit_count["n"] == 1
    finally:
        _remove_handler("bioimageflow", handler)
        _remove_handler("wetlands", handler)


async def test_internal_ws_logger_is_not_captured() -> None:
    """Records emitted on the internal ``bioimageflow_server.ws`` logger
    must not reach the WS handler — that's the primary recursion-prevention
    mechanism (the ContextVar guard is just a backstop)."""
    from bioimageflow_server.ws.logging_bridge import attach_ws_log_handler

    mgr = _StubManager()
    loop = asyncio.get_running_loop()
    handler = attach_ws_log_handler(mgr, loop)
    try:
        logging.getLogger("bioimageflow_server.ws.handler").warning("an internal diagnostic")
        # Give the loop ample chance to schedule something if it would.
        for _ in range(10):
            await asyncio.sleep(0.01)

        assert mgr.broadcast_calls == []
    finally:
        _remove_handler("bioimageflow", handler)
        _remove_handler("wetlands", handler)
