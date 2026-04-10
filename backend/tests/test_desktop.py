"""Tests for desktop (pywebview) module."""

import inspect
from unittest.mock import MagicMock, patch


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
    assert params["host"].annotation == str

    assert "port" in params
    assert params["port"].default == 8000
    assert params["port"].annotation == int

    assert "dev" in params
    assert params["dev"].default is False
    assert params["dev"].annotation == bool

    assert sig.return_annotation is None


@patch("bioimageflow_server.desktop.webview")
@patch("bioimageflow_server.desktop.uvicorn")
@patch("bioimageflow_server.desktop.create_app")
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
@patch("bioimageflow_server.desktop.create_app")
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
@patch("bioimageflow_server.desktop.create_app")
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
    )
    mock_webview.start.assert_called_once()


@patch("bioimageflow_server.desktop.webview")
@patch("bioimageflow_server.desktop.uvicorn")
@patch("bioimageflow_server.desktop.create_app")
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
    )


@patch("bioimageflow_server.desktop.webview")
@patch("bioimageflow_server.desktop.uvicorn")
@patch("bioimageflow_server.desktop.create_app")
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
@patch("bioimageflow_server.desktop.create_app")
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
@patch("bioimageflow_server.desktop.create_app")
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
@patch("bioimageflow_server.desktop.create_app")
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
