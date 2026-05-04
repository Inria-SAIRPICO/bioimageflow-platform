"""Editor opening service and embedded code-server manager."""

from __future__ import annotations

import shlex
import subprocess
import time
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
        if not self.vsix_path.exists():
            raise FileNotFoundError(f"opener extension not found: {self.vsix_path}")
        if install_runner is None and process_launcher is None:
            self._process = self._launch_in_environment()
            return
        install_runner = install_runner or _default_command_runner
        process_launcher = process_launcher or _default_process_launcher
        for command in self.install_commands():
            install_runner(command)
        self._process = process_launcher(self.launch_command())

    def _launch_in_environment(self) -> object:
        env_manager = self._environment_manager_provider()
        if self.env_path is not None:
            environment = env_manager.load("codeserver", self.env_path)
        else:
            environment = env_manager.create(
                "codeserver",
                dependencies={
                    "python": "3.10",
                    "conda": [f"code-server=={CODE_SERVER_VERSION}"],
                    "pip": [],
                },
                use_existing=True,
            )
        commands = [shlex.join(command) for command in self.install_commands()]
        commands.append(shlex.join(self.launch_command()))
        return env_manager.execute_commands(environment, commands)

    def open_path(
        self,
        path: Path,
        *,
        opener: OpenerCall = _default_opener_call,
    ) -> EditorOpenResponse:
        ok = opener(
            f"{self.control_url}/open",
            {"path": str(path), "type": "file", "new_window": "false"},
        )
        if not ok:
            raise ConnectionError("embedded editor opener is unavailable")
        return EditorOpenResponse(
            opened=True,
            method=EditorOpenMethod.EMBEDDED,
            url=self.editor_url,
            path=str(path),
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

    def get_status(self) -> EditorStatus:
        return self._embedded.status()

    def open_path(self, path: str) -> EditorOpenResponse:
        normalized = self._normalize_path(path)
        settings = self._settings_provider()
        command = (settings.external_editor or "").strip()
        if command:
            self._launch_external(command, normalized)
            return EditorOpenResponse(
                opened=True,
                method=EditorOpenMethod.EXTERNAL,
                url=None,
                path=str(normalized),
            )

        status = self._embedded.status()
        if status.available and status.control_available:
            try:
                return self._embedded.open_path(normalized)
            except Exception:
                pass

        launch = getattr(self._embedded, "launch", None)
        if callable(launch):
            try:
                launch()
                response = self._open_after_embedded_launch(normalized)
                if response is not None:
                    return response
            except Exception:
                pass

        return EditorOpenResponse(
            opened=False,
            method=EditorOpenMethod.CLIPBOARD,
            url=None,
            path=str(normalized),
            message=CLIPBOARD_MESSAGE,
        )

    def _open_after_embedded_launch(self, path: Path) -> EditorOpenResponse | None:
        deadline = time.monotonic() + max(0.0, self._embedded_startup_timeout)
        while True:
            status = self._embedded.status()
            if status.available and status.control_available:
                return self._embedded.open_path(path)
            if time.monotonic() >= deadline:
                return None
            time.sleep(max(0.0, self._embedded_poll_interval))

    def _normalize_path(self, path: str) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            raise EditorPathError("path must be absolute")
        candidate = candidate.resolve(strict=False)
        if not candidate.exists():
            raise EditorPathNotFoundError(str(candidate))
        return candidate

    def _launch_external(self, command: str, path: Path) -> None:
        args = shlex.split(command)
        if not args:
            return
        rendered: list[str] = []
        replaced = False
        for arg in args:
            if "{file_path}" in arg:
                rendered.append(arg.replace("{file_path}", str(path)))
                replaced = True
            else:
                rendered.append(arg)
        if not replaced:
            rendered.append(str(path))
        try:
            self._process_launcher(rendered)
        except Exception as exc:
            raise EditorLaunchError(str(exc)) from exc
