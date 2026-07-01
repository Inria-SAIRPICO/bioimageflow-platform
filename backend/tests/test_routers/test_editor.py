from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.editor import EditorOpenMethod, EditorOpenResponse, EditorStatus
from bioimageflow_server.models.tools import AppConfig, ToolMetadata
from bioimageflow_server.services.tool_registry import ToolRegistryService

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

    def open_path(self, path: str, focus_path: str | None = None) -> EditorOpenResponse:
        self.paths.append(path)
        if self.response is not None:
            return self.response
        return EditorOpenResponse(
            opened=False,
            method=EditorOpenMethod.CLIPBOARD,
            path=str(Path(focus_path or path).expanduser()),
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
        "launch_attempted": False,
        "error_code": None,
        "error_detail": None,
    }


async def test_editor_routes_are_present_in_openapi() -> None:
    config = AppConfig(editor_service=_EditorStub())
    async for client in _client(config):
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/editor/status" in paths
    assert "/api/v1/editor/open" in paths
    assert "/api/v1/editor/open-tool" in paths


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


async def test_editor_open_accepts_focus_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tool = workspace / "tools" / "tool.py"
    tool.parent.mkdir()
    tool.write_text("print('x')")
    editor = _EditorStub()
    config = AppConfig(editor_service=editor)
    async for client in _client(config):
        response = await client.post(
            "/api/v1/editor/open",
            json={"path": str(workspace), "focus_path": str(tool)},
        )

    assert response.status_code == 200
    assert response.json()["path"] == str(tool)
    assert editor.paths == [str(workspace)]


async def test_editor_open_tool_opens_workspace_root_and_focuses_source(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tool = workspace / "tools" / "my_tool.py"
    tool.parent.mkdir()
    tool.write_text("class MyTool: pass", encoding="utf-8")
    registry = ToolRegistryService()
    registry.register_tool(
        "MyTool",
        ToolMetadata(
            name="MyTool",
            display_name="My Tool",
            package="__custom__",
            package_version="local",
            tool_type="ProcessingTool",
            source_kind="custom",
            editable=True,
        ),
    )
    registry.register_custom_tool_file(tool, "MyTool")
    editor = _EditorStub()
    config = AppConfig(tool_registry=registry, workflow_root=workspace, editor_service=editor)
    async for client in _client(config):
        response = await client.post(
            "/api/v1/editor/open-tool",
            json={"tool_name": "MyTool"},
        )

    assert response.status_code == 200
    assert response.json()["path"] == str(tool)
    assert editor.paths == [str(workspace)]


async def test_editor_open_package_tool_opens_source_parent(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tool_store = tmp_path / "tool_store"
    package_root = tool_store / "package" / "1.0"
    package_root.mkdir(parents=True)
    tool = package_root / "package_tool.py"
    tool.write_text("class PackageTool: pass", encoding="utf-8")
    registry = ToolRegistryService()
    registry.scan_tool_store(tool_store)
    registry.register_tool(
        "PackageTool",
        ToolMetadata(
            name="PackageTool",
            display_name="Package Tool",
            package="package",
            package_version="1.0",
            tool_type="ProcessingTool",
            source_kind="package",
            editable=False,
        ),
    )
    registry._sources["PackageTool"] = tool
    editor = _EditorStub()
    config = AppConfig(tool_registry=registry, workflow_root=workspace, editor_service=editor)
    async for client in _client(config):
        response = await client.post(
            "/api/v1/editor/open-tool",
            json={"tool_name": "PackageTool"},
        )

    assert response.status_code == 200
    assert response.json()["path"] == str(tool)
    assert editor.paths == [str(package_root)]
