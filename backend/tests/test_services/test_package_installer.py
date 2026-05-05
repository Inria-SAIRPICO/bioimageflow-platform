"""Tests for PypiPackageInstaller (spec v3 §2.5, specs.md §Tool Store).

The real installer delegates to :func:`bioimageflow.tool_loader.ensure_installed`,
which runs ``pip install --target`` through Wetlands' pixi-backed
:class:`EnvironmentManager`. Tests monkeypatch that function on the
:mod:`bioimageflow_server.services.package_installer` module so we don't
spawn pixi subprocesses in unit tests.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import anyio

import pytest

from bioimageflow_server.services import package_installer as installer_module
from bioimageflow_server.services.package_installer import (
    PackageNetworkError,
    PackageNotFoundError,
    PypiPackageInstaller,
    _local_common_tools_root,
    _project_version,
)
from bioimageflow_server.services.pypi_versions import PyPIVersionService
from bioimageflow_server.services.tool_registry import ToolRegistryService

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Helpers — fake `ensure_installed`
# ---------------------------------------------------------------------------


def _ensure_installed_success_factory(calls: list[tuple[str, str, str, Path]]):
    """Return a fake ``ensure_installed`` that records calls and populates target."""

    def _fake(
        pkg_name: str,
        version: str,
        pypi_name: str,
        store_path: Path,
    ) -> None:
        calls.append((pkg_name, version, pypi_name, store_path))
        target = store_path / pkg_name / version
        pkg_dir = target / pkg_name
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "__init__.py").write_text("__version__ = " + repr(version) + "\n")

    return _fake


def _ensure_installed_failure_factory(message: str):
    def _fake(
        pkg_name: str,
        version: str,
        pypi_name: str,
        store_path: Path,
    ) -> None:
        raise RuntimeError(message)

    return _fake


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tool_store(tmp_path: Path) -> Path:
    store = tmp_path / "tool_packages"
    store.mkdir()
    return store


@pytest.fixture
def registry() -> ToolRegistryService:
    reg = MagicMock(spec=ToolRegistryService)
    return reg


@pytest.fixture
def pypi() -> AsyncMock:
    svc = AsyncMock(spec=PyPIVersionService)
    svc.get_latest_stable.return_value = "0.1.1"
    return svc


@pytest.fixture
def installer(
    tool_store: Path,
    registry: ToolRegistryService,
    pypi: PyPIVersionService,
) -> PypiPackageInstaller:
    return PypiPackageInstaller(tool_store=tool_store, registry=registry, pypi=pypi)


# ---------------------------------------------------------------------------
# install()
# ---------------------------------------------------------------------------


async def test_install_delegates_to_wetlands_ensure_installed(
    installer: PypiPackageInstaller,
    tool_store: Path,
    registry: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[str, str, str, Path]] = []
    monkeypatch.setattr(
        installer_module,
        "ensure_installed",
        _ensure_installed_success_factory(calls),
    )

    await installer.install("bioimageflow_core", "0.1.1")

    assert calls == [("bioimageflow_core", "0.1.1", "bioimageflow-core", tool_store)]
    registry.scan_tool_store.assert_called_once_with(tool_store)


async def test_install_creates_expected_target_tree(
    installer: PypiPackageInstaller,
    tool_store: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        installer_module,
        "ensure_installed",
        _ensure_installed_success_factory([]),
    )

    await installer.install("bioimageflow_core", "0.1.1")

    assert (
        tool_store / "bioimageflow_core" / "0.1.1" / "bioimageflow_core" / "__init__.py"
    ).exists()


async def test_install_resolves_latest_when_no_version(
    installer: PypiPackageInstaller,
    pypi: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[str, str, str, Path]] = []
    monkeypatch.setattr(
        installer_module,
        "ensure_installed",
        _ensure_installed_success_factory(calls),
    )

    await installer.install("bioimageflow_core", version=None)
    pypi.get_latest_stable.assert_awaited_once_with("bioimageflow_core")
    assert calls[0][1] == "0.1.1"
    assert calls[0][2] == "bioimageflow-core"


async def test_install_common_tools_uses_local_checkout_without_pypi(
    installer: PypiPackageInstaller,
    tool_store: Path,
    registry: MagicMock,
    pypi: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        installer_module,
        "ensure_installed",
        _ensure_installed_failure_factory("network should not be used"),
    )

    await installer.install("bioimageflow_common_tools", version=None)

    pypi.get_latest_stable.assert_not_called()
    source_root = _local_common_tools_root()
    assert source_root is not None
    version = _project_version(source_root)
    installed = tool_store / "bioimageflow_common_tools" / version / "bioimageflow_common_tools"
    assert (installed / "__init__.py").exists()
    assert (installed / "atlas.py").exists()
    registry.scan_tool_store.assert_called_once_with(tool_store)


async def test_install_not_found_raises_package_not_found(
    installer: PypiPackageInstaller,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        installer_module,
        "ensure_installed",
        _ensure_installed_failure_factory("ERROR: No matching distribution found for foo==9.9.9"),
    )
    with pytest.raises(PackageNotFoundError):
        await installer.install("foo", "9.9.9")


async def test_install_could_not_find_version_raises_package_not_found(
    installer: PypiPackageInstaller,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        installer_module,
        "ensure_installed",
        _ensure_installed_failure_factory(
            "error: Could not find a version that satisfies foo==9.9.9"
        ),
    )
    with pytest.raises(PackageNotFoundError):
        await installer.install("foo", "9.9.9")


async def test_install_missing_module_after_install_raises_not_found(
    installer: PypiPackageInstaller,
    monkeypatch: pytest.MonkeyPatch,
):
    # Mirrors bioimageflow's "expected module 'X' not found in <target>" error,
    # which fires when a wheel publishes a different module name than the
    # normalized package name.
    monkeypatch.setattr(
        installer_module,
        "ensure_installed",
        _ensure_installed_failure_factory(
            "Installation of foo==1.0 succeeded but expected module 'foo' "
            "not found in /tmp/store/foo/1.0."
        ),
    )
    with pytest.raises(PackageNotFoundError):
        await installer.install("foo", "1.0")


async def test_install_network_error_raises_network_error(
    installer: PypiPackageInstaller,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        installer_module,
        "ensure_installed",
        _ensure_installed_failure_factory("error: network timeout while fetching metadata"),
    )
    with pytest.raises(PackageNetworkError):
        await installer.install("foo", "1.0")


async def test_install_unknown_error_defaults_to_network_error(
    installer: PypiPackageInstaller,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        installer_module,
        "ensure_installed",
        _ensure_installed_failure_factory("some weird unparseable error"),
    )
    with pytest.raises(PackageNetworkError):
        await installer.install("foo", "1.0")


# ---------------------------------------------------------------------------
# uninstall()
# ---------------------------------------------------------------------------


async def test_uninstall_removes_single_version(
    installer: PypiPackageInstaller,
    tool_store: Path,
    registry: MagicMock,
):
    pkg_root = tool_store / "bioimageflow_core"
    (pkg_root / "0.1.0" / "bioimageflow_core").mkdir(parents=True)
    (pkg_root / "0.1.0" / "bioimageflow_core" / "__init__.py").write_text("")
    (pkg_root / "0.1.1" / "bioimageflow_core").mkdir(parents=True)
    (pkg_root / "0.1.1" / "bioimageflow_core" / "__init__.py").write_text("")

    await installer.uninstall("bioimageflow_core", "0.1.0")

    assert not (pkg_root / "0.1.0").exists()
    assert (pkg_root / "0.1.1").exists()
    registry.forget_package.assert_called_once_with("bioimageflow_core", "0.1.0")
    registry.scan_tool_store.assert_called_once_with(tool_store)


async def test_uninstall_all_versions_removes_package_dir(
    installer: PypiPackageInstaller,
    tool_store: Path,
    registry: MagicMock,
):
    pkg_root = tool_store / "bioimageflow_core"
    (pkg_root / "0.1.0").mkdir(parents=True)

    await installer.uninstall("bioimageflow_core", version=None)

    assert not pkg_root.exists()
    registry.forget_package.assert_called_once_with("bioimageflow_core", None)


async def test_uninstall_missing_path_raises_not_found(
    installer: PypiPackageInstaller,
    tool_store: Path,
):
    with pytest.raises(PackageNotFoundError):
        await installer.uninstall("ghost", "1.0")


# ---------------------------------------------------------------------------
# Hot-reload suppression hook (Task 5)
# ---------------------------------------------------------------------------


class _FakeHotReload:
    """Records suppress / resume calls to assert ordering and arguments."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, bool | None]] = []

    def suppress(self) -> None:
        self.calls.append(("suppress", None))

    def resume(self, emit_batch: bool = True) -> None:
        self.calls.append(("resume", emit_batch))


@pytest.fixture
def hot_reload() -> _FakeHotReload:
    return _FakeHotReload()


@pytest.fixture
def installer_with_hot_reload(
    tool_store: Path,
    registry: ToolRegistryService,
    pypi: PyPIVersionService,
    hot_reload: _FakeHotReload,
) -> PypiPackageInstaller:
    return PypiPackageInstaller(
        tool_store=tool_store,
        registry=registry,
        pypi=pypi,
        hot_reload=hot_reload,
    )


async def test_install_success_suppresses_then_resumes_with_batch(
    installer_with_hot_reload: PypiPackageInstaller,
    hot_reload: _FakeHotReload,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        installer_module,
        "ensure_installed",
        _ensure_installed_success_factory([]),
    )

    await installer_with_hot_reload.install("foo", "1.0")

    assert hot_reload.calls == [("suppress", None), ("resume", True)]


async def test_install_failure_resumes_with_emit_batch_false(
    installer_with_hot_reload: PypiPackageInstaller,
    hot_reload: _FakeHotReload,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        installer_module,
        "ensure_installed",
        _ensure_installed_failure_factory("ERROR: No matching distribution found for foo==9.9.9"),
    )

    with pytest.raises(PackageNotFoundError):
        await installer_with_hot_reload.install("foo", "9.9.9")

    assert ("suppress", None) in hot_reload.calls
    assert ("resume", False) in hot_reload.calls
    # No (resume, True) on the failure path.
    assert ("resume", True) not in hot_reload.calls


async def test_uninstall_success_suppresses_then_resumes_with_batch(
    installer_with_hot_reload: PypiPackageInstaller,
    tool_store: Path,
    hot_reload: _FakeHotReload,
):
    pkg_root = tool_store / "foo" / "1.0"
    (pkg_root / "foo").mkdir(parents=True)

    await installer_with_hot_reload.uninstall("foo", "1.0")

    assert hot_reload.calls == [("suppress", None), ("resume", True)]


async def test_uninstall_failure_resumes_with_emit_batch_false(
    installer_with_hot_reload: PypiPackageInstaller,
    hot_reload: _FakeHotReload,
):
    with pytest.raises(PackageNotFoundError):
        await installer_with_hot_reload.uninstall("ghost", "1.0")

    assert ("suppress", None) in hot_reload.calls
    assert ("resume", False) in hot_reload.calls
    assert ("resume", True) not in hot_reload.calls


async def test_install_skips_scan_tool_store_when_hot_reload_wired(
    installer_with_hot_reload: PypiPackageInstaller,
    registry: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
):
    """When hot-reload is wired, resume(emit_batch=True) performs the
    load + index — a second scan_tool_store would double the work."""
    monkeypatch.setattr(
        installer_module,
        "ensure_installed",
        _ensure_installed_success_factory([]),
    )

    await installer_with_hot_reload.install("foo", "1.0")

    registry.scan_tool_store.assert_not_called()


async def test_install_calls_scan_tool_store_when_hot_reload_none(
    installer: PypiPackageInstaller,
    registry: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
):
    """Legacy path: without hot-reload the installer must still scan."""
    monkeypatch.setattr(
        installer_module,
        "ensure_installed",
        _ensure_installed_success_factory([]),
    )

    await installer.install("foo", "1.0")

    registry.scan_tool_store.assert_called_once()


async def test_uninstall_skips_scan_tool_store_when_hot_reload_wired(
    installer_with_hot_reload: PypiPackageInstaller,
    tool_store: Path,
    registry: MagicMock,
):
    pkg_root = tool_store / "foo" / "1.0"
    (pkg_root / "foo").mkdir(parents=True)

    await installer_with_hot_reload.uninstall("foo", "1.0")

    registry.scan_tool_store.assert_not_called()


async def test_uninstall_calls_scan_tool_store_when_hot_reload_none(
    installer: PypiPackageInstaller,
    tool_store: Path,
    registry: MagicMock,
):
    pkg_root = tool_store / "foo" / "1.0"
    (pkg_root / "foo").mkdir(parents=True)

    await installer.uninstall("foo", "1.0")

    registry.scan_tool_store.assert_called_once()


async def test_install_suppresses_before_ensure_installed_runs(
    installer_with_hot_reload: PypiPackageInstaller,
    hot_reload: _FakeHotReload,
    monkeypatch: pytest.MonkeyPatch,
):
    """suppress() must fire BEFORE ensure_installed touches disk so the
    watchdog observer doesn't see in-progress files."""
    timeline: list[str] = []

    original_suppress = hot_reload.suppress

    def _record_suppress() -> None:
        timeline.append("suppress")
        original_suppress()

    hot_reload.suppress = _record_suppress  # type: ignore[method-assign]

    def _fake_ensure(*args, **kwargs) -> None:
        timeline.append("ensure")

    monkeypatch.setattr(installer_module, "ensure_installed", _fake_ensure)

    await installer_with_hot_reload.install("foo", "1.0")

    suppress_idx = timeline.index("suppress")
    ensure_idx = timeline.index("ensure")
    assert suppress_idx < ensure_idx


async def test_concurrent_installs_are_serialized(
    installer: PypiPackageInstaller,
    monkeypatch: pytest.MonkeyPatch,
):
    active = 0
    max_active = 0
    calls: list[str] = []

    def _slow_ensure(pkg_name, version, pypi_name, store_path) -> None:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        calls.append(pkg_name)
        import time

        time.sleep(0.05)
        active -= 1

    monkeypatch.setattr(installer_module, "ensure_installed", _slow_ensure)

    async with anyio.create_task_group() as tg:
        tg.start_soon(installer.install, "foo", "1.0")
        tg.start_soon(installer.install, "bar", "1.0")

    assert sorted(calls) == ["bar", "foo"]
    assert max_active == 1
