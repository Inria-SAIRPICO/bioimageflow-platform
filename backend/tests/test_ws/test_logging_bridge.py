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
    ) -> None:
        self.broadcast_calls.append((level, message, node_id, timestamp))


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
    level, message, node_id, _ = mgr.broadcast_calls[0]
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
        level, message, node_id, _ = mgr.broadcast_calls[0]
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
        level, message, node_id, _ = mgr.broadcast_calls[0]
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
        level, message, node_id, _ = mgr.broadcast_calls[0]
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
        ) -> None:
            emit_count["n"] += 1
            # Simulate a downstream failure that logs via a node logger.
            logging.getLogger("bioimageflow.node.recursion_trap").error(
                "failure inside broadcast"
            )

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
        logging.getLogger("bioimageflow_server.ws.handler").warning(
            "an internal diagnostic"
        )
        # Give the loop ample chance to schedule something if it would.
        for _ in range(10):
            await asyncio.sleep(0.01)

        assert mgr.broadcast_calls == []
    finally:
        _remove_handler("bioimageflow", handler)
        _remove_handler("wetlands", handler)
