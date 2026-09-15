"""Tests for the napari_manager helper script's command-dispatch logic.

These tests target ``_handle_command`` only — the pure-ish parser that
maps a command dict to (a) the IPC response and (b) the callbacks that
must be invoked (with a real viewer in production). They do NOT spawn
napari, do NOT import napari, and do NOT exercise the thread_worker /
Listener machinery (those are integration concerns covered by Task B7
Part B).

The helper script is loaded as a plain module from the ``_external/``
directory — that path has no ``__init__.py`` on purpose (see "File
Structure" in the plan), so we use ``importlib.util`` to load it
without polluting ``sys.path`` with the parent.
"""

from __future__ import annotations

import importlib.util
import sys
import threading
import time
from pathlib import Path
from types import ModuleType

import pytest


def _load_napari_manager() -> ModuleType:
    """Import ``backend/src/bioimageflow_server/_external/napari_manager.py``
    as a standalone module (the script is launched as a subprocess in
    production; here we want the dispatch helpers without running its
    entry point).
    """
    backend_root = Path(__file__).resolve().parents[2]
    script_path = backend_root / "src" / "bioimageflow_server" / "_external" / "napari_manager.py"
    spec = importlib.util.spec_from_file_location("napari_manager", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    # Block the napari import path so we never accidentally pull napari
    # in during a unit test run.
    sys.modules.setdefault("napari", _make_napari_stub())
    sys.modules.setdefault("napari.qt", _make_napari_qt_stub())
    sys.modules.setdefault("napari.qt.threading", _make_napari_threading_stub())
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_napari_stub() -> ModuleType:
    mod = ModuleType("napari")
    mod.__dict__["Viewer"] = lambda: None  # not used in unit tests
    mod.__dict__["run"] = lambda: None
    return mod


def _make_napari_qt_stub() -> ModuleType:
    return ModuleType("napari.qt")


def _make_napari_threading_stub() -> ModuleType:
    mod = ModuleType("napari.qt.threading")

    def _thread_worker(fn):
        return fn

    mod.__dict__["thread_worker"] = _thread_worker
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class _Recorder:
    """Mock viewer-callbacks recorder."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def make(self, name: str):
        def _impl(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return _impl

    def callbacks(self) -> dict:
        return {
            "clear_layers": self.make("clear_layers"),
            "open": self.make("open"),
            "close": self.make("close"),
        }


def test_handle_command_open_returns_ok_and_records_open() -> None:
    nm = _load_napari_manager()
    rec = _Recorder()
    response = nm._handle_command(
        {"action": "open", "paths": ["/tmp/a.tif"], "clear_layers": False},
        rec.callbacks(),
    )
    assert response == {"status": "ok"}
    assert rec.calls == [("open", (["/tmp/a.tif"],), {})]


def test_handle_command_open_with_clear_layers_records_both_in_order() -> None:
    nm = _load_napari_manager()
    rec = _Recorder()
    response = nm._handle_command(
        {"action": "open", "paths": ["/tmp/a.tif"], "clear_layers": True},
        rec.callbacks(),
    )
    assert response == {"status": "ok"}
    assert [c[0] for c in rec.calls] == ["clear_layers", "open"]
    assert rec.calls[1] == ("open", (["/tmp/a.tif"],), {})


def test_handle_command_shutdown_returns_ok_and_records_close() -> None:
    nm = _load_napari_manager()
    rec = _Recorder()
    response = nm._handle_command({"action": "shutdown"}, rec.callbacks())
    assert response == {"status": "ok"}
    assert [c[0] for c in rec.calls] == ["close"]


def test_handle_command_unknown_action_returns_error() -> None:
    nm = _load_napari_manager()
    rec = _Recorder()
    response = nm._handle_command({"action": "frobnicate"}, rec.callbacks())
    assert response["status"] == "error"
    assert "frobnicate" in response["detail"]
    assert rec.calls == []


def test_handle_command_missing_action_returns_error() -> None:
    nm = _load_napari_manager()
    rec = _Recorder()
    response = nm._handle_command({"paths": ["/tmp/a"]}, rec.callbacks())
    assert response["status"] == "error"
    assert rec.calls == []


def test_handle_command_non_dict_returns_error() -> None:
    nm = _load_napari_manager()
    rec = _Recorder()
    response = nm._handle_command("not a dict", rec.callbacks())  # type: ignore[arg-type]
    assert response["status"] == "error"
    assert rec.calls == []


def test_port_line_prefix_matches_launcher() -> None:
    """The helper's port line MUST match the launcher's predicate or the
    handshake silently times out.
    """
    nm = _load_napari_manager()
    from bioimageflow_server.services.napari_launcher import _PORT_LINE_PREFIX

    assert nm.PORT_LINE_PREFIX == _PORT_LINE_PREFIX


def test_explicit_reader_is_passed_as_plugin_keyword() -> None:
    nm = _load_napari_manager()
    rec = _Recorder()
    response = nm._handle_command(
        {
            "action": "open",
            "request_id": "request-1",
            "paths": ["/tmp/a.tif"],
            "clear_layers": False,
            "reader_id": "org.example.reader",
        },
        rec.callbacks(),
    )
    assert response == {"status": "ok", "request_id": "request-1"}
    assert rec.calls == [("open", (["/tmp/a.tif"],), {"plugin": "org.example.reader"})]


def test_viewer_exception_returns_typed_open_failure() -> None:
    nm = _load_napari_manager()

    def fail(*args, **kwargs):
        raise ValueError("reader rejected artifact")

    response = nm._handle_command(
        {
            "action": "open",
            "request_id": "request-2",
            "paths": ["/tmp/a.tif"],
            "clear_layers": False,
        },
        {"clear_layers": lambda: None, "open": fail, "close": lambda: None},
    )
    assert response["status"] == "error"
    assert response["error"] == "napari_open_failed"
    assert response["request_id"] == "request-2"
    assert "reader rejected artifact" in response["detail"]


def test_submit_waits_until_qt_callback_finishes() -> None:
    nm = _load_napari_manager()
    callback_entered = threading.Event()
    callback_release = threading.Event()

    def submit(pending):
        def qt_callback():
            callback_entered.set()
            callback_release.wait()
            nm._complete_pending(
                pending,
                {
                    "clear_layers": lambda: None,
                    "open": lambda paths: None,
                    "close": lambda: None,
                },
            )

        threading.Thread(target=qt_callback).start()

    result: list[dict] = []
    waiter = threading.Thread(
        target=lambda: result.append(
            nm._submit_and_wait({"action": "open", "paths": ["/tmp/a.tif"]}, submit)
        )
    )
    waiter.start()
    assert callback_entered.wait(timeout=1)
    time.sleep(0.01)
    assert result == []
    callback_release.set()
    waiter.join(timeout=1)
    assert result == [{"status": "ok"}]


def test_verify_config_path_accepts_exact_public_path(tmp_path) -> None:
    nm = _load_napari_manager()
    requested = tmp_path / "env id" / "settings.yaml"
    settings = type("Settings", (), {"config_path": requested})()
    nm._verify_config_path(lambda: settings, str(requested))


def test_verify_config_path_rejects_mismatch(tmp_path) -> None:
    nm = _load_napari_manager()
    requested = tmp_path / "one" / "settings.yaml"
    actual = tmp_path / "two" / "settings.yaml"
    settings = type("Settings", (), {"config_path": actual})()
    with pytest.raises(RuntimeError, match="expected"):
        nm._verify_config_path(lambda: settings, str(requested))


def test_validate_command_rejects_unknown_fields() -> None:
    nm = _load_napari_manager()
    command, error = nm._validate_command(
        {"action": "open", "paths": ["/tmp/a.tif"], "surprise": True}
    )
    assert command is None
    assert error is not None
    assert "unknown command fields" in error["detail"]
