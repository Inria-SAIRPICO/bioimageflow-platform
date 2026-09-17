# Self-contained script — do NOT import bioimageflow_server here.
"""Authenticated napari IPC helper with Qt-thread completion acknowledgements."""

from __future__ import annotations

import os
import sys
import threading
from multiprocessing.connection import Listener
from pathlib import Path
from typing import Any, Callable


PORT_LINE_PREFIX: str = os.environ.get("NAPARI_PORT_PREFIX", "Listening port ")


def _error(detail: str, request_id: object = None) -> dict[str, Any]:
    response: dict[str, Any] = {
        "status": "error",
        "error": "napari_open_failed",
        "detail": detail,
    }
    if request_id is not None:
        response["request_id"] = request_id
    return response


def _validate_command(command: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Validate the complete wire shape without importing napari."""
    if not isinstance(command, dict):
        return None, _error("command must be an object")
    request_id = command.get("request_id")
    if request_id is not None and not isinstance(request_id, str):
        return None, _error("request_id must be a string")
    action = command.get("action")
    if action not in {"open", "shutdown"}:
        detail = "missing 'action' field" if action is None else f"unknown action: {action}"
        return None, _error(detail, request_id)
    if action == "shutdown":
        allowed = {"action", "request_id"}
    else:
        paths = command.get("paths")
        if not isinstance(paths, list) or not all(isinstance(path, str) and path for path in paths):
            return None, _error("open paths must be a list of non-empty strings", request_id)
        if not isinstance(command.get("clear_layers", False), bool):
            return None, _error("clear_layers must be a boolean", request_id)
        reader_id = command.get("reader_id")
        if reader_id is not None and (not isinstance(reader_id, str) or not reader_id):
            return None, _error("reader_id must be a non-empty string or null", request_id)
        allowed = {"action", "request_id", "paths", "clear_layers", "reader_id"}
    extras = sorted(set(command) - allowed)
    if extras:
        return None, _error(f"unknown command fields: {', '.join(extras)}", request_id)
    return dict(command), None


def _handle_command(command: Any, callbacks: dict[str, Callable[..., Any]]) -> dict[str, Any]:
    """Validate and execute a command, returning only after callbacks finish."""
    normalized, validation_error = _validate_command(command)
    if validation_error is not None:
        return validation_error
    assert normalized is not None
    request_id = normalized.get("request_id")
    try:
        if normalized["action"] == "shutdown":
            callbacks["close"]()
        else:
            if normalized.get("clear_layers", False):
                callbacks["clear_layers"]()
            reader_id = normalized.get("reader_id")
            if reader_id is None:
                callbacks["open"](normalized["paths"])
            else:
                callbacks["open"](normalized["paths"], plugin=reader_id)
    except Exception as exc:
        return _error(f"{type(exc).__name__}: {exc}", request_id)
    response: dict[str, Any] = {"status": "ok"}
    if request_id is not None:
        response["request_id"] = request_id
    return response


def _verify_config_path(get_settings: Callable[[], Any], requested: str) -> None:
    """Fail startup unless napari resolved the exact requested YAML file."""
    requested_path = Path(requested).expanduser().resolve()
    if requested_path.suffix.lower() not in {".yaml", ".yml"}:
        raise RuntimeError("NAPARI_CONFIG must identify a YAML settings file")
    settings = get_settings()
    resolved = getattr(settings, "config_path", None)
    if resolved is None:
        raise RuntimeError("napari settings do not expose a public config_path")
    resolved_path = Path(resolved).expanduser().resolve()
    if resolved_path != requested_path:
        raise RuntimeError(
            f"napari resolved config path {resolved_path}, expected {requested_path}"
        )


class _PendingCommand:
    def __init__(self, command: dict[str, Any]) -> None:
        self.command = command
        self.response: dict[str, Any] | None = None
        self.done = threading.Event()


def _complete_pending(pending: _PendingCommand, callbacks: dict[str, Callable[..., Any]]) -> None:
    """Complete one command on the caller's thread and release its waiter."""
    try:
        pending.response = _handle_command(pending.command, callbacks)
    finally:
        pending.done.set()


def _submit_and_wait(
    command: dict[str, Any], submit: Callable[[_PendingCommand], None]
) -> dict[str, Any]:
    """Submit to Qt and wait until the Qt callback has fully completed."""
    pending = _PendingCommand(command)
    submit(pending)
    pending.done.wait()
    return pending.response or _error(
        "Qt command completed without a response", command.get("request_id")
    )


def _main() -> int:  # pragma: no cover - native napari integration boundary
    authkey_hex = os.environ.get("NAPARI_AUTHKEY")
    requested_config = os.environ.get("NAPARI_CONFIG")
    if not authkey_hex or not requested_config:
        print("FATAL: NAPARI_AUTHKEY and NAPARI_CONFIG are required", file=sys.stderr, flush=True)
        return 1
    try:
        authkey = bytes.fromhex(authkey_hex)
    except ValueError:
        print("FATAL: NAPARI_AUTHKEY is invalid", file=sys.stderr, flush=True)
        return 1

    import napari
    from napari.settings import get_settings
    from qtpy.QtCore import QObject, Signal, Slot
    from qtpy.QtWidgets import QApplication

    try:
        _verify_config_path(get_settings, requested_config)
    except Exception as exc:
        print(f"FATAL: napari configuration isolation failed: {exc}", file=sys.stderr, flush=True)
        return 1

    viewer = napari.Viewer()

    class Dispatcher(QObject):
        submitted = Signal(object)

        def __init__(self) -> None:
            super().__init__()
            self.submitted.connect(self.apply)

        @Slot(object)
        def apply(self, pending: _PendingCommand) -> None:
            callbacks: dict[str, Callable[..., Any]] = {
                "clear_layers": viewer.layers.clear,
                "open": viewer.open,
                "close": viewer.close,
            }
            _complete_pending(pending, callbacks)

    dispatcher = Dispatcher()

    def listen() -> None:
        with Listener(("localhost", 0), authkey=authkey) as listener:
            print(f"{PORT_LINE_PREFIX}{listener.address[1]}", flush=True)
            with listener.accept() as connection:
                while True:
                    command: dict[str, Any] | None = None
                    try:
                        raw = connection.recv()
                    except (EOFError, OSError):
                        return
                    command, validation_error = _validate_command(raw)
                    if validation_error is not None:
                        response = validation_error
                    else:
                        assert command is not None
                        response = _submit_and_wait(command, dispatcher.submitted.emit)
                    try:
                        connection.send(response)
                    except (BrokenPipeError, OSError):
                        return
                    if command is not None and command["action"] == "shutdown":
                        return

    listener_thread = threading.Thread(target=listen, name="napari-ipc", daemon=True)
    listener_thread.start()

    app = QApplication.instance()
    if app is not None:
        app.setQuitOnLastWindowClosed(True)
    napari.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_main())
