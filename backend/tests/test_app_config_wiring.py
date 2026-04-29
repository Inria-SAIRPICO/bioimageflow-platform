"""Tests for default service wiring in create_app.

Covers both:
- Known-packages / package-installer / catalog wiring (plan Task 7).
- Dataset root and upload-size wiring.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow.paths import get_home

from bioimageflow_server.app import create_app
from bioimageflow_server.models.settings import _DEFAULT_MAX_UPLOAD_SIZE
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.routers.datasets import (
    get_datasets_root,
    get_max_upload_size,
)
from bioimageflow_server.services.known_packages import KnownPackagesService
from bioimageflow_server.services.package_installer import (
    PackageInstallerService,
    PackageNetworkError,
    PypiPackageInstaller,
)
from bioimageflow_server.services.pypi_versions import PyPIVersionService
from bioimageflow_server.services.tool_registry import ToolRegistryService

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_tool_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store = tmp_path / "tool_packages"
    store.mkdir()
    monkeypatch.setenv("BIOIMAGEFLOW_TOOL_STORE", str(store))
    return store


class _FakePypi(PyPIVersionService):
    def __init__(self) -> None:
        pass

    async def get_versions(self, package_name: str) -> list[str]:
        return []

    async def get_latest_stable(self, package_name: str) -> str:
        raise AssertionError("not used")

    async def aclose(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Task 7.1 — default installer constructed when config omits it
# ---------------------------------------------------------------------------


async def test_default_installer_constructed(empty_tool_store: Path):
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        known_packages=KnownPackagesService(
            user_path=empty_tool_store / "no_user",
            bundled_path=empty_tool_store / "no_bundled",
        ),
        pypi_versions=_FakePypi(),
    )
    app = create_app(config=config)
    # Sanity: the dependency override no longer returns None.
    from bioimageflow_server.routers.tools import get_package_installer

    resolver = app.dependency_overrides[get_package_installer]
    assert isinstance(resolver(), PypiPackageInstaller)


async def test_install_endpoint_no_longer_500s_by_default(
    empty_tool_store: Path, monkeypatch: pytest.MonkeyPatch
):
    # Monkeypatch the installer to avoid shelling out to real uv.
    async def _fake_install(self, name, version=None):
        return None

    monkeypatch.setattr(PypiPackageInstaller, "install", _fake_install)

    config = AppConfig(
        tool_registry=ToolRegistryService(),
        known_packages=KnownPackagesService(
            user_path=empty_tool_store / "no_user",
            bundled_path=empty_tool_store / "no_bundled",
        ),
        pypi_versions=_FakePypi(),
    )
    app = create_app(config=config)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/tools/packages/bioimageflow_core/install")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Task 7.2 — overrides are preserved
# ---------------------------------------------------------------------------


async def test_custom_installer_override_preserved(empty_tool_store: Path):
    custom = AsyncMock(spec=PackageInstallerService)
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        package_installer=custom,
        known_packages=KnownPackagesService(
            user_path=empty_tool_store / "no_user",
            bundled_path=empty_tool_store / "no_bundled",
        ),
        pypi_versions=_FakePypi(),
    )
    app = create_app(config=config)
    from bioimageflow_server.routers.tools import get_package_installer

    assert app.dependency_overrides[get_package_installer]() is custom


async def test_custom_catalog_override_preserved(empty_tool_store: Path):
    class _StubCatalog:
        def __init__(self) -> None:
            self.refreshes = 0

        async def refresh(self) -> None:
            self.refreshes += 1

        def list_packages(self):
            return []

    stub = _StubCatalog()
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        package_catalog=stub,  # type: ignore[arg-type]
        known_packages=KnownPackagesService(
            user_path=empty_tool_store / "no_user",
            bundled_path=empty_tool_store / "no_bundled",
        ),
        pypi_versions=_FakePypi(),
    )
    app = create_app(config=config)
    from bioimageflow_server.routers.tools import get_package_catalog

    assert app.dependency_overrides[get_package_catalog]() is stub


# ---------------------------------------------------------------------------
# Task 7.3 — lifespan calls catalog.refresh() on startup
# ---------------------------------------------------------------------------


async def test_lifespan_refreshes_catalog_on_startup(empty_tool_store: Path):
    class _RecordingCatalog:
        def __init__(self) -> None:
            self.refresh_count = 0

        async def refresh(self) -> None:
            self.refresh_count += 1

        def list_packages(self):
            return []

    catalog = _RecordingCatalog()
    config = AppConfig(
        tool_registry=ToolRegistryService(),
        package_catalog=catalog,  # type: ignore[arg-type]
        known_packages=KnownPackagesService(
            user_path=empty_tool_store / "no_user",
            bundled_path=empty_tool_store / "no_bundled",
        ),
        pypi_versions=_FakePypi(),
    )
    app = create_app(config=config)
    async with app.router.lifespan_context(app):
        assert catalog.refresh_count == 1


# ---------------------------------------------------------------------------
# Task 7.4 — startup refresh failure is logged, not fatal
# ---------------------------------------------------------------------------


async def test_lifespan_swallows_network_error_from_refresh(
    empty_tool_store: Path,
    caplog: pytest.LogCaptureFixture,
):
    class _BrokenCatalog:
        async def refresh(self) -> None:
            raise PackageNetworkError("pypi down")

        def list_packages(self):
            return []

    config = AppConfig(
        tool_registry=ToolRegistryService(),
        package_catalog=_BrokenCatalog(),  # type: ignore[arg-type]
        known_packages=KnownPackagesService(
            user_path=empty_tool_store / "no_user",
            bundled_path=empty_tool_store / "no_bundled",
        ),
        pypi_versions=_FakePypi(),
    )
    app = create_app(config=config)
    with caplog.at_level("WARNING"):
        async with app.router.lifespan_context(app):
            pass  # startup ran; network error should have been logged
    assert any("refresh" in rec.message.lower() for rec in caplog.records)


# ---------------------------------------------------------------------------
# Dataset deps wiring
# ---------------------------------------------------------------------------


def test_dataset_deps_fall_back_to_defaults():
    app = create_app()
    assert app.dependency_overrides[get_datasets_root]() == get_home() / "datasets"
    assert app.dependency_overrides[get_max_upload_size]() == _DEFAULT_MAX_UPLOAD_SIZE


def test_app_config_wires_datasets_root(tmp_path: Path):
    cfg = AppConfig(datasets_root=tmp_path, max_upload_size=1_000_000)
    app = create_app(config=cfg)
    assert app.dependency_overrides[get_datasets_root]() == tmp_path
    assert app.dependency_overrides[get_max_upload_size]() == 1_000_000


# ---------------------------------------------------------------------------
# ExecutionManager default wiring
# ---------------------------------------------------------------------------


def test_default_app_provides_execution_manager():
    """create_app() with no config must default-construct an ExecutionManager.

    Regression test: previously both production entry points
    (desktop and uvicorn factory) left config.execution_manager=None,
    so POST /execution/run returned 503.
    """
    from bioimageflow_server.routers.execution import (
        get_execution_manager as execution_get_manager,
    )
    from bioimageflow_server.routers.graph import (
        get_execution_manager as graph_get_execution_manager,
    )
    from bioimageflow_server.services.execution import ExecutionManager

    app = create_app()
    em = app.dependency_overrides[execution_get_manager]()
    assert em is not None
    assert isinstance(em, ExecutionManager)
    # Same instance must be shared with the graph router so the
    # is_running lock observed there matches the running execution.
    assert app.dependency_overrides[graph_get_execution_manager]() is em
    assert em.is_running is False


def test_appconfig_supplied_execution_manager_is_preserved():
    """Caller-supplied ExecutionManager must win over the default.

    Tests inject fakes via AppConfig.execution_manager; that contract
    must not regress.
    """
    from bioimageflow_server.routers.execution import (
        get_execution_manager as execution_get_manager,
    )
    from bioimageflow_server.routers.graph import (
        get_execution_manager as graph_get_execution_manager,
    )

    sentinel = object()
    app = create_app(AppConfig(execution_manager=sentinel))
    assert app.dependency_overrides[execution_get_manager]() is sentinel
    assert app.dependency_overrides[graph_get_execution_manager]() is sentinel


# ---------------------------------------------------------------------------
# settings_store field
# ---------------------------------------------------------------------------


def test_app_config_default_settings_store_is_none():
    cfg = AppConfig()
    assert cfg.settings_store is None


def test_app_config_accepts_settings_store(tmp_path: Path):
    from bioimageflow_server.services.settings_store import SettingsStore

    store = SettingsStore(path=tmp_path / "settings.json")
    cfg = AppConfig(settings_store=store)
    assert cfg.settings_store is store


def test_app_config_accepts_both_settings_and_settings_store(tmp_path: Path):
    """Both fields can coexist; create_app prefers settings_store."""
    from bioimageflow_server.models.settings import Settings
    from bioimageflow_server.services.settings_store import SettingsStore

    store = SettingsStore(path=tmp_path / "settings.json")
    settings = Settings(deployment_mode="desktop")
    cfg = AppConfig(settings=settings, settings_store=store)
    assert cfg.settings is settings
    assert cfg.settings_store is store
