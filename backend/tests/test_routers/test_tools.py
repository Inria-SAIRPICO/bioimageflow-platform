"""Tests for the tools router (Tasks 4-9)."""
# pyright: reportPossiblyUnboundVariable=false, reportArgumentType=false
# Rationale: ``async for client in _client(config):`` always yields once (the
# helper is a single-yield async generator), so ``resp`` is bound at the
# assertions — pyright can't prove that statically. Fake service stand-ins
# (``_FakeCatalog``, ``_BrokenCatalog``) deliberately bypass the concrete
# service class; tests only exercise the protocol surface.

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
from bioimageflow_server.models.graph import GraphState, NodeState
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowSaveBody
from bioimageflow_server.services.package_installer import (
    PackageInstallerService,
    PackageNetworkError,
    PackageNotFoundError,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService

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
        inputs={
            "diameter": InputFieldSchema(
                type="float",
                required=True,
                connectable="not_by_default",
                min=0.0,
            )
        },
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
async def populated_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    reg = ToolRegistryService()
    reg.register_tool("Cellpose", _make_tool("Cellpose"))
    reg.register_package("cellpose", _make_package("cellpose"))
    config = AppConfig(tool_registry=reg, workflow_root=tmp_path / "workflow")
    async for c in _client(config):
        yield c


@pytest.fixture
async def empty_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        workflow_root=tmp_path / "workflow",
    )
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


async def test_get_tools_returns_new_metadata_fields(populated_client: httpx.AsyncClient):
    """GET /tools must surface accepts_upstream and dynamic_outputs."""
    resp = await populated_client.get("/api/v1/tools")
    assert resp.status_code == 200
    tool = resp.json()[0]
    assert "accepts_upstream" in tool
    assert "dynamic_outputs" in tool
    assert tool["accepts_upstream"] is True
    assert tool["dynamic_outputs"] is False


async def test_get_tools_empty(empty_client: httpx.AsyncClient):
    resp = await empty_client.get("/api/v1/tools")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_tools_discovers_existing_custom_tools(workflow_root: Path):
    registry = ToolRegistryService()
    custom_root = workflow_root / "tools"
    custom_root.mkdir(parents=True)
    from bioimageflow_server.services.custom_tools import CustomToolService

    source = CustomToolService(workflow_root, registry).render_template(
        "ExistingTool",
        "ProcessingTool",
    )
    (custom_root / "existing_tool.py").write_text(source, encoding="utf-8")
    config = AppConfig(
        tool_registry=registry,
        workflow_root=workflow_root,
        disable_hot_reload=True,
    )
    async for client in _client(config):
        resp = await client.get("/api/v1/tools")
    assert resp.status_code == 200
    tool = next(t for t in resp.json() if t["name"] == "ExistingTool")
    assert tool["source_kind"] == "custom"
    assert tool["editable"] is True


async def test_get_tools_surfaces_nullable_per_field():
    """`nullable` is propagated through the API for each input field."""
    reg = ToolRegistryService()
    reg.register_tool(
        "Mixed",
        ToolMetadata(
            name="Mixed",
            display_name="Mixed",
            package="pkg",
            package_version="1.0",
            tool_type="ProcessingTool",
            inputs={
                "size": InputFieldSchema(
                    type="int",
                    required=True,
                    connectable="not_by_default",
                ),
                "area_lim": InputFieldSchema(
                    type="float",
                    required=False,
                    nullable=True,
                    connectable="not_by_default",
                    default=None,
                ),
            },
            outputs={"out": OutputFieldSchema(type="image")},
        ),
    )
    config = AppConfig(tool_registry=reg)
    async for client in _client(config):
        resp = await client.get("/api/v1/tools")
        assert resp.status_code == 200
        tool = resp.json()[0]
        assert tool["inputs"]["size"]["nullable"] is False
        assert tool["inputs"]["area_lim"]["nullable"] is True
        break


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
    registry = ToolRegistryService()
    config = AppConfig(
        tool_registry=registry,
        workflow_root=workflow_root,
    )
    async for client in _client(config):
        resp = await client.post(
            "/api/v1/tools",
            json={"name": "MySegmenter", "tool_type": "ProcessingTool"},
        )
        tools = await client.get("/api/v1/tools")
    assert resp.status_code == 201
    generated = workflow_root / "tools" / "my_segmenter.py"
    assert generated.exists()
    content = generated.read_text()
    assert "class MySegmenter" in content
    assert "process_row" in content
    body = resp.json()
    assert body["name"] == "MySegmenter"
    assert body["source_kind"] == "custom"
    assert body["editable"] is True

    assert tools.status_code == 200
    created = next(t for t in tools.json() if t["name"] == "MySegmenter")
    assert created["source_kind"] == "custom"
    assert created["editable"] is True


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


async def test_create_tool_webapp_allowed_by_unsafe_debug_flag(workflow_root: Path):
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        workflow_root=workflow_root,
        deployment_mode="webapp",
        settings=Settings(
            deployment_mode="webapp",
            enable_unsafe_webapp_features=True,
        ),
    )
    async for client in _client(config):
        resp = await client.post(
            "/api/v1/tools",
            json={"name": "Foo", "tool_type": "ProcessingTool"},
        )
    assert resp.status_code == 201
    assert (workflow_root / "tools" / "foo.py").exists()


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


async def test_create_tool_rejects_registry_conflict(workflow_root: Path):
    registry = ToolRegistryService()
    registry.register_tool("Cellpose", _make_tool("Cellpose"))
    config = AppConfig(tool_registry=registry, workflow_root=workflow_root)
    async for client in _client(config):
        resp = await client.post(
            "/api/v1/tools",
            json={"name": "Cellpose", "tool_type": "ProcessingTool"},
        )
    assert resp.status_code == 409


async def test_create_tool_invalid_name_returns_422(workflow_root: Path):
    config = AppConfig(tool_registry=ToolRegistryService(), workflow_root=workflow_root)
    async for client in _client(config):
        resp = await client.post(
            "/api/v1/tools",
            json={"name": "../BadTool", "tool_type": "ProcessingTool"},
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Task 7: DELETE /tools/{tool_name} and PATCH /tools/{tool_name}
# ---------------------------------------------------------------------------


async def test_delete_tool_success(workflow_root: Path):
    registry = ToolRegistryService()
    config = AppConfig(
        tool_registry=registry,
        workflow_root=workflow_root,
    )
    async for client in _client(config):
        await client.post(
            "/api/v1/tools",
            json={"name": "Trash", "tool_type": "ProcessingTool"},
        )
        resp = await client.delete("/api/v1/tools/Trash")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    assert resp.json()["affected_workflows"] == []
    assert not (workflow_root / "tools" / "trash.py").exists()
    assert registry.get_tool("Trash") is None


async def test_delete_tool_not_found(workflow_root: Path):
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        workflow_root=workflow_root,
    )
    async for client in _client(config):
        resp = await client.delete("/api/v1/tools/Ghost")
    assert resp.status_code == 404


async def test_delete_package_tool_forbidden(workflow_root: Path):
    registry = ToolRegistryService()
    registry.register_tool("Cellpose", _make_tool("Cellpose"))
    config = AppConfig(tool_registry=registry, workflow_root=workflow_root)
    async for client in _client(config):
        resp = await client.delete("/api/v1/tools/Cellpose")
    assert resp.status_code == 400


async def test_rename_tool_success(workflow_root: Path):
    registry = ToolRegistryService()
    config = AppConfig(
        tool_registry=registry,
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
    body = resp.json()
    assert body["old_name"] == "OldName"
    assert body["new_name"] == "NewName"
    assert not (workflow_root / "tools" / "old_name.py").exists()
    renamed = workflow_root / "tools" / "new_name.py"
    assert renamed.exists()
    assert "class NewName(" in renamed.read_text()
    assert registry.get_tool("OldName") is None
    assert registry.get_tool("NewName") is not None


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


async def test_rename_tool_target_conflict(workflow_root: Path):
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        workflow_root=workflow_root,
    )
    async for client in _client(config):
        await client.post(
            "/api/v1/tools",
            json={"name": "OldName", "tool_type": "ProcessingTool"},
        )
        await client.post(
            "/api/v1/tools",
            json={"name": "NewName", "tool_type": "ProcessingTool"},
        )
        resp = await client.patch(
            "/api/v1/tools/OldName",
            json={"new_name": "NewName"},
        )
    assert resp.status_code == 409


async def test_tool_usage_reports_saved_workflows(workflow_root: Path):
    registry = ToolRegistryService()
    registry.register_tool("MyTool", _make_tool("MyTool"))
    store = WorkflowStoreService(workflow_root, registry)
    store.create_workflow(WorkflowCreate(name="uses_tool"))
    store.save_workflow(
        "uses_tool",
        WorkflowSaveBody(
            graph=GraphState(
                nodes=[
                    NodeState(
                        id="n1",
                        name="n1",
                        tool_name="MyTool",
                        position=(0, 0),
                        parameters={},
                    )
                ],
                edges=[],
            )
        ),
    )
    store.create_workflow(WorkflowCreate(name="other"))
    config = AppConfig(
        tool_registry=registry,
        workflow_root=workflow_root,
        workflow_store=store,
    )
    async for client in _client(config):
        resp = await client.get("/api/v1/tools/MyTool/usage")
    assert resp.status_code == 200
    assert resp.json() == {
        "tool_name": "MyTool",
        "affected_workflows": ["uses_tool"],
        "in_open_workflow": None,
    }


async def test_delete_reports_saved_workflow_usage(workflow_root: Path):
    registry = ToolRegistryService()
    service_store = WorkflowStoreService(workflow_root, registry)
    config = AppConfig(
        tool_registry=registry,
        workflow_root=workflow_root,
        workflow_store=service_store,
    )
    async for client in _client(config):
        await client.post(
            "/api/v1/tools",
            json={"name": "UsedTool", "tool_type": "ProcessingTool"},
        )
        service_store.create_workflow(WorkflowCreate(name="uses_tool"))
        service_store.save_workflow(
            "uses_tool",
            WorkflowSaveBody(
                graph=GraphState(
                    nodes=[
                        NodeState(
                            id="n1",
                            name="n1",
                            tool_name="UsedTool",
                            position=(0, 0),
                            parameters={},
                        )
                    ],
                    edges=[],
                )
            ),
        )
        resp = await client.delete("/api/v1/tools/UsedTool")
    assert resp.status_code == 200
    assert resp.json()["affected_workflows"] == ["uses_tool"]
    assert "saved workflow" in resp.json()["warning"]


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


class _FakeToolEnvironmentService:
    def __init__(self) -> None:
        self.started: list[str] = []
        self.stopped: list[str] = []

    async def start(self, env_name: str) -> str:
        self.started.append(env_name)
        return "running"

    async def stop(self, env_name: str) -> str:
        self.stopped.append(env_name)
        return "stopped"


async def test_start_environment_delegates_to_environment_service():
    envs = _FakeToolEnvironmentService()
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        tool_environment_service=envs,
    )
    async for client in _client(config):
        resp = await client.post("/api/v1/tools/environments/myenv/start")
    assert resp.status_code == 200
    assert resp.json() == {"environment": "myenv", "status": "running"}
    assert envs.started == ["myenv"]


async def test_stop_environment_delegates_to_environment_service():
    envs = _FakeToolEnvironmentService()
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        tool_environment_service=envs,
    )
    async for client in _client(config):
        resp = await client.post("/api/v1/tools/environments/myenv/stop")
    assert resp.status_code == 200
    assert resp.json() == {"environment": "myenv", "status": "stopped"}
    assert envs.stopped == ["myenv"]


async def test_start_environment_for_tool_without_environment_returns_stopped():
    registry = ToolRegistryService()
    registry.register_tool("NoEnvTool", _make_tool("NoEnvTool"))
    registry.register_package("pkg", _make_package("pkg"))
    config = AppConfig(tool_registry=registry)

    async for client in _client(config):
        resp = await client.post("/api/v1/tools/environments/NoEnvTool/start")

    assert resp.status_code == 200
    assert resp.json() == {"environment": "NoEnvTool", "status": "stopped"}
    assert registry.get_package("pkg").environment_status == "stopped"


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
    assert resp.json()["source_kind"] == "custom"
    assert resp.json()["editable"] is True


async def test_get_source_for_package_tool_returns_real_path():
    class LocalTool:
        pass

    reg = ToolRegistryService()
    reg.register_tool("LocalTool", _make_tool("LocalTool"), tool_class=LocalTool)
    config = AppConfig(tool_registry=reg)
    async for client in _client(config):
        resp = await client.get("/api/v1/tools/LocalTool/source")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tool_name"] == "LocalTool"
    assert data["source_kind"] == "package"
    assert data["editable"] is False
    assert Path(data["path"]).exists()
    assert not data["path"].startswith("<package:")


async def test_get_source_prefers_workflow_custom_file(workflow_root: Path):
    class MyTool:
        pass

    tools_dir = workflow_root / "tools"
    tools_dir.mkdir(parents=True)
    custom_path = tools_dir / "my_tool.py"
    custom_path.write_text("class MyTool: pass")

    reg = ToolRegistryService()
    reg.register_tool("MyTool", _make_tool("MyTool"), tool_class=MyTool)
    config = AppConfig(tool_registry=reg, workflow_root=workflow_root)
    async for client in _client(config):
        resp = await client.get("/api/v1/tools/MyTool/source")

    assert resp.status_code == 200
    assert resp.json()["path"] == str(custom_path)
    assert resp.json()["source_kind"] == "custom"
    assert resp.json()["editable"] is True


async def test_get_source_returns_absolute_custom_path_for_relative_workflow_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        workflow_root=Path("workflow"),
        disable_hot_reload=True,
    )
    async for client in _client(config):
        create_resp = await client.post(
            "/api/v1/tools",
            json={"name": "MyTool", "tool_type": "ProcessingTool"},
        )
        resp = await client.get("/api/v1/tools/MyTool/source")

    assert create_resp.status_code == 201
    assert resp.status_code == 200
    path = Path(resp.json()["path"])
    assert path.is_absolute()
    assert path == tmp_path / "workflow" / "tools" / "my_tool.py"


async def test_get_source_for_package_tool_without_resolvable_source_404():
    reg = ToolRegistryService()
    reg.register_tool("GhostPackageTool", _make_tool("GhostPackageTool"))
    config = AppConfig(tool_registry=reg)
    async for client in _client(config):
        resp = await client.get("/api/v1/tools/GhostPackageTool/source")
    assert resp.status_code == 404
    assert "could not be resolved" in resp.json()["detail"]


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
