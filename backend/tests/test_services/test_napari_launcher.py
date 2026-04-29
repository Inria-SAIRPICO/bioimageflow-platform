"""Tests for :mod:`bioimageflow_server.services.napari_launcher`.

Task B3 covers the skeleton: state, ``_is_alive``, ``_send_command``,
``async open/shutdown``, lock-free ``status``. ``_launch()`` raises
``NotImplementedError`` here — its real implementation is Task B4.

External dependencies (Wetlands, multiprocessing.connection.Client) are
mocked. No real subprocess is started.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
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


# ---------------------------------------------------------------------------
# B4 — _launch() with Wetlands
# ---------------------------------------------------------------------------


class _FakeProcessLogger:
    def __init__(self, port_line: str | None = "Listening port 54321") -> None:
        self._port_line = port_line
        self.predicate_calls: list[Any] = []

    def wait_for_line(self, predicate, timeout=None, include_history=True):
        self.predicate_calls.append(predicate)
        if self._port_line is None:
            return None
        if predicate(self._port_line):
            return self._port_line
        return None


class _FakeEnvironment:
    def __init__(self, name: str, path: str) -> None:
        self.name = name
        from pathlib import Path as _P
        self.path = _P(path)


class _FakeEnvManager:
    """Stand-in for wetlands EnvironmentManager."""

    def __init__(self, *, port_line: str | None = "Listening port 54321") -> None:
        self.created: list[dict[str, Any]] = []
        self.loaded: list[tuple[str, Any]] = []
        self.executed: list[dict[str, Any]] = []
        self.process = MagicMock()
        self.process.pid = 9999
        self.process.poll.return_value = None
        self._logger = _FakeProcessLogger(port_line=port_line)
        self._env = _FakeEnvironment("napari", "/envs/napari")

    def create(self, name, dependencies=None, additional_install_commands=None,
               use_existing=False):
        self.created.append(
            {
                "name": name,
                "dependencies": dependencies,
                "use_existing": use_existing,
            }
        )
        return self._env

    def load(self, name, environment_path):
        self.loaded.append((name, environment_path))
        return self._env

    def execute_commands(self, environment, commands, *, popen_kwargs=None,
                         **kwargs):
        self.executed.append(
            {
                "environment": environment,
                "commands": commands,
                "popen_kwargs": popen_kwargs or {},
                "kwargs": kwargs,
            }
        )
        return self.process

    def get_process_logger(self, process):
        return self._logger


def _patch_launch_deps(monkeypatch, *, env_manager: _FakeEnvManager,
                        client_factory, urandom_value: bytes = b"\x00" * 32):
    """Patch external collaborators that ``_launch`` uses."""
    from bioimageflow_server.services import napari_launcher as nl_mod

    monkeypatch.setattr(
        nl_mod, "get_shared_environment_manager", lambda **_: env_manager
    )
    monkeypatch.setattr(nl_mod.os, "urandom", lambda n: urandom_value[:n])
    monkeypatch.setattr(nl_mod, "Client", client_factory)


def test_launch_creates_environment_when_path_is_none(monkeypatch) -> None:
    em = _FakeEnvManager()
    client_calls: list[tuple] = []

    def _client(addr, *, authkey):
        client_calls.append((addr, authkey))
        return _FakeConnection()

    _patch_launch_deps(monkeypatch, env_manager=em, client_factory=_client)
    launcher = _make_launcher()
    launcher._launch()

    assert len(em.created) == 1
    rec = em.created[0]
    assert rec["name"] == "napari"
    assert rec["use_existing"] is False
    deps = rec["dependencies"]
    assert deps["python"] == "3.12"
    assert "conda-forge::napari" in deps["conda"]
    assert "conda-forge::pyqt" in deps["conda"]
    assert deps["pip"] == []


def test_launch_loads_existing_environment_when_path_set(tmp_path, monkeypatch) -> None:
    env_dir = tmp_path / "napari-env"
    env_dir.mkdir()
    em = _FakeEnvManager()

    def _client(addr, *, authkey):
        return _FakeConnection()

    _patch_launch_deps(monkeypatch, env_manager=em, client_factory=_client)
    launcher = NapariLauncher(napari_env_path=str(env_dir))
    launcher._launch()
    assert em.created == []
    assert len(em.loaded) == 1
    name, path = em.loaded[0]
    assert name == "napari"
    assert Path(str(path)).resolve() == env_dir.resolve()


def test_launch_reads_port_from_stdout_via_predicate(monkeypatch) -> None:
    em = _FakeEnvManager(port_line="Listening port 54321")

    seen: list[tuple] = []

    def _client(addr, *, authkey):
        seen.append((addr, authkey))
        return _FakeConnection()

    _patch_launch_deps(monkeypatch, env_manager=em, client_factory=_client)
    launcher = _make_launcher()
    launcher._launch()
    assert seen[0][0] == ("localhost", 54321)
    # Confirm a startswith-style predicate was used (not a string match).
    assert callable(em._logger.predicate_calls[0])


def test_launch_passes_authkey_via_env_var(monkeypatch) -> None:
    fake_authkey = b"\x11" * 32
    em = _FakeEnvManager()
    client_authkeys: list[bytes] = []

    def _client(addr, *, authkey):
        client_authkeys.append(authkey)
        return _FakeConnection()

    _patch_launch_deps(
        monkeypatch, env_manager=em, client_factory=_client,
        urandom_value=fake_authkey,
    )
    launcher = _make_launcher()
    launcher._launch()

    rec = em.executed[0]
    child_env = rec["popen_kwargs"]["env"]
    assert child_env["NAPARI_AUTHKEY"] == fake_authkey.hex()
    assert client_authkeys[0] == fake_authkey


def test_launch_strips_qt_api_from_subprocess_env(monkeypatch) -> None:
    monkeypatch.setenv("QT_API", "pyqt5")
    em = _FakeEnvManager()

    def _client(addr, *, authkey):
        return _FakeConnection()

    _patch_launch_deps(monkeypatch, env_manager=em, client_factory=_client)
    launcher = _make_launcher()
    launcher._launch()

    child_env = em.executed[0]["popen_kwargs"]["env"]
    assert "QT_API" not in child_env


def test_launch_quotes_napari_manager_path(monkeypatch) -> None:
    em = _FakeEnvManager()

    def _client(addr, *, authkey):
        return _FakeConnection()

    _patch_launch_deps(monkeypatch, env_manager=em, client_factory=_client)
    launcher = _make_launcher()
    launcher._launch()

    cmd = em.executed[0]["commands"]
    assert isinstance(cmd, list) and len(cmd) == 1
    cmd_str = cmd[0]
    assert cmd_str.startswith("python -u ")
    assert '"' in cmd_str  # path is double-quoted
    assert "napari_manager.py" in cmd_str


def test_launch_raises_when_port_line_not_found(monkeypatch) -> None:
    em = _FakeEnvManager(port_line=None)

    def _client(addr, *, authkey):
        return _FakeConnection()

    _patch_launch_deps(monkeypatch, env_manager=em, client_factory=_client)
    launcher = _make_launcher()
    with pytest.raises(NapariLaunchError):
        launcher._launch()


def test_launch_raises_when_process_exits_before_port(monkeypatch) -> None:
    em = _FakeEnvManager(port_line=None)
    em.process.poll.return_value = 1  # already exited

    def _client(addr, *, authkey):
        return _FakeConnection()

    _patch_launch_deps(monkeypatch, env_manager=em, client_factory=_client)
    launcher = _make_launcher()
    with pytest.raises(NapariLaunchError):
        launcher._launch()


def test_launch_wraps_authentication_error(monkeypatch) -> None:
    import multiprocessing

    em = _FakeEnvManager()

    def _client(addr, *, authkey):
        raise multiprocessing.AuthenticationError("digest mismatch")

    _patch_launch_deps(monkeypatch, env_manager=em, client_factory=_client)
    launcher = _make_launcher()
    with pytest.raises(NapariLaunchError, match="authkey"):
        launcher._launch()


def test_launch_idempotent_when_already_alive(monkeypatch) -> None:
    em = _FakeEnvManager()
    call_count = {"n": 0}

    def _client(addr, *, authkey):
        call_count["n"] += 1
        return _FakeConnection()

    _patch_launch_deps(monkeypatch, env_manager=em, client_factory=_client)
    launcher = _make_launcher()
    launcher._launch()
    launcher._launch()  # second call — alive, no-op
    assert call_count["n"] == 1
    assert len(em.executed) == 1


def test_launch_emits_creating_then_running_status(monkeypatch) -> None:
    em = _FakeEnvManager()

    def _client(addr, *, authkey):
        return _FakeConnection()

    _patch_launch_deps(monkeypatch, env_manager=em, client_factory=_client)
    cm = MagicMock()
    statuses: list[str] = []
    cm.broadcast_environment_status = (
        lambda env, st: statuses.append(st)
    )
    launcher = _make_launcher(connection_manager=cm)
    launcher._launch()
    assert statuses == ["creating", "running"]


def test_launch_emits_stopped_when_step_fails(monkeypatch) -> None:
    em = _FakeEnvManager(port_line=None)

    def _client(addr, *, authkey):
        return _FakeConnection()

    _patch_launch_deps(monkeypatch, env_manager=em, client_factory=_client)
    cm = MagicMock()
    statuses: list[str] = []
    cm.broadcast_environment_status = (
        lambda env, st: statuses.append(st)
    )
    launcher = _make_launcher(connection_manager=cm)
    with pytest.raises(NapariLaunchError):
        launcher._launch()
    assert statuses == ["creating", "stopped"]


# ---------------------------------------------------------------------------
# B7 Part A — Auto-reconnect, error recovery
# ---------------------------------------------------------------------------


async def test_open_reconnects_on_eof_error(tmp_path, monkeypatch) -> None:
    launcher = _make_launcher()
    a = tmp_path / "a.tif"
    a.write_bytes(b"\0")
    initial = _FakeConnection()
    initial.recv_exc = EOFError()
    fresh = _FakeConnection()
    fresh.responses.append({"status": "ok"})
    _attach_alive(launcher, conn=initial)
    monkeypatch.setattr(
        NapariLauncher, "_launch",
        lambda self: _attach_alive(self, conn=fresh),
    )
    await launcher.open([str(a)])
    assert fresh.sent == [
        {"action": "open", "paths": [str(a)], "clear_layers": False}
    ]


async def test_open_reconnects_on_broken_pipe(tmp_path, monkeypatch) -> None:
    launcher = _make_launcher()
    a = tmp_path / "a.tif"
    a.write_bytes(b"\0")
    initial = _FakeConnection()
    initial.send_exc = BrokenPipeError()
    fresh = _FakeConnection()
    fresh.responses.append({"status": "ok"})
    _attach_alive(launcher, conn=initial)
    monkeypatch.setattr(
        NapariLauncher, "_launch",
        lambda self: _attach_alive(self, conn=fresh),
    )
    await launcher.open([str(a)])
    assert fresh.sent == [
        {"action": "open", "paths": [str(a)], "clear_layers": False}
    ]


async def test_status_reports_new_pid_after_reconnect(tmp_path, monkeypatch) -> None:
    launcher = _make_launcher()
    a = tmp_path / "a.tif"
    a.write_bytes(b"\0")
    initial = _FakeConnection()
    initial.send_exc = ConnectionResetError()
    fresh = _FakeConnection()
    fresh.responses.append({"status": "ok"})
    _attach_alive(launcher, conn=initial, pid=111)

    def _relaunch(self: NapariLauncher) -> None:
        _attach_alive(self, conn=fresh, pid=222)

    monkeypatch.setattr(NapariLauncher, "_launch", _relaunch)
    await launcher.open([str(a)])
    assert launcher.status().pid == 222


async def test_status_after_crash_without_reconnect_reports_not_running() -> None:
    launcher = _make_launcher()
    fake = _attach_alive(launcher)
    fake.send_exc = ConnectionResetError()
    with pytest.raises(NapariConnectionError):
        launcher._send_command({"action": "open", "paths": []})
    # The user-visible truth is running=False (the connection was reset
    # and the process reference cleared by _send_command). The stale
    # pid value is harmless — the next open() call will relaunch.
    assert launcher.status().running is False


async def test_open_does_not_reconnect_more_than_once(tmp_path, monkeypatch) -> None:
    """If the post-launch send also fails with a connection error, we
    surface NapariLaunchError without infinite-looping.
    """
    launcher = _make_launcher()
    a = tmp_path / "a.tif"
    a.write_bytes(b"\0")
    initial = _FakeConnection()
    initial.send_exc = ConnectionResetError()
    retry = _FakeConnection()
    retry.send_exc = ConnectionResetError()  # also fails
    _attach_alive(launcher, conn=initial)
    launch_calls = {"n": 0}

    def _relaunch(self: NapariLauncher) -> None:
        launch_calls["n"] += 1
        _attach_alive(self, conn=retry)

    monkeypatch.setattr(NapariLauncher, "_launch", _relaunch)
    with pytest.raises(NapariLaunchError):
        await launcher.open([str(a)])
    assert launch_calls["n"] == 1  # exactly one reconnect


async def test_simultaneous_open_during_reconnect_skips_relaunch(
    tmp_path, monkeypatch
) -> None:
    """Two concurrent open() calls hitting a dead launcher: only one
    relaunch is performed; the second sees alive and just sends.
    """
    launcher = _make_launcher()
    a = tmp_path / "a.tif"
    a.write_bytes(b"\0")
    fresh = _FakeConnection()
    fresh.responses.extend([{"status": "ok"}, {"status": "ok"}])
    launch_count = {"n": 0}

    def _relaunch(self: NapariLauncher) -> None:
        launch_count["n"] += 1
        _attach_alive(self, conn=fresh)

    monkeypatch.setattr(NapariLauncher, "_launch", _relaunch)

    # Both calls start with a not-alive launcher; they queue on the
    # async lock; the first triggers _launch, the second sees alive.
    t1 = asyncio.create_task(launcher.open([str(a)]))
    t2 = asyncio.create_task(launcher.open([str(a)]))
    await asyncio.wait_for(asyncio.gather(t1, t2), timeout=2.0)
    assert launch_count["n"] == 1


async def test_authkey_mismatch_wraps_as_launch_error_and_emits_stopped(
    monkeypatch,
) -> None:
    import multiprocessing

    em = _FakeEnvManager()

    def _client(addr, *, authkey):
        raise multiprocessing.AuthenticationError("digest mismatch")

    _patch_launch_deps(monkeypatch, env_manager=em, client_factory=_client)
    statuses: list[str] = []
    cm = MagicMock()
    cm.broadcast_environment_status = lambda env, st: statuses.append(st)
    launcher = _make_launcher(connection_manager=cm)
    with pytest.raises(NapariLaunchError, match="authkey"):
        launcher._launch()
    assert statuses == ["creating", "stopped"]


async def test_manager_dies_after_port_before_connect_emits_stopped(
    monkeypatch,
) -> None:
    """Process exits with non-zero between announcing port and Client()
    connect: Client raises ConnectionRefusedError. _launch wraps it and
    emits stopped.
    """
    em = _FakeEnvManager()

    def _client(addr, *, authkey):
        raise ConnectionRefusedError("manager died")

    _patch_launch_deps(monkeypatch, env_manager=em, client_factory=_client)
    statuses: list[str] = []
    cm = MagicMock()
    cm.broadcast_environment_status = lambda env, st: statuses.append(st)
    launcher = _make_launcher(connection_manager=cm)
    with pytest.raises((ConnectionRefusedError, NapariLaunchError)):
        launcher._launch()
    assert statuses == ["creating", "stopped"]


async def test_reconnect_emits_fresh_creating_and_running_events(
    tmp_path, monkeypatch
) -> None:
    """When the open() path triggers a reconnect via _launch, the
    frontend should see a fresh creating -> running cycle so the
    status indicator can flip back to creating briefly.
    """
    a = tmp_path / "a.tif"
    a.write_bytes(b"\0")

    em = _FakeEnvManager()
    fresh = _FakeConnection()
    fresh.responses.append({"status": "ok"})

    def _client(addr, *, authkey):
        return fresh

    _patch_launch_deps(monkeypatch, env_manager=em, client_factory=_client)

    statuses: list[str] = []
    cm = MagicMock()
    cm.broadcast_environment_status = lambda env, st: statuses.append(st)
    launcher = _make_launcher(connection_manager=cm)

    # Simulate a dead initial connection.
    initial = _FakeConnection()
    initial.send_exc = ConnectionResetError()
    _attach_alive(launcher, conn=initial)

    await launcher.open([str(a)])
    assert "creating" in statuses
    assert statuses[-1] == "running"
