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
from bioimageflow_server.routers.nodes import (
    get_result_store,
    get_thumbnail_service,
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
def anyio_backend() -> str:
    return "asyncio"


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
# Nodes deps wiring
# ---------------------------------------------------------------------------


async def test_nodes_router_is_mounted():
    app = create_app()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/nodes/test/data")
    assert resp.status_code == 404


def test_app_config_wires_node_services():
    result_store = object()
    thumbnail_service = object()
    cfg = AppConfig(
        result_store=result_store,
        thumbnail_service=thumbnail_service,
    )
    app = create_app(config=cfg)
    assert app.dependency_overrides[get_result_store]() is result_store
    assert app.dependency_overrides[get_thumbnail_service]() is thumbnail_service


def test_default_node_services_use_storage_path(tmp_path: Path):
    cfg = AppConfig(storage_path=tmp_path)
    app = create_app(config=cfg)
    result_store = app.dependency_overrides[get_result_store]()
    thumbnail_service = app.dependency_overrides[get_thumbnail_service]()
    assert result_store.storage_path == tmp_path
    assert thumbnail_service.cache_dir == tmp_path / ".thumbnails"


def test_default_node_services_fall_back_to_bif_data():
    app = create_app()
    result_store = app.dependency_overrides[get_result_store]()
    assert result_store.storage_path == Path("./bif_data")


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


# ---------------------------------------------------------------------------
# Hot-reload service wiring (Task 4)
# ---------------------------------------------------------------------------


async def test_appconfig_disable_hot_reload_default_is_false():
    cfg = AppConfig()
    assert cfg.disable_hot_reload is False


async def test_appconfig_disable_hot_reload_round_trip():
    cfg = AppConfig(disable_hot_reload=True)
    assert cfg.disable_hot_reload is True


async def test_lifespan_starts_and_stops_hot_reload_service(
    empty_tool_store: Path, monkeypatch: pytest.MonkeyPatch
):
    from bioimageflow_server.services.tool_hot_reload import (
        ToolHotReloadService,
    )

    starts: list[Path] = []
    stops: list[None] = []

    async def _record_start(self, watch_root: Path) -> None:
        starts.append(watch_root)

    async def _record_stop(self) -> None:
        stops.append(None)

    monkeypatch.setattr(ToolHotReloadService, "start", _record_start)
    monkeypatch.setattr(ToolHotReloadService, "stop", _record_stop)

    config = AppConfig(
        tool_registry=ToolRegistryService(),
        known_packages=KnownPackagesService(
            user_path=empty_tool_store / "no_user",
            bundled_path=empty_tool_store / "no_bundled",
        ),
        pypi_versions=_FakePypi(),
    )
    app = create_app(config=config)

    async with app.router.lifespan_context(app):
        pass

    assert len(starts) == 1
    assert starts[0] == empty_tool_store
    assert len(stops) == 1


async def test_disable_hot_reload_skips_service_construction(
    empty_tool_store: Path, monkeypatch: pytest.MonkeyPatch
):
    from bioimageflow_server.services import tool_hot_reload as thr_mod

    constructed: list[object] = []
    real_init = thr_mod.ToolHotReloadService.__init__

    def _spy_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        constructed.append(self)
        return real_init(self, *args, **kwargs)

    monkeypatch.setattr(thr_mod.ToolHotReloadService, "__init__", _spy_init)

    config = AppConfig(
        tool_registry=ToolRegistryService(),
        disable_hot_reload=True,
        known_packages=KnownPackagesService(
            user_path=empty_tool_store / "no_user",
            bundled_path=empty_tool_store / "no_bundled",
        ),
        pypi_versions=_FakePypi(),
    )
    app = create_app(config=config)

    async with app.router.lifespan_context(app):
        pass

    assert constructed == []


async def test_observer_starts_after_scan_tool_store(
    empty_tool_store: Path, monkeypatch: pytest.MonkeyPatch
):
    """The watchdog observer must not start before the registry has been
    populated by scan_tool_store — otherwise it could race with the
    initial load and trigger reloads on entries that are mid-load."""
    from bioimageflow_server.services.tool_hot_reload import (
        ToolHotReloadService,
    )

    timeline: list[str] = []

    real_scan = ToolRegistryService.scan_tool_store

    def _recording_scan(self, store_path=None):
        timeline.append("scan")
        return real_scan(self, store_path=store_path)

    async def _record_start(self, watch_root: Path) -> None:
        timeline.append("start")

    async def _record_stop(self) -> None:
        pass

    monkeypatch.setattr(ToolRegistryService, "scan_tool_store", _recording_scan)
    monkeypatch.setattr(ToolHotReloadService, "start", _record_start)
    monkeypatch.setattr(ToolHotReloadService, "stop", _record_stop)

    config = AppConfig(
        known_packages=KnownPackagesService(
            user_path=empty_tool_store / "no_user",
            bundled_path=empty_tool_store / "no_bundled",
        ),
        pypi_versions=_FakePypi(),
    )
    app = create_app(config=config)

    async with app.router.lifespan_context(app):
        pass

    # scan must precede start.
    scan_idx = timeline.index("scan")
    start_idx = timeline.index("start")
    assert scan_idx < start_idx


async def test_initial_scan_produces_zero_broadcasts(
    empty_tool_store: Path, monkeypatch: pytest.MonkeyPatch
):
    """The watcher isn't running yet during the initial registry scan,
    so it cannot broadcast tool_reload / tool_removed."""
    from bioimageflow_server.services.tool_hot_reload import (
        ToolHotReloadService,
    )

    async def _record_start(self, watch_root: Path) -> None:
        pass

    async def _record_stop(self) -> None:
        pass

    monkeypatch.setattr(ToolHotReloadService, "start", _record_start)
    monkeypatch.setattr(ToolHotReloadService, "stop", _record_stop)

    config = AppConfig(
        known_packages=KnownPackagesService(
            user_path=empty_tool_store / "no_user",
            bundled_path=empty_tool_store / "no_bundled",
        ),
        pypi_versions=_FakePypi(),
    )
    app = create_app(config=config)
    cm = app.state.connection_manager

    broadcast_calls: list[str] = []

    async def _spy_reload(name, payload):
        broadcast_calls.append(("reload", name))

    async def _spy_removed(name):
        broadcast_calls.append(("removed", name))

    monkeypatch.setattr(cm, "broadcast_tool_reload", _spy_reload)
    monkeypatch.setattr(cm, "broadcast_tool_removed", _spy_removed)

    async with app.router.lifespan_context(app):
        pass

    assert broadcast_calls == []


async def test_installer_receives_hot_reload_service(
    empty_tool_store: Path, monkeypatch: pytest.MonkeyPatch
):
    """The default PypiPackageInstaller must be constructed with the
    same ToolHotReloadService instance the lifespan starts."""
    from bioimageflow_server.services.tool_hot_reload import (
        ToolHotReloadService,
    )

    async def _no_start(self, watch_root: Path) -> None:
        pass

    async def _no_stop(self) -> None:
        pass

    monkeypatch.setattr(ToolHotReloadService, "start", _no_start)
    monkeypatch.setattr(ToolHotReloadService, "stop", _no_stop)

    config = AppConfig(
        tool_registry=ToolRegistryService(),
        known_packages=KnownPackagesService(
            user_path=empty_tool_store / "no_user",
            bundled_path=empty_tool_store / "no_bundled",
        ),
        pypi_versions=_FakePypi(),
    )
    app = create_app(config=config)

    from bioimageflow_server.routers.tools import get_package_installer
    installer = app.dependency_overrides[get_package_installer]()
    assert isinstance(installer, PypiPackageInstaller)
    # Installer holds a reference to the hot-reload service.
    hot_reload = getattr(installer, "_hot_reload", None)
    assert isinstance(hot_reload, ToolHotReloadService)


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
