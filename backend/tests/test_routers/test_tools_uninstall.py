"""Regression tests for ``DELETE /api/v1/tools/packages/{name}``.

These tests pin the spec-v1 §2.4 contract — ``?version=X`` as a query
parameter — so that a future "fix" does not accidentally reintroduce the
regression where the frontend sent ``version`` in the request body, FastAPI
silently dropped it, and ``version=None`` reached
``PypiPackageInstaller.uninstall``, wiping every installed version.
"""
# pyright: reportPossiblyUnboundVariable=false
# Rationale: the ``async for client in _client(...):`` helper is a single-yield
# generator; ``resp`` is bound at the assertions.

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services import package_installer as installer_module
from bioimageflow_server.services.package_catalog import PackageCatalogService
from bioimageflow_server.services.package_installer import (
    PackageInstallerService,
    PypiPackageInstaller,
)
from bioimageflow_server.services.pypi_versions import PyPIVersionService
from bioimageflow_server.services.tool_registry import ToolRegistryService

pytestmark = pytest.mark.anyio


async def _client(config: AppConfig) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(config=config)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.parametrize("mode", ["desktop", "webapp"])
async def test_real_uninstall_refuses_unowned_query_then_removes_exact_version(
    mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    root = tmp_path / "tool_store"
    for version in ["1.0", "1.0.0"]:
        selected = root / "foo" / version
        selected.mkdir(parents=True)
        (selected / "sentinel").write_bytes(version.encode())
    outside = tmp_path / "unrelated"
    outside.mkdir()
    (outside / "sentinel").write_bytes(b"unrelated")
    monkeypatch.setenv("BIOIMAGEFLOW_TOOL_STORE", str(root))
    removed: list[Path] = []
    trash = tmp_path / "trash"
    trash.mkdir()

    def temporary_trash(target: str):
        path = Path(target)
        removed.append(path)
        path.rename(trash / path.name)

    monkeypatch.setattr(installer_module, "send2trash", temporary_trash)
    registry = ToolRegistryService()
    forget = MagicMock(wraps=registry.forget_package)
    monkeypatch.setattr(registry, "forget_package", forget)
    pypi = AsyncMock(spec=PyPIVersionService)
    catalog = AsyncMock(spec=PackageCatalogService)
    installer = PypiPackageInstaller(root, registry, pypi)
    config = AppConfig(
        deployment_mode=mode,
        tool_registry=registry,
        package_installer=installer,
        pypi_versions=pypi,
        package_catalog=catalog,
        workspace_path=tmp_path / "workspace",
        workspaces_root=tmp_path / "workspaces",
        workflow_root=tmp_path / "workspace" / "workflows",
        storage_path=tmp_path / "runtime",
        datasets_root=tmp_path / "datasets",
        disable_hot_reload=True,
    )
    async for client in _client(config):
        refused = await client.delete(
            "/api/v1/tools/packages/foo", params={"version": str(outside)},
        )
        assert refused.status_code == 400
        assert refused.json()["error"] == "bad_request"
        assert "safe stored names" in refused.json()["detail"]
        assert removed == []
        forget.assert_not_called()
        catalog.refresh.assert_not_awaited()
        assert (outside / "sentinel").read_bytes() == b"unrelated"
        assert (root / "foo" / "1.0" / "sentinel").read_bytes() == b"1.0"

        accepted = await client.delete(
            "/api/v1/tools/packages/foo", params={"version": "1.0"},
        )
        assert accepted.status_code == 200
        assert accepted.json() == {"status": "uninstalled"}
        assert removed == [root / "foo" / "1.0"]
        assert not (root / "foo" / "1.0").exists()
        assert (root / "foo" / "1.0.0" / "sentinel").read_bytes() == b"1.0.0"
        assert (outside / "sentinel").read_bytes() == b"unrelated"
        forget.assert_called_once_with("foo", "1.0")
        catalog.refresh.assert_awaited_once()


async def test_delete_without_version_removes_all_versions():
    """No query string, no body → installer receives ``version=None`` (spec v1 §2.4)."""
    installer = AsyncMock(spec=PackageInstallerService)
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        package_installer=installer,
    )
    async for client in _client(config):
        resp = await client.delete("/api/v1/tools/packages/cellpose")
    assert resp.status_code == 200
    installer.uninstall.assert_awaited_once_with("cellpose", version=None)


async def test_delete_with_version_query_removes_only_that_version():
    """``?version=0.1.0`` reaches the installer as ``version='0.1.0'``."""
    installer = AsyncMock(spec=PackageInstallerService)
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        package_installer=installer,
    )
    async for client in _client(config):
        resp = await client.delete("/api/v1/tools/packages/cellpose?version=0.1.0")
    assert resp.status_code == 200
    installer.uninstall.assert_awaited_once_with("cellpose", version="0.1.0")


async def test_delete_with_version_in_body_is_ignored():
    """Body is silently dropped; installer receives ``version=None``.

    This is the exact failure mode the user hit — the buggy frontend sent
    ``{data: {version}}`` instead of ``{params: {version}}``, and the
    backend removed the entire package directory.
    """
    installer = AsyncMock(spec=PackageInstallerService)
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        package_installer=installer,
    )
    async for client in _client(config):
        resp = await client.request(
            "DELETE",
            "/api/v1/tools/packages/cellpose",
            json={"version": "0.1.0"},
        )
    assert resp.status_code == 200
    installer.uninstall.assert_awaited_once_with("cellpose", version=None)
