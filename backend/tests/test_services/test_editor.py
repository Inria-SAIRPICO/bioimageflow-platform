from __future__ import annotations

from pathlib import Path

import pytest

from bioimageflow_server.models.editor import EditorOpenMethod, EditorOpenResponse, EditorStatus
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.services.editor import (
    EmbeddedCodeServerManager,
    EditorLaunchError,
    EditorPathError,
    EditorPathNotFoundError,
    EditorService,
    default_opener_vsix_path,
)


class _RecorderLauncher:
    def __init__(self, *, exc: Exception | None = None) -> None:
        self.calls: list[list[str]] = []
        self.exc = exc

    def __call__(self, args: list[str]) -> object:
        self.calls.append(args)
        if self.exc is not None:
            raise self.exc
        return object()


class _Embedded:
    def __init__(
        self,
        *,
        status: EditorStatus | None = None,
        open_response: EditorOpenResponse | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.status_value = status or EditorStatus(
            available=False, url=None, version=None, control_available=False
        )
        self.open_response = open_response
        self.exc = exc
        self.opened: list[Path] = []

    def status(self) -> EditorStatus:
        return self.status_value

    def open_path(self, path: Path) -> EditorOpenResponse:
        self.opened.append(path)
        if self.exc is not None:
            raise self.exc
        assert self.open_response is not None
        return self.open_response


class _LaunchableEmbedded(_Embedded):
    def __init__(self, *, url: str = "http://127.0.0.1:32344") -> None:
        super().__init__(
            status=EditorStatus(
                available=False,
                url=None,
                version=None,
                control_available=False,
            )
        )
        self.launches = 0
        self.url = url

    def status(self) -> EditorStatus:
        if self.launches:
            return EditorStatus(
                available=True,
                url=self.url,
                version=None,
                control_available=True,
            )
        return self.status_value

    def launch(self) -> None:
        self.launches += 1

    def open_path(self, path: Path) -> EditorOpenResponse:
        self.opened.append(path)
        return EditorOpenResponse(
            opened=True,
            method=EditorOpenMethod.EMBEDDED,
            url=self.url,
            path=str(path),
        )


class _EnvironmentManager:
    def __init__(self) -> None:
        self.created: list[tuple[str, dict[str, object], bool]] = []
        self.loaded: list[tuple[str, Path]] = []
        self.executed: list[tuple[object, list[str]]] = []
        self.environment = object()
        self.process = object()

    def create(
        self,
        name: str,
        dependencies: dict[str, object],
        *,
        use_existing: bool = False,
    ) -> object:
        self.created.append((name, dependencies, use_existing))
        return self.environment

    def load(self, name: str, path: Path) -> object:
        self.loaded.append((name, path))
        return self.environment

    def execute_commands(self, environment: object, commands: list[str]) -> object:
        self.executed.append((environment, commands))
        return self.process


def _settings(command: str | None = None) -> Settings:
    return Settings(deployment_mode="desktop", external_editor=command)


def _service(
    *,
    command: str | None = None,
    embedded: _Embedded | None = None,
    launcher: _RecorderLauncher | None = None,
    embedded_startup_timeout: float = 10.0,
    embedded_poll_interval: float = 0.2,
) -> EditorService:
    return EditorService(
        settings_provider=lambda: _settings(command),
        process_launcher=launcher or _RecorderLauncher(),
        embedded_manager=embedded or _Embedded(),
        embedded_startup_timeout=embedded_startup_timeout,
        embedded_poll_interval=embedded_poll_interval,
    )


def test_external_editor_replaces_file_path_placeholder(tmp_path: Path) -> None:
    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    launcher = _RecorderLauncher()
    service = _service(command="code --goto {file_path}:1", launcher=launcher)

    response = service.open_path(str(tool))

    assert response.method == EditorOpenMethod.EXTERNAL
    assert launcher.calls == [["code", "--goto", f"{tool}:1"]]


def test_external_editor_appends_path_when_placeholder_missing(tmp_path: Path) -> None:
    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    launcher = _RecorderLauncher()
    service = _service(command="code --reuse-window", launcher=launcher)

    service.open_path(str(tool))

    assert launcher.calls == [["code", "--reuse-window", str(tool)]]


def test_external_editor_launch_failure_is_reported(tmp_path: Path) -> None:
    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    service = _service(
        command="code {file_path}",
        launcher=_RecorderLauncher(exc=OSError("boom")),
    )

    with pytest.raises(EditorLaunchError):
        service.open_path(str(tool))


def test_open_path_expands_user_and_requires_existing_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tool = home / "tool.py"
    tool.write_text("print('x')")
    monkeypatch.setenv("HOME", str(home))
    launcher = _RecorderLauncher()
    service = _service(command="code", launcher=launcher)

    service.open_path("~/tool.py")

    assert launcher.calls[0][-1] == str(tool)


def test_missing_path_raises_not_found(tmp_path: Path) -> None:
    service = _service()

    with pytest.raises(EditorPathNotFoundError):
        service.open_path(str(tmp_path / "missing.py"))


def test_relative_path_is_rejected() -> None:
    service = _service()

    with pytest.raises(EditorPathError):
        service.open_path("tool.py")


def test_embedded_open_uses_manager_when_control_available(tmp_path: Path) -> None:
    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    embedded = _Embedded(
        status=EditorStatus(
            available=True,
            url="http://127.0.0.1:32344",
            version=None,
            control_available=True,
        ),
        open_response=EditorOpenResponse(
            opened=True,
            method=EditorOpenMethod.EMBEDDED,
            url="http://127.0.0.1:32344",
            path=str(tool),
        ),
    )
    service = _service(embedded=embedded)

    response = service.open_path(str(tool))

    assert response.method == EditorOpenMethod.EMBEDDED
    assert embedded.opened == [tool]


def test_embedded_connection_failure_falls_back_to_clipboard(tmp_path: Path) -> None:
    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    embedded = _Embedded(
        status=EditorStatus(
            available=True,
            url="http://127.0.0.1:32344",
            version=None,
            control_available=True,
        ),
        exc=ConnectionError("no opener"),
    )
    service = _service(embedded=embedded)

    response = service.open_path(str(tool))

    assert response.opened is False
    assert response.method == EditorOpenMethod.CLIPBOARD


def test_clipboard_fallback_when_no_editor_available(tmp_path: Path) -> None:
    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    service = _service()

    response = service.open_path(str(tool))

    assert response == EditorOpenResponse(
        opened=False,
        method=EditorOpenMethod.CLIPBOARD,
        url=None,
        path=str(tool),
        message="Path copied - open in your local editor.",
    )


def test_status_can_launch_default_embedded_editor() -> None:
    embedded = _LaunchableEmbedded()
    service = _service(embedded=embedded)

    status = service.get_status(launch=True)

    assert embedded.launches == 1
    assert status.available is True
    assert status.url == "http://127.0.0.1:32344"


def test_default_embedded_editor_launches_when_not_already_running(tmp_path: Path) -> None:
    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    embedded = _LaunchableEmbedded()
    service = _service(embedded=embedded)

    response = service.open_path(str(tool))

    assert embedded.launches == 1
    assert embedded.opened == [tool]
    assert response.method == EditorOpenMethod.EMBEDDED
    assert response.url == "http://127.0.0.1:32344"


def test_default_embedded_editor_waits_until_control_endpoint_is_ready(
    tmp_path: Path,
) -> None:
    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    embedded = _LaunchableEmbedded()
    status_calls = 0

    def delayed_status() -> EditorStatus:
        nonlocal status_calls
        status_calls += 1
        if embedded.launches and status_calls >= 3:
            return EditorStatus(
                available=True,
                url=embedded.url,
                version=None,
                control_available=True,
            )
        return EditorStatus(
            available=bool(embedded.launches),
            url=embedded.url if embedded.launches else None,
            version=None,
            control_available=False,
        )

    embedded.status = delayed_status  # type: ignore[method-assign]
    service = _service(
        embedded=embedded,
        embedded_startup_timeout=1.0,
        embedded_poll_interval=0.001,
    )

    response = service.open_path(str(tool))

    assert status_calls >= 3
    assert embedded.opened == [tool]
    assert response.method == EditorOpenMethod.EMBEDDED


def test_default_embedded_editor_does_not_report_opened_without_opener(
    tmp_path: Path,
) -> None:
    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    embedded = _LaunchableEmbedded()
    embedded.status = lambda: EditorStatus(  # type: ignore[method-assign]
        available=bool(embedded.launches),
        url=embedded.url if embedded.launches else None,
        version=None,
        control_available=False,
    )
    service = _service(
        embedded=embedded,
        embedded_startup_timeout=0.0,
        embedded_poll_interval=0.0,
    )

    response = service.open_path(str(tool))

    assert embedded.opened == []
    assert response.method == EditorOpenMethod.CLIPBOARD
    assert response.opened is False


def test_embedded_folder_open_does_not_require_control_endpoint(tmp_path: Path) -> None:
    tool_dir = tmp_path / "tool_package"
    tool_dir.mkdir()
    embedded = _Embedded(
        status=EditorStatus(
            available=True,
            url="http://127.0.0.1:32344",
            version=None,
            control_available=False,
        ),
        open_response=EditorOpenResponse(
            opened=True,
            method=EditorOpenMethod.EMBEDDED,
            url="http://127.0.0.1:32344/?folder=x",
            path=str(tool_dir),
        ),
    )
    service = _service(embedded=embedded)

    response = service.open_path(str(tool_dir))

    assert embedded.opened == [tool_dir]
    assert response.method == EditorOpenMethod.EMBEDDED


def test_embedded_manager_default_ports_and_command_order(tmp_path: Path) -> None:
    vsix = tmp_path / "opener-0.0.2.vsix"
    vsix.write_bytes(b"vsix")
    calls: list[list[str]] = []

    def runner(args: list[str]) -> object:
        calls.append(args)
        return object()

    manager = EmbeddedCodeServerManager(env_path=tmp_path / "codeserver", vsix_path=vsix)
    manager.launch(install_runner=runner, process_launcher=runner)

    assert manager.editor_url == "http://127.0.0.1:32344"
    assert manager.control_url == "http://127.0.0.1:60351"
    assert calls[0][-2:] == ["--install-extension", str(vsix)]
    assert calls[-1] == [
        "code-server",
        "--disable-workspace-trust",
        "--disable-telemetry",
        "--auth",
        "none",
        "--bind-addr",
        "127.0.0.1:32344",
    ]


def test_embedded_manager_default_launch_uses_codeserver_environment(tmp_path: Path) -> None:
    vsix = tmp_path / "opener-0.0.2.vsix"
    vsix.write_bytes(b"vsix")
    env_manager = _EnvironmentManager()

    manager = EmbeddedCodeServerManager(
        env_path=None,
        vsix_path=vsix,
        environment_manager_provider=lambda: env_manager,
    )
    manager.launch()

    assert env_manager.created == [
        (
            "codeserver",
            {"python": "3.10", "conda": ["code-server==4.106.2"], "pip": []},
            True,
        )
    ]
    assert env_manager.executed
    commands = env_manager.executed[0][1]
    assert commands[0].startswith("code-server --install-extension ")
    assert str(vsix) in commands[0]
    assert commands[-1].endswith("--bind-addr 127.0.0.1:32344")


def test_embedded_manager_loads_configured_environment_path(tmp_path: Path) -> None:
    vsix = tmp_path / "opener-0.0.2.vsix"
    vsix.write_bytes(b"vsix")
    env_path = tmp_path / "codeserver"
    env_manager = _EnvironmentManager()

    manager = EmbeddedCodeServerManager(
        env_path=env_path,
        vsix_path=vsix,
        environment_manager_provider=lambda: env_manager,
    )
    manager.launch()

    assert env_manager.loaded == [("codeserver", env_path)]
    assert env_manager.created == []


def test_embedded_manager_launch_command_uses_configured_editor_url(tmp_path: Path) -> None:
    manager = EmbeddedCodeServerManager(
        env_path=tmp_path / "codeserver",
        editor_url="http://127.0.0.1:42344/",
    )

    assert manager.launch_command()[-1] == "127.0.0.1:42344"


def test_default_opener_extension_is_packaged() -> None:
    vsix = default_opener_vsix_path()

    assert vsix.name == "opener-0.0.2.vsix"
    assert vsix.is_file()
    assert vsix.stat().st_size > 0


def test_embedded_manager_missing_opener_extension_is_unavailable(tmp_path: Path) -> None:
    manager = EmbeddedCodeServerManager(env_path=tmp_path / "codeserver", vsix_path=tmp_path / "missing.vsix")

    status = manager.status(url_probe=lambda url: True)

    assert status.available is True
    assert status.control_available is False


def test_embedded_manager_open_path_calls_opener_with_file_type(tmp_path: Path) -> None:
    opened: list[tuple[str, dict[str, str]]] = []
    manager = EmbeddedCodeServerManager(env_path=tmp_path / "codeserver")
    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")

    def opener(url: str, params: dict[str, str]) -> bool:
        opened.append((url, params))
        return True

    response = manager.open_path(tool, opener=opener)

    assert opened == [
        (
            "http://127.0.0.1:60351/open",
            {"path": str(tool), "type": "file", "new_window": "false"},
        )
    ]
    assert response.method == EditorOpenMethod.EMBEDDED


def test_embedded_manager_open_path_calls_opener_with_folder_type(tmp_path: Path) -> None:
    opened: list[tuple[str, dict[str, str]]] = []
    manager = EmbeddedCodeServerManager(env_path=tmp_path / "codeserver")
    tool_dir = tmp_path / "tool_package"
    tool_dir.mkdir()

    def opener(url: str, params: dict[str, str]) -> bool:
        opened.append((url, params))
        return True

    response = manager.open_path(tool_dir, opener=opener)

    assert opened == []
    assert response.method == EditorOpenMethod.EMBEDDED
    assert response.url == f"http://127.0.0.1:32344/?folder={str(tool_dir).replace('/', '%2F')}"
