"""Tests for desktop (pywebview) module."""

import inspect
from unittest.mock import ANY, MagicMock, patch

import pytest


def test_import_webview():
    """Verify that pywebview is installed and importable."""
    import webview  # noqa: F401


def test_start_desktop_exists_and_signature():
    """start_desktop has the correct signature with expected defaults."""
    from bioimageflow_server.desktop import start_desktop

    sig = inspect.signature(start_desktop)
    params = sig.parameters

    assert "host" in params
    assert params["host"].default == "127.0.0.1"
    # With `from __future__ import annotations` the annotation is the string 'str'
    assert params["host"].annotation in (str, "str")

    assert "port" in params
    assert params["port"].default == 8000
    assert params["port"].annotation in (int, "int")

    assert "dev" in params
    assert params["dev"].default is False
    assert params["dev"].annotation in (bool, "bool")

    assert sig.return_annotation is None or sig.return_annotation == "None"


def _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls):
    """Helper: wire up common mocks for start_desktop tests.

    Returns (mock_server, mock_thread, mock_window).
    """
    mock_server = MagicMock()
    mock_uvicorn.Config.return_value = MagicMock()
    mock_uvicorn.Server.return_value = mock_server

    mock_thread = MagicMock()
    mock_thread_cls.return_value = mock_thread

    mock_window = MagicMock()
    mock_webview.create_window.return_value = mock_window

    return mock_server, mock_thread, mock_window


class _MockEvent:
    """Small pywebview Event stand-in that records += handlers."""

    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self


@patch("bioimageflow_server.desktop.webview")
@patch("bioimageflow_server.desktop.uvicorn")
@patch("bioimageflow_server.app.create_app")
@patch("bioimageflow_server.desktop.threading.Thread")
@patch("bioimageflow_server.desktop.urllib.request.urlopen")
def test_uvicorn_runs_in_daemon_thread(
    mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
):
    """uvicorn is started in a daemon thread."""
    from bioimageflow_server.desktop import start_desktop

    mock_create_app.return_value = MagicMock()
    _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

    start_desktop()

    mock_thread_cls.assert_called_once()
    _, kwargs = mock_thread_cls.call_args
    assert kwargs.get("daemon") is True
    mock_thread_cls.return_value.start.assert_called_once()


@patch("bioimageflow_server.desktop.webview")
@patch("bioimageflow_server.desktop.uvicorn")
@patch("bioimageflow_server.app.create_app")
@patch("bioimageflow_server.desktop.threading.Thread")
@patch("bioimageflow_server.desktop.urllib.request.urlopen")
def test_uvicorn_config_and_server_created(
    mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
):
    """uvicorn.Config and uvicorn.Server are created with correct args."""
    from bioimageflow_server.desktop import start_desktop

    mock_app = MagicMock()
    mock_create_app.return_value = mock_app
    mock_server, _, _ = _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

    start_desktop(host="0.0.0.0", port=9000)

    mock_uvicorn.Config.assert_called_once()
    _, kwargs = mock_uvicorn.Config.call_args
    assert mock_uvicorn.Config.call_args.args[0] is mock_app
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 9000
    assert kwargs["log_config"].endswith("logging.yaml")
    mock_uvicorn.Server.assert_called_once_with(mock_uvicorn.Config.return_value)


@patch("bioimageflow_server.desktop.webview")
@patch("bioimageflow_server.desktop.uvicorn")
@patch("bioimageflow_server.app.create_app")
@patch("bioimageflow_server.desktop.threading.Thread")
@patch("bioimageflow_server.desktop.urllib.request.urlopen")
def test_uvicorn_config_uses_custom_log_config(
    mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
):
    """start_desktop forwards a custom Uvicorn log config path."""
    from bioimageflow_server.desktop import start_desktop

    mock_create_app.return_value = MagicMock()
    _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

    start_desktop(log_config="/tmp/custom-logging.yaml")

    _, kwargs = mock_uvicorn.Config.call_args
    assert kwargs["log_config"] == "/tmp/custom-logging.yaml"


@patch("bioimageflow_server.desktop.webview")
@patch("bioimageflow_server.desktop.uvicorn")
@patch("bioimageflow_server.app.create_app")
@patch("bioimageflow_server.desktop.threading.Thread")
@patch("bioimageflow_server.desktop.urllib.request.urlopen")
def test_server_run_is_thread_target(
    mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
):
    """The thread target is server.run."""
    from bioimageflow_server.desktop import start_desktop

    mock_create_app.return_value = MagicMock()
    mock_server, _, _ = _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

    start_desktop()

    _, kwargs = mock_thread_cls.call_args
    assert kwargs["target"] is mock_server.run


@patch("bioimageflow_server.desktop.webview")
@patch("bioimageflow_server.desktop.uvicorn")
@patch("bioimageflow_server.app.create_app")
@patch("bioimageflow_server.desktop.threading.Thread")
@patch("bioimageflow_server.desktop.urllib.request.urlopen")
def test_webview_window_created_with_correct_url(
    mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
):
    """A pywebview window is created with the correct title and URL."""
    from bioimageflow_server.desktop import start_desktop

    _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

    start_desktop(host="127.0.0.1", port=8000)

    mock_webview.create_window.assert_called_once_with(
        "BioImageFlow",
        "http://127.0.0.1:8000",
        width=1440,
        height=900,
        min_size=(1280, 720),
        resizable=True,
        confirm_close=True,
        js_api=ANY,
    )
    mock_webview.start.assert_called_once()


@patch("bioimageflow_server.desktop.webview")
@patch("bioimageflow_server.desktop.uvicorn")
@patch("bioimageflow_server.app.create_app")
@patch("bioimageflow_server.desktop.threading.Thread")
@patch("bioimageflow_server.desktop.urllib.request.urlopen")
def test_webview_window_custom_host_port(
    mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
):
    """A pywebview window URL reflects custom host and port."""
    from bioimageflow_server.desktop import start_desktop

    _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

    start_desktop(host="0.0.0.0", port=3000)

    mock_webview.create_window.assert_called_once_with(
        "BioImageFlow",
        "http://127.0.0.1:3000",
        width=1440,
        height=900,
        min_size=(1280, 720),
        resizable=True,
        confirm_close=True,
        js_api=ANY,
    )


@patch("bioimageflow_server.desktop.webview")
@patch("bioimageflow_server.desktop.uvicorn")
@patch("bioimageflow_server.app.create_app")
@patch("bioimageflow_server.desktop.threading.Thread")
@patch("bioimageflow_server.desktop.urllib.request.urlopen")
def test_window_default_size(
    mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
):
    """Window opens at 1440x900 default size."""
    from bioimageflow_server.desktop import start_desktop

    _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

    start_desktop()

    _, kwargs = mock_webview.create_window.call_args
    assert kwargs["width"] == 1440
    assert kwargs["height"] == 900


@patch("bioimageflow_server.desktop.webview")
@patch("bioimageflow_server.desktop.uvicorn")
@patch("bioimageflow_server.app.create_app")
@patch("bioimageflow_server.desktop.threading.Thread")
@patch("bioimageflow_server.desktop.urllib.request.urlopen")
def test_window_min_size(
    mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
):
    """Window min_size is (1280, 720)."""
    from bioimageflow_server.desktop import start_desktop

    _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

    start_desktop()

    _, kwargs = mock_webview.create_window.call_args
    assert kwargs["min_size"] == (1280, 720)


@patch("bioimageflow_server.desktop.webview")
@patch("bioimageflow_server.desktop.uvicorn")
@patch("bioimageflow_server.app.create_app")
@patch("bioimageflow_server.desktop.threading.Thread")
@patch("bioimageflow_server.desktop.urllib.request.urlopen")
def test_window_resizable(
    mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
):
    """Window is resizable."""
    from bioimageflow_server.desktop import start_desktop

    _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

    start_desktop()

    _, kwargs = mock_webview.create_window.call_args
    assert kwargs["resizable"] is True


@patch("bioimageflow_server.desktop.webview")
@patch("bioimageflow_server.desktop.uvicorn")
@patch("bioimageflow_server.app.create_app")
@patch("bioimageflow_server.desktop.threading.Thread")
@patch("bioimageflow_server.desktop.urllib.request.urlopen")
def test_window_confirm_close(
    mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
):
    """Window has confirm_close enabled."""
    from bioimageflow_server.desktop import start_desktop

    _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

    start_desktop()

    _, kwargs = mock_webview.create_window.call_args
    assert kwargs["confirm_close"] is True


class TestMainDesktopFlag:
    """Tests for __main__.py --desktop flag support."""

    @patch("bioimageflow_server.desktop.start_desktop")
    def test_main_with_desktop_flag(self, mock_start_desktop):
        """When --desktop is passed, start_desktop is called."""
        from bioimageflow_server.__main__ import main

        main(["--desktop"])

        mock_start_desktop.assert_called_once()

    @patch("bioimageflow_server.__main__.uvicorn")
    def test_main_without_desktop_flag(self, mock_uvicorn):
        """Without --desktop, uvicorn.run is called directly."""
        from bioimageflow_server.__main__ import main

        main([])

        mock_uvicorn.run.assert_called_once()
        _, kwargs = mock_uvicorn.run.call_args
        assert kwargs["log_config"].endswith("logging.yaml")

    @patch("bioimageflow_server.__main__.uvicorn")
    def test_main_dev_reload_watches_only_backend_source(self, mock_uvicorn):
        """Dev reload must not watch the repo root where Wetlands/Pixi envs live."""
        from bioimageflow_server.__main__ import main

        main(["--dev"])

        _, kwargs = mock_uvicorn.run.call_args
        assert kwargs["reload"] is True
        assert kwargs["reload_dirs"]
        assert all("bioimageflow_server" in path for path in kwargs["reload_dirs"])
        assert ".pixi/*" in kwargs["reload_excludes"]
        assert "bif_data/*" in kwargs["reload_excludes"]
        assert kwargs["log_config"].endswith("logging.yaml")

    @patch("bioimageflow_server.__main__.uvicorn")
    def test_main_accepts_custom_log_config(self, mock_uvicorn):
        """--log-config forwards a custom Uvicorn logging config path."""
        from bioimageflow_server.__main__ import main

        main(["--log-config", "/tmp/custom-logging.yaml"])

        _, kwargs = mock_uvicorn.run.call_args
        assert kwargs["log_config"] == "/tmp/custom-logging.yaml"

    @patch("bioimageflow_server.desktop.start_desktop")
    def test_main_desktop_passes_host_port(self, mock_start_desktop):
        """--desktop with --host and --port forwards them to start_desktop."""
        from bioimageflow_server.__main__ import main

        main(["--desktop", "--host", "0.0.0.0", "--port", "9000"])

        mock_start_desktop.assert_called_once()
        _, kwargs = mock_start_desktop.call_args
        assert kwargs["host"] == "0.0.0.0"
        assert kwargs["port"] == 9000
        assert kwargs["dev"] is False
        assert kwargs["log_config"].endswith("logging.yaml")

    @patch("bioimageflow_server.desktop.start_desktop")
    def test_main_desktop_with_dev_flag(self, mock_start_desktop):
        """--desktop with --dev forwards dev=True to start_desktop."""
        from bioimageflow_server.__main__ import main

        main(["--desktop", "--dev"])

        mock_start_desktop.assert_called_once()
        _, kwargs = mock_start_desktop.call_args
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == 8000
        assert kwargs["dev"] is True
        assert kwargs["log_config"].endswith("logging.yaml")


# ---------------------------------------------------------------------------
# DesktopApi tests
# ---------------------------------------------------------------------------


class TestDesktopApiClass:
    """Tests for the DesktopApi class itself."""

    def test_desktop_api_importable(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        assert api is not None

    def test_desktop_api_has_required_methods(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        assert callable(getattr(api, "select_file", None))
        assert callable(getattr(api, "select_files", None))
        assert callable(getattr(api, "select_folder", None))
        assert callable(getattr(api, "save_file", None))
        assert callable(getattr(api, "reveal_path", None))
        assert callable(getattr(api, "set_title", None))
        assert callable(getattr(api, "open_code_editor_window", None))
        assert callable(getattr(api, "close_code_editor_window", None))

    def test_set_window(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        assert api._window is None
        mock_window = MagicMock()
        api.set_window(mock_window)
        assert api._window is mock_window


class TestDesktopApiSelectFile:
    """Tests for DesktopApi.select_file."""

    def test_returns_none_when_no_window(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        assert api.select_file() is None

    @patch("bioimageflow_server.desktop.webview")
    def test_returns_path_on_selection(self, mock_webview):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = ("/some/file.tif",)
        api.set_window(mock_window)

        result = api.select_file("Pick", ["*.tif"])

        assert result == "/some/file.tif"
        mock_window.create_file_dialog.assert_called_once_with(
            mock_webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=("*.tif",),
        )

    def test_returns_none_on_cancel(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = None
        api.set_window(mock_window)

        assert api.select_file() is None

    def test_returns_none_on_empty_tuple(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = ()
        api.set_window(mock_window)

        assert api.select_file() is None

    def test_return_type_is_str_or_none(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = ("/path/to/file",)
        api.set_window(mock_window)

        result = api.select_file()
        assert isinstance(result, str) or result is None


class TestDesktopApiSelectFiles:
    """Tests for DesktopApi.select_files."""

    def test_returns_empty_list_when_no_window(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        assert api.select_files() == []

    @patch("bioimageflow_server.desktop.webview")
    def test_returns_list_of_paths(self, mock_webview):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = ("/a.tif", "/b.tif")
        api.set_window(mock_window)

        result = api.select_files("Pick", ["*.tif"])

        assert result == ["/a.tif", "/b.tif"]
        mock_window.create_file_dialog.assert_called_once_with(
            mock_webview.FileDialog.OPEN,
            allow_multiple=True,
            file_types=("*.tif",),
        )

    def test_returns_empty_list_on_cancel(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = None
        api.set_window(mock_window)

        assert api.select_files() == []

    def test_return_type_is_list(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = ("/x",)
        api.set_window(mock_window)

        result = api.select_files()
        assert isinstance(result, list)


class TestDesktopApiSelectFolder:
    """Tests for DesktopApi.select_folder."""

    def test_returns_none_when_no_window(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        assert api.select_folder() is None

    @patch("bioimageflow_server.desktop.webview")
    def test_returns_folder_path(self, mock_webview):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = ("/some/folder",)
        api.set_window(mock_window)

        result = api.select_folder("Pick folder")

        assert result == "/some/folder"
        mock_window.create_file_dialog.assert_called_once_with(
            mock_webview.FileDialog.FOLDER,
        )

    def test_returns_none_on_cancel(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = None
        api.set_window(mock_window)

        assert api.select_folder() is None


class TestDesktopApiSaveFile:
    """Tests for DesktopApi.save_file."""

    def test_returns_none_when_no_window(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        assert api.save_file() is None

    @patch("bioimageflow_server.desktop.webview")
    def test_returns_save_path(self, mock_webview):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = "/save/here.tif"
        api.set_window(mock_window)

        result = api.save_file("Save", ["*.tif"], "output.tif")

        assert result == "/save/here.tif"
        mock_window.create_file_dialog.assert_called_once_with(
            mock_webview.FileDialog.SAVE,
            save_filename="output.tif",
            file_types=("*.tif",),
        )

    def test_returns_none_on_cancel(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = None
        api.set_window(mock_window)

        assert api.save_file() is None


class TestDesktopApiRevealPath:
    """Tests for DesktopApi.reveal_path."""

    @patch("bioimageflow_server.routers.filesystem.platform.system", return_value="Darwin")
    @patch("bioimageflow_server.routers.filesystem.subprocess.Popen")
    def test_reveal_macos(self, mock_popen, mock_system):
        from bioimageflow_server.desktop import DesktopApi

        DesktopApi.reveal_path("/some/file.tif")

        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[0] == "open"
        assert args[1] == "-R"

    @patch("bioimageflow_server.routers.filesystem.platform.system", return_value="Linux")
    @patch("bioimageflow_server.routers.filesystem.subprocess.Popen")
    @patch("bioimageflow_server.routers.filesystem.os.path.isfile", return_value=True)
    def test_reveal_linux_file(self, mock_isfile, mock_popen, mock_system):
        from bioimageflow_server.desktop import DesktopApi

        DesktopApi.reveal_path("/some/file.tif")

        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[0] == "xdg-open"

    @patch("bioimageflow_server.routers.filesystem.platform.system", return_value="Windows")
    @patch("bioimageflow_server.routers.filesystem.subprocess.Popen")
    def test_reveal_windows(self, mock_popen, mock_system):
        from bioimageflow_server.desktop import DesktopApi

        DesktopApi.reveal_path("C:\\some\\file.tif")

        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[0] == "explorer"

    @patch("bioimageflow_server.routers.filesystem.platform.system", return_value="UnknownOS")
    def test_reveal_unsupported_raises(self, mock_system):
        from bioimageflow_server.desktop import DesktopApi

        with pytest.raises(OSError, match="Unsupported platform"):
            DesktopApi.reveal_path("/some/path")


class TestDesktopApiSetTitle:
    """Tests for DesktopApi.set_title."""

    def test_set_title_calls_window(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        mock_window = MagicMock()
        api.set_window(mock_window)

        api.set_title("New Title")

        mock_window.set_title.assert_called_once_with("New Title")

    def test_set_title_noop_without_window(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        # Should not raise
        api.set_title("Title")


class TestDesktopApiCodeEditorWindow:
    """Tests for DesktopApi code editor child-window management."""

    @patch("bioimageflow_server.desktop.webview")
    def test_open_code_editor_window_creates_child_window(self, mock_webview):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        child_window = MagicMock()
        closed_event = _MockEvent()
        child_window.events.closed = closed_event
        mock_webview.create_window.return_value = child_window

        assert api.open_code_editor_window(
            "http://127.0.0.1:32344/?folder=/tmp/tool", "Tool Editor"
        )

        mock_webview.create_window.assert_called_once_with(
            "Tool Editor",
            "http://127.0.0.1:32344/?folder=/tmp/tool",
            width=1200,
            height=800,
            min_size=(800, 600),
            resizable=True,
            confirm_close=False,
        )
        assert api._code_editor_window is child_window
        assert len(closed_event.handlers) == 1

    @patch("bioimageflow_server.desktop.webview")
    def test_open_code_editor_window_reuses_existing_child(self, mock_webview):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        child_window = MagicMock()
        child_window.events.closed = _MockEvent()
        mock_webview.create_window.return_value = child_window

        api.open_code_editor_window("http://localhost:32344", "Code Editor")
        api.open_code_editor_window("http://localhost:32344", "Focused Editor")

        mock_webview.create_window.assert_called_once()
        child_window.set_title.assert_called_once_with("Focused Editor")
        child_window.restore.assert_called_once()
        child_window.show.assert_called_once()

    @patch("bioimageflow_server.desktop.webview")
    def test_close_code_editor_window_destroys_child(self, mock_webview):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        child_window = MagicMock()
        child_window.events.closed = _MockEvent()
        mock_webview.create_window.return_value = child_window

        api.open_code_editor_window("http://127.0.0.1:32344", "Code Editor")

        assert api.close_code_editor_window() is True
        child_window.destroy.assert_called_once()
        assert api._code_editor_window is None

    def test_close_code_editor_window_without_child_returns_false(self):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()

        assert api.close_code_editor_window() is False

    @patch("bioimageflow_server.desktop.webview")
    def test_child_close_event_clears_state_and_notifies_frontend(self, mock_webview):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        main_window = MagicMock()
        child_window = MagicMock()
        closed_event = _MockEvent()
        child_window.events.closed = closed_event
        mock_webview.create_window.return_value = child_window
        api.set_window(main_window)

        api.open_code_editor_window("http://127.0.0.1:32344", "Code Editor")
        on_closed = closed_event.handlers[0]
        on_closed()

        assert api._code_editor_window is None
        main_window.evaluate_js.assert_called_once_with(
            "window.dispatchEvent(new CustomEvent("
            "'bioimageflow:code-editor-window-closed'"
            "))"
        )

    @patch("bioimageflow_server.desktop.webview")
    def test_programmatic_close_does_not_emit_manual_close_event(self, mock_webview):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()
        main_window = MagicMock()
        child_window = MagicMock()
        closed_event = _MockEvent()
        child_window.events.closed = closed_event
        mock_webview.create_window.return_value = child_window
        api.set_window(main_window)

        api.open_code_editor_window("http://127.0.0.1:32344", "Code Editor")
        api.close_code_editor_window()
        on_closed = closed_event.handlers[0]
        on_closed()

        main_window.evaluate_js.assert_not_called()

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com",
            "http://192.168.1.5:32344",
            "file:///tmp/index.html",
            "ftp://localhost/editor",
            "not-a-url",
        ],
    )
    def test_open_code_editor_window_rejects_non_local_urls(self, url):
        from bioimageflow_server.desktop import DesktopApi

        api = DesktopApi()

        with pytest.raises(ValueError):
            api.open_code_editor_window(url, "Code Editor")


class TestStartDesktopDevUrl:
    """Tests for dev-mode URL routing in start_desktop."""

    @patch("bioimageflow_server.desktop.webview")
    @patch("bioimageflow_server.desktop.uvicorn")
    @patch("bioimageflow_server.app.create_app")
    @patch("bioimageflow_server.desktop.threading.Thread")
    @patch("bioimageflow_server.desktop.urllib.request.urlopen")
    def test_dev_true_uses_vite_url(
        self, mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
    ):
        """dev=True points the window at the Vite dev server."""
        from bioimageflow_server.desktop import start_desktop

        _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

        start_desktop(host="127.0.0.1", port=8000, dev=True)

        args, _ = mock_webview.create_window.call_args
        assert args[1] == "http://localhost:5173"

    @patch("bioimageflow_server.desktop.webview")
    @patch("bioimageflow_server.desktop.uvicorn")
    @patch("bioimageflow_server.app.create_app")
    @patch("bioimageflow_server.desktop.threading.Thread")
    @patch("bioimageflow_server.desktop.urllib.request.urlopen")
    def test_dev_false_uses_fastapi_url(
        self, mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
    ):
        """dev=False points the window at the FastAPI server."""
        from bioimageflow_server.desktop import start_desktop

        _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

        start_desktop(host="127.0.0.1", port=8000, dev=False)

        args, _ = mock_webview.create_window.call_args
        assert args[1] == "http://127.0.0.1:8000"

    @patch("bioimageflow_server.desktop.webview")
    @patch("bioimageflow_server.desktop.uvicorn")
    @patch("bioimageflow_server.app.create_app")
    @patch("bioimageflow_server.desktop.threading.Thread")
    @patch("bioimageflow_server.desktop.urllib.request.urlopen")
    def test_dev_false_custom_host_port(
        self, mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
    ):
        """dev=False with custom host/port builds the correct URL."""
        from bioimageflow_server.desktop import start_desktop

        _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

        start_desktop(host="0.0.0.0", port=9000, dev=False)

        args, _ = mock_webview.create_window.call_args
        assert args[1] == "http://127.0.0.1:9000"

    @patch("bioimageflow_server.desktop.webview")
    @patch("bioimageflow_server.desktop.uvicorn")
    @patch("bioimageflow_server.app.create_app")
    @patch("bioimageflow_server.desktop.threading.Thread")
    @patch("bioimageflow_server.desktop.urllib.request.urlopen")
    def test_dev_true_ignores_host_port_for_window_url(
        self, mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
    ):
        """dev=True always uses localhost:5173 regardless of host/port args."""
        from bioimageflow_server.desktop import start_desktop

        _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

        start_desktop(host="0.0.0.0", port=9000, dev=True)

        args, _ = mock_webview.create_window.call_args
        assert args[1] == "http://localhost:5173"

    @patch("bioimageflow_server.desktop.webview")
    @patch("bioimageflow_server.desktop.uvicorn")
    @patch("bioimageflow_server.app.create_app")
    @patch("bioimageflow_server.desktop.threading.Thread")
    @patch("bioimageflow_server.desktop.urllib.request.urlopen")
    def test_dev_true_still_starts_fastapi_server(
        self, mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
    ):
        """dev=True still starts the FastAPI backend (needed for the API)."""
        from bioimageflow_server.desktop import start_desktop

        _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

        start_desktop(dev=True)

        mock_uvicorn.Config.assert_called_once()
        mock_uvicorn.Server.assert_called_once()
        mock_thread_cls.return_value.start.assert_called_once()


class TestStartDesktopJsApi:
    """Tests that start_desktop wires the JS API correctly."""

    @patch("bioimageflow_server.desktop.webview")
    @patch("bioimageflow_server.desktop.uvicorn")
    @patch("bioimageflow_server.app.create_app")
    @patch("bioimageflow_server.desktop.threading.Thread")
    @patch("bioimageflow_server.desktop.urllib.request.urlopen")
    def test_js_api_passed_to_create_window(
        self, mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
    ):
        """create_window receives a DesktopApi instance as js_api."""
        from bioimageflow_server.desktop import DesktopApi, start_desktop

        _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

        start_desktop()

        _, kwargs = mock_webview.create_window.call_args
        assert "js_api" in kwargs
        assert isinstance(kwargs["js_api"], DesktopApi)

    @patch("bioimageflow_server.desktop.webview")
    @patch("bioimageflow_server.desktop.uvicorn")
    @patch("bioimageflow_server.app.create_app")
    @patch("bioimageflow_server.desktop.threading.Thread")
    @patch("bioimageflow_server.desktop.urllib.request.urlopen")
    def test_js_api_window_is_set(
        self, mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
    ):
        """The DesktopApi instance has its window set to the created window."""
        from bioimageflow_server.desktop import DesktopApi, start_desktop

        _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)
        mock_window = mock_webview.create_window.return_value

        start_desktop()

        _, kwargs = mock_webview.create_window.call_args
        api_instance = kwargs["js_api"]
        assert isinstance(api_instance, DesktopApi)
        assert api_instance._window is mock_window


# ---------------------------------------------------------------------------
# Shutdown lifecycle tests
# ---------------------------------------------------------------------------


class TestShutdown:
    """Tests for the _shutdown function."""

    def test_shutdown_sets_should_exit(self):
        """_shutdown sets server.should_exit = True."""
        from bioimageflow_server.desktop import _shutdown

        mock_server = MagicMock()
        mock_server.should_exit = False
        mock_thread = MagicMock()

        _shutdown(mock_server, mock_thread)

        assert mock_server.should_exit is True

    def test_shutdown_joins_thread(self):
        """_shutdown joins the server thread with a timeout."""
        from bioimageflow_server.desktop import _SERVER_THREAD_JOIN_TIMEOUT, _shutdown

        mock_server = MagicMock()
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False

        _shutdown(mock_server, mock_thread)

        mock_thread.join.assert_called_once_with(timeout=_SERVER_THREAD_JOIN_TIMEOUT)

    def test_shutdown_logs_warning_if_thread_alive(self, caplog):
        """_shutdown logs a warning if the server thread does not stop in time."""
        import logging
        from bioimageflow_server.desktop import _shutdown

        mock_server = MagicMock()
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True

        with caplog.at_level(logging.WARNING, logger="bioimageflow_server.desktop"):
            _shutdown(mock_server, mock_thread)

        assert any("did not terminate" in msg for msg in caplog.messages)

    def test_shutdown_no_warning_if_thread_stopped(self, caplog):
        """No warning if the thread exits cleanly."""
        import logging
        from bioimageflow_server.desktop import _shutdown

        mock_server = MagicMock()
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False

        with caplog.at_level(logging.WARNING, logger="bioimageflow_server.desktop"):
            _shutdown(mock_server, mock_thread)

        assert not any("did not terminate" in msg for msg in caplog.messages)

    def test_shutdown_logs_info_messages(self, caplog):
        """_shutdown logs 'Shutting down...' and 'Shutdown complete'."""
        import logging
        from bioimageflow_server.desktop import _shutdown

        mock_server = MagicMock()
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False

        with caplog.at_level(logging.INFO, logger="bioimageflow_server.desktop"):
            _shutdown(mock_server, mock_thread)

        assert "Shutting down..." in caplog.messages
        assert "Shutdown complete" in caplog.messages

    def test_shutdown_steps_execute_in_order(self, caplog):
        """All five shutdown steps execute in the correct order."""
        import logging
        from bioimageflow_server.desktop import _shutdown

        mock_server = MagicMock()
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False

        with caplog.at_level(logging.DEBUG, logger="bioimageflow_server.desktop"):
            _shutdown(mock_server, mock_thread)

        debug_msgs = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
        step_msgs = [m for m in debug_msgs if m.startswith("Shutdown step")]

        assert len(step_msgs) == 5
        assert "1/5" in step_msgs[0]
        assert "2/5" in step_msgs[1]
        assert "3/5" in step_msgs[2]
        assert "4/5" in step_msgs[3]
        assert "5/5" in step_msgs[4]


class TestOnClosing:
    """Tests for the _on_closing event handler."""

    def test_on_closing_returns_true(self):
        """_on_closing currently always returns True (allow close)."""
        from bioimageflow_server.desktop import _on_closing

        assert _on_closing() is True

    def test_on_closing_is_callable(self):
        """_on_closing is a callable."""
        from bioimageflow_server.desktop import _on_closing

        assert callable(_on_closing)


class TestStartDesktopShutdownIntegration:
    """Tests that start_desktop wires shutdown and closing correctly."""

    @patch("bioimageflow_server.desktop._shutdown")
    @patch("bioimageflow_server.desktop.webview")
    @patch("bioimageflow_server.desktop.uvicorn")
    @patch("bioimageflow_server.app.create_app")
    @patch("bioimageflow_server.desktop.threading.Thread")
    @patch("bioimageflow_server.desktop.urllib.request.urlopen")
    def test_shutdown_called_after_webview_start(
        self, mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn,
        mock_webview, mock_shutdown,
    ):
        """_shutdown is called after webview.start() returns."""
        from bioimageflow_server.desktop import start_desktop

        mock_server, _, _ = _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

        start_desktop()

        mock_shutdown.assert_called_once_with(mock_server, mock_thread_cls.return_value)

    @patch("bioimageflow_server.desktop._shutdown")
    @patch("bioimageflow_server.desktop._on_closing")
    @patch("bioimageflow_server.desktop.webview")
    @patch("bioimageflow_server.desktop.uvicorn")
    @patch("bioimageflow_server.app.create_app")
    @patch("bioimageflow_server.desktop.threading.Thread")
    @patch("bioimageflow_server.desktop.urllib.request.urlopen")
    def test_closing_event_registered_on_window(
        self, mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn,
        mock_webview, mock_on_closing, mock_shutdown,
    ):
        """The closing event handler is registered on the window."""
        from bioimageflow_server.desktop import start_desktop

        _, _, mock_window = _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)

        # Make events.closing track += calls via a list
        registered_handlers = []
        mock_closing = MagicMock()
        mock_closing.__iadd__ = MagicMock(side_effect=lambda h: registered_handlers.append(h) or mock_closing)
        mock_window.events.closing = mock_closing
        mock_on_closing.return_value = True

        start_desktop()

        assert len(registered_handlers) == 1
        assert registered_handlers[0]() is True
        mock_on_closing.assert_called_once()

    @patch("bioimageflow_server.desktop._shutdown")
    @patch("bioimageflow_server.desktop.webview")
    @patch("bioimageflow_server.desktop.uvicorn")
    @patch("bioimageflow_server.app.create_app")
    @patch("bioimageflow_server.desktop.threading.Thread")
    @patch("bioimageflow_server.desktop.urllib.request.urlopen")
    def test_shutdown_called_even_if_webview_start_raises(
        self, mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn,
        mock_webview, mock_shutdown,
    ):
        """_shutdown is called even if webview.start() raises an exception."""
        from bioimageflow_server.desktop import start_desktop

        mock_server, _, _ = _make_start_desktop_mocks(mock_webview, mock_uvicorn, mock_thread_cls)
        mock_webview.start.side_effect = Exception("crash")

        with pytest.raises(Exception, match="crash"):
            start_desktop()

        mock_shutdown.assert_called_once_with(mock_server, mock_thread_cls.return_value)


class TestShutdownConstants:
    """Tests for shutdown-related constants."""

    def test_server_thread_join_timeout_is_positive(self):
        from bioimageflow_server.desktop import _SERVER_THREAD_JOIN_TIMEOUT

        assert _SERVER_THREAD_JOIN_TIMEOUT > 0

    def test_execution_stop_timeout_is_positive(self):
        from bioimageflow_server.desktop import _EXECUTION_STOP_TIMEOUT

        assert _EXECUTION_STOP_TIMEOUT > 0

    def test_execution_stop_timeout_is_10s(self):
        from bioimageflow_server.desktop import _EXECUTION_STOP_TIMEOUT

        assert _EXECUTION_STOP_TIMEOUT == 10.0


class TestEntryPoint:
    """Tests for the bioimageflow-gui console script entry point."""

    def test_bioimageflow_gui_entry_point(self):
        """The bioimageflow-gui console_scripts entry point resolves correctly."""
        from importlib.metadata import entry_points

        eps = entry_points(group="console_scripts")
        matches = [ep for ep in eps if ep.name == "bioimageflow-gui"]
        assert len(matches) == 1
        assert matches[0].value == "bioimageflow_server.desktop:main_desktop"

    def test_main_desktop_exists_and_callable(self):
        """main_desktop is importable and callable with no arguments."""
        from bioimageflow_server.desktop import main_desktop

        assert callable(main_desktop)
        sig = inspect.signature(main_desktop)
        # main_desktop takes no parameters
        assert len(sig.parameters) == 0

    def test_main_desktop_calls_start_desktop(self):
        """main_desktop delegates to start_desktop with default arguments."""
        with patch("bioimageflow_server.desktop.start_desktop") as mock_start:
            from bioimageflow_server.desktop import main_desktop

            main_desktop()
            mock_start.assert_called_once_with()
