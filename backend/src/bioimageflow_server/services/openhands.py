"""OpenHands local subprocess lifecycle service."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from bioimageflow_server.models.openhands import OpenHandsContext, OpenHandsStatus
from bioimageflow_server.models.settings import Settings, _is_loopback_host


_logger = logging.getLogger(__name__)

_SHUTDOWN_WAIT_SECONDS = 5.0
_ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
_RISKY_ENV_FRAGMENTS = (
    "KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "CREDENTIAL",
    "AUTH",
)
_RISKY_ENV_NAMES = {
    "SSH_AUTH_SOCK",
    "PYTHONPATH",
    "VIRTUAL_ENV",
    "CONDA_PREFIX",
    "CONDA_DEFAULT_ENV",
    "UV_INDEX_URL",
    "PIP_INDEX_URL",
}


class OpenHandsLaunchError(Exception):
    """OpenHands could not be launched."""


class OpenHandsUnavailableError(OpenHandsLaunchError):
    """OpenHands is unavailable under the effective settings."""


class OpenHandsService:
    """Owns at most one OpenHands subprocess started by this server."""

    def __init__(
        self,
        *,
        settings_provider: Callable[[], Settings],
        default_workspace_provider: Callable[[], Path] | None = None,
    ) -> None:
        self._settings_provider = settings_provider
        self._default_workspace_provider = default_workspace_provider
        self._process: subprocess.Popen[Any] | None = None
        self._pid: int | None = None
        self._lock = asyncio.Lock()

    def _settings(self) -> Settings:
        return self._settings_provider()

    def _is_alive(self) -> bool:
        proc = self._process
        return proc is not None and proc.poll() is None

    def status(self) -> OpenHandsStatus:
        settings = self._settings()
        available, reason = self._availability(settings)
        if not self._is_alive():
            self._pid = None
        running = self._is_alive()
        installed = self._is_installed(settings)
        configured = settings.openhands_process_acknowledged
        setup_state = self._setup_state(
            available=available,
            installed=installed,
            configured=configured,
            running=running,
        )
        return OpenHandsStatus(
            available=available,
            running=running,
            pid=self._pid if running else None,
            url=self._url(settings) if running else None,
            reason=reason,
            installed=installed,
            configured=configured,
            setup_state=setup_state,
        )

    def context(self) -> OpenHandsContext:
        settings = self._settings()
        available, reason = self._availability(settings)
        return OpenHandsContext(
            available=available,
            reason=reason,
            deployment_mode=settings.deployment_mode,
            unsafe_webapp_features_enabled=settings.enable_unsafe_webapp_features,
            runtime=settings.openhands_runtime,
            host=settings.openhands_host,
            port=settings.openhands_port,
            url=self._url(settings),
            workspace=str(self._workspace_path(settings)),
            process_acknowledged=settings.openhands_process_acknowledged,
        )

    async def launch(self) -> OpenHandsStatus:
        async with self._lock:
            settings = self._settings()
            available, reason = self._availability(settings)
            if not available:
                raise OpenHandsUnavailableError(reason or "OpenHands is unavailable")
            if self._is_alive():
                return self.status()
            await asyncio.to_thread(self._launch_sync, settings)
            return self.status()

    async def shutdown(self) -> OpenHandsStatus:
        async with self._lock:
            proc = self._process
            if proc is None or proc.poll() is not None:
                self._process = None
                self._pid = None
                return self.status()

            self._terminate_process_group(proc, kill=False)
            try:
                await asyncio.to_thread(proc.wait, _SHUTDOWN_WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                _logger.warning(
                    "openhands did not exit within %.1fs; killing",
                    _SHUTDOWN_WAIT_SECONDS,
                )
                self._terminate_process_group(proc, kill=True)
            except Exception as exc:  # noqa: BLE001
                _logger.warning("openhands wait raised: %r", exc)
            finally:
                self._process = None
                self._pid = None

            return self.status()

    def _launch_sync(self, settings: Settings) -> None:
        workspace = self._workspace_path(settings)
        workspace.mkdir(parents=True, exist_ok=True)
        args, env = self._command_and_env(settings)

        try:
            proc = subprocess.Popen(
                args,
                cwd=str(workspace),
                env=env,
                start_new_session=True,
            )
        except OSError as exc:
            raise OpenHandsLaunchError(str(exc)) from exc

        self._process = proc
        self._pid = proc.pid
        try:
            self._wait_until_listening(
                settings.openhands_host,
                settings.openhands_port,
                settings.openhands_startup_timeout,
            )
        except Exception:
            self._terminate_failed_launch(proc)
            self._process = None
            self._pid = None
            raise

    def _command_and_env(self, settings: Settings) -> tuple[list[str], dict[str, str]]:
        rendered = settings.openhands_command.format(
            runtime=settings.openhands_runtime,
            host=settings.openhands_host,
            port=settings.openhands_port,
            workspace=str(self._workspace_path(settings)),
        )
        tokens = shlex.split(rendered)
        if not tokens:
            raise OpenHandsLaunchError("openhands_command resolved to an empty command")

        env_assignments: dict[str, str] = {}
        while tokens and _ENV_ASSIGNMENT_RE.match(tokens[0]):
            key, value = tokens.pop(0).split("=", 1)
            env_assignments[key] = value
        if not tokens:
            raise OpenHandsLaunchError("openhands_command did not contain an executable")

        tokens = self._normalize_command_args(tokens, settings)
        child_env = self._scrubbed_env()
        child_env.update(env_assignments)
        child_env["RUNTIME"] = settings.openhands_runtime
        return tokens, child_env

    def _wait_until_listening(self, host: str, port: int, timeout: float) -> None:
        if timeout <= 0:
            return

        deadline = time.monotonic() + timeout
        last_error: OSError | None = None
        while time.monotonic() < deadline:
            proc = self._process
            if proc is not None and proc.poll() is not None:
                raise OpenHandsLaunchError(
                    f"OpenHands exited during startup with code {proc.poll()}"
                )
            try:
                with socket.create_connection((host, port), timeout=0.2):
                    return
            except OSError as exc:
                last_error = exc
                time.sleep(0.1)
        detail = f": {last_error}" if last_error is not None else ""
        raise OpenHandsLaunchError(
            f"OpenHands did not listen on {host}:{port} within {timeout:.1f}s{detail}"
        )

    def _availability(self, settings: Settings) -> tuple[bool, str | None]:
        if settings.openhands_enabled is False:
            return False, "disabled"
        if settings.deployment_mode == "desktop":
            return True, None
        if settings.enable_unsafe_webapp_features:
            return True, None
        return False, "unsafe_webapp_features_disabled"

    def _workspace_path(self, settings: Settings) -> Path:
        if (
            self._default_workspace_provider is not None
            and settings.openhands_workspace == Settings.model_fields["openhands_workspace"].default
        ):
            return self._default_workspace_provider().expanduser().resolve()
        return Path(settings.openhands_workspace).expanduser().resolve()

    def _is_installed(self, settings: Settings) -> bool:
        try:
            tokens = shlex.split(settings.openhands_command)
        except ValueError:
            return False
        executable = next(
            (token for token in tokens if not _ENV_ASSIGNMENT_RE.match(token)),
            None,
        )
        if executable is None:
            return False
        return shutil.which(Path(executable).name) is not None

    def _setup_state(
        self,
        *,
        available: bool,
        installed: bool,
        configured: bool,
        running: bool,
    ) -> str:
        if running:
            return "running"
        if not available:
            return "unavailable"
        if not installed:
            return "missing"
        if not configured:
            return "needs_config"
        return "ready"

    def _url(self, settings: Settings) -> str:
        host = f"[{settings.openhands_host}]" if ":" in settings.openhands_host else settings.openhands_host
        return f"http://{host}:{settings.openhands_port}"

    def _normalize_command_args(self, args: list[str], settings: Settings) -> list[str]:
        executable = Path(args[0]).name
        if executable != "openhands":
            raise OpenHandsLaunchError("openhands_command executable must be 'openhands'")

        normalized: list[str] = []
        host_seen = False
        port_seen = False
        index = 0
        while index < len(args):
            arg = args[index]
            host: str | None = None
            if arg == "--host":
                if index + 1 >= len(args):
                    raise OpenHandsLaunchError("OpenHands command --host is missing a value")
                host = args[index + 1]
                host_seen = True
                if not _is_loopback_host(host):
                    raise OpenHandsLaunchError("OpenHands command host must be loopback-only")
                normalized.extend(["--host", settings.openhands_host])
                index += 2
                continue
            elif arg.startswith("--host="):
                host = arg.split("=", 1)[1]
                host_seen = True
                if not _is_loopback_host(host):
                    raise OpenHandsLaunchError("OpenHands command host must be loopback-only")
                normalized.append(f"--host={settings.openhands_host}")
                index += 1
                continue
            if arg == "--port":
                if index + 1 >= len(args):
                    raise OpenHandsLaunchError("OpenHands command --port is missing a value")
                port_seen = True
                normalized.extend(["--port", str(settings.openhands_port)])
                index += 2
                continue
            if arg.startswith("--port="):
                port_seen = True
                normalized.append(f"--port={settings.openhands_port}")
                index += 1
                continue
            normalized.append(arg)
            index += 1
        if not host_seen:
            normalized.extend(["--host", settings.openhands_host])
        if not port_seen:
            normalized.extend(["--port", str(settings.openhands_port)])
        return normalized

    def _scrubbed_env(self) -> dict[str, str]:
        env: dict[str, str] = {}
        for key, value in os.environ.items():
            upper = key.upper()
            if upper in _RISKY_ENV_NAMES:
                continue
            if any(fragment in upper for fragment in _RISKY_ENV_FRAGMENTS):
                continue
            env[key] = value
        return env

    def _terminate_failed_launch(self, proc: subprocess.Popen[Any]) -> None:
        if proc.poll() is not None:
            return
        try:
            self._terminate_process_group(proc, kill=False)
            proc.wait(timeout=_SHUTDOWN_WAIT_SECONDS)
        except subprocess.TimeoutExpired:
            self._terminate_process_group(proc, kill=True)
        except Exception:  # noqa: BLE001
            _logger.warning("failed to terminate failed OpenHands launch", exc_info=True)

    def _terminate_process_group(self, proc: subprocess.Popen[Any], *, kill: bool) -> None:
        sig = signal.SIGKILL if kill else signal.SIGTERM
        try:
            os.killpg(proc.pid, sig)
            return
        except (AttributeError, ProcessLookupError, PermissionError, OSError):
            if kill:
                proc.kill()
            else:
                proc.terminate()
