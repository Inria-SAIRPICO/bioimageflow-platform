"""Tests for the tools router (Tasks 4-9)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import (
    AppConfig,
    InputFieldSchema,
    OutputFieldSchema,
    PackageInfo,
    ToolMetadata,
)
from bioimageflow_server.services.known_packages import KnownPackagesService
from bioimageflow_server.services.package_catalog import PackageCatalogService
from bioimageflow_server.services.package_installer import (
    PackageInstallerService,
    PackageNetworkError,
    PackageNotFoundError,
)
from bioimageflow_server.services.pypi_versions import PyPIVersionService
from bioimageflow_server.services.tool_registry import ToolRegistryService

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool(name: str = "Cellpose") -> ToolMetadata:
    return ToolMetadata(
        name=name,
        display_name=name,
        package="pkg",
        package_version="1.0",
        tool_type="ProcessingTool",
        inputs={"diameter": InputFieldSchema(type="float", min=0.0)},
        outputs={"masks": OutputFieldSchema(type="image")},
    )


def _make_package(name: str = "cellpose") -> PackageInfo:
    return PackageInfo(name=name, installed_versions=["2.0"])


async def _client(config: AppConfig) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(config=config)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def populated_client() -> AsyncIterator[httpx.AsyncClient]:
    reg = ToolRegistryService()
    reg.register_tool("Cellpose", _make_tool("Cellpose"))
    reg.register_package("cellpose", _make_package("cellpose"))
    config = AppConfig(tool_registry=reg)
    async for c in _client(config):
        yield c


@pytest.fixture
async def empty_client() -> AsyncIterator[httpx.AsyncClient]:
    config = AppConfig(tool_registry=ToolRegistryService())
    async for c in _client(config):
        yield c


# ---------------------------------------------------------------------------
# Task 4: GET /tools
# ---------------------------------------------------------------------------


async def test_get_tools_populated(populated_client: httpx.AsyncClient):
    resp = await populated_client.get("/api/v1/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Cellpose"


async def test_get_tools_empty(empty_client: httpx.AsyncClient):
    resp = await empty_client.get("/api/v1/tools")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Task 5: GET /tools/packages
# ---------------------------------------------------------------------------


async def test_get_packages_populated(populated_client: httpx.AsyncClient):
    resp = await populated_client.get("/api/v1/tools/packages")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "cellpose"


async def test_get_packages_empty(empty_client: httpx.AsyncClient):
    resp = await empty_client.get("/api/v1/tools/packages")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Task 6: POST /tools (create tool from template)
# ---------------------------------------------------------------------------


@pytest.fixture
def workflow_root(tmp_path: Path) -> Path:
    return tmp_path / "workflow"


async def test_create_processing_tool(workflow_root: Path):
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        workflow_root=workflow_root,
    )
    async for client in _client(config):
        resp = await client.post(
            "/api/v1/tools",
            json={"name": "MySegmenter", "tool_type": "ProcessingTool"},
        )
    assert resp.status_code == 201
    generated = workflow_root / "tools" / "my_segmenter.py"
    assert generated.exists()
    content = generated.read_text()
    assert "class MySegmenter" in content
    assert "process_row" in content


async def test_create_dataframe_tool(workflow_root: Path):
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        workflow_root=workflow_root,
    )
    async for client in _client(config):
        resp = await client.post(
            "/api/v1/tools",
            json={"name": "StatsTool", "tool_type": "DataFrameTool"},
        )
    assert resp.status_code == 201
    generated = workflow_root / "tools" / "stats_tool.py"
    assert generated.exists()
    content = generated.read_text()
    assert "class StatsTool" in content
    assert "transform" in content


async def test_create_tool_webapp_forbidden(workflow_root: Path):
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        workflow_root=workflow_root,
        deployment_mode="webapp",
    )
    async for client in _client(config):
        resp = await client.post(
            "/api/v1/tools",
            json={"name": "Foo", "tool_type": "ProcessingTool"},
        )
    assert resp.status_code == 403


async def test_create_tool_duplicate(workflow_root: Path):
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        workflow_root=workflow_root,
    )
    async for client in _client(config):
        await client.post(
            "/api/v1/tools",
            json={"name": "Dup", "tool_type": "ProcessingTool"},
        )
        resp = await client.post(
            "/api/v1/tools",
            json={"name": "Dup", "tool_type": "ProcessingTool"},
        )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Task 7: DELETE /tools/{tool_name} and PATCH /tools/{tool_name}
# ---------------------------------------------------------------------------


async def test_delete_tool_success(workflow_root: Path):
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        workflow_root=workflow_root,
    )
    async for client in _client(config):
        await client.post(
            "/api/v1/tools",
            json={"name": "Trash", "tool_type": "ProcessingTool"},
        )
        resp = await client.delete("/api/v1/tools/Trash")
    assert resp.status_code == 200
    assert not (workflow_root / "tools" / "trash.py").exists()


async def test_delete_tool_not_found(workflow_root: Path):
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        workflow_root=workflow_root,
    )
    async for client in _client(config):
        resp = await client.delete("/api/v1/tools/Ghost")
    assert resp.status_code == 404


async def test_rename_tool_success(workflow_root: Path):
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        workflow_root=workflow_root,
    )
    async for client in _client(config):
        await client.post(
            "/api/v1/tools",
            json={"name": "OldName", "tool_type": "ProcessingTool"},
        )
        resp = await client.patch(
            "/api/v1/tools/OldName",
            json={"new_name": "NewName"},
        )
    assert resp.status_code == 200
    assert not (workflow_root / "tools" / "old_name.py").exists()
    assert (workflow_root / "tools" / "new_name.py").exists()


async def test_rename_tool_not_found(workflow_root: Path):
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        workflow_root=workflow_root,
    )
    async for client in _client(config):
        resp = await client.patch(
            "/api/v1/tools/Ghost",
            json={"new_name": "Whatever"},
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Task 8: Package install/uninstall
# ---------------------------------------------------------------------------


async def test_install_package_success():
    installer = AsyncMock(spec=PackageInstallerService)
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        package_installer=installer,
    )
    async for client in _client(config):
        resp = await client.post("/api/v1/tools/packages/cellpose/install")
    assert resp.status_code == 200
    installer.install.assert_awaited_once_with("cellpose", version=None)


async def test_install_package_not_found():
    installer = AsyncMock(spec=PackageInstallerService)
    installer.install.side_effect = PackageNotFoundError("nope")
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        package_installer=installer,
    )
    async for client in _client(config):
        resp = await client.post("/api/v1/tools/packages/nope/install")
    assert resp.status_code == 404


async def test_install_package_network_error():
    installer = AsyncMock(spec=PackageInstallerService)
    installer.install.side_effect = PackageNetworkError("timeout")
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        package_installer=installer,
    )
    async for client in _client(config):
        resp = await client.post("/api/v1/tools/packages/cellpose/install")
    assert resp.status_code == 502


async def test_uninstall_package_success():
    installer = AsyncMock(spec=PackageInstallerService)
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        package_installer=installer,
    )
    async for client in _client(config):
        resp = await client.delete("/api/v1/tools/packages/cellpose")
    assert resp.status_code == 200
    installer.uninstall.assert_awaited_once_with("cellpose", version=None)


async def test_uninstall_package_not_found():
    installer = AsyncMock(spec=PackageInstallerService)
    installer.uninstall.side_effect = PackageNotFoundError("nope")
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        package_installer=installer,
    )
    async for client in _client(config):
        resp = await client.delete("/api/v1/tools/packages/nope")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Task 9: Environment start/stop + GET source
# ---------------------------------------------------------------------------


async def test_start_environment():
    config = AppConfig(tool_registry=ToolRegistryService())
    async for client in _client(config):
        resp = await client.post("/api/v1/tools/environments/myenv/start")
    assert resp.status_code == 200
    assert resp.json()["status"] == "creating"
    assert resp.json()["environment"] == "myenv"


async def test_stop_environment():
    config = AppConfig(tool_registry=ToolRegistryService())
    async for client in _client(config):
        resp = await client.post("/api/v1/tools/environments/myenv/stop")
    assert resp.status_code == 200
    assert resp.json()["status"] == "stopped"


async def test_get_source_success(workflow_root: Path):
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        workflow_root=workflow_root,
    )
    async for client in _client(config):
        # create the tool first
        await client.post(
            "/api/v1/tools",
            json={"name": "MyTool", "tool_type": "ProcessingTool"},
        )
        resp = await client.get("/api/v1/tools/MyTool/source")
    assert resp.status_code == 200
    assert "my_tool.py" in resp.json()["path"]


async def test_get_source_not_found(workflow_root: Path):
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        workflow_root=workflow_root,
    )
    async for client in _client(config):
        resp = await client.get("/api/v1/tools/Ghost/source")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /tools/packages/{package_name}/use
# ---------------------------------------------------------------------------


async def test_use_package_version_success(populated_client: httpx.AsyncClient):
    resp = await populated_client.post(
        "/api/v1/tools/packages/cellpose/use",
        json={"version": "2.0"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["package"] == "cellpose"
    assert data["version"] == "2.0"
    assert data["status"] == "active"


async def test_use_package_version_not_found(empty_client: httpx.AsyncClient):
    resp = await empty_client.post(
        "/api/v1/tools/packages/nonexistent/use",
        json={"version": "1.0"},
    )
    assert resp.status_code == 404


async def test_use_package_version_not_installed(populated_client: httpx.AsyncClient):
    resp = await populated_client.post(
        "/api/v1/tools/packages/cellpose/use",
        json={"version": "9.9.9"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Catalog-backed GET /packages + POST /packages/refresh (plan Task 6)
# ---------------------------------------------------------------------------


class _FakeCatalog:
    """Stand-in catalog that records refresh calls and returns a fixed snapshot."""

    def __init__(self, packages: list[PackageInfo]):
        self._packages = packages
        self.refresh_calls = 0

    async def refresh(self) -> None:
        self.refresh_calls += 1

    def list_packages(self) -> list[PackageInfo]:
        return list(self._packages)


async def test_get_packages_returns_catalog_snapshot():
    # A known-but-not-installed package is present in the catalog but not the registry.
    reg = ToolRegistryService()
    catalog_packages = [
        PackageInfo(
            name="bioimageflow_core",
            installed_versions=[],
            available_versions=["0.1.0", "0.1.1"],
        ),
    ]
    config = AppConfig(
        tool_registry=reg,
        package_catalog=_FakeCatalog(catalog_packages),
    )
    async for client in _client(config):
        resp = await client.get("/api/v1/tools/packages")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "bioimageflow_core"
    assert data[0]["installed_versions"] == []
    assert data[0]["available_versions"] == ["0.1.0", "0.1.1"]


async def test_refresh_endpoint_triggers_catalog_refresh():
    catalog = _FakeCatalog([])
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        package_catalog=catalog,
    )
    async for client in _client(config):
        resp = await client.post("/api/v1/tools/packages/refresh")
    assert resp.status_code == 200
    assert resp.json() == {"status": "refreshed"}
    assert catalog.refresh_calls == 1


async def test_install_triggers_catalog_refresh():
    installer = AsyncMock(spec=PackageInstallerService)
    catalog = _FakeCatalog([])
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        package_installer=installer,
        package_catalog=catalog,
    )
    async for client in _client(config):
        resp = await client.post("/api/v1/tools/packages/bioimageflow_core/install")
    assert resp.status_code == 200
    installer.install.assert_awaited_once_with("bioimageflow_core", version=None)
    assert catalog.refresh_calls == 1


async def test_uninstall_triggers_catalog_refresh():
    installer = AsyncMock(spec=PackageInstallerService)
    catalog = _FakeCatalog([])
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        package_installer=installer,
        package_catalog=catalog,
    )
    async for client in _client(config):
        resp = await client.delete("/api/v1/tools/packages/bioimageflow_core")
    assert resp.status_code == 200
    installer.uninstall.assert_awaited_once_with("bioimageflow_core", version=None)
    assert catalog.refresh_calls == 1


async def test_refresh_endpoint_network_error_returns_502():
    class _BrokenCatalog(_FakeCatalog):
        async def refresh(self) -> None:
            raise PackageNetworkError("pypi unreachable")

    config = AppConfig(
        tool_registry=ToolRegistryService(),
        package_catalog=_BrokenCatalog([]),
    )
    async for client in _client(config):
        resp = await client.post("/api/v1/tools/packages/refresh")
    assert resp.status_code == 502
