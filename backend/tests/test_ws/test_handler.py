"""Tests for ConnectionManager and /ws endpoint."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ---- Mock WebSocket ---------------------------------------------------------


class MockWebSocket:
    """Minimal WebSocket stand-in for ConnectionManager tests."""

    def __init__(self, *, fail_on_send: bool = False) -> None:
        self.sent: list[dict[str, Any]] = []
        self.fail_on_send = fail_on_send
        self.closed = False
        self._send_delay: float | None = None

    async def accept(self) -> None:
        pass

    async def send_json(self, payload: dict[str, Any]) -> None:
        if self.fail_on_send:
            raise RuntimeError("simulated disconnect")
        if self._send_delay is not None:
            await asyncio.sleep(self._send_delay)
        self.sent.append(payload)

    async def close(self) -> None:
        self.closed = True


# ---- connect/disconnect -----------------------------------------------------


async def test_connect_adds_connection() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()

    await mgr.connect(ws)
    assert ws in mgr.connections

    await mgr.disconnect(ws)


async def test_disconnect_removes_connection() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)
    await mgr.disconnect(ws)
    assert ws not in mgr.connections


async def test_disconnect_unknown_is_noop() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    # Should not raise
    await mgr.disconnect(ws)


# ---- broadcast_progress ------------------------------------------------------


async def _drain(mgr: Any) -> None:
    """Let the sender tasks process queued messages."""
    # Yield to the event loop repeatedly so sender tasks get a chance to run.
    for _ in range(10):
        await asyncio.sleep(0)


async def test_broadcast_progress_sends_to_all() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws1, ws2 = MockWebSocket(), MockWebSocket()
    await mgr.connect(ws1)
    await mgr.connect(ws2)

    await mgr.broadcast_progress("n1", "running", 3, 10, 1.0)
    await _drain(mgr)

    for ws in (ws1, ws2):
        assert len(ws.sent) == 1
        payload = ws.sent[0]
        assert payload["type"] == "progress"
        assert payload["node_id"] == "n1"
        assert payload["status"] == "running"
        assert payload["row"] == 3
        assert payload["total_rows"] == 10
        assert payload["timestamp"] == 1.0


async def test_broadcast_progress_no_connections() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    # Should not raise
    await mgr.broadcast_progress("n1", "running", 0, 1, 0.0)


async def test_broadcast_removes_failing_connection() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws_ok = MockWebSocket()
    ws_bad = MockWebSocket(fail_on_send=True)
    await mgr.connect(ws_ok)
    await mgr.connect(ws_bad)

    await mgr.broadcast_progress("n1", "running", 0, 1, 0.0)
    await _drain(mgr)

    assert ws_bad not in mgr.connections
    assert ws_ok in mgr.connections
    assert len(ws_ok.sent) == 1


# ---- broadcast_node_state ---------------------------------------------------


async def test_broadcast_node_state_shape() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)

    await mgr.broadcast_node_state(
        "n1", "failed", False, error="boom", traceback="tb"
    )
    await _drain(mgr)

    assert ws.sent[0] == {
        "type": "node_state",
        "node_id": "n1",
        "status": "failed",
        "cached": False,
        "error": "boom",
        "traceback": "tb",
    }


# ---- broadcast_log and subscription filtering -------------------------------


async def test_broadcast_log_no_filter_sends_everything() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)

    await mgr.broadcast_log("DEBUG", "m1", "n1", 0.0)
    await mgr.broadcast_log("INFO", "m2", "n2", 0.0)
    await mgr.broadcast_log("WARNING", "m3", None, 0.0)
    await _drain(mgr)

    assert len(ws.sent) == 3


async def test_broadcast_log_filters_by_node_id() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)
    mgr.set_log_subscription(ws, node_id="n1", level=None)

    await mgr.broadcast_log("INFO", "for n1", "n1", 0.0)
    await mgr.broadcast_log("INFO", "for n2", "n2", 0.0)
    await mgr.broadcast_log("INFO", "no node", None, 0.0)
    await _drain(mgr)

    assert [m["message"] for m in ws.sent] == ["for n1"]


async def test_broadcast_log_filters_by_level() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)
    mgr.set_log_subscription(ws, node_id=None, level="WARNING")

    await mgr.broadcast_log("DEBUG", "d", "n", 0.0)
    await mgr.broadcast_log("INFO", "i", "n", 0.0)
    await mgr.broadcast_log("WARNING", "w", "n", 0.0)
    await mgr.broadcast_log("ERROR", "e", "n", 0.0)
    await _drain(mgr)

    assert [m["level"] for m in ws.sent] == ["WARNING", "ERROR"]


async def test_broadcast_log_combines_filters_and() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)
    mgr.set_log_subscription(ws, node_id="n1", level="WARNING")

    await mgr.broadcast_log("INFO", "wrong_level", "n1", 0.0)
    await mgr.broadcast_log("WARNING", "wrong_node", "n2", 0.0)
    await mgr.broadcast_log("WARNING", "match", "n1", 0.0)
    await _drain(mgr)

    assert [m["message"] for m in ws.sent] == ["match"]


async def test_subscription_roundtrip() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)

    mgr.set_log_subscription(ws, node_id="x", level="INFO")
    assert mgr.get_log_subscription(ws) == {"node_id": "x", "level": "INFO"}


# ---- other broadcast_* ------------------------------------------------------


async def test_broadcast_execution_complete() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)

    await mgr.broadcast_execution_complete(
        success=True, errors=[], node_statuses={"n1": {"status": "executed"}}
    )
    await _drain(mgr)

    assert ws.sent[0]["type"] == "execution_complete"
    assert ws.sent[0]["success"] is True


async def test_broadcast_execution_complete_serializes_pydantic_node_statuses() -> None:
    """ExecutionManager passes ``dict[str, NodeStatus]`` (Pydantic models).
    The broadcast must convert them to plain dicts so ``json.dumps`` works.
    Regression test: previously the values flowed through unchanged and would
    raise ``TypeError`` the first time a real execution finished with a
    connected client.
    """
    import json

    from bioimageflow_server.models.validation import NodeStatus
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)

    statuses = {
        "n1": NodeStatus(node_id="n1", status="executed", cached=False),
        "n2": NodeStatus(
            node_id="n2",
            status="failed",
            cached=False,
            error="boom",
            traceback="...",
        ),
    }
    await mgr.broadcast_execution_complete(
        success=False, errors=[{"type": "X", "detail": "y"}], node_statuses=statuses
    )
    await _drain(mgr)

    payload = ws.sent[0]
    # Round-trips through json.dumps without a TypeError.
    json.dumps(payload)
    assert payload["type"] == "execution_complete"
    assert payload["node_statuses"]["n1"] == {
        "node_id": "n1",
        "status": "executed",
        "cached": False,
        "error": None,
        "traceback": None,
    }
    assert payload["node_statuses"]["n2"]["status"] == "failed"
    assert payload["node_statuses"]["n2"]["error"] == "boom"


async def test_send_status_snapshot_serializes_pydantic_node_statuses() -> None:
    from bioimageflow_server.models.validation import NodeStatus
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)

    await mgr.send_status_snapshot(
        ws,
        {
            "state": "running",
            "last_result": None,
            "progress": {"node_id": "n1", "row": 2, "total_rows": 5},
            "node_statuses": {
                "n1": NodeStatus(node_id="n1", status="running", cached=False),
            },
        },
    )
    await _drain(mgr)

    assert ws.sent[0] == {
        "type": "status_snapshot",
        "state": "running",
        "last_result": None,
        "progress": {"node_id": "n1", "row": 2, "total_rows": 5},
        "node_statuses": {
            "n1": {
                "node_id": "n1",
                "status": "running",
                "cached": False,
                "error": None,
                "traceback": None,
            }
        },
    }


async def test_broadcast_tool_reload() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)

    await mgr.broadcast_tool_reload("t1", {"name": "t1"})
    await _drain(mgr)

    assert ws.sent[0] == {
        "type": "tool_reload",
        "tool_name": "t1",
        "tool_metadata": {"name": "t1"},
    }


async def test_broadcast_tool_removed() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)

    await mgr.broadcast_tool_removed("GaussianSmooth")
    await _drain(mgr)

    assert ws.sent[0] == {
        "type": "tool_removed",
        "tool_name": "GaussianSmooth",
    }


async def test_broadcast_system_error_sets_timestamp() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)

    await mgr.broadcast_system_error("tool_reload_failed", "syntax error")
    await _drain(mgr)

    payload = ws.sent[0]
    assert payload["type"] == "system_error"
    assert payload["code"] == "tool_reload_failed"
    assert payload["detail"] == "syntax error"
    # Server-side timestamp set via time.time() — must be a float > 0.
    assert isinstance(payload["timestamp"], float)
    assert payload["timestamp"] > 0


async def test_broadcast_system_error_to_all_connections() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws1, ws2 = MockWebSocket(), MockWebSocket()
    await mgr.connect(ws1)
    await mgr.connect(ws2)

    await mgr.broadcast_system_error("c", "d")
    await _drain(mgr)

    for ws in (ws1, ws2):
        assert len(ws.sent) == 1
        assert ws.sent[0]["type"] == "system_error"


async def test_broadcast_package_install() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)

    await mgr.broadcast_package_install("pkg", "installing", detail="x")
    await _drain(mgr)

    assert ws.sent[0] == {
        "type": "package_install",
        "package_name": "pkg",
        "status": "installing",
        "detail": "x",
    }


async def test_broadcast_environment_status() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)

    await mgr.broadcast_environment_status("napari", "running")
    await _drain(mgr)

    assert ws.sent[0] == {
        "type": "environment_status",
        "env_name": "napari",
        "status": "running",
    }


async def test_send_ack() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws1, ws2 = MockWebSocket(), MockWebSocket()
    await mgr.connect(ws1)
    await mgr.connect(ws2)

    await mgr.send_ack(ws1, "ref-1")
    await _drain(mgr)

    assert ws1.sent == [{"type": "ack", "ref": "ref-1"}]
    assert ws2.sent == []


async def test_send_error() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)

    await mgr.send_error(ws, "invalid_payload", "bad json", ref="m1")
    await _drain(mgr)

    assert ws.sent[0] == {
        "type": "error",
        "ref": "m1",
        "code": "invalid_payload",
        "detail": "bad json",
    }


async def test_multiple_connections_independent() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    clients = [MockWebSocket() for _ in range(5)]
    for ws in clients:
        await mgr.connect(ws)

    await mgr.broadcast_progress("n1", "running", 0, 1, 0.0)
    await _drain(mgr)

    for ws in clients:
        assert len(ws.sent) == 1


# ---- Sync publish_* wrappers ------------------------------------------------


async def test_publish_progress_schedules_broadcast() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    loop = asyncio.get_running_loop()
    mgr = ConnectionManager(loop=loop)

    with patch.object(mgr, "broadcast_progress") as mock_broadcast:
        async def _fake(*args, **kwargs):
            return None

        mock_broadcast.side_effect = _fake

        with patch(
            "bioimageflow_server.ws.handler.asyncio.run_coroutine_threadsafe"
        ) as mock_schedule:
            fut = MagicMock()
            fut.add_done_callback = MagicMock()
            mock_schedule.return_value = fut

            mgr.publish_progress("n1", "running", 1, 2, 3.0)

            mock_schedule.assert_called_once()
            scheduled_coro, scheduled_loop = mock_schedule.call_args.args
            assert scheduled_loop is loop
            scheduled_coro.close()


async def test_publish_node_state_schedules_broadcast() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    loop = asyncio.get_running_loop()
    mgr = ConnectionManager(loop=loop)

    with patch.object(mgr, "broadcast_node_state") as mock_broadcast:
        async def _fake(*args, **kwargs):
            return None

        mock_broadcast.side_effect = _fake

        with patch(
            "bioimageflow_server.ws.handler.asyncio.run_coroutine_threadsafe"
        ) as mock_schedule:
            fut = MagicMock()
            mock_schedule.return_value = fut
            mgr.publish_node_state("n1", "failed", False, error="e", traceback="tb")
            mock_schedule.assert_called_once()
            scheduled_coro, scheduled_loop = mock_schedule.call_args.args
            assert scheduled_loop is loop
            scheduled_coro.close()


async def test_publish_log_schedules_broadcast() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    loop = asyncio.get_running_loop()
    mgr = ConnectionManager(loop=loop)

    with patch.object(mgr, "broadcast_log") as mock_broadcast:
        async def _fake(*args, **kwargs):
            return None

        mock_broadcast.side_effect = _fake

        with patch(
            "bioimageflow_server.ws.handler.asyncio.run_coroutine_threadsafe"
        ) as mock_schedule:
            fut = MagicMock()
            mock_schedule.return_value = fut
            mgr.publish_log("ERROR", "failed", "n1", 3.0)
            mock_schedule.assert_called_once()
            scheduled_coro, scheduled_loop = mock_schedule.call_args.args
            assert scheduled_loop is loop
            scheduled_coro.close()


async def test_publish_execution_complete_schedules_broadcast() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    loop = asyncio.get_running_loop()
    mgr = ConnectionManager(loop=loop)

    with patch.object(mgr, "broadcast_execution_complete") as mock_broadcast:
        async def _fake(*args, **kwargs):
            return None

        mock_broadcast.side_effect = _fake

        with patch(
            "bioimageflow_server.ws.handler.asyncio.run_coroutine_threadsafe"
        ) as mock_schedule:
            fut = MagicMock()
            mock_schedule.return_value = fut
            mgr.publish_execution_complete(True, [], {})
            mock_schedule.assert_called_once()
            scheduled_coro, scheduled_loop = mock_schedule.call_args.args
            assert scheduled_loop is loop
            scheduled_coro.close()


async def test_publish_from_background_thread() -> None:
    """Calling publish_* from a non-event-loop thread schedules on stored loop."""
    from bioimageflow_server.ws.handler import ConnectionManager

    loop = asyncio.get_running_loop()
    mgr = ConnectionManager(loop=loop)
    ws = MockWebSocket()
    await mgr.connect(ws)

    done = threading.Event()

    def _worker() -> None:
        mgr.publish_progress("n1", "running", 1, 2, 3.0)
        done.set()

    thread = threading.Thread(target=_worker)
    thread.start()
    # Let the thread schedule, then give the event loop time to run the coroutine
    await asyncio.get_running_loop().run_in_executor(None, done.wait, 1.0)
    thread.join(timeout=1.0)
    assert done.is_set()

    # Give broadcast + sender tasks time to run
    for _ in range(20):
        await asyncio.sleep(0.01)
        if ws.sent:
            break

    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "progress"


async def test_publish_without_loop_drops_silently(caplog: pytest.LogCaptureFixture) -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=None)
    with caplog.at_level(logging.DEBUG, logger="bioimageflow_server.ws"):
        # Should not raise AttributeError
        mgr.publish_progress("n1", "running", 1, 2, 3.0)
        mgr.publish_node_state("n1", "running", False)
        mgr.publish_log("ERROR", "failed", "n1", 3.0)
        mgr.publish_execution_complete(True, [], {})

    # At least one DEBUG log about dropping
    assert any(
        "dropped" in r.message.lower() or "loop" in r.message.lower()
        for r in caplog.records
    )


async def test_publish_logs_future_exceptions(caplog: pytest.LogCaptureFixture) -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    loop = asyncio.get_running_loop()
    mgr = ConnectionManager(loop=loop)

    async def _boom(*args, **kwargs):
        raise RuntimeError("scheduled broadcast failed")

    with patch.object(mgr, "broadcast_progress", side_effect=_boom):
        with caplog.at_level(logging.WARNING, logger="bioimageflow_server.ws"):
            mgr.publish_progress("n1", "running", 1, 2, 3.0)
            # Wait for the coroutine to run and the callback to fire
            for _ in range(20):
                await asyncio.sleep(0.01)

    assert any(
        "scheduled broadcast failed" in r.message
        or "broadcast" in r.message.lower()
        for r in caplog.records
    )


# ---- Backpressure: per-connection queue -------------------------------------


async def test_queue_backpressure_drops_oldest() -> None:
    """Filling queue beyond maxsize drops the oldest messages, not newest."""
    from bioimageflow_server.ws.handler import ConnectionManager

    # Use a small max_queue_size for this test
    mgr = ConnectionManager(loop=asyncio.get_running_loop(), max_queue_size=3)
    ws = MockWebSocket()
    # Make send_json slow so the queue actually fills up
    ws._send_delay = 10.0  # effectively blocks
    await mgr.connect(ws)

    # The first message goes to the sender (dequeued immediately). After that,
    # the queue fills up: 3 stay, plus extras drop the oldest.
    for i in range(10):
        await mgr.broadcast_progress(f"n{i}", "running", 0, 1, float(i))

    assert mgr.get_dropped_count(ws) > 0
    # Remove slow consumer for cleanup
    await mgr.disconnect(ws)


async def test_slow_consumer_does_not_block_fast_consumer() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop(), max_queue_size=64)
    ws_slow = MockWebSocket()
    ws_slow._send_delay = 1.0  # blocks
    ws_fast = MockWebSocket()

    await mgr.connect(ws_slow)
    await mgr.connect(ws_fast)

    for i in range(5):
        await mgr.broadcast_progress(f"n{i}", "running", 0, 1, float(i))

    # Fast consumer should get messages even though slow consumer is still blocked
    for _ in range(20):
        await asyncio.sleep(0.01)
        if len(ws_fast.sent) == 5:
            break

    assert len(ws_fast.sent) == 5
    # Slow consumer still stuck on first message
    assert len(ws_slow.sent) == 0

    await mgr.disconnect(ws_slow)
    await mgr.disconnect(ws_fast)


async def test_disconnect_stops_sender_task() -> None:
    from bioimageflow_server.ws.handler import ConnectionManager

    mgr = ConnectionManager(loop=asyncio.get_running_loop())
    ws = MockWebSocket()
    await mgr.connect(ws)
    task = mgr.get_sender_task(ws)
    assert task is not None
    assert not task.done()

    await mgr.disconnect(ws)
    # Sender task should exit shortly after disconnect
    for _ in range(20):
        await asyncio.sleep(0.01)
        if task.done():
            break
    assert task.done()


# ---- /ws endpoint integration (Task 3) --------------------------------------
# These use FastAPI TestClient (sync context manager, which runs its own loop).


def _make_app_with_ws(status_provider=None):
    from contextlib import asynccontextmanager

    from fastapi import FastAPI

    from bioimageflow_server.ws.handler import ConnectionManager, register_ws

    manager = ConnectionManager()

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        manager._loop = asyncio.get_running_loop()  # type: ignore[attr-defined]
        yield
        manager._loop = None  # type: ignore[attr-defined]

    app = FastAPI(lifespan=_lifespan)
    register_ws(app, manager, status_provider=status_provider)
    return app, manager


def test_endpoint_connect_no_initial_message() -> None:
    from fastapi.testclient import TestClient

    app, _ = _make_app_with_ws()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            # No immediate server-pushed message; receive_json with a short
            # timeout should not surface anything. We can't easily test "no
            # message"; instead, round-trip a subscribe_logs and assert only
            # the ack comes back.
            ws.send_json({"type": "subscribe_logs", "message_id": "m1"})
            msg = ws.receive_json()
            assert msg == {"type": "ack", "ref": "m1"}


def test_endpoint_sends_initial_status_snapshot_when_provider_configured() -> None:
    from fastapi.testclient import TestClient

    app, _ = _make_app_with_ws(
        status_provider=lambda: {
            "state": "running",
            "last_result": None,
            "progress": {"node_id": "n1", "row": 2, "total_rows": 5},
            "node_statuses": {
                "n1": {"node_id": "n1", "status": "running", "cached": False}
            },
        }
    )
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "status_snapshot"
            assert msg["state"] == "running"
            assert msg["progress"]["row"] == 2
            assert msg["node_statuses"]["n1"]["status"] == "running"


def test_endpoint_subscribe_logs_without_message_id_no_ack() -> None:
    from fastapi.testclient import TestClient

    app, manager = _make_app_with_ws()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {"type": "subscribe_logs", "node_id": "n1", "level": "INFO"}
            )
            # To assert no ack is sent, trigger a broadcast and verify it is
            # the first thing we receive (not an ack).
            # Drive the broadcast via the manager's public API on the server loop.
            # The simplest way is to send another message; manager has processed
            # the subscribe_logs, then we confirm no ack was queued by sending
            # a subscribe_logs WITH an id and seeing that ack is the only ack.
            ws.send_json({"type": "subscribe_logs", "message_id": "m2"})
            msg = ws.receive_json()
            assert msg == {"type": "ack", "ref": "m2"}


def test_endpoint_invalid_payload_returns_error() -> None:
    from fastapi.testclient import TestClient

    app, _ = _make_app_with_ws()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "bogus"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "invalid_payload"
            assert msg["ref"] is None


def test_endpoint_invalid_payload_preserves_message_id_ref() -> None:
    from fastapi.testclient import TestClient

    app, _ = _make_app_with_ws()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "bogus", "message_id": "caller-1"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["ref"] == "caller-1"


def test_endpoint_subscribe_and_receive_filtered_log() -> None:
    """subscribe_logs sets a filter; a subsequent broadcast_log respects it."""
    from fastapi.testclient import TestClient

    app, manager = _make_app_with_ws()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {
                    "type": "subscribe_logs",
                    "message_id": "m1",
                    "node_id": "target",
                }
            )
            ack = ws.receive_json()
            assert ack["type"] == "ack"

            # Drive broadcast_log from the server's event loop.
            loop = manager._loop  # type: ignore[attr-defined]
            assert loop is not None

            async def _emit() -> None:
                await manager.broadcast_log("INFO", "skip", "other", 0.0)
                await manager.broadcast_log("INFO", "keep", "target", 0.0)

            fut = asyncio.run_coroutine_threadsafe(_emit(), loop)
            fut.result(timeout=1.0)

            msg = ws.receive_json()
            assert msg["type"] == "log"
            assert msg["message"] == "keep"
            assert msg["node_id"] == "target"


def test_endpoint_clean_disconnect() -> None:
    """Closing the client does not crash the server."""
    from fastapi.testclient import TestClient

    app, manager = _make_app_with_ws()
    with TestClient(app) as client:
        with client.websocket_connect("/ws"):
            pass  # close immediately
        # After closing, the server-side should have removed the connection.
        # Give the loop a moment to process the disconnect.
        import time

        for _ in range(20):
            if not manager.connections:
                break
            time.sleep(0.01)
        assert manager.connections == []


def test_endpoint_multiple_concurrent_clients_all_receive_broadcast() -> None:
    from fastapi.testclient import TestClient

    app, manager = _make_app_with_ws()
    with TestClient(app) as client:
        with (
            client.websocket_connect("/ws") as ws1,
            client.websocket_connect("/ws") as ws2,
        ):
            # Wait until both connections are registered on the server side.
            import time

            for _ in range(20):
                if len(manager.connections) == 2:
                    break
                time.sleep(0.01)
            assert len(manager.connections) == 2

            loop = manager._loop  # type: ignore[attr-defined]
            fut = asyncio.run_coroutine_threadsafe(
                manager.broadcast_progress("n1", "running", 1, 5, 0.0), loop
            )
            fut.result(timeout=1.0)

            m1 = ws1.receive_json()
            m2 = ws2.receive_json()
            assert m1["type"] == "progress"
            assert m2["type"] == "progress"
