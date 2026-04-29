"""Tests for :mod:`bioimageflow_server.services.napari_launcher`.

Task B3 covers the skeleton: state, ``_is_alive``, ``_send_command``,
``async open/shutdown``, lock-free ``status``. ``_launch()`` raises
``NotImplementedError`` here — its real implementation is Task B4.

External dependencies (Wetlands, multiprocessing.connection.Client) are
mocked. No real subprocess is started.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from bioimageflow_server.models.napari import NapariStatus
from bioimageflow_server.services.napari_launcher import (
    NapariConnectionError,
    NapariLauncher,
    NapariLaunchError,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeConnection:
    """In-process stand-in for ``multiprocessing.connection.Connection``."""

    def __init__(self) -> None:
        self.sent: list[Any] = []
        self.responses: list[Any] = []
        self.poll_results: list[bool] | None = None
        self.send_exc: Exception | None = None
        self.recv_exc: Exception | None = None
        self.closed = False

    def send(self, obj: Any) -> None:
        if self.send_exc is not None:
            raise self.send_exc
        self.sent.append(obj)

    def recv(self) -> Any:
        if self.recv_exc is not None:
            raise self.recv_exc
        return self.responses.pop(0)

    def poll(self, timeout: float | None = None) -> bool:
        if self.poll_results is not None:
            return self.poll_results.pop(0)
        return True

    def close(self) -> None:
        self.closed = True


def _alive_process(pid: int = 4242) -> MagicMock:
    proc = MagicMock(name="process")
    proc.pid = pid
    proc.poll.return_value = None  # still running
    return proc


def _make_launcher(*, connection_manager: Any = None) -> NapariLauncher:
    return NapariLauncher(
        napari_env_path=None, connection_manager=connection_manager
    )


def _attach_alive(launcher: NapariLauncher, *, conn: _FakeConnection | None = None,
                  pid: int = 4242, env_path: str = "/envs/napari") -> _FakeConnection:
    """Wire a fake alive process+connection onto ``launcher`` (skipping _launch)."""
    fake = conn or _FakeConnection()
    launcher._connection = fake  # type: ignore[assignment]
    launcher._process = _alive_process(pid)
    launcher._env_path = env_path
    launcher._pid = pid
    return fake


# ---------------------------------------------------------------------------
# _is_alive
# ---------------------------------------------------------------------------


def test_is_alive_false_when_process_is_none() -> None:
    launcher = _make_launcher()
    assert launcher._is_alive() is False


def test_is_alive_true_when_process_running_and_connection_open() -> None:
    launcher = _make_launcher()
    _attach_alive(launcher)
    assert launcher._is_alive() is True


def test_is_alive_false_when_process_has_exited() -> None:
    launcher = _make_launcher()
    _attach_alive(launcher)
    launcher._process.poll.return_value = 0  # type: ignore[union-attr]
    assert launcher._is_alive() is False


def test_is_alive_false_when_connection_is_none() -> None:
    launcher = _make_launcher()
    launcher._process = _alive_process()
    launcher._connection = None
    assert launcher._is_alive() is False


# ---------------------------------------------------------------------------
# _send_command
# ---------------------------------------------------------------------------


def test_send_command_sends_and_receives() -> None:
    launcher = _make_launcher()
    fake = _attach_alive(launcher)
    fake.responses.append({"status": "ok"})
    response = launcher._send_command({"action": "open", "paths": []})
    assert fake.sent == [{"action": "open", "paths": []}]
    assert response == {"status": "ok"}


def test_send_command_raises_napari_connection_error_on_connection_reset() -> None:
    launcher = _make_launcher()
    fake = _attach_alive(launcher)
    fake.send_exc = ConnectionResetError()
    with pytest.raises(NapariConnectionError):
        launcher._send_command({"action": "open", "paths": []})


def test_send_command_raises_napari_connection_error_on_eof() -> None:
    launcher = _make_launcher()
    fake = _attach_alive(launcher)
    fake.recv_exc = EOFError()
    with pytest.raises(NapariConnectionError):
        launcher._send_command({"action": "open", "paths": []})


def test_send_command_raises_napari_connection_error_on_broken_pipe() -> None:
    launcher = _make_launcher()
    fake = _attach_alive(launcher)
    fake.send_exc = BrokenPipeError()
    with pytest.raises(NapariConnectionError):
        launcher._send_command({"action": "open", "paths": []})


def test_send_command_resets_connection_and_process_on_connection_error() -> None:
    launcher = _make_launcher()
    fake = _attach_alive(launcher)
    fake.send_exc = ConnectionResetError()
    with pytest.raises(NapariConnectionError):
        launcher._send_command({"action": "open", "paths": []})
    assert launcher._connection is None
    assert launcher._process is None


def test_send_command_raises_timeout_when_poll_false() -> None:
    launcher = _make_launcher()
    fake = _attach_alive(launcher)
    fake.poll_results = [False]
    with pytest.raises(TimeoutError):
        launcher._send_command({"action": "open", "paths": []})


# ---------------------------------------------------------------------------
# status() — lock-free
# ---------------------------------------------------------------------------


def test_status_returns_running_false_when_not_launched() -> None:
    launcher = _make_launcher()
    s = launcher.status()
    assert s == NapariStatus(running=False, env_path=None, pid=None)


def test_status_returns_correct_napari_status_when_running() -> None:
    launcher = _make_launcher()
    _attach_alive(launcher, pid=99, env_path="/envs/napari")
    s = launcher.status()
    assert s.running is True
    assert s.pid == 99
    assert s.env_path == "/envs/napari"


def test_status_does_not_perform_ipc() -> None:
    launcher = _make_launcher()
    fake = _attach_alive(launcher)
    launcher.status()
    assert fake.sent == []
    # responses untouched too
    assert fake.responses == []


async def test_status_is_lock_free_while_lock_held() -> None:
    """status() must return immediately even when another coroutine holds the lock."""
    launcher = _make_launcher()
    _attach_alive(launcher, pid=7)

    async with launcher._lock:
        # If status() tried to acquire the lock, this would deadlock.
        s = await asyncio.wait_for(asyncio.to_thread(launcher.status), timeout=0.5)
    assert s.running is True
    assert s.pid == 7


# ---------------------------------------------------------------------------
# open()
# ---------------------------------------------------------------------------


async def test_open_validates_paths_before_acquiring_lock(tmp_path) -> None:
    launcher = _make_launcher()
    # Hold the lock from another task to prove validation happens BEFORE locking.
    missing = tmp_path / "does_not_exist.tif"

    async with launcher._lock:
        with pytest.raises(FileNotFoundError) as excinfo:
            await launcher.open([str(missing)])
        assert str(missing) in str(excinfo.value)


async def test_open_lists_all_missing_paths(tmp_path) -> None:
    launcher = _make_launcher()
    a = tmp_path / "a.tif"
    a.write_bytes(b"\0")
    missing1 = tmp_path / "m1.tif"
    missing2 = tmp_path / "m2.tif"
    with pytest.raises(FileNotFoundError) as excinfo:
        await launcher.open([str(a), str(missing1), str(missing2)])
    msg = str(excinfo.value)
    assert str(missing1) in msg
    assert str(missing2) in msg


async def test_open_calls_launch_when_not_alive(tmp_path, monkeypatch) -> None:
    launcher = _make_launcher()
    a = tmp_path / "a.tif"
    a.write_bytes(b"\0")

    fake_conn = _FakeConnection()
    fake_conn.responses.append({"status": "ok"})
    launch_calls = []

    def _stub_launch(self: NapariLauncher) -> None:
        launch_calls.append(True)
        _attach_alive(self, conn=fake_conn)

    monkeypatch.setattr(NapariLauncher, "_launch", _stub_launch)
    await launcher.open([str(a)])
    assert launch_calls == [True]
    assert fake_conn.sent == [
        {"action": "open", "paths": [str(a)], "clear_layers": False}
    ]


async def test_open_sends_correct_command_dict(tmp_path, monkeypatch) -> None:
    launcher = _make_launcher()
    a = tmp_path / "a.tif"
    a.write_bytes(b"\0")
    fake_conn = _FakeConnection()
    fake_conn.responses.append({"status": "ok"})
    _attach_alive(launcher, conn=fake_conn)

    await launcher.open([str(a)], clear_layers=True)
    assert fake_conn.sent == [
        {"action": "open", "paths": [str(a)], "clear_layers": True}
    ]


async def test_open_auto_reconnects_once_on_connection_error(tmp_path, monkeypatch) -> None:
    launcher = _make_launcher()
    a = tmp_path / "a.tif"
    a.write_bytes(b"\0")

    initial_conn = _FakeConnection()
    initial_conn.send_exc = ConnectionResetError()
    new_conn = _FakeConnection()
    new_conn.responses.append({"status": "ok"})

    _attach_alive(launcher, conn=initial_conn)
    launch_count = {"n": 0}

    def _stub_launch(self: NapariLauncher) -> None:
        launch_count["n"] += 1
        _attach_alive(self, conn=new_conn)

    monkeypatch.setattr(NapariLauncher, "_launch", _stub_launch)

    await launcher.open([str(a)])
    # First call hit the dead conn (reset), launched once, then retried.
    assert launch_count["n"] == 1
    assert new_conn.sent == [
        {"action": "open", "paths": [str(a)], "clear_layers": False}
    ]


async def test_open_raises_napari_launch_error_when_retry_fails(tmp_path, monkeypatch) -> None:
    launcher = _make_launcher()
    a = tmp_path / "a.tif"
    a.write_bytes(b"\0")

    initial_conn = _FakeConnection()
    initial_conn.send_exc = ConnectionResetError()
    retry_conn = _FakeConnection()
    retry_conn.send_exc = ConnectionResetError()  # also dies

    _attach_alive(launcher, conn=initial_conn)

    def _stub_launch(self: NapariLauncher) -> None:
        _attach_alive(self, conn=retry_conn)

    monkeypatch.setattr(NapariLauncher, "_launch", _stub_launch)

    with pytest.raises(NapariLaunchError):
        await launcher.open([str(a)])


async def test_concurrent_open_calls_are_serialized(tmp_path, monkeypatch) -> None:
    """Two concurrent open() calls must not both call _launch — only one."""
    launcher = _make_launcher()
    a = tmp_path / "a.tif"
    a.write_bytes(b"\0")

    conn = _FakeConnection()
    conn.responses.extend([{"status": "ok"}, {"status": "ok"}])

    launch_count = {"n": 0}
    started_event = asyncio.Event()
    release_event = asyncio.Event()

    def _slow_launch(self: NapariLauncher) -> None:
        launch_count["n"] += 1
        _attach_alive(self, conn=conn)
        # signal we started, then block to keep the lock held
        started_event.set()
        # busy-wait on a sync event flag; this stub runs in a thread (asyncio.to_thread)
        # so we can sleep here without blocking the loop.
        import time
        for _ in range(50):
            if release_event.is_set():
                return
            time.sleep(0.01)

    monkeypatch.setattr(NapariLauncher, "_launch", _slow_launch)

    t1 = asyncio.create_task(launcher.open([str(a)]))
    await started_event.wait()
    # Second call should queue on the lock; by the time it acquires, we are alive.
    t2 = asyncio.create_task(launcher.open([str(a)]))
    # Allow t1 to finish.
    release_event.set()
    await asyncio.wait_for(asyncio.gather(t1, t2), timeout=2.0)
    assert launch_count["n"] == 1


# ---------------------------------------------------------------------------
# shutdown()
# ---------------------------------------------------------------------------


async def test_shutdown_sends_shutdown_command_and_waits_for_exit() -> None:
    launcher = _make_launcher()
    fake = _FakeConnection()
    fake.responses.append({"status": "ok"})
    _attach_alive(launcher, conn=fake)
    proc = launcher._process
    proc.wait.return_value = 0  # type: ignore[union-attr]

    await launcher.shutdown()
    assert fake.sent == [{"action": "shutdown"}]
    proc.wait.assert_called_once()  # type: ignore[union-attr]
    assert launcher._connection is None
    assert launcher._process is None


async def test_shutdown_kills_process_if_no_exit_within_timeout() -> None:
    import subprocess

    launcher = _make_launcher()
    fake = _FakeConnection()
    fake.responses.append({"status": "ok"})
    _attach_alive(launcher, conn=fake)
    proc = launcher._process
    proc.wait.side_effect = subprocess.TimeoutExpired(cmd="napari", timeout=5)  # type: ignore[union-attr]

    await launcher.shutdown()
    proc.kill.assert_called_once()  # type: ignore[union-attr]
    assert launcher._connection is None
    assert launcher._process is None


async def test_shutdown_is_noop_when_not_running() -> None:
    launcher = _make_launcher()
    # Should simply not raise; no IPC.
    await launcher.shutdown()
    assert launcher._connection is None
    assert launcher._process is None


async def test_shutdown_is_idempotent() -> None:
    launcher = _make_launcher()
    fake = _FakeConnection()
    fake.responses.append({"status": "ok"})
    _attach_alive(launcher, conn=fake)
    proc = launcher._process
    proc.wait.return_value = 0  # type: ignore[union-attr]

    await launcher.shutdown()
    await launcher.shutdown()  # second call — must not raise / no-op
    # Only one shutdown command was sent.
    assert fake.sent == [{"action": "shutdown"}]


async def test_shutdown_emits_environment_status_stopped_when_cm_provided() -> None:
    cm = MagicMock()
    cm.broadcast_environment_status = MagicMock()
    launcher = _make_launcher(connection_manager=cm)
    fake = _FakeConnection()
    fake.responses.append({"status": "ok"})
    _attach_alive(launcher, conn=fake)
    launcher._process.wait.return_value = 0  # type: ignore[union-attr]

    await launcher.shutdown()
    cm.broadcast_environment_status.assert_called_once_with("napari", "stopped")


# ---------------------------------------------------------------------------
# _launch placeholder
# ---------------------------------------------------------------------------


def test_launch_placeholder_raises_not_implemented() -> None:
    launcher = _make_launcher()
    with pytest.raises(NotImplementedError):
        launcher._launch()
