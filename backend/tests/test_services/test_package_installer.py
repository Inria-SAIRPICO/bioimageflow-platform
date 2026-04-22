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

import pytest

from bioimageflow_server.services import package_installer as installer_module
from bioimageflow_server.services.package_installer import (
    PackageNetworkError,
    PackageNotFoundError,
    PypiPackageInstaller,
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


async def test_install_not_found_raises_package_not_found(
    installer: PypiPackageInstaller,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        installer_module,
        "ensure_installed",
        _ensure_installed_failure_factory(
            "ERROR: No matching distribution found for foo==9.9.9"
        ),
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
        _ensure_installed_failure_factory(
            "error: network timeout while fetching metadata"
        ),
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
