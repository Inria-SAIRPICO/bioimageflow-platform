"""Legacy and per-environment napari process lifecycle services.

The backend hosts no Qt event loop. Each launcher starts the standalone
``napari_manager.py`` helper in its selected Python environment and talks to it
over authenticated local IPC.
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import os
import queue
import subprocess
import threading
import time
from collections.abc import Callable
from multiprocessing.connection import Client
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID, uuid4

from bioimageflow.env_manager import get_shared_environment_manager
from wetlands import (
    EnvironmentNotReadyError,
    EnvironmentSpec,
    ManagedProcess,
    OutputStream,
    ProcessLineTimeoutError,
    ProcessTimeoutError,
)

from bioimageflow_server.models.napari import NapariEnvironmentStatus, NapariStatus
from bioimageflow_server.models.napari_environments import (
    NapariEnvironment,
    NapariEnvironmentList,
)
from bioimageflow_server.services.environment_logging import log_environment_operation_event

if TYPE_CHECKING:
    from multiprocessing.connection import Connection

    from bioimageflow_server.ws.handler import ConnectionManager


_logger = logging.getLogger(__name__)

_SHUTDOWN_WAIT_SECONDS = 5.0
_RESPONSE_TIMEOUT_SECONDS = 10.0
_PORT_LINE_TIMEOUT_SECONDS = 30.0
_PORT_LINE_PREFIX = "Listening port "
LifecycleStatus = Literal["stopped", "opening", "running", "failed"]


class NapariConnectionError(Exception):
    """Connection to the Napari manager process was lost."""

    def __init__(self, detail: str, *, command_may_have_been_sent: bool = False) -> None:
        super().__init__(detail)
        self.command_may_have_been_sent = command_may_have_been_sent


class NapariLaunchError(Exception):
    """Failed to launch (or relaunch) the Napari manager process."""


class NapariOpenError(Exception):
    """Napari completed an open request with a viewer/reader error."""


class NapariOpenOutcomeUnknown(TimeoutError):
    """An open was sent, but its completion could not be observed safely."""


class _SubprocessHandle:
    """Small process adapter used for registered-environment launches."""

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process
        self.pid = process.pid
        self._lines: queue.Queue[str | None] = queue.Queue()
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()

    @property
    def running(self) -> bool:
        return self._process.poll() is None

    def _read_output(self) -> None:
        stream = self._process.stdout
        if stream is None:
            self._lines.put(None)
            return
        try:
            for line in stream:
                self._lines.put(line.rstrip("\r\n"))
        finally:
            self._lines.put(None)

    def wait_for_port(self, timeout: float) -> int:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise NapariLaunchError(
                    f"napari manager did not announce a port within {timeout:.0f}s"
                )
            try:
                line = self._lines.get(timeout=remaining)
            except queue.Empty as exc:
                raise NapariLaunchError(
                    f"napari manager did not announce a port within {timeout:.0f}s"
                ) from exc
            if line is None:
                raise NapariLaunchError(
                    "napari manager exited before announcing its listening port"
                )
            if line.startswith(_PORT_LINE_PREFIX):
                try:
                    return int(line.removeprefix(_PORT_LINE_PREFIX).strip())
                except ValueError as exc:
                    raise NapariLaunchError(
                        f"napari manager announced an invalid port: {line!r}"
                    ) from exc

    async def wait_async(self, timeout: float, *, check: bool = False) -> None:
        del check
        await asyncio.to_thread(self._process.wait, timeout=timeout)

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=2)
        if self._process.stdout is not None:
            self._process.stdout.close()


class NapariLauncher:
    """Owns the lifecycle of the Napari manager subprocess.

    The Conda environment creation and subprocess launch are deferred to
    the first ``open()`` call so that constructing the launcher is cheap
    and safe at app startup.
    """

    def __init__(
        self,
        connection_manager: ConnectionManager | None = None,
        *,
        environment: NapariEnvironment | None = None,
        config_root: Path | None = None,
        process_factory: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
        managed_environment_provider: Callable[[str], Any] | None = None,
    ) -> None:
        self._connection_manager = connection_manager
        self._connection: Connection | None = None
        self._process: ManagedProcess | _SubprocessHandle | None = None
        self._env_path: str | None = None
        self._pid: int | None = None
        self._lock = asyncio.Lock()
        self._environment = environment
        self._config_root = config_root or Path.home() / ".bioimageflow" / "napari"
        self._process_factory = process_factory
        self._managed_environment_provider = (
            managed_environment_provider
            or (lambda name: get_shared_environment_manager().environment(name))
        )
        self._lifecycle_status: LifecycleStatus = "stopped"
        self._last_error: str | None = None

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

    def environment_status(self) -> NapariEnvironmentStatus:
        environment = self._environment
        if environment is None:
            raise RuntimeError("legacy launcher has no registered environment status")
        running = self._is_alive()
        status = "running" if running else self._lifecycle_status
        if not running and status == "running":
            status = "failed"
            self._last_error = self._last_error or "napari manager process is no longer connected"
        if status == "running":
            self._lifecycle_status = "running"
        return NapariEnvironmentStatus(
            running=running,
            env_path=environment.root,
            pid=self._pid,
            environment_id=environment.id,
            environment_name=environment.name,
            installation_identity=_installation_identity(environment),
            status=status,
            detail=self._last_error,
        )

    # ------------------------------------------------------------------
    # IPC
    # ------------------------------------------------------------------

    def _send_command(self, command: dict[str, Any]) -> dict[str, Any]:
        """Send a command and read the response.

        Raises:
            NapariConnectionError: if the channel is broken.
            NapariOpenOutcomeUnknown: if no trustworthy response arrives.
        """
        conn = self._connection
        if conn is None:
            raise NapariConnectionError("no active connection")
        sent = False
        try:
            # Once Connection.send() starts, a local exception cannot prove
            # that the peer accepted none of the framed payload.
            sent = True
            conn.send(command)
            if not conn.poll(timeout=_RESPONSE_TIMEOUT_SECONDS):
                self._invalidate_connection("napari manager response timed out")
                raise NapariOpenOutcomeUnknown(
                    f"napari manager did not respond within {_RESPONSE_TIMEOUT_SECONDS}s"
                )
            response = conn.recv()
        except NapariOpenOutcomeUnknown:
            raise
        except (EOFError, OSError) as exc:
            self._invalidate_connection(f"napari connection lost: {exc}")
            raise NapariConnectionError(
                str(exc), command_may_have_been_sent=sent
            ) from exc
        if not isinstance(response, dict):
            self._invalidate_connection("napari manager returned an invalid response")
            raise NapariOpenOutcomeUnknown("napari manager returned an invalid response")
        return response

    def _invalidate_connection(self, detail: str | None = None) -> None:
        connection = self._connection
        self._connection = None
        if connection is not None:
            try:
                connection.close()
            except (OSError, AttributeError):
                pass
        if self._environment is not None:
            self._lifecycle_status = "failed"
            self._last_error = detail

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def open(
        self,
        paths: list[str],
        clear_layers: bool = False,
        *,
        reader_id: str | None = None,
    ) -> None:
        """Open ``paths`` in the Napari viewer (lazily launching it).

        Validation note: paths are checked **before** the launcher lock is
        acquired so a bad request fails fast even when a slow ``_launch``
        is running for an earlier caller.

        The helper acknowledges only after the Qt-thread ``viewer.open()``
        call returns. A timeout or disconnect after dispatch is reported as
        an unknown outcome and is never replayed automatically.
        """
        missing = [p for p in paths if not Path(p).exists()]
        if missing:
            raise FileNotFoundError(missing)

        async with self._lock:
            if not self._is_alive():
                await asyncio.to_thread(self._launch)

            command: dict[str, Any] = {
                "action": "open",
                "paths": paths,
                "clear_layers": clear_layers,
            }
            if self._environment is not None:
                command["request_id"] = str(uuid4())
            if reader_id is not None:
                command["reader_id"] = reader_id
            try:
                response = self._send_command(command)
            except NapariConnectionError as exc:
                if exc.command_may_have_been_sent:
                    raise NapariOpenOutcomeUnknown(
                        "napari connection was lost after dispatch; the open outcome is unknown"
                    ) from exc
                raise NapariLaunchError(
                    f"napari connection was unavailable before dispatch: {exc}"
                ) from exc
            self._check_open_response(command, response)

    async def launch(self) -> None:
        """Start the viewer if needed without dispatching an open command."""

        async with self._lock:
            if not self._is_alive():
                await asyncio.to_thread(self._launch)

    async def shutdown(self) -> None:
        """Terminate the manager process. Idempotent."""
        async with self._lock:
            if not self._is_alive():
                stale_process = self._process
                self._invalidate_connection()
                self._process = None
                self._pid = None
                if stale_process is not None:
                    try:
                        await asyncio.to_thread(stale_process.close)
                    except Exception as exc:  # noqa: BLE001
                        _logger.warning("stale napari process cleanup raised: %r", exc)
                self._lifecycle_status = "stopped"
                self._last_error = None
                if self._environment is not None and stale_process is not None:
                    self._broadcast_status("stopped")
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
            except (ProcessTimeoutError, subprocess.TimeoutExpired):
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

            self._invalidate_connection()
            self._process = None
            self._pid = None
            self._lifecycle_status = "stopped"
            self._last_error = None

            if self._connection_manager is not None:
                self._broadcast_status("stopped")

    def _check_open_response(
        self, command: dict[str, Any], response: dict[str, Any]
    ) -> None:
        request_id = command.get("request_id")
        if request_id is not None and response.get("request_id") != request_id:
            self._invalidate_connection("napari manager response request ID did not match")
            raise NapariOpenOutcomeUnknown(
                "napari manager response did not match the dispatched request"
            )
        if response.get("status") == "ok":
            return
        if response.get("status") == "error":
            raise NapariOpenError(str(response.get("detail") or "napari open failed"))
        self._invalidate_connection("napari manager returned an invalid response")
        raise NapariOpenOutcomeUnknown("napari manager returned an invalid response")

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

        if self._environment is not None:
            try:
                self._launch_registered()
            except Exception as exc:
                if self._lifecycle_status != "failed":
                    self._lifecycle_status = "failed"
                    self._last_error = str(exc)
                    self._broadcast_status("failed")
                if isinstance(exc, NapariLaunchError):
                    raise
                raise NapariLaunchError(str(exc)) from exc
            return

        stale_process = self._process
        self._process = None
        self._invalidate_connection()
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

            operation = env_manager.provision(
                "napari",
                EnvironmentSpec(
                    python="3.12.*",
                    conda=("napari", "pyqt"),
                    channels=("conda-forge",),
                ),
                replace_existing=True,
            )
            operation.listen(
                lambda event: log_environment_operation_event(event, owner="Napari environment")
            )
            environment = operation.wait_for()

            # Step 6: per-launch authkey (32 random bytes, hex-encoded for
            # safe transit through the env var).
            authkey = os.urandom(32)

            # Step 7: absolute path to the helper script (handles paths
            # with spaces).
            napari_manager_path = (
                Path(__file__).parent.parent / "_external" / "napari_manager.py"
            ).resolve()
            config_path = (self._config_root / "legacy" / "settings.yaml").resolve()
            config_path.parent.mkdir(parents=True, exist_ok=True)

            process = environment.spawn(
                ["python", "-u", str(napari_manager_path)],
                env={
                    "QT_API": None,
                    "NAPARI_AUTHKEY": authkey.hex(),
                    "NAPARI_PORT_PREFIX": _PORT_LINE_PREFIX,
                    "NAPARI_CONFIG": str(config_path),
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

    def _launch_registered(self) -> None:
        environment = self._environment
        assert environment is not None
        if environment.state in {
            "setup_needed",
            "creating",
            "failed",
            "cancelled",
            "removing",
            "missing",
            "replaced",
            "probe_failed",
        }:
            raise NapariLaunchError(
                environment.last_error
                or f"napari environment is not launchable ({environment.state})"
            )
        if not environment.launch.argv_prefix:
            raise NapariLaunchError("registered napari environment has no launch argv")

        stale_process = self._process
        self._process = None
        self._invalidate_connection()
        if stale_process is not None:
            stale_process.close()

        config_path = (
            self._config_root / str(environment.id) / "settings.yaml"
        ).resolve()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        authkey = os.urandom(32)
        manager_path = (
            Path(__file__).parent.parent / "_external" / "napari_manager.py"
        ).resolve()
        argv = [
            *environment.launch.argv_prefix,
            "-u",
            str(manager_path),
        ]
        launch_env = _registered_launch_environment(
            authkey=authkey,
            config_path=config_path,
        )
        self._lifecycle_status = "opening"
        self._last_error = None
        self._broadcast_status("opening")
        process: ManagedProcess | _SubprocessHandle | None = None
        try:
            managed_environment = self._managed_environment_for_launch(environment)
            if managed_environment is not None:
                managed_process: ManagedProcess = managed_environment.spawn(
                    argv,
                    env=_managed_launch_environment(
                        authkey=authkey,
                        config_path=config_path,
                    ),
                    output_limit=16 * 1024 * 1024,
                )
                process = managed_process
                event = managed_process.wait_for_line(
                    lambda output: (
                        output.stream is OutputStream.STDOUT
                        and output.text.startswith(_PORT_LINE_PREFIX)
                    ),
                    timeout=_PORT_LINE_TIMEOUT_SECONDS,
                )
                port = int(event.text.removeprefix(_PORT_LINE_PREFIX).strip())
            else:
                popen = self._process_factory(  # noqa: S603 - persisted argv, never a shell
                    argv,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=launch_env,
                    shell=False,
                )
                process = _SubprocessHandle(popen)
                port = process.wait_for_port(_PORT_LINE_TIMEOUT_SECONDS)
            connection = Client(("localhost", port), authkey=authkey)
            assert process is not None
            self._process = process
            self._connection = connection
            self._env_path = environment.root
            self._pid = process.pid
        except (EOFError, ProcessLineTimeoutError) as exc:
            if process is not None:
                process.close()
            self._lifecycle_status = "failed"
            self._last_error = str(exc)
            self._broadcast_status("failed")
            raise NapariLaunchError(
                "napari manager did not announce a port within "
                f"{_PORT_LINE_TIMEOUT_SECONDS:.0f}s"
            ) from exc
        except Exception as exc:
            if process is not None:
                process.close()
            self._lifecycle_status = "failed"
            self._last_error = str(exc)
            self._broadcast_status("failed")
            if isinstance(exc, NapariLaunchError):
                raise
            raise NapariLaunchError(str(exc)) from exc
        self._lifecycle_status = "running"
        self._broadcast_status("running")

    def _managed_environment_for_launch(self, environment: NapariEnvironment) -> Any | None:
        metadata = environment.managed
        if environment.ownership != "managed" or metadata is None:
            return None
        try:
            managed_environment = self._managed_environment_provider(metadata.wetlands_name)
        except EnvironmentNotReadyError as exc:
            if metadata.recipe.source == "adopted":
                # Wetlands 1 pixi/workspaces installations can be adopted by
                # interpreter but are not generations owned by Wetlands 2.
                return None
            raise NapariLaunchError(
                f"managed napari environment {metadata.wetlands_name!r} is not ready"
            ) from exc
        managed_path = Path(managed_environment.path).resolve()
        if managed_path != Path(environment.root).resolve():
            if metadata.recipe.source == "adopted":
                return None
            raise NapariLaunchError(
                "managed napari environment generation does not match its registry root"
            )
        return managed_environment

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _broadcast_status(self, status: str) -> None:
        cm = self._connection_manager
        if cm is None:
            return
        try:
            environment = self._environment
            if _has_explicit_method(cm, "publish_environment_status"):
                publish = getattr(cm, "publish_environment_status")
                if environment is None:
                    publish("napari", status)
                else:
                    publish(
                        "napari",
                        status,
                        environment_id=str(environment.id),
                        environment_name=environment.name,
                    )
            else:
                broadcast = getattr(cm, "broadcast_environment_status")
                if environment is None:
                    broadcast("napari", status)
                else:
                    broadcast(
                        "napari",
                        status,
                        environment_id=str(environment.id),
                        environment_name=environment.name,
                    )
            if _has_explicit_method(cm, "publish_log"):
                label = environment.name if environment is not None else "Napari"
                getattr(cm, "publish_log")(
                    "INFO",
                    f"{label} environment {status}",
                    None,
                    time.time(),
                )
        except Exception as exc:  # noqa: BLE001
            # Broadcasts must never fail the launch/shutdown path.
            _logger.warning("environment_status broadcast failed: %r", exc)


def _has_explicit_method(obj: Any, name: str) -> bool:
    return name in getattr(obj, "__dict__", {}) or callable(getattr(type(obj), name, None))


def _installation_identity(environment: NapariEnvironment) -> str:
    inventory = environment.inventory.fingerprint if environment.inventory else "unprobed"
    if environment.managed is not None:
        base = str(environment.managed.installation_generation)
    else:
        base = f"{environment.interpreter_identity}:{environment.interpreter_fingerprint}"
    return f"{base}:{inventory}"


def _registered_launch_environment(
    *, authkey: bytes, config_path: Path
) -> dict[str, str]:
    keep = {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "XAUTHORITY",
        "DBUS_SESSION_BUS_ADDRESS",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
    }
    environment = {key: value for key, value in os.environ.items() if key in keep}
    environment.update(
        {
            "PYTHONNOUSERSITE": "1",
            "NAPARI_AUTHKEY": authkey.hex(),
            "NAPARI_PORT_PREFIX": _PORT_LINE_PREFIX,
            "NAPARI_CONFIG": str(config_path),
        }
    )
    return environment


def _managed_launch_environment(
    *, authkey: bytes, config_path: Path
) -> dict[str, str | None]:
    """Overrides for Wetlands-managed spawn, including inherited-state scrubbing."""
    return {
        "PYTHONHOME": None,
        "PYTHONPATH": None,
        "PYTHONUSERBASE": None,
        "QT_API": None,
        "PYTHONNOUSERSITE": "1",
        "NAPARI_AUTHKEY": authkey.hex(),
        "NAPARI_PORT_PREFIX": _PORT_LINE_PREFIX,
        "NAPARI_CONFIG": str(config_path),
    }


class NapariLauncherPool:
    """Lazy, independently locked launchers keyed by environment UUID."""

    def __init__(
        self,
        environment_provider: Callable[[], NapariEnvironmentList],
        *,
        legacy_launcher: NapariLauncher,
        connection_manager: ConnectionManager | None = None,
        config_root: Path,
        launcher_factory: Callable[..., NapariLauncher] = NapariLauncher,
        managed_environment_provider: Callable[[str], Any] | None = None,
    ) -> None:
        self._environment_provider = environment_provider
        self._legacy_launcher = legacy_launcher
        self._connection_manager = connection_manager
        self._config_root = config_root
        self._launcher_factory = launcher_factory
        self._managed_environment_provider = managed_environment_provider
        self._launchers: dict[UUID, NapariLauncher] = {}
        self._identities: dict[UUID, str] = {}
        self._locks: dict[UUID, asyncio.Lock] = {}

    def _resolve(self, environment_id: UUID) -> NapariEnvironment:
        for environment in self._environment_provider().environments:
            if environment.id == environment_id:
                return environment
        raise KeyError(f"napari environment {environment_id} is not registered")

    async def _launcher(self, environment_id: UUID) -> NapariLauncher:
        lock = self._locks.setdefault(environment_id, asyncio.Lock())
        async with lock:
            environment = self._resolve(environment_id)
            identity = _installation_identity(environment)
            current = self._launchers.get(environment_id)
            if current is not None and self._identities.get(environment_id) != identity:
                await current.shutdown()
                current = None
            if current is None:
                current = self._launcher_factory(
                    connection_manager=self._connection_manager,
                    environment=environment,
                    config_root=self._config_root,
                    managed_environment_provider=self._managed_environment_provider,
                )
                self._launchers[environment_id] = current
                self._identities[environment_id] = identity
            else:
                current._environment = environment
            return current

    async def open(
        self,
        paths: list[str],
        clear_layers: bool = False,
        *,
        environment_id: UUID | None = None,
        reader_id: str | None = None,
    ) -> None:
        if environment_id is None:
            if reader_id is None:
                await self._legacy_launcher.open(paths, clear_layers)
            else:
                await self._legacy_launcher.open(paths, clear_layers, reader_id=reader_id)
            return
        if len(paths) != 1:
            raise ValueError("an explicit napari environment requires exactly one artifact")
        if not Path(paths[0]).exists():
            raise FileNotFoundError(paths)
        launcher = await self._launcher(environment_id)
        await launcher.open(paths, clear_layers, reader_id=reader_id)

    async def launch(self, environment_id: UUID) -> None:
        """Start one registered viewer without adding or clearing layers."""

        launcher = await self._launcher(environment_id)
        await launcher.launch()

    def status(
        self, environment_id: UUID | None = None
    ) -> NapariStatus | NapariEnvironmentStatus:
        if environment_id is None:
            return self._legacy_launcher.status()
        environment = self._resolve(environment_id)
        launcher = self._launchers.get(environment_id)
        identity = _installation_identity(environment)
        if launcher is None or self._identities.get(environment_id) != identity:
            stale = launcher is not None
            if stale:
                stale_status = launcher.environment_status()
                if stale_status.running:
                    return stale_status.model_copy(
                        update={
                            "environment_name": environment.name,
                            "installation_identity": identity,
                            "status": "restart_required",
                            "detail": (
                                "environment inventory changed; the existing viewer must restart"
                            ),
                        }
                    )
            return NapariEnvironmentStatus(
                running=False,
                env_path=environment.root,
                pid=None,
                environment_id=environment.id,
                environment_name=environment.name,
                installation_identity=identity,
                status="stopped",
                detail=None,
            )
        launcher._environment = environment
        return launcher.environment_status()

    async def shutdown(self, environment_id: UUID | None = None) -> None:
        if environment_id is None:
            await self._legacy_launcher.shutdown()
            return
        launcher = self._launchers.get(environment_id)
        if launcher is None:
            self._resolve(environment_id)
            return
        await launcher.shutdown()

    async def shutdown_all(self) -> None:
        await asyncio.gather(
            self._legacy_launcher.shutdown(),
            *(launcher.shutdown() for launcher in list(self._launchers.values())),
            return_exceptions=False,
        )
