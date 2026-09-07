"""Editor opening service and embedded code-server manager."""

from __future__ import annotations

import hashlib
import logging
import os
import shlex
import subprocess
import threading
import time
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx
from wetlands import EnvironmentSpec, ManagedProcess

from bioimageflow_server.models.editor import (
    EditorLaunchPhase,
    EditorOpenMethod,
    EditorOpenResponse,
    EditorStatus,
)
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.services.editor_workspace import ensure_editor_workspace

CODE_SERVER_VERSION = "4.106.2"
DEFAULT_EDITOR_URL = "http://127.0.0.1:32344"
DEFAULT_CONTROL_URL = "http://127.0.0.1:60351"
CLIPBOARD_MESSAGE = "Path copied - open in your local editor."
EMBEDDED_LAUNCH_FAILED = "embedded_launch_failed"
EMBEDDED_STARTUP_TIMEOUT = "embedded_startup_timeout"
EMBEDDED_STARTUP_TIMEOUT_DETAIL = "code-server did not become available before timeout"
EMBEDDED_OPENER_TIMEOUT = "embedded_opener_timeout"
EMBEDDED_OPENER_TIMEOUT_DETAIL = (
    "code-server is running but the opener endpoint did not become available before timeout"
)
EMBEDDED_WORKSPACE_FAILED = "embedded_workspace_failed"

# Editor lifecycle records use the streamed framework logger so setup progress
# is available in the existing Logger panel as well as the Code Editor panel.
logger = logging.getLogger("bioimageflow.editor")


class EditorError(Exception):
    """Base class for editor service errors."""


class EditorPathError(EditorError):
    """Raised when the requested path is invalid for local editor opening."""


class EditorPathNotFoundError(EditorPathError, FileNotFoundError):
    """Raised when a requested path does not exist."""


class EditorLaunchError(EditorError):
    """Raised when the external editor command cannot be launched."""


CommandRunner = Callable[[list[str]], object]
ProcessLauncher = Callable[[list[str]], object]
SettingsProvider = Callable[[], Settings]
UrlProbe = Callable[[str], bool]
OpenerCall = Callable[[str, dict[str, str]], bool]
EnvironmentManagerProvider = Callable[[], Any]
PathProvider = Callable[[], Path]


def _default_process_launcher(args: list[str]) -> subprocess.Popen[Any]:
    return subprocess.Popen(args, start_new_session=True)


def _default_command_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, text=True, capture_output=True)


def _default_url_probe(url: str) -> bool:
    try:
        response = httpx.get(url, timeout=0.2)
    except httpx.HTTPError:
        return False
    return response.status_code < 500


def _default_opener_call(url: str, params: dict[str, str]) -> bool:
    try:
        response = httpx.get(url, params=params, timeout=5.0)
    except httpx.HTTPError as exc:
        logger.warning("Embedded editor opener request failed: %s", _exception_summary(exc))
        return False
    if 200 <= response.status_code < 300:
        return True
    logger.warning(
        "Embedded editor opener returned HTTP %s: %s",
        response.status_code,
        response.text.strip()[:500],
    )
    return False


def default_opener_vsix_path() -> Path:
    return Path(str(files("bioimageflow_server._external.opener") / "bioimageflow-opener-0.1.0.vsix"))


def _default_environment_manager_provider() -> Any:
    from bioimageflow.env_manager import get_shared_environment_manager

    return get_shared_environment_manager()


def _bind_addr_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return f"{host}:{port}"


class EmbeddedCodeServerManager:
    """Small manager for the embedded code-server instance.

    Status checks are intentionally cheap: they only probe already-running
    loopback URLs and never create environments or install extensions.
    """

    def __init__(
        self,
        *,
        editor_url: str = DEFAULT_EDITOR_URL,
        control_url: str = DEFAULT_CONTROL_URL,
        vsix_path: Path | None = None,
        code_server_binary: str = "code-server",
        environment_manager_provider: EnvironmentManagerProvider = (
            _default_environment_manager_provider
        ),
    ) -> None:
        self.editor_url = editor_url.rstrip("/")
        self.control_url = control_url.rstrip("/")
        self.vsix_path = vsix_path or default_opener_vsix_path()
        self.code_server_binary = code_server_binary
        self._environment_manager_provider = environment_manager_provider
        self._process: ManagedProcess | object | None = None
        self._launch_status_lock = threading.Lock()
        self._launch_phase = EditorLaunchPhase.IDLE
        self._launch_message: str | None = None
        self._launch_started_at: float | None = None
        self._launch_current: int | None = None
        self._launch_total: int | None = None

    def status(self, *, url_probe: UrlProbe = _default_url_probe) -> EditorStatus:
        editor_available = url_probe(self.editor_url)
        control_available = self.vsix_path.exists() and url_probe(f"{self.control_url}/open")
        if editor_available:
            self.set_launch_phase(EditorLaunchPhase.READY, "Code editor is ready.")
        elif self._launch_status()[0] == EditorLaunchPhase.READY:
            self._reset_launch_status()
        phase, message, started_at, current, total = self._launch_status()
        return EditorStatus(
            available=editor_available,
            url=self.editor_url if editor_available else None,
            version=CODE_SERVER_VERSION if editor_available else None,
            control_available=control_available,
            launch_phase=phase,
            launch_message=message,
            launch_started_at=started_at,
            launch_current=current,
            launch_total=total,
        )

    def set_launch_phase(
        self,
        phase: EditorLaunchPhase,
        message: str | None = None,
        *,
        current: int | None = None,
        total: int | None = None,
    ) -> None:
        """Publish a pollable embedded-editor launch phase."""
        with self._launch_status_lock:
            if phase == EditorLaunchPhase.PREPARING and self._launch_phase in {
                EditorLaunchPhase.IDLE, EditorLaunchPhase.READY, EditorLaunchPhase.FAILED
            }:
                self._launch_started_at = time.time()
            elif phase not in {EditorLaunchPhase.IDLE, EditorLaunchPhase.READY}:
                self._launch_started_at = self._launch_started_at or time.time()
            changed = (
                phase != self._launch_phase
                or message != self._launch_message
                or current != self._launch_current
                or total != self._launch_total
            )
            self._launch_phase = phase
            self._launch_message = message
            self._launch_current = current
            self._launch_total = total
        if changed:
            logger.info(
                "Embedded editor launch phase: phase=%s message=%s current=%s total=%s",
                phase.value,
                message,
                current,
                total,
            )

    def _reset_launch_status(self) -> None:
        with self._launch_status_lock:
            self._launch_phase = EditorLaunchPhase.IDLE
            self._launch_message = None
            self._launch_started_at = None
            self._launch_current = None
            self._launch_total = None

    def _launch_status(
        self,
    ) -> tuple[EditorLaunchPhase, str | None, float | None, int | None, int | None]:
        with self._launch_status_lock:
            return (
                self._launch_phase,
                self._launch_message,
                self._launch_started_at,
                self._launch_current,
                self._launch_total,
            )

    def diagnostics(self) -> dict[str, object]:
        return {
            "editor_url": self.editor_url,
            "editor_probe": _url_probe_diagnostic(self.editor_url),
            "control_url": f"{self.control_url}/open",
            "control_probe": _url_probe_diagnostic(f"{self.control_url}/open"),
            "opener_vsix_path": str(self.vsix_path),
            "opener_vsix_exists": self.vsix_path.exists(),
        }

    def install_commands(self) -> list[list[str]]:
        return [
            [self.code_server_binary, "--force", "--install-extension", str(self.vsix_path)],
            [self.code_server_binary, "--install-extension", "ms-python.python"],
            [self.code_server_binary, "--install-extension", "ms-python.vscode-python-envs"],
            [self.code_server_binary, "--install-extension", "ms-python.debugpy"],
            [self.code_server_binary, "--install-extension", "detachhead.basedpyright"],
        ]

    def legacy_uninstall_command(self) -> list[str]:
        return [self.code_server_binary, "--uninstall-extension", "sairpico.opener"]

    def launch_command(self) -> list[str]:
        return [
            self.code_server_binary,
            "--disable-workspace-trust",
            "--disable-telemetry",
            "--auth",
            "none",
            "--bind-addr",
            _bind_addr_from_url(self.editor_url),
        ]

    def launch(
        self,
        *,
        install_runner: CommandRunner | None = None,
        process_launcher: ProcessLauncher | None = None,
    ) -> None:
        self.set_launch_phase(
            EditorLaunchPhase.PREPARING,
            "Checking the code editor environment.",
        )
        logger.info(
            "Launching embedded code-server: editor_url=%s control_url=%s",
            self.editor_url,
            self.control_url,
        )
        try:
            if not self.vsix_path.exists():
                raise FileNotFoundError(f"opener extension not found: {self.vsix_path}")
            if install_runner is None and process_launcher is None:
                self._process = self._launch_in_environment()
                return
            install_runner = install_runner or _default_command_runner
            process_launcher = process_launcher or _default_process_launcher
            self._install_extensions(install_runner)
            command = self.launch_command()
            self.set_launch_phase(EditorLaunchPhase.STARTING, "Starting code-server.")
            logger.info("Starting code-server process: %s", shlex.join(command))
            self._process = process_launcher(command)
        except Exception as exc:
            self.set_launch_phase(EditorLaunchPhase.FAILED, _exception_summary(exc))
            raise

    def _install_extensions(
        self, runner: CommandRunner, *, integration_stamp: Path | None = None
    ) -> None:
        self.set_launch_phase(
            EditorLaunchPhase.PREPARING, "Checking installed editor extensions."
        )
        result = runner([self.code_server_binary, "--list-extensions"])
        output = getattr(result, "stdout", "")
        installed = set(output.lower().splitlines()) if isinstance(output, str) else set()
        if "sairpico.opener" in installed:
            self._uninstall_legacy_opener(runner)
        integration_digest = hashlib.sha256(self.vsix_path.read_bytes()).hexdigest()
        integration_current = False
        if integration_stamp is not None and integration_stamp.is_file():
            integration_current = integration_stamp.read_text() == integration_digest
        commands = [
            command for command in self.install_commands()
            if (
                not integration_current or "bioimageflow.bioimageflow-opener" not in installed
                if command[-1] == str(self.vsix_path)
                else command[-1].lower() not in installed
            )
        ]
        total = len(commands)
        for current, command in enumerate(commands, start=1):
            extension = command[-1]
            extension_label = {
                str(self.vsix_path): "BioImageFlow editor integration",
                "ms-python.python": "Python support",
                "ms-python.vscode-python-envs": "Python environment support",
                "ms-python.debugpy": "Python debugging support",
                "detachhead.basedpyright": "Python type checking",
            }.get(extension, extension)
            self.set_launch_phase(
                EditorLaunchPhase.INSTALLING_EXTENSIONS,
                f"Installing {extension_label}.",
                current=current,
                total=total,
            )
            logger.info("Installing code-server extension: %s", shlex.join(command))
            runner(command)
            if command[-1] == str(self.vsix_path) and integration_stamp is not None:
                integration_stamp.write_text(integration_digest)

    def _uninstall_legacy_opener(self, install_runner: CommandRunner) -> None:
        command = self.legacy_uninstall_command()
        logger.info("Removing legacy code-server opener extension: %s", shlex.join(command))
        try:
            install_runner(command)
        except Exception as exc:
            logger.info("Legacy code-server opener removal skipped or failed: %s", exc)

    def _launch_in_environment(self) -> object:
        env_manager = self._environment_manager_provider()
        logger.info(
            "Provisioning managed code-server environment: version=%s",
            CODE_SERVER_VERSION,
        )
        environment = env_manager.provision(
            "codeserver",
            EnvironmentSpec(
                python="3.10.*",
                conda=(f"code-server=={CODE_SERVER_VERSION}",),
            ),
            replace_existing=True,
        ).wait_for()
        self._install_extensions(
            environment.run,
            integration_stamp=environment.path / ".bioimageflow-opener.sha256",
        )
        command = self.launch_command()
        self.set_launch_phase(EditorLaunchPhase.STARTING, "Starting code-server.")
        logger.info("Starting managed code-server process: %s", shlex.join(command))
        return environment.spawn(command, output_limit=16 * 1024 * 1024)

    def shutdown(self) -> None:
        """Close the managed code-server process, if one was launched."""
        process = self._process
        self._process = None
        if process is None:
            return
        close = getattr(process, "close", None)
        if callable(close):
            close()

    def open_path(
        self,
        path: Path,
        focus_path: Path | None = None,
        *,
        opener: OpenerCall = _default_opener_call,
    ) -> EditorOpenResponse:
        if path.is_dir() or _is_workspace_file(path):
            query_name = "workspace" if _is_workspace_file(path) else "folder"
            return EditorOpenResponse(
                opened=True,
                method=EditorOpenMethod.EMBEDDED,
                url=f"{self.editor_url}/?{urlencode({query_name: str(path)})}",
                path=str(focus_path or path),
                project_path=str(path),
            )

        ok = opener(
            f"{self.control_url}/open",
            {
                "path": str(path),
                "type": "file",
                "new_window": "false",
            },
        )
        if not ok:
            raise ConnectionError("embedded editor opener is unavailable")
        return EditorOpenResponse(
            opened=True,
            method=EditorOpenMethod.EMBEDDED,
            url=self.editor_url,
            path=str(focus_path or path),
        )


class EditorService:
    def __init__(
        self,
        *,
        settings_provider: SettingsProvider,
        process_launcher: ProcessLauncher = _default_process_launcher,
        embedded_manager: EmbeddedCodeServerManager | None = None,
        embedded_startup_timeout: float = 10.0,
        embedded_poll_interval: float = 0.2,
        workspace_path_provider: PathProvider | None = None,
        tool_store_path_provider: PathProvider | None = None,
    ) -> None:
        self._settings_provider = settings_provider
        self._process_launcher = process_launcher
        self._embedded = embedded_manager or EmbeddedCodeServerManager()
        self._embedded_startup_timeout = embedded_startup_timeout
        self._embedded_poll_interval = embedded_poll_interval
        self._workspace_path_provider = workspace_path_provider
        self._tool_store_path_provider = tool_store_path_provider
        self._embedded_lock = threading.RLock()

    async def shutdown(self) -> None:
        """Stop the embedded editor without blocking the application event loop."""
        shutdown = getattr(self._embedded, "shutdown", None)
        if callable(shutdown):
            import asyncio

            await asyncio.to_thread(shutdown)

    def get_status(self, *, launch: bool = False, workspace: bool = False) -> EditorStatus:
        workspace_path: Path | None = None
        if launch and workspace:
            try:
                workspace_path = self._managed_workspace_path()
            except Exception as exc:
                logger.exception("Embedded editor workspace generation failed")
                return EditorStatus(
                    available=False,
                    url=None,
                    version=None,
                    control_available=False,
                    launch_attempted=True,
                    launch_phase=EditorLaunchPhase.FAILED,
                    launch_message=_exception_summary(exc),
                    error_code=EMBEDDED_WORKSPACE_FAILED,
                    error_detail=_exception_summary(exc),
                )
        status = self._embedded.status()
        if not launch or status.available:
            return _status_for_workspace(status, workspace_path)

        with self._embedded_lock:
            status = self._embedded.status()
            if status.available:
                return _status_for_workspace(
                    status.model_copy(update={"launch_attempted": True}),
                    workspace_path,
                )
            if status.control_available:
                status = self._wait_for_embedded_status()
                if status.available:
                    return _status_for_workspace(
                        status.model_copy(update={"launch_attempted": True}),
                        workspace_path,
                    )
                self._set_embedded_launch_phase(
                    EditorLaunchPhase.FAILED,
                    EMBEDDED_STARTUP_TIMEOUT_DETAIL,
                )
                return status.model_copy(
                    update={
                        "launch_attempted": True,
                        "launch_phase": EditorLaunchPhase.FAILED,
                        "launch_message": EMBEDDED_STARTUP_TIMEOUT_DETAIL,
                        "error_code": EMBEDDED_STARTUP_TIMEOUT,
                        "error_detail": EMBEDDED_STARTUP_TIMEOUT_DETAIL,
                    }
                )

            start = getattr(self._embedded, "launch", None)
            if callable(start):
                try:
                    start()
                except Exception as exc:
                    logger.exception("Embedded code-server launch failed")
                    self._set_embedded_launch_phase(
                        EditorLaunchPhase.FAILED,
                        _exception_summary(exc),
                    )
                    return self._embedded.status().model_copy(
                        update={
                            "launch_attempted": True,
                            "launch_phase": EditorLaunchPhase.FAILED,
                            "launch_message": _exception_summary(exc),
                            "error_code": EMBEDDED_LAUNCH_FAILED,
                            "error_detail": _exception_summary(exc),
                        }
                    )

            status = self._wait_for_embedded_status()
            if status.available:
                return _status_for_workspace(
                    status.model_copy(update={"launch_attempted": True}),
                    workspace_path,
                )
            self._set_embedded_launch_phase(
                EditorLaunchPhase.FAILED,
                EMBEDDED_STARTUP_TIMEOUT_DETAIL,
            )
            return status.model_copy(
                update={
                    "launch_attempted": True,
                    "launch_phase": EditorLaunchPhase.FAILED,
                    "launch_message": EMBEDDED_STARTUP_TIMEOUT_DETAIL,
                    "error_code": EMBEDDED_STARTUP_TIMEOUT,
                    "error_detail": EMBEDDED_STARTUP_TIMEOUT_DETAIL,
                }
            )

    def open_path(
        self,
        path: str,
        focus_path: str | None = None,
        *,
        workspace: bool = False,
    ) -> EditorOpenResponse:
        normalized = self._normalize_path(path)
        normalized_focus = (
            self._normalize_path(focus_path, resolve_symlinks=False)
            if focus_path is not None
            else None
        )
        logger.info(
            "Editor service opening path: project_path=%s focus_path=%s",
            normalized,
            normalized_focus,
        )
        settings = self._settings_provider()
        command = (settings.external_editor or "").strip()
        if command:
            logger.info("Using external editor command for path open")
            self._launch_external(command, normalized, normalized_focus)
            return EditorOpenResponse(
                opened=True,
                method=EditorOpenMethod.EXTERNAL,
                url=None,
                path=str(normalized_focus or normalized),
                project_path=str(normalized) if normalized.is_dir() else None,
            )

        embedded_project = normalized
        if workspace:
            try:
                embedded_project = self._managed_workspace_path()
            except Exception as exc:
                logger.exception("Embedded editor workspace generation failed")
                return self._clipboard_response(
                    normalized_focus or normalized,
                    EMBEDDED_WORKSPACE_FAILED,
                    _exception_summary(exc),
                )

        with self._embedded_lock:
            return self._open_path_embedded_locked(embedded_project, normalized_focus)

    def _open_path_embedded_locked(
        self,
        normalized: Path,
        normalized_focus: Path | None,
    ) -> EditorOpenResponse:
        status = self._embedded.status()
        logger.info(
            "Embedded editor status before open: available=%s control_available=%s url=%s",
            status.available,
            status.control_available,
            status.url,
        )
        if normalized_focus is not None and status.available and not status.control_available:
            logger.warning(
                "Embedded editor control endpoint unavailable before open: diagnostics=%s",
                _embedded_diagnostics(self._embedded),
            )
        if status.available or status.control_available:
            if not status.available:
                logger.info(
                    "Embedded editor control endpoint is available while editor URL is unavailable; "
                    "waiting for the existing editor instead of launching"
                )
            response = self._open_with_running_embedded(
                normalized,
                normalized_focus,
                initial_status=status,
            )
            if response is not None:
                return response
            error_code = EMBEDDED_OPENER_TIMEOUT
            error_detail = EMBEDDED_OPENER_TIMEOUT_DETAIL
            logger.warning(
                "Embedded editor is running but could not open path: "
                "project_path=%s focus_path=%s diagnostics=%s",
                normalized,
                normalized_focus,
                _embedded_diagnostics(self._embedded),
            )
            return self._clipboard_response(
                normalized_focus or normalized,
                error_code,
                error_detail,
                project_path=normalized if normalized.is_dir() else None,
            )

        error_code: str | None = None
        error_detail: str | None = None
        launch = getattr(self._embedded, "launch", None)
        if callable(launch):
            try:
                logger.info("Embedded editor is unavailable or incomplete; launching")
                launch()
                response = self._open_after_embedded_launch(normalized, normalized_focus)
                if response is not None:
                    logger.info("Embedded editor became available after launch")
                    return response
                logger.warning(
                    "Embedded editor startup timed out: project_path=%s focus_path=%s",
                    normalized,
                    normalized_focus,
                )
                logger.warning(
                    "Embedded editor diagnostics at timeout: diagnostics=%s",
                    _embedded_diagnostics(self._embedded),
                )
                error_code = EMBEDDED_STARTUP_TIMEOUT
                error_detail = EMBEDDED_STARTUP_TIMEOUT_DETAIL
                self._set_embedded_launch_phase(
                    EditorLaunchPhase.FAILED,
                    EMBEDDED_STARTUP_TIMEOUT_DETAIL,
                )
            except Exception as exc:
                logger.exception("Embedded code-server launch failed")
                error_code = EMBEDDED_LAUNCH_FAILED
                error_detail = _exception_summary(exc)
                self._set_embedded_launch_phase(
                    EditorLaunchPhase.FAILED,
                    error_detail,
                )

        return self._clipboard_response(
            normalized_focus or normalized,
            error_code,
            error_detail,
            project_path=normalized if normalized.is_dir() else None,
        )

    def _clipboard_response(
        self,
        path: Path,
        error_code: str | None,
        error_detail: str | None,
        *,
        project_path: Path | None = None,
    ) -> EditorOpenResponse:
        logger.warning(
            "Falling back to clipboard for editor open: path=%s error_code=%s error_detail=%s",
            path,
            error_code,
            error_detail,
        )
        return EditorOpenResponse(
            opened=False,
            method=EditorOpenMethod.CLIPBOARD,
            url=None,
            path=str(path),
            project_path=str(project_path) if project_path is not None else None,
            message=CLIPBOARD_MESSAGE,
            error_code=error_code,
            error_detail=error_detail,
        )

    def _open_with_running_embedded(
        self,
        path: Path,
        focus_path: Path | None,
        *,
        initial_status: EditorStatus,
    ) -> EditorOpenResponse | None:
        deadline = time.monotonic() + max(0.0, self._embedded_startup_timeout)
        status = initial_status
        last_error: Exception | None = None
        while True:
            if _can_open_embedded(status, path, focus_path):
                try:
                    logger.info("Opening path with already-running embedded editor")
                    return self._embedded.open_path(path, focus_path)
                except Exception as exc:
                    last_error = exc
                    logger.warning("Already-running embedded editor open failed: %s", exc)
            if time.monotonic() >= deadline:
                logger.warning(
                    "Already-running embedded editor did not become ready before timeout: "
                    "available=%s control_available=%s url=%s focus_requested=%s "
                    "last_error=%s diagnostics=%s",
                    status.available,
                    status.control_available,
                    status.url,
                    focus_path is not None,
                    _exception_summary(last_error) if last_error else None,
                    _embedded_diagnostics(self._embedded),
                )
                return None
            time.sleep(max(0.0, self._embedded_poll_interval))
            status = self._embedded.status()

    def _open_after_embedded_launch(
        self,
        path: Path,
        focus_path: Path | None,
    ) -> EditorOpenResponse | None:
        self._set_embedded_launch_phase(
            EditorLaunchPhase.WAITING,
            "Waiting for the code editor to respond.",
        )
        deadline = time.monotonic() + max(0.0, self._embedded_startup_timeout)
        last_status: EditorStatus | None = None
        last_error: Exception | None = None
        while True:
            status = self._embedded.status()
            last_status = status
            if _can_open_embedded(status, path, focus_path):
                try:
                    return self._embedded.open_path(path, focus_path)
                except Exception as exc:
                    last_error = exc
                    logger.warning("Embedded editor open after launch failed: %s", exc)
            if time.monotonic() >= deadline:
                logger.warning(
                    "Embedded editor did not become ready before timeout: "
                    "available=%s control_available=%s url=%s focus_requested=%s "
                    "last_error=%s diagnostics=%s",
                    last_status.available if last_status else None,
                    last_status.control_available if last_status else None,
                    last_status.url if last_status else None,
                    focus_path is not None,
                    _exception_summary(last_error) if last_error else None,
                    _embedded_diagnostics(self._embedded),
                )
                return None
            time.sleep(max(0.0, self._embedded_poll_interval))

    def _wait_for_embedded_status(self) -> EditorStatus:
        self._set_embedded_launch_phase(
            EditorLaunchPhase.WAITING,
            "Waiting for the code editor to respond.",
        )
        deadline = time.monotonic() + max(0.0, self._embedded_startup_timeout)
        last_status = self._embedded.status()
        while not last_status.available and time.monotonic() < deadline:
            time.sleep(max(0.0, self._embedded_poll_interval))
            last_status = self._embedded.status()
        return last_status

    def _set_embedded_launch_phase(
        self,
        phase: EditorLaunchPhase,
        message: str | None,
    ) -> None:
        setter = getattr(self._embedded, "set_launch_phase", None)
        if callable(setter):
            setter(phase, message)

    def _managed_workspace_path(self) -> Path:
        if self._workspace_path_provider is None or self._tool_store_path_provider is None:
            raise RuntimeError("embedded editor workspace providers are not configured")
        return ensure_editor_workspace(
            self._workspace_path_provider(),
            self._tool_store_path_provider(),
        )

    def _normalize_path(self, path: str, *, resolve_symlinks: bool = True) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            raise EditorPathError("path must be absolute")
        candidate = (
            candidate.resolve(strict=False)
            if resolve_symlinks
            else Path(os.path.abspath(candidate))
        )
        if not candidate.exists():
            raise EditorPathNotFoundError(str(candidate))
        return candidate

    def _launch_external(self, command: str, path: Path, focus_path: Path | None = None) -> None:
        args = shlex.split(command)
        if not args:
            return
        rendered: list[str] = []
        replaced = False
        file_path = focus_path or path
        for arg in args:
            if "{file_path}" in arg:
                rendered.append(arg.replace("{file_path}", str(file_path)))
                replaced = True
            elif "{workspace_path}" in arg:
                rendered.append(arg.replace("{workspace_path}", str(path)))
                replaced = True
            else:
                rendered.append(arg)
        if not replaced:
            rendered.append(str(path))
            if focus_path is not None:
                rendered.append(str(focus_path))
        try:
            logger.info("Launching external editor command: %s", shlex.join(rendered))
            self._process_launcher(rendered)
        except Exception as exc:
            raise EditorLaunchError(str(exc)) from exc


def _exception_summary(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _can_open_embedded(status: EditorStatus, path: Path, _focus_path: Path | None) -> bool:
    if not status.available:
        return False
    if path.is_dir() or _is_workspace_file(path):
        return True
    return status.control_available


def _is_workspace_file(path: Path) -> bool:
    return path.is_file() and path.suffix == ".code-workspace"


def _status_for_workspace(status: EditorStatus, workspace_path: Path | None) -> EditorStatus:
    if workspace_path is None or not status.available or status.url is None:
        return status
    return status.model_copy(
        update={
            "url": f"{status.url.rstrip('/')}/?{urlencode({'workspace': str(workspace_path)})}",
        }
    )


def _embedded_diagnostics(embedded: object) -> dict[str, object] | None:
    diagnostics = getattr(embedded, "diagnostics", None)
    if not callable(diagnostics):
        return None
    try:
        result = diagnostics()
    except Exception as exc:
        return {"diagnostics_error": _exception_summary(exc)}
    return result if isinstance(result, dict) else {"diagnostics": result}


def _url_probe_diagnostic(url: str) -> str:
    try:
        response = httpx.get(url, timeout=0.5)
    except httpx.HTTPError as exc:
        return f"{type(exc).__name__}: {exc}"
    text = response.text.strip().replace("\n", " ")
    if len(text) > 200:
        text = text[:200] + "..."
    return f"HTTP {response.status_code}: {text}"
