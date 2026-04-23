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
from unittest.mock import AsyncMock

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.package_installer import PackageInstallerService
from bioimageflow_server.services.tool_registry import ToolRegistryService

pytestmark = pytest.mark.anyio


async def _client(config: AppConfig) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(config=config)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


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
