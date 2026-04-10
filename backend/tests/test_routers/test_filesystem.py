"""Tests for the filesystem router."""

from unittest.mock import patch

import httpx
import pytest


pytestmark = pytest.mark.anyio


async def test_reveal_path_returns_200(client: httpx.AsyncClient) -> None:
    """POST /fs/reveal returns 200 on success."""
    with patch("bioimageflow_server.routers.filesystem.reveal_in_file_browser"):
        response = await client.post(
            "/api/v1/fs/reveal",
            json={"path": "/some/file.tif"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_reveal_path_calls_reveal_function(client: httpx.AsyncClient) -> None:
    """POST /fs/reveal calls reveal_in_file_browser with the given path."""
    with patch(
        "bioimageflow_server.routers.filesystem.reveal_in_file_browser"
    ) as mock_reveal:
        await client.post(
            "/api/v1/fs/reveal",
            json={"path": "/my/folder"},
        )

    mock_reveal.assert_called_once_with("/my/folder")


async def test_reveal_path_requires_path(client: httpx.AsyncClient) -> None:
    """POST /fs/reveal returns 422 when path is missing."""
    response = await client.post("/api/v1/fs/reveal", json={})

    assert response.status_code == 422


async def test_reveal_path_handles_os_error(client: httpx.AsyncClient) -> None:
    """POST /fs/reveal returns 500 when reveal_in_file_browser raises OSError."""
    with patch(
        "bioimageflow_server.routers.filesystem.reveal_in_file_browser",
        side_effect=OSError("Unsupported platform: UnknownOS"),
    ):
        response = await client.post(
            "/api/v1/fs/reveal",
            json={"path": "/some/path"},
        )

    assert response.status_code == 500
