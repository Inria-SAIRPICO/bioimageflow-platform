from __future__ import annotations

import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from wetlands import EnvironmentSpec

from bioimageflow_server.models.editor import (
    EditorLaunchPhase,
    EditorOpenMethod,
    EditorOpenResponse,
    EditorStatus,
)
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

    def open_path(self, path: Path, focus_path: Path | None = None) -> EditorOpenResponse:
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

    def open_path(self, path: Path, focus_path: Path | None = None) -> EditorOpenResponse:
        self.opened.append(path)
        return EditorOpenResponse(
            opened=True,
            method=EditorOpenMethod.EMBEDDED,
            url=self.url,
            path=str(focus_path or path),
        )


class _BlockingLaunchEmbedded(_LaunchableEmbedded):
    def __init__(self, *, url: str = "http://127.0.0.1:32344") -> None:
        super().__init__(url=url)
        self.launch_started = threading.Event()
        self.release_launch = threading.Event()
        self._launched = False
        self._lock = threading.Lock()

    def status(self) -> EditorStatus:
        with self._lock:
            launched = self._launched
        if launched:
            return EditorStatus(
                available=True,
                url=self.url,
                version=None,
                control_available=True,
            )
        return self.status_value

    def launch(self) -> None:
        with self._lock:
            self.launches += 1
        self.launch_started.set()
        assert self.release_launch.wait(timeout=2.0)
        with self._lock:
            self._launched = True


class _EnvironmentManager:
    def __init__(self) -> None:
        self.provisioned: list[tuple[str, object, bool]] = []
        self.environment = MagicMock()
        self.environment.run.side_effect = [
            SimpleNamespace(returncode=0, stderr=""),
            *[SimpleNamespace(returncode=0, stderr="") for _ in range(5)],
        ]
        self.process = object()
        self.environment.spawn.return_value = self.process

    def provision(
        self,
        name: str,
        spec: object,
        *,
        replace_existing: bool = False,
    ) -> object:
        self.provisioned.append((name, spec, replace_existing))
        return SimpleNamespace(wait_for=lambda: self.environment)


def _settings(command: str | None = None) -> Settings:
    return Settings(deployment_mode="desktop", external_editor=command)


def _service(
    *,
    command: str | None = None,
    embedded: _Embedded | None = None,
    launcher: _RecorderLauncher | None = None,
    embedded_startup_timeout: float = 10.0,
    embedded_poll_interval: float = 0.2,
    workspace_path_provider=None,
    tool_store_path_provider=None,
) -> EditorService:
    return EditorService(
        settings_provider=lambda: _settings(command),
        process_launcher=launcher or _RecorderLauncher(),
        embedded_manager=embedded or _Embedded(),
        embedded_startup_timeout=embedded_startup_timeout,
        embedded_poll_interval=embedded_poll_interval,
        workspace_path_provider=workspace_path_provider,
        tool_store_path_provider=tool_store_path_provider,
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


def test_external_editor_opens_workspace_and_focused_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tool = workspace / "tools" / "tool.py"
    tool.parent.mkdir()
    tool.write_text("print('x')")
    launcher = _RecorderLauncher()
    service = _service(command="code --reuse-window", launcher=launcher)

    response = service.open_path(str(workspace), str(tool))

    assert response.path == str(tool)
    assert launcher.calls == [["code", "--reuse-window", str(workspace), str(tool)]]


def test_external_editor_focus_path_placeholder_prefers_focused_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tool = workspace / "tools" / "tool.py"
    tool.parent.mkdir()
    tool.write_text("print('x')")
    launcher = _RecorderLauncher()
    service = _service(command="code --goto {file_path}:1 {workspace_path}", launcher=launcher)

    service.open_path(str(workspace), str(tool))

    assert launcher.calls == [["code", "--goto", f"{tool}:1", str(workspace)]]


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
    service = _service(
        embedded=embedded,
        embedded_startup_timeout=0.0,
        embedded_poll_interval=0.0,
    )

    response = service.open_path(str(tool))

    assert response.opened is False
    assert response.method == EditorOpenMethod.CLIPBOARD


def test_running_embedded_file_open_without_control_does_not_launch_again(
    tmp_path: Path,
) -> None:
    class AvailableLaunchableEmbedded(_Embedded):
        def __init__(self) -> None:
            super().__init__(
                status=EditorStatus(
                    available=True,
                    url="http://127.0.0.1:32344",
                    version=None,
                    control_available=False,
                )
            )
            self.launches = 0

        def launch(self) -> None:
            self.launches += 1

    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    embedded = AvailableLaunchableEmbedded()
    service = _service(
        embedded=embedded,
        embedded_startup_timeout=0.0,
        embedded_poll_interval=0.0,
    )

    response = service.open_path(str(tool))

    assert embedded.launches == 0
    assert embedded.opened == []
    assert response.method == EditorOpenMethod.CLIPBOARD
    assert response.error_code == "embedded_opener_timeout"


def test_running_embedded_opener_failure_does_not_launch_again(tmp_path: Path) -> None:
    class AvailableLaunchableEmbedded(_Embedded):
        def __init__(self) -> None:
            super().__init__(
                status=EditorStatus(
                    available=True,
                    url="http://127.0.0.1:32344",
                    version=None,
                    control_available=True,
                ),
                exc=ConnectionError("no opener"),
            )
            self.launches = 0

        def launch(self) -> None:
            self.launches += 1

    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    embedded = AvailableLaunchableEmbedded()
    service = _service(
        embedded=embedded,
        embedded_startup_timeout=0.0,
        embedded_poll_interval=0.0,
    )

    response = service.open_path(str(tool))

    assert embedded.launches == 0
    assert embedded.opened == [tool]
    assert response.method == EditorOpenMethod.CLIPBOARD
    assert response.error_code == "embedded_opener_timeout"


def test_reloading_embedded_editor_waits_instead_of_launching_again(tmp_path: Path) -> None:
    class ReloadingEmbedded(_Embedded):
        def __init__(self) -> None:
            self.ready_status = EditorStatus(
                available=True,
                url="http://127.0.0.1:32344",
                version=None,
                control_available=True,
            )
            self.status_values = [
                EditorStatus(
                    available=False,
                    url=None,
                    version=None,
                    control_available=True,
                ),
                self.ready_status,
            ]
            super().__init__(
                status=self.status_values[0],
                open_response=EditorOpenResponse(
                    opened=True,
                    method=EditorOpenMethod.EMBEDDED,
                    url="http://127.0.0.1:32344",
                    path="",
                ),
            )
            self.launches = 0

        def status(self) -> EditorStatus:
            if self.status_values:
                return self.status_values.pop(0)
            return self.ready_status

        def launch(self) -> None:
            self.launches += 1

        def open_path(self, path: Path, focus_path: Path | None = None) -> EditorOpenResponse:
            self.opened.append(path)
            return EditorOpenResponse(
                opened=True,
                method=EditorOpenMethod.EMBEDDED,
                url="http://127.0.0.1:32344",
                path=str(focus_path or path),
            )

    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    embedded = ReloadingEmbedded()
    service = _service(
        embedded=embedded,
        embedded_startup_timeout=1.0,
        embedded_poll_interval=0.0,
    )

    response = service.open_path(str(tool))

    assert embedded.launches == 0
    assert embedded.opened == [tool]
    assert response.method == EditorOpenMethod.EMBEDDED
    assert response.path == str(tool)


def test_embedded_open_after_launch_retries_transient_opener_failure(tmp_path: Path) -> None:
    class LaunchingEmbedded(_LaunchableEmbedded):
        def __init__(self) -> None:
            super().__init__()
            self.failures_remaining = 1

        def open_path(self, path: Path, focus_path: Path | None = None) -> EditorOpenResponse:
            self.opened.append(path)
            if self.failures_remaining:
                self.failures_remaining -= 1
                raise ConnectionError("workspace is still reloading")
            return EditorOpenResponse(
                opened=True,
                method=EditorOpenMethod.EMBEDDED,
                url=self.url,
                path=str(focus_path or path),
            )

    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    embedded = LaunchingEmbedded()
    service = _service(
        embedded=embedded,
        embedded_startup_timeout=1.0,
        embedded_poll_interval=0.0,
    )

    response = service.open_path(str(tool))

    assert embedded.launches == 1
    assert embedded.opened == [tool, tool]
    assert response.method == EditorOpenMethod.EMBEDDED
    assert response.path == str(tool)


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
    assert status.launch_attempted is True


def test_plain_status_does_not_generate_managed_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    tool_store = tmp_path / "tool_packages"
    workspace.mkdir()
    tool_store.mkdir()
    service = _service(
        workspace_path_provider=lambda: workspace,
        tool_store_path_provider=lambda: tool_store,
    )

    service.get_status()

    assert not (workspace / ".bioimageflow" / "BioImageFlow.code-workspace").exists()


def test_status_can_launch_managed_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    tool_store = tmp_path / "tool_packages"
    workspace.mkdir()
    tool_store.mkdir()
    embedded = _LaunchableEmbedded()
    service = _service(
        embedded=embedded,
        workspace_path_provider=lambda: workspace,
        tool_store_path_provider=lambda: tool_store,
    )

    status = service.get_status(launch=True, workspace=True)

    workspace_file = workspace / ".bioimageflow" / "BioImageFlow.code-workspace"
    assert status.available is True
    assert status.url == (
        "http://127.0.0.1:32344/?workspace="
        + str(workspace_file).replace("/", "%2F")
    )


def test_status_reports_managed_workspace_failure(tmp_path: Path) -> None:
    service = _service(
        workspace_path_provider=lambda: tmp_path / "missing",
        tool_store_path_provider=lambda: tmp_path / "also-missing",
    )

    status = service.get_status(launch=True, workspace=True)

    assert status.available is False
    assert status.error_code == "embedded_workspace_failed"
    assert "FileNotFoundError" in str(status.error_detail)


def test_status_reports_embedded_launch_failure() -> None:
    class FailingEmbedded(_Embedded):
        def launch(self) -> None:
            raise TypeError("bad wetlands api")

    service = _service(embedded=FailingEmbedded())

    status = service.get_status(launch=True)

    assert status.available is False
    assert status.launch_attempted is True
    assert status.error_code == "embedded_launch_failed"
    assert status.error_detail == "TypeError: bad wetlands api"


def test_status_reports_embedded_startup_timeout() -> None:
    embedded = _LaunchableEmbedded()
    embedded.status = lambda: EditorStatus(  # type: ignore[method-assign]
        available=False,
        url=None,
        version=None,
        control_available=False,
    )
    service = _service(
        embedded=embedded,
        embedded_startup_timeout=0.0,
        embedded_poll_interval=0.0,
    )

    status = service.get_status(launch=True)

    assert embedded.launches == 1
    assert status.available is False
    assert status.launch_attempted is True
    assert status.error_code == "embedded_startup_timeout"
    assert status.error_detail == "code-server did not become available before timeout"


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


def test_embedded_tool_open_uses_managed_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    tool_store = tmp_path / "tool_packages"
    tool = tool_store / "package" / "1.0" / "tool.py"
    workspace.mkdir()
    tool.parent.mkdir(parents=True)
    tool.write_text("print('x')")
    embedded = _LaunchableEmbedded()
    service = _service(
        embedded=embedded,
        workspace_path_provider=lambda: workspace,
        tool_store_path_provider=lambda: tool_store,
    )

    response = service.open_path(str(tool_store), str(tool), workspace=True)

    workspace_file = workspace / ".bioimageflow" / "BioImageFlow.code-workspace"
    assert embedded.opened == [workspace_file]
    assert response.path == str(tool)


def test_external_tool_open_does_not_generate_managed_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    tool_store = tmp_path / "tool_packages"
    tool = tool_store / "package" / "1.0" / "tool.py"
    workspace.mkdir()
    tool.parent.mkdir(parents=True)
    tool.write_text("print('x')")
    launcher = _RecorderLauncher()
    service = _service(
        command="code {workspace_path} --goto {file_path}",
        launcher=launcher,
        workspace_path_provider=lambda: workspace,
        tool_store_path_provider=lambda: tool_store,
    )

    service.open_path(str(tool_store), str(tool), workspace=True)

    assert launcher.calls == [["code", str(tool_store), "--goto", str(tool)]]
    assert not (workspace / ".bioimageflow" / "BioImageFlow.code-workspace").exists()


def test_concurrent_embedded_opens_share_single_launch(tmp_path: Path) -> None:
    tool_a = tmp_path / "a.py"
    tool_b = tmp_path / "b.py"
    tool_a.write_text("print('a')")
    tool_b.write_text("print('b')")
    embedded = _BlockingLaunchEmbedded()
    service = _service(
        embedded=embedded,
        embedded_startup_timeout=1.0,
        embedded_poll_interval=0.001,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(service.open_path, str(tool_a))
        assert embedded.launch_started.wait(timeout=2.0)
        second = executor.submit(service.open_path, str(tool_b))
        time.sleep(0.05)
        embedded.release_launch.set()
        responses = [first.result(timeout=2.0), second.result(timeout=2.0)]

    assert embedded.launches == 1
    assert [response.method for response in responses] == [
        EditorOpenMethod.EMBEDDED,
        EditorOpenMethod.EMBEDDED,
    ]
    assert embedded.opened == [tool_a, tool_b]


def test_status_launch_and_open_path_share_single_launch(tmp_path: Path) -> None:
    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    embedded = _BlockingLaunchEmbedded()
    service = _service(
        embedded=embedded,
        embedded_startup_timeout=1.0,
        embedded_poll_interval=0.001,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        status_future = executor.submit(service.get_status, launch=True)
        assert embedded.launch_started.wait(timeout=2.0)
        open_future = executor.submit(service.open_path, str(tool))
        time.sleep(0.05)
        embedded.release_launch.set()
        status = status_future.result(timeout=2.0)
        response = open_future.result(timeout=2.0)

    assert embedded.launches == 1
    assert status.available is True
    assert status.launch_attempted is True
    assert response.method == EditorOpenMethod.EMBEDDED
    assert embedded.opened == [tool]


def test_open_path_clipboard_fallback_reports_embedded_launch_failure(tmp_path: Path) -> None:
    class FailingEmbedded(_Embedded):
        def launch(self) -> None:
            raise TypeError("bad wetlands api")

    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    service = _service(embedded=FailingEmbedded())

    response = service.open_path(str(tool))

    assert response.opened is False
    assert response.method == EditorOpenMethod.CLIPBOARD
    assert response.error_code == "embedded_launch_failed"
    assert response.error_detail == "TypeError: bad wetlands api"


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
    assert response.error_code == "embedded_startup_timeout"
    assert response.error_detail == "code-server did not become available before timeout"
    assert response.opened is False


def test_embedded_folder_focus_opens_project_before_control_endpoint(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tool = workspace / "tools" / "tool.py"
    tool.parent.mkdir()
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

    response = service.open_path(str(workspace), str(tool))

    assert embedded.opened == [workspace]
    assert response.method == EditorOpenMethod.EMBEDDED
    assert response.path == str(tool)


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
    vsix = tmp_path / "bioimageflow-opener-0.1.0.vsix"
    vsix.write_bytes(b"vsix")
    calls: list[list[str]] = []

    def runner(args: list[str]) -> object:
        calls.append(args)
        return object()

    manager = EmbeddedCodeServerManager(vsix_path=vsix)
    manager.launch(install_runner=runner, process_launcher=runner)

    assert manager.editor_url == "http://127.0.0.1:32344"
    assert manager.control_url == "http://127.0.0.1:60351"
    assert calls[0] == ["code-server", "--uninstall-extension", "sairpico.opener"]
    assert calls[1][-2:] == ["--install-extension", str(vsix)]
    assert calls[-1] == [
        "code-server",
        "--disable-workspace-trust",
        "--disable-telemetry",
        "--auth",
        "none",
        "--bind-addr",
        "127.0.0.1:32344",
    ]
    status = manager.status(url_probe=lambda _url: False)
    assert status.launch_phase == EditorLaunchPhase.STARTING
    assert status.launch_message == "Starting code-server."
    assert status.launch_started_at is not None


def test_embedded_manager_reports_extension_installation_steps(tmp_path: Path) -> None:
    vsix = tmp_path / "bioimageflow-opener-0.1.0.vsix"
    vsix.write_bytes(b"vsix")
    progress: list[tuple[EditorLaunchPhase, int | None, int | None, str | None]] = []
    manager = EmbeddedCodeServerManager(vsix_path=vsix)

    def runner(args: list[str]) -> object:
        if "--install-extension" in args:
            status = manager.status(url_probe=lambda _url: False)
            progress.append(
                (
                    status.launch_phase,
                    status.launch_current,
                    status.launch_total,
                    status.launch_message,
                )
            )
        return object()

    manager.launch(install_runner=runner, process_launcher=runner)

    assert [(phase, current, total) for phase, current, total, _ in progress] == [
        (EditorLaunchPhase.INSTALLING_EXTENSIONS, 1, 5),
        (EditorLaunchPhase.INSTALLING_EXTENSIONS, 2, 5),
        (EditorLaunchPhase.INSTALLING_EXTENSIONS, 3, 5),
        (EditorLaunchPhase.INSTALLING_EXTENSIONS, 4, 5),
        (EditorLaunchPhase.INSTALLING_EXTENSIONS, 5, 5),
    ]
    assert progress[0][3] == "Installing BioImageFlow editor integration."
    assert progress[-1][3] == "Installing Python type checking."


def test_embedded_manager_launch_status_can_be_polled_concurrently(tmp_path: Path) -> None:
    vsix = tmp_path / "bioimageflow-opener-0.1.0.vsix"
    vsix.write_bytes(b"vsix")
    manager = EmbeddedCodeServerManager(vsix_path=vsix)
    install_started = threading.Event()
    release_install = threading.Event()

    def runner(args: list[str]) -> object:
        if "--install-extension" in args:
            install_started.set()
            assert release_install.wait(timeout=2.0)
        return object()

    with ThreadPoolExecutor(max_workers=1) as executor:
        launch = executor.submit(
            manager.launch,
            install_runner=runner,
            process_launcher=lambda _args: object(),
        )
        assert install_started.wait(timeout=2.0)
        status = manager.status(url_probe=lambda _url: False)
        release_install.set()
        launch.result(timeout=2.0)

    assert status.launch_phase == EditorLaunchPhase.INSTALLING_EXTENSIONS
    assert status.launch_current == 1
    assert status.launch_total == 5


def test_embedded_manager_reports_launch_failure(tmp_path: Path) -> None:
    vsix = tmp_path / "bioimageflow-opener-0.1.0.vsix"
    vsix.write_bytes(b"vsix")
    manager = EmbeddedCodeServerManager(vsix_path=vsix)

    with pytest.raises(RuntimeError, match="extension failed"):
        manager.launch(
            install_runner=lambda _args: (_ for _ in ()).throw(
                RuntimeError("extension failed")
            ),
            process_launcher=lambda _args: object(),
        )

    status = manager.status(url_probe=lambda _url: False)
    assert status.launch_phase == EditorLaunchPhase.FAILED
    assert status.launch_message == "RuntimeError: extension failed"


def test_embedded_manager_ignores_missing_legacy_opener_uninstall(
    tmp_path: Path,
) -> None:
    vsix = tmp_path / "bioimageflow-opener-0.1.0.vsix"
    vsix.write_bytes(b"vsix")
    calls: list[list[str]] = []

    def runner(args: list[str]) -> object:
        calls.append(args)
        if args == ["code-server", "--uninstall-extension", "sairpico.opener"]:
            raise RuntimeError("Extension 'sairpico.opener' is not installed")
        return object()

    manager = EmbeddedCodeServerManager(vsix_path=vsix)
    manager.launch(install_runner=runner, process_launcher=runner)

    assert calls[0] == ["code-server", "--uninstall-extension", "sairpico.opener"]
    assert calls[1][-2:] == ["--install-extension", str(vsix)]
    assert calls[-1][0] == "code-server"


def test_embedded_manager_default_launch_uses_codeserver_environment(tmp_path: Path) -> None:
    vsix = tmp_path / "bioimageflow-opener-0.1.0.vsix"
    vsix.write_bytes(b"vsix")
    env_manager = _EnvironmentManager()

    manager = EmbeddedCodeServerManager(
        vsix_path=vsix,
        environment_manager_provider=lambda: env_manager,
    )
    manager.launch()

    assert env_manager.provisioned == [
        (
            "codeserver",
            EnvironmentSpec(
                python="3.10.*",
                conda=("code-server==4.106.2",),
            ),
            True,
        )
    ]
    run_calls = env_manager.environment.run.call_args_list
    assert run_calls[0].args[0] == [
        "code-server",
        "--uninstall-extension",
        "sairpico.opener",
    ]
    assert run_calls[0].kwargs == {"check": False}
    assert run_calls[1].args[0] == ["code-server", "--install-extension", str(vsix)]
    launch_call = env_manager.environment.spawn.call_args
    assert launch_call.args[0][-2:] == ["--bind-addr", "127.0.0.1:32344"]
    assert launch_call.kwargs == {"output_limit": 16 * 1024 * 1024}


def test_embedded_manager_launch_command_uses_configured_editor_url(tmp_path: Path) -> None:
    manager = EmbeddedCodeServerManager(
        editor_url="http://127.0.0.1:42344/",
    )

    assert manager.launch_command()[-1] == "127.0.0.1:42344"


def test_default_opener_extension_is_packaged() -> None:
    vsix = default_opener_vsix_path()

    assert vsix.name == "bioimageflow-opener-0.1.0.vsix"
    assert vsix.is_file()
    assert vsix.stat().st_size > 0


def test_default_opener_extension_matches_source_package() -> None:
    vsix = default_opener_vsix_path()
    source_package = vsix.parent / "extension-src" / "package.json"
    source_code = vsix.parent / "extension-src" / "src" / "extension.ts"

    package_text = source_package.read_text(encoding="utf-8")
    source_text = source_code.read_text(encoding="utf-8")
    with zipfile.ZipFile(vsix) as archive:
        packaged_package = archive.read("extension/package.json").decode("utf-8")
        packaged_extension = archive.read("extension/out/extension.js").decode("utf-8")

    assert '"name": "bioimageflow-opener"' in package_text
    assert '"publisher": "bioimageflow"' in package_text
    assert '"version": "0.1.0"' in package_text
    assert '"name": "bioimageflow-opener"' in packaged_package
    assert '"publisher": "bioimageflow"' in packaged_package
    assert '"version": "0.1.0"' in packaged_package
    assert "openQueue" in source_text
    assert "openQueue" in packaged_extension
    assert "revealInExplorer" not in source_text
    assert "revealInExplorer" not in packaged_extension


def test_embedded_manager_missing_opener_extension_is_unavailable(tmp_path: Path) -> None:
    manager = EmbeddedCodeServerManager(vsix_path=tmp_path / "missing.vsix")

    status = manager.status(url_probe=lambda url: True)

    assert status.available is True
    assert status.control_available is False


def test_embedded_manager_diagnostics_report_probe_results(tmp_path: Path) -> None:
    manager = EmbeddedCodeServerManager(
        vsix_path=tmp_path / "missing.vsix",
    )

    diagnostics = manager.diagnostics()

    assert diagnostics["editor_url"] == "http://127.0.0.1:32344"
    assert diagnostics["control_url"] == "http://127.0.0.1:60351/open"
    assert diagnostics["opener_vsix_path"] == str(tmp_path / "missing.vsix")
    assert diagnostics["opener_vsix_exists"] is False
    assert "probe" in str(diagnostics["editor_probe"]).lower() or diagnostics["editor_probe"]
    assert "probe" in str(diagnostics["control_probe"]).lower() or diagnostics["control_probe"]


def test_embedded_manager_open_path_calls_opener_with_file_type(tmp_path: Path) -> None:
    opened: list[tuple[str, dict[str, str]]] = []
    manager = EmbeddedCodeServerManager()
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
    manager = EmbeddedCodeServerManager()
    tool_dir = tmp_path / "tool_package"
    tool_dir.mkdir()

    def opener(url: str, params: dict[str, str]) -> bool:
        opened.append((url, params))
        return True

    response = manager.open_path(tool_dir, opener=opener)

    assert opened == []
    assert response.method == EditorOpenMethod.EMBEDDED
    assert response.url == f"http://127.0.0.1:32344/?folder={str(tool_dir).replace('/', '%2F')}"


def test_embedded_manager_open_path_can_focus_file_inside_folder(tmp_path: Path) -> None:
    manager = EmbeddedCodeServerManager()
    workspace = tmp_path / "workspace"
    tool = workspace / "tools" / "tool.py"
    tool.parent.mkdir(parents=True)
    tool.write_text("print('x')")

    response = manager.open_path(workspace, focus_path=tool)

    assert response.method == EditorOpenMethod.EMBEDDED
    assert response.path == str(tool)
    assert f"folder={str(workspace).replace('/', '%2F')}" in response.url
    assert "file=" not in response.url


def test_embedded_manager_open_path_can_focus_file_inside_workspace(tmp_path: Path) -> None:
    manager = EmbeddedCodeServerManager()
    workspace_file = tmp_path / "BioImageFlow.code-workspace"
    workspace_file.write_text('{"folders": []}')
    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")

    response = manager.open_path(workspace_file, focus_path=tool)

    assert response.method == EditorOpenMethod.EMBEDDED
    assert response.path == str(tool)
    assert response.project_path == str(workspace_file)
    assert f"workspace={str(workspace_file).replace('/', '%2F')}" in str(response.url)
    assert "folder=" not in str(response.url)
