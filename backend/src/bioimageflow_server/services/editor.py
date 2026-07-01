"""Editor opening service and embedded code-server manager."""

from __future__ import annotations

import logging
import shlex
import subprocess
import time
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx

from bioimageflow_server.models.editor import (
    EditorOpenMethod,
    EditorOpenResponse,
    EditorStatus,
)
from bioimageflow_server.models.settings import Settings

CODE_SERVER_VERSION = "4.106.2"
DEFAULT_EDITOR_URL = "http://127.0.0.1:32344"
DEFAULT_CONTROL_URL = "http://127.0.0.1:60351"
CLIPBOARD_MESSAGE = "Path copied - open in your local editor."
EMBEDDED_LAUNCH_FAILED = "embedded_launch_failed"
EMBEDDED_STARTUP_TIMEOUT = "embedded_startup_timeout"
EMBEDDED_STARTUP_TIMEOUT_DETAIL = "code-server did not become available before timeout"

logger = logging.getLogger(__name__)


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


def _default_process_launcher(args: list[str]) -> subprocess.Popen[Any]:
    return subprocess.Popen(args, start_new_session=True)


def _default_command_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, text=True)


def _default_url_probe(url: str) -> bool:
    try:
        response = httpx.get(url, timeout=0.2)
    except httpx.HTTPError:
        return False
    return response.status_code < 500


def _default_opener_call(url: str, params: dict[str, str]) -> bool:
    try:
        response = httpx.get(url, params=params, timeout=0.5)
    except httpx.HTTPError:
        return False
    return 200 <= response.status_code < 300


def default_opener_vsix_path() -> Path:
    return Path(str(files("bioimageflow_server._external.opener") / "opener-0.0.2.vsix"))


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
        env_path: Path | None = None,
        editor_url: str = DEFAULT_EDITOR_URL,
        control_url: str = DEFAULT_CONTROL_URL,
        vsix_path: Path | None = None,
        code_server_binary: str = "code-server",
        environment_manager_provider: EnvironmentManagerProvider = (
            _default_environment_manager_provider
        ),
    ) -> None:
        self.env_path = env_path
        self.editor_url = editor_url.rstrip("/")
        self.control_url = control_url.rstrip("/")
        self.vsix_path = vsix_path or default_opener_vsix_path()
        self.code_server_binary = code_server_binary
        self._environment_manager_provider = environment_manager_provider
        self._process: object | None = None

    def status(self, *, url_probe: UrlProbe = _default_url_probe) -> EditorStatus:
        editor_available = url_probe(self.editor_url)
        control_available = self.vsix_path.exists() and url_probe(f"{self.control_url}/open")
        return EditorStatus(
            available=editor_available,
            url=self.editor_url if editor_available else None,
            version=CODE_SERVER_VERSION if editor_available else None,
            control_available=control_available,
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
            [self.code_server_binary, "--install-extension", str(self.vsix_path)],
            [self.code_server_binary, "--install-extension", "ms-python.python"],
            [self.code_server_binary, "--install-extension", "ms-python.vscode-python-envs"],
            [self.code_server_binary, "--install-extension", "ms-python.debugpy"],
            [self.code_server_binary, "--install-extension", "detachhead.basedpyright"],
        ]

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
        logger.info(
            "Launching embedded code-server: editor_url=%s control_url=%s env_path=%s",
            self.editor_url,
            self.control_url,
            self.env_path,
        )
        if not self.vsix_path.exists():
            raise FileNotFoundError(f"opener extension not found: {self.vsix_path}")
        if install_runner is None and process_launcher is None:
            self._process = self._launch_in_environment()
            return
        install_runner = install_runner or _default_command_runner
        process_launcher = process_launcher or _default_process_launcher
        for command in self.install_commands():
            logger.info("Installing code-server extension: %s", shlex.join(command))
            install_runner(command)
        logger.info("Starting code-server process: %s", shlex.join(self.launch_command()))
        self._process = process_launcher(self.launch_command())

    def _launch_in_environment(self) -> object:
        env_manager = self._environment_manager_provider()
        if self.env_path is not None:
            logger.info("Loading configured code-server environment: %s", self.env_path)
            environment = env_manager.load("codeserver", self.env_path)
        else:
            environment = self._create_or_load_default_environment(env_manager)
        commands = [shlex.join(command) for command in self.install_commands()]
        commands.append(shlex.join(self.launch_command()))
        logger.info(
            "Executing embedded code-server startup in environment: commands=%s",
            commands,
        )
        return env_manager.execute_commands(environment, commands)

    def _create_or_load_default_environment(self, env_manager: Any) -> object:
        try:
            logger.info(
                "Creating or reusing default code-server environment: version=%s",
                CODE_SERVER_VERSION,
            )
            return env_manager.create(
                "codeserver",
                dependencies={
                    "python": "3.10",
                    "conda": [f"code-server=={CODE_SERVER_VERSION}"],
                    "pip": [],
                },
                replace_existing=False,
            )
        except Exception as exc:
            if not _is_missing_metadata_environment_reuse_error(exc):
                raise
            logger.warning(
                "Loading existing codeserver environment with missing Wetlands metadata: %s",
                exc,
            )
            return env_manager.load("codeserver")

    def open_path(
        self,
        path: Path,
        focus_path: Path | None = None,
        *,
        opener: OpenerCall = _default_opener_call,
    ) -> EditorOpenResponse:
        if path.is_dir():
            return EditorOpenResponse(
                opened=True,
                method=EditorOpenMethod.EMBEDDED,
                url=f"{self.editor_url}/?{urlencode({'folder': str(path)})}",
                path=str(focus_path or path),
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
    ) -> None:
        self._settings_provider = settings_provider
        self._process_launcher = process_launcher
        self._embedded = embedded_manager or EmbeddedCodeServerManager()
        self._embedded_startup_timeout = embedded_startup_timeout
        self._embedded_poll_interval = embedded_poll_interval

    def get_status(self, *, launch: bool = False) -> EditorStatus:
        status = self._embedded.status()
        if not launch or status.available:
            return status

        start = getattr(self._embedded, "launch", None)
        if callable(start):
            try:
                start()
            except Exception as exc:
                logger.exception("Embedded code-server launch failed")
                return self._embedded.status().model_copy(
                    update={
                        "launch_attempted": True,
                        "error_code": EMBEDDED_LAUNCH_FAILED,
                        "error_detail": _exception_summary(exc),
                    }
                )

        status = self._wait_for_embedded_status()
        if status.available:
            return status.model_copy(update={"launch_attempted": True})
        return status.model_copy(
            update={
                "launch_attempted": True,
                "error_code": EMBEDDED_STARTUP_TIMEOUT,
                "error_detail": EMBEDDED_STARTUP_TIMEOUT_DETAIL,
            }
        )

    def open_path(self, path: str, focus_path: str | None = None) -> EditorOpenResponse:
        normalized = self._normalize_path(path)
        normalized_focus = self._normalize_path(focus_path) if focus_path is not None else None
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
            )

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
        if _can_open_embedded(status, normalized, normalized_focus):
            try:
                logger.info("Opening path with already-running embedded editor")
                return self._embedded.open_path(normalized, normalized_focus)
            except Exception as exc:
                logger.warning("Already-running embedded editor open failed: %s", exc)

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
            except Exception as exc:
                logger.exception("Embedded code-server launch failed")
                error_code = EMBEDDED_LAUNCH_FAILED
                error_detail = _exception_summary(exc)

        logger.warning(
            "Falling back to clipboard for editor open: path=%s error_code=%s error_detail=%s",
            normalized_focus or normalized,
            error_code,
            error_detail,
        )
        return EditorOpenResponse(
            opened=False,
            method=EditorOpenMethod.CLIPBOARD,
            url=None,
            path=str(normalized_focus or normalized),
            message=CLIPBOARD_MESSAGE,
            error_code=error_code,
            error_detail=error_detail,
        )

    def _open_after_embedded_launch(
        self,
        path: Path,
        focus_path: Path | None,
    ) -> EditorOpenResponse | None:
        deadline = time.monotonic() + max(0.0, self._embedded_startup_timeout)
        last_status: EditorStatus | None = None
        while True:
            status = self._embedded.status()
            last_status = status
            if _can_open_embedded(status, path, focus_path):
                return self._embedded.open_path(path, focus_path)
            if time.monotonic() >= deadline:
                logger.warning(
                    "Embedded editor did not become ready before timeout: "
                    "available=%s control_available=%s url=%s focus_requested=%s diagnostics=%s",
                    last_status.available if last_status else None,
                    last_status.control_available if last_status else None,
                    last_status.url if last_status else None,
                    focus_path is not None,
                    _embedded_diagnostics(self._embedded),
                )
                return None
            time.sleep(max(0.0, self._embedded_poll_interval))

    def _wait_for_embedded_status(self) -> EditorStatus:
        deadline = time.monotonic() + max(0.0, self._embedded_startup_timeout)
        last_status = self._embedded.status()
        while not last_status.available and time.monotonic() < deadline:
            time.sleep(max(0.0, self._embedded_poll_interval))
            last_status = self._embedded.status()
        return last_status

    def _normalize_path(self, path: str) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            raise EditorPathError("path must be absolute")
        candidate = candidate.resolve(strict=False)
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


def _can_open_embedded(status: EditorStatus, path: Path, focus_path: Path | None) -> bool:
    if not status.available:
        return False
    if focus_path is not None:
        return status.control_available
    return path.is_dir() or status.control_available


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


def _is_missing_metadata_environment_reuse_error(exc: Exception) -> bool:
    return type(exc).__name__ == "EnvironmentReuseError" and "metadata is missing" in str(exc)
