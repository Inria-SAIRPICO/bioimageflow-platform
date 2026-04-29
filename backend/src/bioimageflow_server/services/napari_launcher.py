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
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bioimageflow_server.models.napari import NapariStatus

if TYPE_CHECKING:
    from multiprocessing.connection import Connection

    from bioimageflow_server.ws.handler import ConnectionManager


_logger = logging.getLogger(__name__)

_SHUTDOWN_WAIT_SECONDS = 5.0
_RESPONSE_TIMEOUT_SECONDS = 10.0


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

        Implemented in Task B4. The B3 skeleton raises ``NotImplementedError``
        so any test path that calls it without monkeypatching fails loudly.
        """
        raise NotImplementedError("Task B4: implement Wetlands env + subprocess launch")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _broadcast_status(self, status: str) -> None:
        cm = self._connection_manager
        if cm is None:
            return
        try:
            cm.broadcast_environment_status("napari", status)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            # Broadcasts must never fail the launch/shutdown path.
            _logger.warning("environment_status broadcast failed: %r", exc)
