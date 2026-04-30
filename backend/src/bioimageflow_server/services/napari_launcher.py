"""NapariLauncher service.

Manages an external Napari process for viewing image outputs. The launcher
hosts no Qt event loop itself: it spawns a helper script
(``napari_manager.py``) inside an isolated Conda environment and talks to it
over an authenticated ``multiprocessing.connection`` channel.

Task B3 implements the skeleton (state, lock-free status, send/recv,
async open/shutdown). Task B4 implements ``_launch()``.
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import os
import subprocess
import time
from multiprocessing.connection import Client
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bioimageflow.env_manager import get_shared_environment_manager

from bioimageflow_server.models.napari import NapariStatus

if TYPE_CHECKING:
    from multiprocessing.connection import Connection

    from bioimageflow_server.ws.handler import ConnectionManager


_logger = logging.getLogger(__name__)

_SHUTDOWN_WAIT_SECONDS = 5.0
_RESPONSE_TIMEOUT_SECONDS = 10.0
_PORT_LINE_TIMEOUT_SECONDS = 30.0
_PORT_LINE_PREFIX = "Listening port "


class NapariConnectionError(Exception):
    """Connection to the Napari manager process was lost."""


class NapariLaunchError(Exception):
    """Failed to launch (or relaunch) the Napari manager process."""


class NapariLauncher:
    """Owns the lifecycle of the Napari manager subprocess.

    The Conda environment creation and subprocess launch are deferred to
    the first ``open()`` call so that constructing the launcher is cheap
    and safe at app startup.
    """

    def __init__(
        self,
        napari_env_path: str | None = None,
        connection_manager: ConnectionManager | None = None,
    ) -> None:
        self._napari_env_path = napari_env_path
        self._connection_manager = connection_manager
        self._connection: Connection | None = None
        self._process: subprocess.Popen[Any] | None = None
        self._env_path: str | None = None
        self._pid: int | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lock-free probes
    # ------------------------------------------------------------------

    def _is_alive(self) -> bool:
        proc = self._process
        if proc is None or self._connection is None:
            return False
        return proc.poll() is None

    def status(self) -> NapariStatus:
        """Return current status. **Lock-free** — safe to call concurrently
        with a long-running ``_launch``.
        """
        return NapariStatus(
            running=self._is_alive(),
            env_path=self._env_path,
            pid=self._pid,
        )

    # ------------------------------------------------------------------
    # IPC
    # ------------------------------------------------------------------

    def _send_command(self, command: dict[str, Any]) -> dict[str, Any]:
        """Send a command and read the response.

        Raises:
            NapariConnectionError: if the channel is broken (caller may
                relaunch and retry).
            TimeoutError: if no response arrives within the response window.
        """
        conn = self._connection
        if conn is None:
            raise NapariConnectionError("no active connection")
        try:
            conn.send(command)
            if not conn.poll(timeout=_RESPONSE_TIMEOUT_SECONDS):
                raise TimeoutError(
                    f"napari manager did not respond within {_RESPONSE_TIMEOUT_SECONDS}s"
                )
            return conn.recv()
        except (ConnectionResetError, EOFError, BrokenPipeError) as exc:
            self._connection = None
            self._process = None
            raise NapariConnectionError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def open(self, paths: list[str], clear_layers: bool = False) -> None:
        """Open ``paths`` in the Napari viewer (lazily launching it).

        Validation note: paths are checked **before** the launcher lock is
        acquired so a bad request fails fast even when a slow ``_launch``
        is running for an earlier caller.

        Open-result fidelity caveat: the response is queued onto the Qt
        thread; the manager replies ``{"status": "ok"}`` as soon as the
        command is enqueued, *before* ``viewer.open()`` actually finishes.
        Callers cannot distinguish a successful open from one that errors
        inside napari. v1 platform-produced outputs always carry their
        canonical extension; the symlink fallback used by Galaxy is out of
        scope here.
        """
        missing = [p for p in paths if not Path(p).exists()]
        if missing:
            raise FileNotFoundError(missing)

        async with self._lock:
            if not self._is_alive():
                await asyncio.to_thread(self._launch)

            command = {"action": "open", "paths": paths, "clear_layers": clear_layers}
            try:
                self._send_command(command)
            except NapariConnectionError:
                # Auto-reconnect once and retry. If the second attempt
                # fails we surface a launch error.
                await asyncio.to_thread(self._launch)
                try:
                    self._send_command(command)
                except NapariConnectionError as exc:
                    raise NapariLaunchError(
                        f"napari connection lost after relaunch: {exc}"
                    ) from exc

    async def shutdown(self) -> None:
        """Terminate the manager process. Idempotent."""
        async with self._lock:
            if not self._is_alive():
                # Already stopped — emit nothing (broadcasting "stopped" on
                # every shutdown call would be noisy on app teardown).
                self._connection = None
                self._process = None
                self._pid = None
                return

            proc = self._process
            assert proc is not None  # for type narrowing

            try:
                self._send_command({"action": "shutdown"})
            except (NapariConnectionError, TimeoutError) as exc:
                _logger.debug("napari shutdown command failed: %r", exc)

            try:
                await asyncio.to_thread(proc.wait, _SHUTDOWN_WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                _logger.warning(
                    "napari did not exit within %.1fs; killing", _SHUTDOWN_WAIT_SECONDS
                )
                proc.kill()
            except Exception as exc:  # noqa: BLE001
                _logger.warning("napari wait raised: %r", exc)

            self._connection = None
            self._process = None
            self._pid = None

            if self._connection_manager is not None:
                self._broadcast_status("stopped")

    # ------------------------------------------------------------------
    # Hooks for Task B4
    # ------------------------------------------------------------------

    def _launch(self) -> None:
        """Create/reuse the Conda env and launch ``napari_manager.py``.

        Synchronous: spawns the manager process, waits for the port-line
        on stdout, and connects the IPC channel. Called via
        ``asyncio.to_thread`` from ``open()`` so the event loop stays
        responsive while a multi-minute Conda solve runs.
        """
        # Step 1: short-circuit if already alive.
        if self._is_alive():
            return

        # Step 2: announce the long-running solve so the UI can flip a
        # spinner before we block on Wetlands.
        self._broadcast_status("creating")

        try:
            # Steps 3–5: get/create the Wetlands environment.
            env_manager = get_shared_environment_manager()
            if self._napari_env_path:
                environment = env_manager.load(
                    "napari", Path(self._napari_env_path)
                )
            else:
                environment = env_manager.create(
                    "napari",
                    dependencies={
                        "python": "3.12",
                        "conda": ["conda-forge::napari", "conda-forge::pyqt"],
                        "pip": [],
                    },
                    use_existing=True,
                )

            # Step 6: per-launch authkey (32 random bytes, hex-encoded for
            # safe transit through the env var).
            authkey = os.urandom(32)

            # Step 7: absolute path to the helper script (handles paths
            # with spaces).
            napari_manager_path = (
                Path(__file__).parent.parent / "_external" / "napari_manager.py"
            ).resolve()

            # Step 8: build child env, strip QT_API leak, inject authkey.
            child_env = os.environ.copy()
            child_env.pop("QT_API", None)
            child_env["NAPARI_AUTHKEY"] = authkey.hex()
            child_env["NAPARI_PORT_PREFIX"] = _PORT_LINE_PREFIX

            # Step 9: launch the helper. List-of-strings form (Galaxy
            # convention).
            commands = [f'python -u "{napari_manager_path}"']
            process = env_manager.execute_commands(
                environment,
                commands,
                popen_kwargs={"env": child_env},
            )

            # Step 10: get the process logger (default log=True keeps
            # stdout buffered for wait_for_line).
            process_logger = env_manager.get_process_logger(process)

            # Step 11: read the port from stdout via a startswith
            # predicate (matches Wetlands' own port_predicate
            # convention).
            line = process_logger.wait_for_line(
                lambda output_line: output_line.startswith(_PORT_LINE_PREFIX),
                timeout=_PORT_LINE_TIMEOUT_SECONDS,
            )
            if line is None:
                raise NapariLaunchError(
                    f"napari manager did not announce a port within "
                    f"{_PORT_LINE_TIMEOUT_SECONDS:.0f}s"
                )

            # Step 12: parse.
            port = int(line.removeprefix(_PORT_LINE_PREFIX).strip())

            # Step 13: connect; wrap AuthenticationError so the caller
            # sees a single failure type.
            try:
                connection = Client(("localhost", port), authkey=authkey)
            except multiprocessing.AuthenticationError as exc:
                raise NapariLaunchError(
                    f"napari authkey mismatch on connect: {exc}"
                ) from exc

            # Step 14: install state.
            self._process = process
            self._connection = connection
            env_path = getattr(environment, "path", None)
            self._env_path = str(env_path) if env_path else None
            self._pid = getattr(process, "pid", None)
        except Exception:
            # Any failure between "creating" and a successful connect
            # must flip the indicator back to "stopped" so the UI does
            # not stay stuck on the spinner.
            self._broadcast_status("stopped")
            raise

        # Step 15: announce success.
        self._broadcast_status("running")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _broadcast_status(self, status: str) -> None:
        cm = self._connection_manager
        if cm is None:
            return
        try:
            if _has_explicit_method(cm, "publish_environment_status"):
                getattr(cm, "publish_environment_status")("napari", status)
            else:
                getattr(cm, "broadcast_environment_status")("napari", status)
            if _has_explicit_method(cm, "publish_log"):
                getattr(cm, "publish_log")(
                    "INFO",
                    f"Napari environment {status}",
                    None,
                    time.time(),
                )
        except Exception as exc:  # noqa: BLE001
            # Broadcasts must never fail the launch/shutdown path.
            _logger.warning("environment_status broadcast failed: %r", exc)


def _has_explicit_method(obj: Any, name: str) -> bool:
    return name in getattr(obj, "__dict__", {}) or callable(getattr(type(obj), name, None))
