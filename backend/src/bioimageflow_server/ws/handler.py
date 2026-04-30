"""WebSocket connection manager and /ws endpoint.

Defines ``ConnectionManager`` — the transport-layer singleton that tracks active
WebSocket connections, manages per-connection send queues, and exposes the
broadcast interface consumed by peer plans (Execution, Hot-Reload, Tools Panel).

The sync ``publish_*`` wrappers implement the ``ExecutionEventBus`` protocol so
the execution worker thread can enqueue broadcasts onto the FastAPI event loop
via ``asyncio.run_coroutine_threadsafe``.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import time
from typing import Any, Protocol

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import TypeAdapter, ValidationError

from bioimageflow_server.models.ws import ClientMessage, SubscribeLogsMessage


_logger = logging.getLogger("bioimageflow_server.ws")

# Level name → numeric mapping; built from stdlib logging to avoid drift.
_LEVEL_ORDER = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class _WebSocketLike(Protocol):
    async def accept(self) -> None: ...
    async def send_json(self, payload: dict[str, Any]) -> None: ...


_SENTINEL = object()


class _ConnectionState:
    __slots__ = (
        "websocket",
        "queue",
        "sender_task",
        "subscription_node_id",
        "subscription_level",
        "dropped_count",
        "drop_warning_emitted",
    )

    def __init__(self, websocket: _WebSocketLike, queue: asyncio.Queue) -> None:
        self.websocket = websocket
        self.queue = queue
        self.sender_task: asyncio.Task | None = None
        self.subscription_node_id: str | None = None
        self.subscription_level: str | None = None
        self.dropped_count: int = 0
        self.drop_warning_emitted: bool = False


class ConnectionManager:
    """Tracks active WebSocket connections and broadcasts server-to-client messages.

    Each connection has its own bounded ``asyncio.Queue`` and a dedicated sender
    task so that a slow consumer never blocks broadcasts to other connections.

    The ``loop`` parameter captures the running event loop at FastAPI startup
    (stored by ``create_app`` in Task 5). The synchronous ``publish_*`` wrappers
    use it with ``asyncio.run_coroutine_threadsafe`` to forward calls from
    non-event-loop threads (e.g. the execution worker).
    """

    DEFAULT_MAX_QUEUE_SIZE = 1024

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop | None = None,
        *,
        max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE,
    ) -> None:
        self._loop = loop
        self._max_queue_size = max_queue_size
        self._states: dict[Any, _ConnectionState] = {}

    # ---- introspection --------------------------------------------------

    @property
    def connections(self) -> list[Any]:
        """List of active WebSocket objects (order not guaranteed)."""
        return list(self._states.keys())

    def get_dropped_count(self, websocket: Any) -> int:
        state = self._states.get(websocket)
        return state.dropped_count if state is not None else 0

    def get_sender_task(self, websocket: Any) -> asyncio.Task | None:
        state = self._states.get(websocket)
        return state.sender_task if state is not None else None

    # ---- connection lifecycle -------------------------------------------

    async def connect(self, websocket: Any) -> None:
        await websocket.accept()
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue_size)
        state = _ConnectionState(websocket=websocket, queue=queue)
        self._states[websocket] = state
        state.sender_task = asyncio.create_task(
            self._sender_loop(state),
            name=f"ws-sender-{id(websocket)}",
        )

    async def disconnect(self, websocket: Any) -> None:
        state = self._states.pop(websocket, None)
        if state is None:
            return
        # Signal sender to exit
        try:
            state.queue.put_nowait(_SENTINEL)
        except asyncio.QueueFull:
            # Queue is already full; the sender will notice when draining.
            pass
        if state.sender_task is not None and not state.sender_task.done():
            # Give the sender a chance to drain & exit; if it's wedged (e.g. slow
            # send_json), cancel it so tests and shutdowns don't hang.
            try:
                await asyncio.wait_for(state.sender_task, timeout=0.1)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                state.sender_task.cancel()
                try:
                    await state.sender_task
                except (asyncio.CancelledError, Exception):
                    pass

    # ---- per-connection log subscription --------------------------------

    def set_log_subscription(
        self,
        websocket: Any,
        node_id: str | None,
        level: str | None,
    ) -> None:
        state = self._states.get(websocket)
        if state is None:
            return
        state.subscription_node_id = node_id
        state.subscription_level = level

    def get_log_subscription(self, websocket: Any) -> dict[str, Any]:
        state = self._states.get(websocket)
        if state is None:
            return {"node_id": None, "level": None}
        return {
            "node_id": state.subscription_node_id,
            "level": state.subscription_level,
        }

    # ---- broadcast methods (server → client) ----------------------------

    async def broadcast_progress(
        self,
        node_id: str,
        status: str,
        row: int,
        total_rows: int,
        timestamp: float,
    ) -> None:
        payload = {
            "type": "progress",
            "node_id": node_id,
            "status": status,
            "row": row,
            "total_rows": total_rows,
            "timestamp": timestamp,
        }
        self._enqueue_all(payload)

    async def broadcast_node_state(
        self,
        node_id: str,
        status: str,
        cached: bool,
        error: str | None = None,
        traceback: str | None = None,
    ) -> None:
        payload = {
            "type": "node_state",
            "node_id": node_id,
            "status": status,
            "cached": cached,
            "error": error,
            "traceback": traceback,
        }
        self._enqueue_all(payload)

    async def broadcast_log(
        self,
        level: str,
        message: str,
        node_id: str | None,
        timestamp: float,
    ) -> None:
        payload = {
            "type": "log",
            "level": level,
            "message": message,
            "node_id": node_id,
            "timestamp": timestamp,
        }
        for state in list(self._states.values()):
            if not self._matches_subscription(state, level=level, node_id=node_id):
                continue
            self._enqueue_one(state, payload)

    async def broadcast_execution_complete(
        self,
        success: bool,
        errors: list,
        node_statuses: dict,
    ) -> None:
        # ExecutionManager passes a dict[str, NodeStatus] (Pydantic models).
        # ``send_json`` uses plain ``json.dumps``, which can't serialize models —
        # so dump them here. Plain dicts pass through unchanged.
        payload = {
            "type": "execution_complete",
            "success": success,
            "errors": list(errors),
            "node_statuses": {
                k: v.model_dump() if hasattr(v, "model_dump") else v
                for k, v in node_statuses.items()
            },
        }
        self._enqueue_all(payload)

    async def broadcast_tool_reload(
        self, tool_name: str, tool_metadata: dict
    ) -> None:
        payload = {
            "type": "tool_reload",
            "tool_name": tool_name,
            "tool_metadata": dict(tool_metadata),
        }
        self._enqueue_all(payload)

    async def broadcast_tool_removed(self, tool_name: str) -> None:
        payload = {
            "type": "tool_removed",
            "tool_name": tool_name,
        }
        self._enqueue_all(payload)

    async def broadcast_system_error(
        self, code: str, detail: str
    ) -> None:
        payload = {
            "type": "system_error",
            "code": code,
            "detail": detail,
            "timestamp": time.time(),
        }
        self._enqueue_all(payload)

    async def broadcast_package_install(
        self,
        package_name: str,
        status: str,
        detail: str | None = None,
    ) -> None:
        payload = {
            "type": "package_install",
            "package_name": package_name,
            "status": status,
            "detail": detail,
        }
        self._enqueue_all(payload)

    async def broadcast_environment_status(
        self, env_name: str, status: str
    ) -> None:
        payload = {
            "type": "environment_status",
            "env_name": env_name,
            "status": status,
        }
        self._enqueue_all(payload)

    async def send_ack(self, websocket: Any, ref: str) -> None:
        state = self._states.get(websocket)
        if state is None:
            return
        self._enqueue_one(state, {"type": "ack", "ref": ref})

    async def send_error(
        self,
        websocket: Any,
        code: str,
        detail: str,
        ref: str | None = None,
    ) -> None:
        state = self._states.get(websocket)
        if state is None:
            return
        self._enqueue_one(
            state,
            {"type": "error", "ref": ref, "code": code, "detail": detail},
        )

    # ---- sync wrappers for ExecutionEventBus ----------------------------

    def publish_progress(
        self,
        node_id: str,
        status: str,
        row: int,
        total_rows: int,
        timestamp: float,
    ) -> None:
        self._schedule(
            self.broadcast_progress(node_id, status, row, total_rows, timestamp),
            "progress",
        )

    def publish_node_state(
        self,
        node_id: str,
        status: str,
        cached: bool,
        error: str | None = None,
        traceback: str | None = None,
    ) -> None:
        self._schedule(
            self.broadcast_node_state(node_id, status, cached, error, traceback),
            "node_state",
        )

    def publish_log(
        self,
        level: str,
        message: str,
        node_id: str | None,
        timestamp: float,
    ) -> None:
        self._schedule(
            self.broadcast_log(level, message, node_id, timestamp),
            "log",
        )

    def publish_execution_complete(
        self,
        success: bool,
        errors: list,
        node_statuses: dict,
    ) -> None:
        self._schedule(
            self.broadcast_execution_complete(success, errors, node_statuses),
            "execution_complete",
        )

    def publish_package_install(
        self,
        package_name: str,
        status: str,
        detail: str | None = None,
    ) -> None:
        self._schedule(
            self.broadcast_package_install(package_name, status, detail),
            "package_install",
        )

    def publish_environment_status(self, env_name: str, status: str) -> None:
        self._schedule(
            self.broadcast_environment_status(env_name, status),
            "environment_status",
        )

    # ---- internals ------------------------------------------------------

    def _schedule(self, coro, kind: str) -> None:
        if self._loop is None:
            # Loop-not-ready guard: startup hasn't run or shutdown already fired.
            # Route the diagnostic through bioimageflow_server.ws so the WebSocket
            # logging bridge doesn't recurse on it.
            _logger.debug(
                "Dropped scheduled %s broadcast: event loop not yet bound", kind
            )
            coro.close()
            return
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        future.add_done_callback(self._log_future_exception)

    @staticmethod
    def _log_future_exception(fut: concurrent.futures.Future) -> None:
        try:
            exc = fut.exception()
        except (concurrent.futures.CancelledError, asyncio.CancelledError):
            return
        if exc is not None:
            _logger.warning(
                "Scheduled WebSocket broadcast failed: %r", exc, exc_info=exc
            )

    def _enqueue_all(self, payload: dict[str, Any]) -> None:
        for state in list(self._states.values()):
            self._enqueue_one(state, payload)

    def _enqueue_one(self, state: _ConnectionState, payload: dict[str, Any]) -> None:
        try:
            state.queue.put_nowait(payload)
        except asyncio.QueueFull:
            # Drop oldest to make room; this keeps the newest (more useful) state.
            try:
                state.queue.get_nowait()
            except asyncio.QueueEmpty:  # pragma: no cover - extremely unlikely
                pass
            try:
                state.queue.put_nowait(payload)
            except asyncio.QueueFull:  # pragma: no cover - should not happen
                return
            state.dropped_count += 1
            if not state.drop_warning_emitted:
                _logger.warning(
                    "WebSocket send queue full; dropping oldest messages for a "
                    "slow consumer (dropped_count=%d)",
                    state.dropped_count,
                )
                state.drop_warning_emitted = True

    @staticmethod
    def _matches_subscription(
        state: _ConnectionState, *, level: str, node_id: str | None
    ) -> bool:
        sub_node = state.subscription_node_id
        if sub_node is not None and sub_node != node_id:
            return False
        sub_level = state.subscription_level
        if sub_level is not None:
            sub_levelno = _level_to_number(sub_level)
            msg_levelno = _level_to_number(level)
            if msg_levelno < sub_levelno:
                return False
        return True

    async def _sender_loop(self, state: _ConnectionState) -> None:
        """Drain the per-connection queue and forward to ``send_json``.

        Exits on sentinel or on any send error (the connection is then removed
        from the active set so subsequent broadcasts skip it).
        """
        queue = state.queue
        ws = state.websocket
        while True:
            msg = await queue.get()
            if msg is _SENTINEL:
                return
            try:
                await ws.send_json(msg)
            except Exception as exc:  # noqa: BLE001 - broad by design
                _logger.debug(
                    "WebSocket send failed, removing connection: %r", exc
                )
                # Drop this connection from the active set without recursing
                # into ``disconnect`` (which would try to wait for us).
                self._states.pop(ws, None)
                return


# ---- level number helpers ---------------------------------------------------


def _level_to_number(name: str) -> int:
    # Fall back to logging.getLevelName for non-standard names; unknown names
    # coerce to 0 (never filtered out).
    if name in _LEVEL_ORDER:
        return _LEVEL_ORDER[name]
    value = logging.getLevelName(name.upper())
    return value if isinstance(value, int) else 0


# ---- /ws endpoint (Task 3 lives here too) -----------------------------------


def register_ws(app: FastAPI, manager: ConnectionManager) -> None:
    """Register the /ws route on ``app`` using the given ``ConnectionManager``.

    Accepts client connections, parses incoming messages against ``ClientMessage``,
    handles ``subscribe_logs`` (with optional ack), and cleans up on disconnect.
    """
    adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await manager.connect(websocket)
        try:
            while True:
                try:
                    raw = await websocket.receive_json()
                except WebSocketDisconnect:
                    return
                except Exception as exc:  # invalid JSON / framing
                    _logger.debug("WebSocket receive failed: %r", exc)
                    await manager.send_error(
                        websocket, "invalid_payload", str(exc)
                    )
                    continue

                ref = raw.get("message_id") if isinstance(raw, dict) else None
                try:
                    msg = adapter.validate_python(raw)
                except ValidationError as exc:
                    await manager.send_error(
                        websocket,
                        code="invalid_payload",
                        detail=str(exc),
                        ref=ref,
                    )
                    continue

                if isinstance(msg, SubscribeLogsMessage):
                    manager.set_log_subscription(
                        websocket, node_id=msg.node_id, level=msg.level
                    )
                    if msg.message_id is not None:
                        await manager.send_ack(websocket, msg.message_id)
        except WebSocketDisconnect:
            pass
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Unhandled WebSocket error: %r", exc, exc_info=exc)
        finally:
            await manager.disconnect(websocket)


__all__ = ["ConnectionManager", "register_ws"]
