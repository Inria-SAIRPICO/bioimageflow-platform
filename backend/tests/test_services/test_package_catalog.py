"""Tests for ToolRegistryService.forget_package and PackageCatalogService."""

from __future__ import annotations

import pytest

from bioimageflow_server.models.tools import (
    InputFieldSchema,
    OutputFieldSchema,
    PackageInfo,
    ToolMetadata,
)
from bioimageflow_server.services.known_packages import KnownPackagesService
from bioimageflow_server.services.package_catalog import PackageCatalogService
from bioimageflow_server.services.package_installer import PackageNetworkError
from bioimageflow_server.services.pypi_versions import PyPIVersionService
from bioimageflow_server.services.tool_registry import ToolRegistryService

pytestmark = pytest.mark.anyio


def _meta(name: str, package: str, version: str) -> ToolMetadata:
    return ToolMetadata(
        name=name,
        display_name=name,
        package=package,
        package_version=version,
        tool_type="ProcessingTool",
        inputs={
            "x": InputFieldSchema(type="int", required=True, connectable="not_by_default")
        },
        outputs={"y": OutputFieldSchema(type="int")},
    )


# ---------------------------------------------------------------------------
# ToolRegistryService.forget_package
# ---------------------------------------------------------------------------


def test_forget_package_specific_version_keeps_other_versions():
    reg = ToolRegistryService()
    reg.register_tool("A1", _meta("A1", "pkg", "1.0"))
    reg.register_tool("A2", _meta("A2", "pkg", "2.0"))
    reg.register_package(
        "pkg",
        PackageInfo(
            name="pkg",
            installed_versions=["1.0", "2.0"],
            tools={"1.0": ["A1"], "2.0": ["A2"]},
        ),
    )

    reg.forget_package("pkg", "1.0")

    pkg = reg.get_package("pkg")
    assert pkg is not None
    assert pkg.installed_versions == ["2.0"]
    assert "1.0" not in pkg.tools
    assert reg.get_tool("A1") is None
    assert reg.get_tool("A2") is not None


def test_forget_package_entire_package():
    reg = ToolRegistryService()
    reg.register_tool("A", _meta("A", "pkg", "1.0"))
    reg.register_tool("B", _meta("B", "other", "1.0"))
    reg.register_package("pkg", PackageInfo(name="pkg", installed_versions=["1.0"]))
    reg.register_package("other", PackageInfo(name="other", installed_versions=["1.0"]))

    reg.forget_package("pkg", None)

    assert reg.get_package("pkg") is None
    assert reg.get_tool("A") is None
    assert reg.get_tool("B") is not None
    assert reg.get_package("other") is not None


def test_forget_absent_package_is_noop():
    reg = ToolRegistryService()
    reg.forget_package("ghost", "1.0")  # must not raise
    reg.forget_package("ghost", None)


# ---------------------------------------------------------------------------
# PackageCatalogService
# ---------------------------------------------------------------------------


class _FakeKnown(KnownPackagesService):
    def __init__(self, names: list[str]):
        self._names = names

    def list_known_packages(self) -> list[str]:
        return list(self._names)


class _FakePypi(PyPIVersionService):
    def __init__(
        self,
        releases: dict[str, list[str]] | None = None,
        errors: dict[str, Exception] | None = None,
    ):
        self._releases = releases or {}
        self._errors = errors or {}
        self.get_versions_calls: list[str] = []

    async def get_versions(self, package_name: str) -> list[str]:
        self.get_versions_calls.append(package_name)
        if package_name in self._errors:
            raise self._errors[package_name]
        return list(self._releases.get(package_name, []))

    async def get_latest_stable(self, package_name: str) -> str:
        if package_name in self._errors:
            raise self._errors[package_name]
        return self._releases.get(package_name, [])[-1]

    async def aclose(self) -> None:
        pass


def _make_pypi(
    releases: dict[str, list[str]] | None = None,
    errors: dict[str, Exception] | None = None,
) -> _FakePypi:
    return _FakePypi(releases=releases, errors=errors)


async def test_catalog_includes_known_but_not_installed():
    reg = ToolRegistryService()  # empty
    known = _FakeKnown(["bioimageflow_core"])
    pypi = _make_pypi({"bioimageflow_core": ["0.1.0", "0.1.1"]})
    catalog = PackageCatalogService(registry=reg, known=known, pypi=pypi)

    await catalog.refresh()
    pkgs = {p.name: p for p in catalog.list_packages()}

    assert "bioimageflow_core" in pkgs
    assert pkgs["bioimageflow_core"].installed_versions == []
    assert pkgs["bioimageflow_core"].available_versions == ["0.1.0", "0.1.1"]


async def test_catalog_merges_installed_and_pypi_versions():
    reg = ToolRegistryService()
    reg.register_package(
        "bioimageflow_core",
        PackageInfo(
            name="bioimageflow_core",
            installed_versions=["0.1.0"],
            available_versions=["0.1.0"],
            tools={"0.1.0": ["Foo"]},
        ),
    )
    known = _FakeKnown(["bioimageflow_core"])
    pypi = _make_pypi({"bioimageflow_core": ["0.1.0", "0.1.1", "0.2.0"]})
    catalog = PackageCatalogService(registry=reg, known=known, pypi=pypi)

    await catalog.refresh()
    pkg = {p.name: p for p in catalog.list_packages()}["bioimageflow_core"]

    assert pkg.installed_versions == ["0.1.0"]
    # Merged, deduped, sorted ascending.
    assert pkg.available_versions == ["0.1.0", "0.1.1", "0.2.0"]
    assert pkg.tools == {"0.1.0": ["Foo"]}


async def test_catalog_installed_unknown_package_is_queried_for_upgrades():
    """Installed packages are queried on PyPI even when absent from the
    known list, so upgrades are discoverable (e.g. a user installed
    ``bioimageflow_common_tools==0.1.0`` and ``0.1.1`` is now out).
    """
    reg = ToolRegistryService()
    reg.register_package(
        "custom_pkg",
        PackageInfo(
            name="custom_pkg",
            installed_versions=["0.1.0"],
            available_versions=["0.1.0"],
        ),
    )
    known = _FakeKnown([])  # not in the known list
    pypi = _make_pypi({"custom_pkg": ["0.1.0", "0.1.1"]})
    catalog = PackageCatalogService(registry=reg, known=known, pypi=pypi)

    await catalog.refresh()
    pkg = {p.name: p for p in catalog.list_packages()}["custom_pkg"]

    assert pkg.installed_versions == ["0.1.0"]
    assert pkg.available_versions == ["0.1.0", "0.1.1"]
    assert pypi.get_versions_calls == ["custom_pkg"]


async def test_catalog_installed_unknown_package_falls_back_when_pypi_404s():
    """A locally-developed package not published on PyPI still shows up
    with its installed versions when the PyPI lookup fails.
    """
    reg = ToolRegistryService()
    reg.register_package(
        "local_only_pkg",
        PackageInfo(
            name="local_only_pkg",
            installed_versions=["0.1.0"],
            available_versions=["0.1.0"],
        ),
    )
    known = _FakeKnown([])
    pypi = _make_pypi(errors={"local_only_pkg": PackageNetworkError("404")})
    catalog = PackageCatalogService(registry=reg, known=known, pypi=pypi)

    await catalog.refresh()
    pkg = {p.name: p for p in catalog.list_packages()}["local_only_pkg"]

    assert pkg.available_versions == ["0.1.0"]


async def test_catalog_pypi_error_does_not_fail_whole_refresh(
    caplog: pytest.LogCaptureFixture,
):
    reg = ToolRegistryService()
    known = _FakeKnown(["good_pkg", "broken_pkg"])
    pypi = _make_pypi(
        releases={"good_pkg": ["1.0"]},
        errors={"broken_pkg": PackageNetworkError("boom")},
    )
    catalog = PackageCatalogService(registry=reg, known=known, pypi=pypi)

    with caplog.at_level("WARNING"):
        await catalog.refresh()

    pkgs = {p.name: p for p in catalog.list_packages()}
    assert pkgs["good_pkg"].available_versions == ["1.0"]
    # Broken package still listed with empty available_versions; warning logged.
    assert "broken_pkg" in pkgs
    assert pkgs["broken_pkg"].available_versions == []
    assert any("broken_pkg" in rec.message for rec in caplog.records)


async def test_catalog_list_packages_without_refresh_returns_registry_snapshot():
    reg = ToolRegistryService()
    reg.register_package(
        "only_installed",
        PackageInfo(name="only_installed", installed_versions=["1.0"]),
    )
    known = _FakeKnown(["only_installed"])
    pypi = _make_pypi({"only_installed": ["1.0", "2.0"]})
    catalog = PackageCatalogService(registry=reg, known=known, pypi=pypi)

    # No refresh() yet — fall back to the registry view.
    snapshot = catalog.list_packages()
    names = {p.name for p in snapshot}
    assert names == {"only_installed"}
    # PyPI was not consulted.
    assert pypi.get_versions_calls == []
