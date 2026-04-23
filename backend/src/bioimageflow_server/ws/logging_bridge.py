"""Python logging.Handler that forwards ``bioimageflow.node.*`` records to WS clients."""

from __future__ import annotations

import asyncio
import contextvars
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bioimageflow_server.ws.handler import ConnectionManager  # pragma: no cover


_INTERNAL_LOGGER = logging.getLogger("bioimageflow_server.ws")

# Recursion guard: if ConnectionManager.broadcast_log (or anything below it)
# itself logs through a bioimageflow.node.* logger, this flag short-circuits
# the re-entrant emit. Context-local so it tracks the current call stack
# across threads correctly (thread-local would also work, but contextvars
# compose better with asyncio).
_EMITTING: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "bioimageflow_ws_emitting", default=False
)


class WebSocketLogHandler(logging.Handler):
    """Forwards log records from ``bioimageflow.node.*`` loggers to WS clients.

    The handler must be safe to call from any thread (library code runs in
    worker threads via ``asyncio.to_thread``). It schedules
    ``connection_manager.broadcast_log`` onto the stored event loop using
    ``asyncio.run_coroutine_threadsafe``.
    """

    def __init__(
        self,
        connection_manager: "ConnectionManager",
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        super().__init__()
        self._manager = connection_manager
        self._loop = loop

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        if _EMITTING.get():
            # Already emitting on this stack — any log from inside
            # broadcast_log must not recurse back into us.
            return
        token = _EMITTING.set(True)
        try:
            node_id = _extract_node_id(record.name)
            payload = (
                record.levelname,
                self.format(record),
                node_id,
                record.created,
            )
            self._schedule_broadcast(*payload)
        finally:
            _EMITTING.reset(token)

    def _schedule_broadcast(
        self,
        level: str,
        message: str,
        node_id: str | None,
        timestamp: float,
    ) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            # Silent graceful degradation — the logging bridge must never
            # crash the logger in tests or during shutdown.
            return
        try:
            coro = self._manager.broadcast_log(level, message, node_id, timestamp)
            asyncio.run_coroutine_threadsafe(coro, loop)
        except RuntimeError:
            # Loop just closed between the `is_closed` check and the schedule.
            return


def _extract_node_id(logger_name: str) -> str | None:
    """Return the node name from a ``bioimageflow.node.<name>`` logger, else None."""
    prefix = "bioimageflow.node."
    if logger_name.startswith(prefix):
        suffix = logger_name[len(prefix):]
        # Only take the first segment so nested loggers still map to their node.
        return suffix.split(".", 1)[0] if suffix else None
    return None


def attach_ws_log_handler(
    manager: "ConnectionManager",
    loop: asyncio.AbstractEventLoop,
) -> WebSocketLogHandler:
    """Attach a ``WebSocketLogHandler`` to the ``bioimageflow.node`` logger.

    Propagation is **not** disabled: keeping it on preserves terminal/file
    logging in dev environments, which is valuable for debugging. The
    recursion guard + dedicated ``bioimageflow_server.ws`` internal logger
    prevent self-capture loops.
    """
    handler = WebSocketLogHandler(manager, loop=loop)
    handler.setLevel(logging.DEBUG)
    node_logger = logging.getLogger("bioimageflow.node")
    node_logger.addHandler(handler)
    # Ensure DEBUG-and-above records actually reach the handler.
    if node_logger.level == logging.NOTSET or node_logger.level > logging.DEBUG:
        node_logger.setLevel(logging.DEBUG)
    return handler


__all__ = ["WebSocketLogHandler", "attach_ws_log_handler"]
