"""Tests for the /settings router."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.settings_store import SettingsStore


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def settings_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    settings_path = tmp_path / "settings.json"
    store = SettingsStore(path=settings_path)
    config = AppConfig(settings_store=store, deployment_mode="desktop")
    app = create_app(config)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client


class TestGetSettings:
    async def test_get_returns_full_model(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        response = await settings_client.get("/api/v1/settings")
        assert response.status_code == 200
        body = response.json()
        # Wrapper contains the Settings fields plus the resolved-path helpers.
        assert body["deployment_mode"] == "desktop"
        assert body["execution_engine"] == "sequential"
        assert body["external_editor"] is None
        assert "resolved_tool_store_path" in body
        assert "resolved_output_data_folder" in body
        # Resolved paths should be absolute.
        assert body["resolved_tool_store_path"].startswith("/")
        assert body["resolved_output_data_folder"].startswith("/")


class TestPatchSettings:
    async def test_patch_updates_field(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        response = await settings_client.patch(
            "/api/v1/settings", json={"external_editor": "code {file_path}"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["external_editor"] == "code {file_path}"
        # GET reflects the change.
        getresp = await settings_client.get("/api/v1/settings")
        assert getresp.json()["external_editor"] == "code {file_path}"

    async def test_patch_invalid_value(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        response = await settings_client.patch(
            "/api/v1/settings", json={"execution_engine": "dask"}
        )
        assert response.status_code == 422

    async def test_patch_unknown_key(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        response = await settings_client.patch(
            "/api/v1/settings", json={"foo": 1}
        )
        assert response.status_code == 422

    async def test_patch_dev_mode_false_rejected(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        response = await settings_client.patch(
            "/api/v1/settings", json={"dev_mode": False}
        )
        assert response.status_code == 422
        body = response.json()
        # ErrorResponse shape from app.py.
        assert "dev_mode cannot be disabled" in body["detail"]

    async def test_patch_dev_mode_true_accepted(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        response = await settings_client.patch(
            "/api/v1/settings", json={"dev_mode": True}
        )
        assert response.status_code == 200

    async def test_patch_empty_body(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        response = await settings_client.patch("/api/v1/settings", json={})
        assert response.status_code == 200

    async def test_patch_clear_with_null(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        await settings_client.patch(
            "/api/v1/settings", json={"external_editor": "vim"}
        )
        response = await settings_client.patch(
            "/api/v1/settings", json={"external_editor": None}
        )
        assert response.status_code == 200
        assert response.json()["external_editor"] is None

    async def test_patch_negative_cache_max_executions(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        response = await settings_client.patch(
            "/api/v1/settings", json={"cache_max_executions": -1}
        )
        assert response.status_code == 422

    async def test_patch_zero_cache_max_executions_accepted(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        response = await settings_client.patch(
            "/api/v1/settings", json={"cache_max_executions": 0}
        )
        assert response.status_code == 200
        assert response.json()["cache_max_executions"] == 0


class TestDevModeAtModelLayer:
    """The model itself stays permissive — only the router rejects dev_mode=False."""

    def test_settings_dev_mode_false_constructible(self) -> None:
        from bioimageflow_server.models.settings import Settings

        s = Settings(deployment_mode="desktop", dev_mode=False)
        assert s.dev_mode is False
