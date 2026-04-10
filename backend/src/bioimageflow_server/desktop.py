"""Desktop entrypoint using pywebview."""

import threading
import time
import urllib.request
import urllib.error

import uvicorn
import webview

from bioimageflow_server.app import create_app


def start_desktop(host: str = "127.0.0.1", port: int = 8000, dev: bool = False) -> None:
    """Start the FastAPI server in a background thread and open a pywebview window.

    Args:
        host: The host to bind the server to.
        port: The port to bind the server to.
        dev: Whether to enable development mode.
    """
    app = create_app()

    server_thread = threading.Thread(
        target=lambda: uvicorn.run(app, host=host, port=port),
        daemon=True,
    )
    server_thread.start()

    # Wait for the server to be ready
    health_url = f"http://{host}:{port}/api/v1/health"
    _wait_for_server(health_url)

    webview.create_window("BioImageFlow", f"http://{host}:{port}")
    webview.start()


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
