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
import time
from multiprocessing.connection import Client
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bioimageflow.env_manager import get_shared_environment_manager
from wetlands import (
    EnvironmentNotReadyError,
    EnvironmentSpec,
    ManagedProcess,
    OutputStream,
    ProcessLineTimeoutError,
    ProcessTimeoutError,
)

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
        connection_manager: ConnectionManager | None = None,
    ) -> None:
        self._connection_manager = connection_manager
        self._connection: Connection | None = None
        self._process: ManagedProcess | None = None
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
        return proc.running

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
                stale_process = self._process
                self._connection = None
                self._process = None
                self._pid = None
                if stale_process is not None:
                    try:
                        await asyncio.to_thread(stale_process.close)
                    except Exception as exc:  # noqa: BLE001
                        _logger.warning("stale napari process cleanup raised: %r", exc)
                # Already stopped — emit nothing (broadcasting "stopped" on
                # every shutdown call would be noisy on app teardown).
                return

            proc = self._process
            assert proc is not None  # for type narrowing

            try:
                self._send_command({"action": "shutdown"})
            except (NapariConnectionError, TimeoutError) as exc:
                _logger.debug("napari shutdown command failed: %r", exc)

            try:
                await proc.wait_async(_SHUTDOWN_WAIT_SECONDS, check=False)
            except ProcessTimeoutError:
                _logger.warning(
                    "napari did not exit within %.1fs; Wetlands terminated its process tree",
                    _SHUTDOWN_WAIT_SECONDS,
                )
            except Exception as exc:  # noqa: BLE001
                _logger.warning("napari wait raised: %r", exc)
            finally:
                try:
                    await asyncio.to_thread(proc.close)
                except Exception as exc:  # noqa: BLE001
                    _logger.warning("napari process cleanup raised: %r", exc)

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

        stale_process = self._process
        self._process = None
        if stale_process is not None:
            stale_process.close()

        process: ManagedProcess | None = None
        try:
            env_manager = get_shared_environment_manager()
            try:
                env_manager.environment("napari")
                launch_status = "opening"
            except EnvironmentNotReadyError:
                launch_status = "creating"

            # Announce whether Wetlands must install the environment or can
            # immediately launch Napari from an existing one.
            self._broadcast_status(launch_status)

            environment = env_manager.provision(
                "napari",
                EnvironmentSpec(
                    python="3.12.*",
                    conda=("napari", "pyqt"),
                    channels=("conda-forge",),
                ),
                replace_existing=True,
            ).wait_for()

            # Step 6: per-launch authkey (32 random bytes, hex-encoded for
            # safe transit through the env var).
            authkey = os.urandom(32)

            # Step 7: absolute path to the helper script (handles paths
            # with spaces).
            napari_manager_path = (
                Path(__file__).parent.parent / "_external" / "napari_manager.py"
            ).resolve()

            process = environment.spawn(
                ["python", "-u", str(napari_manager_path)],
                env={
                    "QT_API": None,
                    "NAPARI_AUTHKEY": authkey.hex(),
                    "NAPARI_PORT_PREFIX": _PORT_LINE_PREFIX,
                },
                output_limit=16 * 1024 * 1024,
            )
            assert process is not None
            try:
                event = process.wait_for_line(
                    lambda output: output.stream is OutputStream.STDOUT
                    and output.text.startswith(_PORT_LINE_PREFIX),
                    timeout=_PORT_LINE_TIMEOUT_SECONDS,
                )
            except (EOFError, ProcessLineTimeoutError) as exc:
                raise NapariLaunchError(
                    "napari manager did not announce a port within "
                    f"{_PORT_LINE_TIMEOUT_SECONDS:.0f}s"
                ) from exc

            # Step 12: parse.
            port = int(event.text.removeprefix(_PORT_LINE_PREFIX).strip())

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
            if process is not None:
                try:
                    process.close()
                except Exception:  # noqa: BLE001
                    _logger.exception("failed to clean up unsuccessful napari launch")
            # Any failure between the initial status and a successful connect
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
