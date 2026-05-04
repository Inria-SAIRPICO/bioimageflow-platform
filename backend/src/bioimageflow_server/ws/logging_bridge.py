"""Python logging.Handler that forwards execution-environment records to WS clients."""

from __future__ import annotations

import asyncio
import contextvars
import logging
import re
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
    """Forwards log records from ``bioimageflow`` loggers to WS clients.

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
        self._wetlands_active_nodes: dict[str, str] = {}

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        if not _is_bioimageflow_record(record.name):
            return
        if _EMITTING.get():
            # Already emitting on this stack — any log from inside
            # broadcast_log must not recurse back into us.
            return
        token = _EMITTING.set(True)
        try:
            message = self.format(record)
            node_id = _extract_node_id(record.name)
            if node_id is None:
                node_id = self._extract_wetlands_node_id(record.name, message)
            payload = (
                record.levelname,
                message,
                node_id,
                record.created,
            )
            self._schedule_broadcast(*payload)
        finally:
            _EMITTING.reset(token)

    def _extract_wetlands_node_id(
        self,
        logger_name: str,
        message: str,
    ) -> str | None:
        if not _is_wetlands_record(logger_name):
            return None

        key = _wetlands_context_key(logger_name, message)
        parsed = _extract_node_id_from_wetlands_message(message)
        if parsed is not None:
            self._wetlands_active_nodes[key] = parsed
            return parsed

        active = self._wetlands_active_nodes.get(key)
        if active is None and len(set(self._wetlands_active_nodes.values())) == 1:
            active = next(iter(self._wetlands_active_nodes.values()))

        if active is not None and _is_wetlands_context_terminal(message):
            self._wetlands_active_nodes.pop(key, None)
            for active_key, active_node in list(self._wetlands_active_nodes.items()):
                if active_node == active:
                    self._wetlands_active_nodes.pop(active_key, None)
            if not self._wetlands_active_nodes:
                self._wetlands_active_nodes.clear()

        return active

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


def _is_bioimageflow_record(logger_name: str) -> bool:
    return (
        logger_name == "bioimageflow"
        or logger_name.startswith("bioimageflow.")
        or _is_wetlands_record(logger_name)
    )


def _is_wetlands_record(logger_name: str) -> bool:
    return logger_name == "wetlands" or logger_name.startswith("wetlands.")


_WETLANDS_DATA_NODE_RE = re.compile(r"(?:^|[\\/])data[\\/]([^\\/'\"),\s]+)[\\/]")
_WETLANDS_CHANNEL_RE = re.compile(
    r"\b(?:DEBUG|INFO|WARNING|ERROR|CRITICAL):\d+:([^:]+):"
)


def _extract_node_id_from_wetlands_message(message: str) -> str | None:
    match = _WETLANDS_DATA_NODE_RE.search(message)
    if match:
        return match.group(1)
    return None


def _wetlands_context_key(logger_name: str, message: str) -> str:
    match = _WETLANDS_CHANNEL_RE.search(message)
    if match:
        return f"{logger_name}:{match.group(1)}"
    return logger_name


def _is_wetlands_context_terminal(message: str) -> bool:
    stripped = message.strip().lower()
    return stripped == "exit" or stripped.endswith(":exit")


def attach_ws_log_handler(
    manager: "ConnectionManager",
    loop: asyncio.AbstractEventLoop,
) -> WebSocketLogHandler:
    """Attach a ``WebSocketLogHandler`` to execution-related library loggers.

    Attaching at the framework root captures both framework-level records
    (``bioimageflow`` / ``bioimageflow.engine``) and per-node records
    (``bioimageflow.node.<node_id>``) once through normal logger propagation.
    The Wetlands root is attached too so environment/process lifecycle logs
    reach subscribers alongside BioImageFlow execution logs.
    Propagation is **not** disabled: keeping it on preserves terminal/file
    logging in dev environments. The recursion guard + dedicated
    ``bioimageflow_server.ws`` internal logger prevent self-capture loops.
    """
    handler = WebSocketLogHandler(manager, loop=loop)
    handler.setLevel(logging.DEBUG)
    bioimageflow_logger = logging.getLogger("bioimageflow")
    bioimageflow_logger.addHandler(handler)
    # If the deployer hasn't pinned a level on this logger, default to DEBUG so
    # WS subscribers see all records (filtering then happens per-subscription).
    # Respect any explicitly-set level — overriding it would change the volume
    # going to *other* handlers (terminal/file) attached to the same logger.
    if bioimageflow_logger.level == logging.NOTSET:
        bioimageflow_logger.setLevel(logging.DEBUG)
    wetlands_logger = logging.getLogger("wetlands")
    wetlands_logger.addHandler(handler)
    if wetlands_logger.level == logging.NOTSET:
        wetlands_logger.setLevel(logging.DEBUG)
    return handler


__all__ = ["WebSocketLogHandler", "attach_ws_log_handler"]
