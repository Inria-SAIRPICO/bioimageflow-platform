"""Desktop entrypoint using pywebview."""

from __future__ import annotations

import logging
import threading
import time
import urllib.request
import urllib.error

import uvicorn
import webview

logger = logging.getLogger(__name__)


class DesktopApi:
    """JS API bridge exposed to the frontend via pywebview.

    Methods on this class are available in JavaScript as
    ``window.pywebview.api.<method_name>()``.
    """

    def __init__(self) -> None:
        self._window: webview.Window | None = None

    def set_window(self, window: webview.Window) -> None:
        """Bind the pywebview window reference after creation."""
        self._window = window

    # ---- File dialogs ----

    def select_file(self, title: str = "Select File", file_types: list[str] | None = None) -> str | None:
        """Open a native file picker and return the selected path, or None.

        ``title`` is part of the API contract but not supported by pywebview's
        native dialogs -- it is accepted for forward-compatibility only.
        """
        if self._window is None:
            return None
        file_types = file_types or []
        result = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=tuple(file_types) if file_types else (),
        )
        if result and len(result) > 0:
            return str(result[0])
        return None

    def select_files(self, title: str = "Select Files", file_types: list[str] | None = None) -> list[str]:
        """Open a native file picker allowing multiple selection.

        ``title`` is part of the API contract but not supported by pywebview's
        native dialogs -- it is accepted for forward-compatibility only.
        """
        if self._window is None:
            return []
        file_types = file_types or []
        result = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=True,
            file_types=tuple(file_types) if file_types else (),
        )
        if result:
            return [str(p) for p in result]
        return []

    def select_folder(self, title: str = "Select Folder") -> str | None:
        """Open a native folder picker.

        ``title`` is part of the API contract but not supported by pywebview's
        native dialogs -- it is accepted for forward-compatibility only.
        """
        if self._window is None:
            return None
        result = self._window.create_file_dialog(
            webview.FileDialog.FOLDER,
        )
        if result and len(result) > 0:
            return str(result[0])
        return None

    def save_file(
        self,
        title: str = "Save File",
        file_types: list[str] | None = None,
        default_name: str = "",
    ) -> str | None:
        """Open a native save dialog and return the chosen path, or None.

        ``title`` is part of the API contract but not supported by pywebview's
        native dialogs -- it is accepted for forward-compatibility only.
        """
        if self._window is None:
            return None
        file_types = file_types or []
        result = self._window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=default_name,
            file_types=tuple(file_types) if file_types else (),
        )
        if result:
            return str(result)
        return None

    # ---- Reveal path ----

    @staticmethod
    def reveal_path(path: str) -> None:
        """Open the given path in the system file browser.

        Delegates to :func:`bioimageflow_server.routers.filesystem.reveal_in_file_browser`.
        """
        from bioimageflow_server.routers.filesystem import reveal_in_file_browser

        reveal_in_file_browser(path)

    # ---- Window helpers ----

    def set_title(self, title: str) -> None:
        """Update the window title."""
        if self._window is not None:
            self._window.set_title(title)


def start_desktop(host: str = "127.0.0.1", port: int = 8000, dev: bool = False) -> None:
    """Start the FastAPI server in a background thread and open a pywebview window.

    Args:
        host: The host to bind the server to.
        port: The port to bind the server to.
        dev: Whether to enable development mode.
    """
    from bioimageflow_server.app import create_app

    app = create_app()

    config = uvicorn.Config(app, host=host, port=port)
    server = uvicorn.Server(config)

    server_thread = threading.Thread(
        target=server.run,
        daemon=True,
    )
    server_thread.start()

    # Wait for the server to be ready
    poll_host = "127.0.0.1" if host == "0.0.0.0" else host
    health_url = f"http://{poll_host}:{port}/api/v1/health"
    _wait_for_server(health_url)

    api = DesktopApi()

    window = webview.create_window(
        "BioImageFlow",
        f"http://{host}:{port}",
        width=1440,
        height=900,
        min_size=(1280, 720),
        resizable=True,
        confirm_close=True,
        js_api=api,
    )
    api.set_window(window)

    window.events.closing += _on_closing

    try:
        webview.start()
    finally:
        # Window has been closed (or start() raised) -- run shutdown sequence
        _shutdown(server, server_thread)


def _on_closing() -> bool:
    """Handle the pywebview ``closing`` event.

    Returning ``False`` prevents the window from closing (e.g. when there are
    unsaved changes and the user cancels).  Returning ``True`` allows the close
    to proceed.

    .. note::

       Checking the frontend for unsaved changes is not yet implemented.
       This handler currently always allows the close.
    """
    # TODO: query the frontend for unsaved changes via the JS API and, if
    # present, show a native confirmation dialog.  For now, always allow close.
    logger.debug("Window closing event received — allowing close")
    return True


_SERVER_THREAD_JOIN_TIMEOUT = 5.0
_EXECUTION_STOP_TIMEOUT = 10.0


def _shutdown(
    server: uvicorn.Server,
    server_thread: threading.Thread,
) -> None:
    """Run the full shutdown sequence after the pywebview window closes.

    Steps executed in order:

    1. Stop any running execution (placeholder).
    2. Terminate the Napari process if running (placeholder).
    3. Clean up shared memory segments (placeholder).
    4. Save pending settings (placeholder).
    5. Signal the uvicorn server to exit and wait for the thread to finish.
    """
    logger.info("Shutting down...")

    # 1. Stop running execution (placeholder)
    logger.debug("Shutdown step 1/5: stopping execution (no-op placeholder)")

    # 2. Terminate Napari (placeholder)
    logger.debug("Shutdown step 2/5: terminating Napari (no-op placeholder)")

    # 3. Clean up shared memory (placeholder)
    logger.debug("Shutdown step 3/5: cleaning shared memory (no-op placeholder)")

    # 4. Save settings (placeholder)
    logger.debug("Shutdown step 4/5: saving settings (no-op placeholder)")

    # 5. Signal uvicorn to stop and wait for the server thread
    logger.debug("Shutdown step 5/5: stopping uvicorn server")
    server.should_exit = True
    server_thread.join(timeout=_SERVER_THREAD_JOIN_TIMEOUT)
    if server_thread.is_alive():
        logger.warning(
            "Server thread did not terminate within %.1fs",
            _SERVER_THREAD_JOIN_TIMEOUT,
        )

    logger.info("Shutdown complete")


def _wait_for_server(url: str, timeout: float = 10.0, interval: float = 0.1) -> None:
    """Poll a URL until it responds or the timeout is reached."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except (urllib.error.URLError, OSError):
            time.sleep(interval)
    raise TimeoutError(f"Server did not become ready at {url} within {timeout}s")
