from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.editor import EditorOpenMethod, EditorOpenResponse, EditorStatus
from bioimageflow_server.models.tools import AppConfig

pytestmark = pytest.mark.anyio


class _EditorStub:
    def __init__(self, response: EditorOpenResponse | None = None) -> None:
        self.response = response
        self.paths: list[str] = []

    def get_status(self, *, launch: bool = False) -> EditorStatus:
        return EditorStatus(
            available=True,
            url="http://127.0.0.1:32344",
            version=None,
            control_available=True,
        )

    def open_path(self, path: str) -> EditorOpenResponse:
        self.paths.append(path)
        if self.response is not None:
            return self.response
        return EditorOpenResponse(
            opened=False,
            method=EditorOpenMethod.CLIPBOARD,
            path=str(Path(path).expanduser()),
            message="Path copied - open in your local editor.",
        )


async def _client(config: AppConfig) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(config=config)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_editor_status_endpoint_uses_service() -> None:
    config = AppConfig(editor_service=_EditorStub())
    async for client in _client(config):
        response = await client.get("/api/v1/editor/status")

    assert response.status_code == 200
    assert response.json() == {
        "available": True,
        "url": "http://127.0.0.1:32344",
        "version": None,
        "control_available": True,
    }


async def test_editor_routes_are_present_in_openapi() -> None:
    config = AppConfig(editor_service=_EditorStub())
    async for client in _client(config):
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/editor/status" in paths
    assert "/api/v1/editor/open" in paths


async def test_editor_open_external_response(tmp_path: Path) -> None:
    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    config = AppConfig(
        editor_service=_EditorStub(
            EditorOpenResponse(
                opened=True,
                method=EditorOpenMethod.EXTERNAL,
                path=str(tool),
            )
        )
    )
    async for client in _client(config):
        response = await client.post("/api/v1/editor/open", json={"path": str(tool)})

    assert response.status_code == 200
    assert response.json()["method"] == "external"


async def test_editor_open_embedded_response(tmp_path: Path) -> None:
    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    config = AppConfig(
        editor_service=_EditorStub(
            EditorOpenResponse(
                opened=True,
                method=EditorOpenMethod.EMBEDDED,
                url="http://127.0.0.1:32344",
                path=str(tool),
            )
        )
    )
    async for client in _client(config):
        response = await client.post("/api/v1/editor/open", json={"path": str(tool)})

    assert response.status_code == 200
    assert response.json()["method"] == "embedded"
    assert response.json()["url"] == "http://127.0.0.1:32344"


async def test_editor_open_clipboard_response(tmp_path: Path) -> None:
    tool = tmp_path / "tool.py"
    tool.write_text("print('x')")
    config = AppConfig(editor_service=_EditorStub())
    async for client in _client(config):
        response = await client.post("/api/v1/editor/open", json={"path": str(tool)})

    assert response.status_code == 200
    assert response.json()["method"] == "clipboard"
    assert response.json()["opened"] is False


async def test_editor_open_rejects_empty_path() -> None:
    config = AppConfig(editor_service=_EditorStub())
    async for client in _client(config):
        response = await client.post("/api/v1/editor/open", json={"path": " "})

    assert response.status_code == 422


async def test_editor_open_missing_path_returns_404(tmp_path: Path) -> None:
    config = AppConfig()
    async for client in _client(config):
        response = await client.post(
            "/api/v1/editor/open",
            json={"path": str(tmp_path / "missing.py")},
        )

    assert response.status_code == 404
