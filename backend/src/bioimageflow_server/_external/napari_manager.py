# Self-contained script — do NOT add imports from bioimageflow_server.
# Executed as a subprocess inside the Napari Conda env (see
# services/napari_launcher.py).
# The PORT_LINE_PREFIX literal below MUST match _PORT_LINE_PREFIX in
# napari_launcher.py — the two processes use it as their port-handshake
# contract and the helper cannot import from the server package.
"""Napari manager helper.

Hosts a ``multiprocessing.connection.Listener`` on localhost (with an
``authkey`` so other local processes can't drive it) and runs a
``napari.Viewer`` on the main thread. Commands flow in over the IPC
channel, get parsed in a background thread (so the Listener stays
responsive), and are *applied* on the Qt main thread via napari's
``thread_worker`` ``yielded`` signal — the blessed pattern for
thread-safe Qt updates.

Reference: Galaxy's ``napari_manager.py`` is the original port; this
file adapts it to use an authkey'd Listener and an explicit ``shutdown``
action.
"""

from __future__ import annotations

import os
import sys
from multiprocessing.connection import Listener
from typing import Any, Callable

# Default fallback; the launcher passes the same literal via the
# ``NAPARI_PORT_PREFIX`` env var so a future protocol change is a
# single point of truth.
PORT_LINE_PREFIX: str = os.environ.get("NAPARI_PORT_PREFIX", "Listening port ")


def _handle_command(
    command: Any, callbacks: dict[str, Callable[..., Any]]
) -> dict[str, Any]:
    """Dispatch a command dict to ``callbacks`` and return the IPC response.

    The ``callbacks`` indirection makes this function unit-testable
    without spinning up a real ``napari.Viewer``. Production code wires
    callbacks bound to a real viewer via :func:`_apply_command`; the
    worker thread invokes a no-op callback set when it just needs the
    response (the actual side effects run on the Qt main thread).
    """
    if not isinstance(command, dict) or "action" not in command:
        return {"status": "error", "detail": "missing 'action' field"}

    action = command["action"]
    if action == "open":
        if command.get("clear_layers"):
            callbacks["clear_layers"]()
        callbacks["open"](command.get("paths", []))
        return {"status": "ok"}
    if action == "shutdown":
        callbacks["close"]()
        return {"status": "ok"}
    return {"status": "error", "detail": f"unknown action: {action}"}


def _apply_command(command: Any, viewer: Any) -> None:
    """Run a command's side effects on the Qt main thread.

    Wrapped over :func:`_handle_command` with callbacks bound to the
    real ``viewer`` — the response is discarded here since the worker
    thread already sent one.
    """
    callbacks: dict[str, Callable[..., Any]] = {
        "clear_layers": lambda: viewer.layers.clear(),
        "open": lambda paths: viewer.open(paths, plugin=None),
        "close": lambda: viewer.close(),
    }
    _handle_command(command, callbacks)


def _no_op_callbacks() -> dict[str, Callable[..., Any]]:
    """Callback set used in the worker thread.

    The worker only needs ``_handle_command`` for its return value (the
    IPC response). We deliberately do **not** touch the viewer here —
    those side effects must run on the Qt main thread, and ``yield msg``
    later marshals them through ``worker.yielded``.
    """
    return {
        "clear_layers": lambda: None,
        "open": lambda _paths: None,
        "close": lambda: None,
    }


def _main() -> int:  # pragma: no cover - exercised by integration tests
    authkey_hex = os.environ.get("NAPARI_AUTHKEY")
    if not authkey_hex:
        print(
            "FATAL: NAPARI_AUTHKEY env var is required",
            file=sys.stderr,
            flush=True,
        )
        return 1
    authkey = bytes.fromhex(authkey_hex)

    # Imported here so the unit-test loader can avoid pulling napari /
    # qtpy into the test process.
    import napari
    from napari.qt.threading import thread_worker
    from qtpy.QtWidgets import QApplication

    viewer = napari.Viewer()

    @thread_worker
    def listen():
        with Listener(("localhost", 0), authkey=authkey) as listener:
            print(
                f"{PORT_LINE_PREFIX}{listener.address[1]}",
                flush=True,
            )
            with listener.accept() as conn:
                while True:
                    try:
                        msg = conn.recv()
                    except (EOFError, OSError):
                        return
                    response = _handle_command(msg, _no_op_callbacks())
                    try:
                        conn.send(response)
                    except (BrokenPipeError, OSError):
                        return
                    yield msg
                    if isinstance(msg, dict) and msg.get("action") == "shutdown":
                        return

    worker = listen()
    worker.yielded.connect(lambda cmd: _apply_command(cmd, viewer))
    worker.start()

    app = QApplication.instance()
    if app is not None:
        app.lastWindowClosed.connect(worker.quit)
        app.setQuitOnLastWindowClosed(True)

    napari.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_main())
