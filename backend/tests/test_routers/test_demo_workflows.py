"""Bundled demo workflow API tests."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncIterator
from unittest.mock import AsyncMock

import httpx
import pytest

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.package_installer import PackageInstallerService, PackageNetworkError
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
    installer: PackageInstallerService | None = None,
    catalog: object | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    registry = ToolRegistryService()
    store = WorkflowStoreService(
        tmp_path / "workflows",
        registry,
    )
    app = create_app(
        AppConfig(
            tool_registry=registry,
            workflow_store=store,
            execution_manager=_ExecutionManager(is_running),
            connection_manager=connection_manager,  # type: ignore[arg-type]
            disable_hot_reload=True,
            package_installer=installer or AsyncMock(spec=PackageInstallerService),
            package_catalog=catalog,  # type: ignore[arg-type]
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
    installer = AsyncMock(spec=PackageInstallerService)
    async for client in _client(tmp_path, is_running=True, installer=installer):
        response = await client.post("/api/v1/demo-workflows/install")

    assert response.status_code == 423
    installer.install.assert_not_awaited()


async def test_startup_seeds_only_a_missing_workflow_root(tmp_path: Path) -> None:
    new_root = tmp_path / "new" / "workflows"
    installer = AsyncMock(spec=PackageInstallerService)

    async def install(_package: str, *, version: str) -> None:
        assert version
        assert not (new_root / "Demo").exists()

    installer.install.side_effect = install
    app = create_app(
        AppConfig(
            tool_registry=ToolRegistryService(),
            workflow_root=new_root,
            storage_path=tmp_path / "new-outputs",
            disable_hot_reload=True,
            package_installer=installer,
        )
    )
    async with app.router.lifespan_context(app):
        pass
    assert (new_root / "Demo" / "Fish Analysis" / "workflow.json").exists()
    assert [(call.args[0], call.kwargs["version"]) for call in installer.install.await_args_list] == [
        ("bioimageflow_common_tools", "0.2.2"),
        ("bioimageflow_io_tools", "0.2.2"),
        ("bioimageflow_segmentation_tools", "0.3.2"),
        ("bioimageflow_spot_tools", "0.2.2"),
    ]

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


async def test_failed_install_is_actionable_and_does_not_publish_demos(tmp_path: Path) -> None:
    installer = AsyncMock(spec=PackageInstallerService)
    installer.install.side_effect = PackageNetworkError("offline, retry later")
    catalog = AsyncMock()
    catalog.refresh.side_effect = RuntimeError("catalog unavailable too")
    async for client in _client(tmp_path, installer=installer, catalog=catalog):
        response = await client.post("/api/v1/demo-workflows/install")
        status = await client.get("/api/v1/demo-workflows")
    assert response.status_code == 502
    assert "offline, retry later" in response.json()["detail"]
    assert status.json()["status"] == "missing"
    catalog.refresh.assert_awaited_once()


async def test_automatic_offline_failure_starts_app_and_allows_explicit_retry(tmp_path: Path) -> None:
    root = tmp_path / "new" / "workflows"
    installer = AsyncMock(spec=PackageInstallerService)
    installer.install.side_effect = PackageNetworkError("offline")
    config = AppConfig(
        workflow_root=root,
        tool_registry=ToolRegistryService(),
        package_installer=installer,
        disable_hot_reload=True,
    )
    app = create_app(config)
    async with app.router.lifespan_context(app):
        assert root.is_dir()
        assert not (root / "Demo").exists()
    installer.install.reset_mock()
    restarted = create_app(config)
    async with restarted.router.lifespan_context(restarted):
        installer.install.assert_not_awaited()
        installer.install.side_effect = None
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted), base_url="http://test") as client:
            response = await client.post("/api/v1/demo-workflows/install")
    assert response.status_code == 200
    assert response.json()["status"] == "installed"
    assert installer.install.await_count == 4


async def test_new_switched_workspace_waits_for_packages_including_concurrent_reads(tmp_path: Path) -> None:
    original = tmp_path / "original"
    (original / "workflows").mkdir(parents=True)
    switched = tmp_path / "switched"
    entered = asyncio.Event()
    finish = asyncio.Event()
    installer = AsyncMock(spec=PackageInstallerService)

    async def install(_package: str, *, version: str) -> None:
        assert version
        entered.set()
        assert not (switched / "workflows" / "Demo").exists()
        await finish.wait()

    installer.install.side_effect = install
    app = create_app(AppConfig(
        workspace_path=original,
        tool_registry=ToolRegistryService(),
        package_installer=installer,
        disable_hot_reload=True,
    ))
    async with app.router.lifespan_context(app):
        installer.install.assert_not_awaited()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch("/api/v1/workspace", json={"workspace_path": str(switched)})
            assert response.status_code == 200
            first = asyncio.create_task(client.get("/api/v1/demo-workflows"))
            await asyncio.wait_for(entered.wait(), 5)
            second = asyncio.create_task(client.get("/api/v1/demo-workflows"))
            try:
                await asyncio.sleep(0.05)
                assert not first.done()
                assert not second.done()
                assert not (switched / "workflows" / "Demo").exists()
            finally:
                finish.set()
            results = await asyncio.wait_for(asyncio.gather(first, second), 5)
    assert all(response.json()["status"] == "installed" for response in results)
    assert installer.install.await_count == 4
    assert not (original / "workflows" / "Demo").exists()


@pytest.mark.parametrize("method", ["get", "post"])
async def test_switched_workspace_recovery_failure_keeps_typed_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str,
) -> None:
    from bioimageflow_server.services.workflow_store import WorkflowMoveRecoveryError

    original = tmp_path / "original"
    (original / "workflows").mkdir(parents=True)
    app = create_app(AppConfig(workspace_path=original, disable_hot_reload=True))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        switched = await client.patch("/api/v1/workspace", json={"workspace_path": str(tmp_path / "switched")})
        assert switched.status_code == 200

        def fail_recovery(_self: WorkflowStoreService) -> None:
            raise WorkflowMoveRecoveryError("Retained move needs repair")

        monkeypatch.setattr(WorkflowStoreService, "recover_workflow_format_migration", fail_recovery)
        response = await client.request(method, "/api/v1/demo-workflows")
    assert response.status_code == 503
    assert response.json()["error"] == "workflow_move_recovery_required"
