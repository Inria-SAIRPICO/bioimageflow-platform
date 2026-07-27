"""Desktop entrypoint using pywebview."""

from __future__ import annotations

import logging
from pathlib import Path
import sys
import threading
import time
from urllib.parse import urlparse
import urllib.request

import uvicorn
import webview

from bioimageflow_server.logging_config import resolve_log_config_path

logger = logging.getLogger(__name__)

_DESKTOP_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
_LINUX_APP_ICON = _DESKTOP_ASSETS_DIR / "app_icon.png"
_MACOS_APP_ICON = _DESKTOP_ASSETS_DIR / "app_icon.icns"
_WINDOWS_APP_ICON = _DESKTOP_ASSETS_DIR / "app_icon.ico"


def _native_app_icon_path(platform: str | None = None) -> Path:
    """Return the platform-native desktop icon bundled with the backend."""
    platform = platform or sys.platform
    if platform == "darwin":
        return _MACOS_APP_ICON
    if platform == "win32":
        return _WINDOWS_APP_ICON
    return _LINUX_APP_ICON


def _configure_native_window_icon(window: webview.Window) -> None:
    """Apply native icons where pywebview cannot use ``start(icon=...)``.

    pywebview supports its public icon argument on GTK and Qt. BioImageFlow is
    installed from a Python release archive instead of a frozen executable, so
    macOS and Windows need their native application/window APIs at runtime.
    """
    if sys.platform not in {"darwin", "win32"}:
        return

    icon_path = _native_app_icon_path()

    def apply_icon() -> None:
        try:
            if sys.platform == "darwin":
                _set_macos_app_icon(icon_path)
            else:
                _set_windows_window_icon(window, icon_path)
        except Exception:
            logger.warning(
                "Could not set the native desktop icon from %s",
                icon_path,
                exc_info=True,
            )

    window.events.shown += apply_icon


def _set_macos_app_icon(icon_path: Path) -> None:
    """Set the macOS Dock icon on the Cocoa main thread."""
    from AppKit import NSApplication, NSImage  # type: ignore[import-not-found]

    image = NSImage.alloc().initWithContentsOfFile_(str(icon_path))
    if image is None:
        raise RuntimeError(f"Could not load macOS application icon: {icon_path}")

    application = NSApplication.sharedApplication()
    application.performSelectorOnMainThread_withObject_waitUntilDone_(
        "setApplicationIconImage:",
        image,
        True,
    )


def _set_windows_window_icon(window: webview.Window, icon_path: Path) -> None:
    """Set a WinForms window icon through pywebview's native window handle."""
    from System import Action  # type: ignore[import-not-found]
    from System.Drawing import Icon  # type: ignore[import-not-found]

    native_window = window.native
    if native_window is None:
        raise RuntimeError("pywebview did not expose its native Windows window")

    def apply_icon() -> None:
        source_icon = Icon(str(icon_path))
        try:
            native_window.Icon = source_icon.Clone()
        finally:
            source_icon.Dispose()

    if native_window.InvokeRequired:
        native_window.Invoke(Action(apply_icon))
    else:
        apply_icon()


class DesktopApi:
    """JS API bridge exposed to the frontend via pywebview.

    Methods on this class are available in JavaScript as
    ``window.pywebview.api.<method_name>()``.
    """

    def __init__(self) -> None:
        self._window: webview.Window | None = None
        self._code_editor_window: webview.Window | None = None

    def set_window(self, window: webview.Window) -> None:
        """Bind the pywebview window reference after creation."""
        self._window = window

    # ---- File dialogs ----

    def select_file(
        self, title: str = "Select File", file_types: list[str] | None = None
    ) -> str | None:
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

    def select_files(
        self, title: str = "Select Files", file_types: list[str] | None = None
    ) -> list[str]:
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

    # ---- Code editor child window ----

    def open_code_editor_window(self, url: str, title: str = "Code Editor") -> bool:
        """Open or focus the detached code-server window.

        Only local code-server URLs are accepted. This bridge intentionally does
        not provide arbitrary native-window navigation.
        """
        _validate_local_editor_url(url)

        if self._code_editor_window is not None:
            self._focus_code_editor_window(title)
            return True

        window = webview.create_window(
            title or "Code Editor",
            url,
            width=1200,
            height=800,
            min_size=(800, 600),
            resizable=True,
            confirm_close=False,
        )
        if window is None:
            return False

        _configure_native_window_icon(window)
        self._code_editor_window = window

        def on_closed(*_args: object) -> None:
            if self._code_editor_window is window:
                self._code_editor_window = None
                self._notify_code_editor_window_closed()

        window.events.closed += on_closed
        return True

    def close_code_editor_window(self) -> bool:
        """Close the detached Code Editor window, if one is open."""
        window = self._code_editor_window
        if window is None:
            return False
        self._code_editor_window = None
        try:
            window.destroy()
        except Exception:
            logger.exception("Failed to close Code Editor window")
            return False
        return True

    def _focus_code_editor_window(self, title: str) -> None:
        window = self._code_editor_window
        if window is None:
            return
        if title:
            window.set_title(title)
        window.restore()
        window.show()

    def _notify_code_editor_window_closed(self) -> None:
        if self._window is None:
            return
        try:
            self._window.evaluate_js(
                "window.dispatchEvent(new CustomEvent("
                "'bioimageflow:code-editor-window-closed'"
                "))"
            )
        except Exception:
            logger.exception("Failed to notify frontend that Code Editor window closed")


def main_desktop() -> None:
    """Console-script entry point for ``bioimageflow-gui``.

    Launches the desktop application with default settings.  This is the
    target of the ``[project.scripts]`` entry point so that users can
    simply run ``bioimageflow-gui`` from the command line.
    """
    start_desktop()


def start_desktop(
    host: str = "127.0.0.1",
    port: int = 8000,
    dev: bool = False,
    log_config: str | None = None,
) -> None:
    """Start the FastAPI server in a background thread and open a pywebview window.

    When *dev* is ``True`` the window loads the Vite dev server at
    ``http://localhost:5173`` so that frontend changes are reflected
    instantly via HMR, and pywebview opens its developer tools.  When
    *dev* is ``False`` (the default, used in production), the window loads
    the FastAPI server which serves the pre-built frontend assets and
    pywebview's developer tools remain disabled.

    The FastAPI backend is always started regardless of *dev* because
    the frontend needs the API endpoints.

    Args:
        host: The host to bind the FastAPI server to.
        port: The port to bind the FastAPI server to.
        dev: If ``True``, point the window at the Vite dev server
            (``http://localhost:5173``) for hot-module-replacement and
            enable pywebview's developer tools.
        log_config: Optional Uvicorn logging config path. Defaults to the
            packaged BioImageFlow logging config.
    """
    from bioimageflow_server.app import create_app
    from bioimageflow_server.models.tools import AppConfig

    app_config = AppConfig()
    if not dev:
        # In production mode, serve the pre-built frontend from frontend/dist/
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        static_dir = project_root / "frontend" / "dist"
        if static_dir.is_dir():
            app_config.static_dir = static_dir
        else:
            logger.warning(
                "Frontend dist directory not found at %s; static serving disabled",
                static_dir,
            )

    app = create_app(config=app_config)

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_config=resolve_log_config_path(log_config),
    )
    server = uvicorn.Server(config)

    server_thread = threading.Thread(
        target=server.run,
        daemon=True,
    )
    server_thread.start()

    display_host = "127.0.0.1" if host == "0.0.0.0" else host
    _wait_for_server(
        server,
        server_thread,
        health_url=f"http://{display_host}:{port}/api/v1/health",
    )

    api = DesktopApi()

    window_url = "http://localhost:5173" if dev else f"http://{display_host}:{port}"
    logger.info("Window URL: %s (dev=%s)", window_url, dev)

    window = webview.create_window(
        "BioImageFlow",
        window_url,
        width=1440,
        height=900,
        min_size=(1280, 720),
        resizable=True,
        confirm_close=True,
        js_api=api,
    )
    assert window is not None, "webview.create_window returned None"
    _configure_native_window_icon(window)
    api.set_window(window)

    def on_main_window_closing() -> bool:
        api.close_code_editor_window()
        return _on_closing()

    window.events.closing += on_main_window_closing

    try:
        print("BioImageFlow Desktop Initialized")
        if sys.platform in {"darwin", "win32"}:
            webview.start(debug=dev)
        else:
            webview.start(debug=dev, icon=str(_LINUX_APP_ICON))
    finally:
        api.close_code_editor_window()
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


def _validate_local_editor_url(url: str) -> None:
    """Reject non-local URLs before opening a native child window."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Code Editor window URL must use http or https")
    if parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("Code Editor window URL must be local")


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


def _wait_for_server(
    server: uvicorn.Server,
    server_thread: threading.Thread,
    health_url: str,
    timeout: float = 10.0,
    interval: float = 0.1,
) -> None:
    """Wait until uvicorn has started, or raise if the thread died first.

    Watches ``server.started`` and fails fast if the uvicorn thread exits
    before the server is ready. Uvicorn logs the underlying startup exception;
    this guard prevents a silent hang after any such failure.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.started:
            try:
                with urllib.request.urlopen(health_url, timeout=interval):
                    return
            except OSError:
                pass
        if not server_thread.is_alive():
            raise RuntimeError(
                "Backend server failed to start. The uvicorn thread exited "
                "before the server became ready. Review the preceding uvicorn "
                "error for the root cause."
            )
        time.sleep(interval)
    raise TimeoutError(f"Server did not become ready within {timeout}s")


if __name__ == "__main__":
    main_desktop()
