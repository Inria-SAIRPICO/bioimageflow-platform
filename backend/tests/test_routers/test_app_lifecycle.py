"""Tests for SettingsStore wiring into the app lifespan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.routers.graph import get_dev_mode as graph_get_dev_mode
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedWorkflowSnapshotService,
)
from bioimageflow_server.services.settings_store import SettingsStore


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_lifespan_loads_pre_existing_settings(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "settings_version": 1,
                "deployment_mode": "desktop",
                "external_editor": "code",
            }
        )
    )
    store = SettingsStore(path=path)
    config = AppConfig(settings_store=store, disable_hot_reload=True)
    app = create_app(config)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings")
        assert resp.status_code == 200
        assert resp.json()["external_editor"] == "code"


async def test_lifespan_load_and_snapshot_cleanup_run_before_catalog_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path=path)
    order: list[str] = []

    real_load = store.load

    async def wrapped_load() -> Any:
        order.append("load")
        return await real_load()

    store.load = wrapped_load  # type: ignore[method-assign]

    def cleanup_snapshots(_service: NestedWorkflowSnapshotService) -> list[Any]:
        order.append("snapshot_cleanup")
        return []

    monkeypatch.setattr(
        NestedWorkflowSnapshotService,
        "cleanup_orphaned_snapshots",
        cleanup_snapshots,
    )

    class _RecordingCatalog:
        async def refresh(self) -> None:
            order.append("refresh")

        def list_packages(self):
            return []

    config = AppConfig(
        settings_store=store,
        package_catalog=_RecordingCatalog(),  # type: ignore[arg-type]
        disable_hot_reload=True,
    )
    app = create_app(config)
    async with app.router.lifespan_context(app):
        pass

    assert order == ["load", "snapshot_cleanup", "refresh"], order


async def test_lifespan_snapshot_cleanup_failure_is_logged_and_nonfatal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    refreshed = False

    def fail_cleanup(_service: NestedWorkflowSnapshotService) -> list[Any]:
        raise OSError("snapshot inventory unavailable")

    class _RecordingCatalog:
        async def refresh(self) -> None:
            nonlocal refreshed
            refreshed = True

        def list_packages(self):
            return []

    monkeypatch.setattr(
        NestedWorkflowSnapshotService,
        "cleanup_orphaned_snapshots",
        fail_cleanup,
    )
    app = create_app(
        AppConfig(
            workspace_path=tmp_path / "workspace",
            storage_path=tmp_path / "storage",
            package_catalog=_RecordingCatalog(),  # type: ignore[arg-type]
            disable_hot_reload=True,
        )
    )

    with caplog.at_level("WARNING", logger="bioimageflow_server.app"):
        async with app.router.lifespan_context(app):
            pass

    assert refreshed is True
    assert "Retained nested snapshot orphan cleanup failed at startup" in caplog.text
    assert "snapshot inventory unavailable" in caplog.text


async def test_lifespan_calls_flush_on_shutdown(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path=path)
    flush_mock = AsyncMock()
    store.flush = flush_mock  # type: ignore[method-assign]
    config = AppConfig(settings_store=store, disable_hot_reload=True)
    app = create_app(config)
    async with app.router.lifespan_context(app):
        flush_mock.assert_not_awaited()
    flush_mock.assert_awaited_once()


async def test_lifespan_seeds_missing_settings_file(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    assert not path.exists()
    store = SettingsStore(path=path)
    config = AppConfig(settings_store=store, disable_hot_reload=True)
    app = create_app(config)
    async with app.router.lifespan_context(app):
        pass
    assert path.exists()
    on_disk = json.loads(path.read_text())
    assert on_disk["settings_version"] == 1


async def test_dev_mode_dependency_resolves_through_store(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path=path)
    config = AppConfig(settings_store=store, disable_hot_reload=True)
    app = create_app(config)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.patch("/api/v1/settings", json={"dev_mode": True})
        # Dependency override should call into the store for live reads.
        assert app.dependency_overrides[graph_get_dev_mode]() is True
