"""Bundled demo workflow API tests."""

from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

import httpx
import pytest

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService


pytestmark = pytest.mark.anyio


class _ExecutionManager:
    def __init__(self, is_running: bool = False) -> None:
        self.is_running = is_running


class _ConnectionManager:
    def __init__(self) -> None:
        self.actions: list[str] = []

    def publish_workflow_tree_changed(self, *, action: str, **_kwargs: object) -> None:
        self.actions.append(action)


async def _client(
    tmp_path: Path,
    *,
    is_running: bool = False,
    connection_manager: _ConnectionManager | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    registry = ToolRegistryService()
    store = WorkflowStoreService(
        tmp_path / "workflows",
        registry,
        storage_base_dir=tmp_path / "outputs",
    )
    app = create_app(
        AppConfig(
            tool_registry=registry,
            workflow_store=store,
            execution_manager=_ExecutionManager(is_running),
            connection_manager=connection_manager,  # type: ignore[arg-type]
            disable_hot_reload=True,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


async def test_status_and_install_endpoints(tmp_path: Path) -> None:
    manager = _ConnectionManager()
    async for client in _client(tmp_path, connection_manager=manager):
        missing = await client.get("/api/v1/demo-workflows")
        installed = await client.post("/api/v1/demo-workflows/install")

    assert missing.status_code == 200
    assert missing.json()["status"] == "missing"
    assert installed.status_code == 200
    assert installed.json()["status"] == "installed"
    assert manager.actions == ["demos_installed"]


async def test_install_is_locked_during_execution(tmp_path: Path) -> None:
    async for client in _client(tmp_path, is_running=True):
        response = await client.post("/api/v1/demo-workflows/install")

    assert response.status_code == 423


async def test_startup_seeds_only_a_missing_workflow_root(tmp_path: Path) -> None:
    new_root = tmp_path / "new" / "workflows"
    app = create_app(
        AppConfig(
            tool_registry=ToolRegistryService(),
            workflow_root=new_root,
            storage_path=tmp_path / "new-outputs",
            disable_hot_reload=True,
        )
    )
    async with app.router.lifespan_context(app):
        pass
    assert (new_root / "Demo" / "Fish Analysis" / "workflow.json").exists()

    existing_root = tmp_path / "existing" / "workflows"
    existing_root.mkdir(parents=True)
    existing_app = create_app(
        AppConfig(
            tool_registry=ToolRegistryService(),
            workflow_root=existing_root,
            storage_path=tmp_path / "existing-outputs",
            disable_hot_reload=True,
        )
    )
    async with existing_app.router.lifespan_context(existing_app):
        pass
    assert not (existing_root / "Demo").exists()
