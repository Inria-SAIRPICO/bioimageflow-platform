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

    mock_app = MagicMock()
    mock_create_app.return_value = mock_app

    mock_thread = MagicMock()
    mock_thread_cls.return_value = mock_thread

    start_desktop()

    mock_thread_cls.assert_called_once()
    _, kwargs = mock_thread_cls.call_args
    assert kwargs.get("daemon") is True
    mock_thread.start.assert_called_once()


@patch("bioimageflow_server.desktop.webview")
@patch("bioimageflow_server.desktop.uvicorn")
@patch("bioimageflow_server.app.create_app")
@patch("bioimageflow_server.desktop.threading.Thread")
@patch("bioimageflow_server.desktop.urllib.request.urlopen")
def test_uvicorn_target_called_with_app(
    mock_urlopen, mock_thread_cls, mock_create_app, mock_uvicorn, mock_webview
):
    """The thread target calls uvicorn.run with the created app."""
    from bioimageflow_server.desktop import start_desktop

    mock_app = MagicMock()
    mock_create_app.return_value = mock_app

    mock_thread = MagicMock()
    mock_thread_cls.return_value = mock_thread

    start_desktop(host="0.0.0.0", port=9000)

    _, kwargs = mock_thread_cls.call_args
    # Extract and call the target to verify uvicorn.run is called correctly
    target = kwargs["target"]
    target()

    mock_uvicorn.run.assert_called_once_with(mock_app, host="0.0.0.0", port=9000)


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

    mock_thread = MagicMock()
    mock_thread_cls.return_value = mock_thread

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

    mock_thread = MagicMock()
    mock_thread_cls.return_value = mock_thread

    start_desktop(host="0.0.0.0", port=3000)

    mock_webview.create_window.assert_called_once_with(
        "BioImageFlow",
        "http://0.0.0.0:3000",
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

    mock_thread_cls.return_value = MagicMock()

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

    mock_thread_cls.return_value = MagicMock()

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

    mock_thread_cls.return_value = MagicMock()

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

    mock_thread_cls.return_value = MagicMock()

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

    @patch("bioimageflow_server.desktop.start_desktop")
    def test_main_desktop_passes_host_port(self, mock_start_desktop):
        """--desktop with --host and --port forwards them to start_desktop."""
        from bioimageflow_server.__main__ import main

        main(["--desktop", "--host", "0.0.0.0", "--port", "9000"])

        mock_start_desktop.assert_called_once_with(
            host="0.0.0.0", port=9000, dev=False
        )

    @patch("bioimageflow_server.desktop.start_desktop")
    def test_main_desktop_with_dev_flag(self, mock_start_desktop):
        """--desktop with --dev forwards dev=True to start_desktop."""
        from bioimageflow_server.__main__ import main

        main(["--desktop", "--dev"])

        mock_start_desktop.assert_called_once_with(
            host="127.0.0.1", port=8000, dev=True
        )


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

        mock_thread_cls.return_value = MagicMock()

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

        mock_thread_cls.return_value = MagicMock()
        mock_window = MagicMock()
        mock_webview.create_window.return_value = mock_window

        start_desktop()

        _, kwargs = mock_webview.create_window.call_args
        api_instance = kwargs["js_api"]
        assert isinstance(api_instance, DesktopApi)
        assert api_instance._window is mock_window
