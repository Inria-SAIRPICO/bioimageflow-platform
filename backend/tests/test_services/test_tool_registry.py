"""Tests for ToolRegistryService."""

import pytest

from bioimageflow_server.models.tools import (
    InputFieldSchema,
    OutputFieldSchema,
    PackageInfo,
    ToolMetadata,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService

pytestmark = pytest.mark.anyio


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


# --- Tools ---


def test_empty_registry_list_tools():
    reg = ToolRegistryService()
    assert reg.list_tools() == []


def test_empty_registry_get_tool():
    reg = ToolRegistryService()
    assert reg.get_tool("Nope") is None


def test_register_and_get_tool():
    reg = ToolRegistryService()
    meta = _make_tool("Cellpose")
    reg.register_tool("Cellpose", meta)
    assert reg.get_tool("Cellpose") is meta


def test_register_multiple_and_list():
    reg = ToolRegistryService()
    reg.register_tool("A", _make_tool("A"))
    reg.register_tool("B", _make_tool("B"))
    names = {t.name for t in reg.list_tools()}
    assert names == {"A", "B"}


# --- Packages ---


def test_empty_registry_list_packages():
    reg = ToolRegistryService()
    assert reg.list_packages() == []


def test_empty_registry_get_package():
    reg = ToolRegistryService()
    assert reg.get_package("nope") is None


def test_register_and_get_package():
    reg = ToolRegistryService()
    info = _make_package("cellpose")
    reg.register_package("cellpose", info)
    assert reg.get_package("cellpose") is info


def test_register_multiple_packages_and_list():
    reg = ToolRegistryService()
    reg.register_package("a", _make_package("a"))
    reg.register_package("b", _make_package("b"))
    names = {p.name for p in reg.list_packages()}
    assert names == {"a", "b"}


# --- accepts_upstream / dynamic_outputs via _register_tool_from_class ---


def _load_common_tools_class(class_name: str) -> type:
    """Load a tool class from bioimageflow_common_tools, skipping if unavailable."""
    pytest.importorskip("bioimageflow.tool_loader")
    from bioimageflow.tool_loader import load_versioned_package

    package_name, version = "bioimageflow_common_tools", "0.1.1"
    try:
        mod = load_versioned_package(package_name, version)
    except Exception as exc:
        pytest.skip(f"{package_name}=={version} not installed: {exc}")
    cls = getattr(mod, class_name, None)
    if cls is None:
        pytest.skip(f"{class_name} missing from {package_name}")
    return cls


def _register(class_name: str) -> ToolMetadata:
    cls = _load_common_tools_class(class_name)
    reg = ToolRegistryService()
    reg._register_tool_from_class(cls, class_name, "bioimageflow_common_tools", "0.1.1")
    meta = reg.get_tool(class_name)
    assert meta is not None
    return meta


def test_files_accepts_upstream_is_false():
    meta = _register("Files")
    assert meta.tool_type == "DataFrameTool"
    assert meta.accepts_upstream is False


def test_inner_join_accepts_upstream_is_true():
    meta = _register("InnerJoin")
    assert meta.tool_type == "DataFrameTool"
    assert meta.accepts_upstream is True


def test_processing_tool_atlas_has_correct_type_and_accepts_upstream():
    meta = _register("Atlas")
    assert meta.tool_type == "ProcessingTool"
    assert meta.accepts_upstream is True


def test_scan_tool_store_picks_latest_version_by_default(tmp_path, monkeypatch):
    """Each tool class should default to the highest installed version.

    Regression: lex-sorted iteration of the version directories meant that
    `0.1.2` won over `0.1.10` and `0.1.3` won over `0.1.20`, so a freshly
    created node from a package that had multiple installed versions
    started life on an older version than the user expected.
    """
    pkg_dir = tmp_path / "fakepkg"
    pkg_dir.mkdir()

    versions = ["0.1.2", "0.1.10", "0.1.3"]

    # Build empty version directories. The library's register_package will
    # fail to load real metadata, but scan_tool_store records the version
    # set regardless — which is what we want to assert on.
    for v in versions:
        (pkg_dir / v).mkdir()

    reg = ToolRegistryService()
    reg.scan_tool_store(store_path=tmp_path)

    info = reg.get_package("fakepkg")
    assert info is not None, "package should be registered even if no tools loaded"
    # installed_versions stays in ascending order for the GUI dropdown.
    assert info.installed_versions == ["0.1.2", "0.1.3", "0.1.10"]
    # The newest installed version is the workflow's default active version
    # so freshly created nodes execute against the latest available code.
    assert info.active_version == "0.1.10"


def test_set_active_version_updates_package_active_version(tmp_path):
    """Switching the active version updates ``PackageInfo.active_version``
    so the GUI can mark which row is current. Lib registry rebinding can
    soft-fail on test fixtures (no real package on disk) — the field still
    needs to record the user's choice."""
    pkg_dir = tmp_path / "fakepkg"
    pkg_dir.mkdir()
    for v in ["0.1.0", "0.2.0"]:
        (pkg_dir / v).mkdir()

    reg = ToolRegistryService()
    reg.scan_tool_store(store_path=tmp_path)

    info = reg.get_package("fakepkg")
    assert info is not None
    # Newest installed wins by default.
    assert info.active_version == "0.2.0"

    reg.set_active_version("fakepkg", "0.1.0")
    info_after = reg.get_package("fakepkg")
    assert info_after is not None
    assert info_after.active_version == "0.1.0"


def test_scan_tool_store_registers_common_tools():
    """End-to-end regression: scanning the real tool store must surface
    every tool re-exported from bioimageflow_common_tools' __init__.py.

    Caught a class of bug where the package's __init__.py used absolute
    imports — _stamp_tool_classes skipped every class, register_package
    filtered them all out, and the GUI's tool list came up empty with
    no diagnostic. If this test goes red with a count mismatch, check
    that the package __init__.py uses relative imports
    (`from .X import Y`), not absolute (`from pkg.X import Y`).
    """
    from bioimageflow.paths import get_tool_store_path
    store_path = get_tool_store_path()
    common_tools_dir = store_path / "bioimageflow_common_tools"
    if not common_tools_dir.exists():
        pytest.skip("bioimageflow_common_tools not installed in tool store")

    reg = ToolRegistryService()
    reg.scan_tool_store()

    expected = {
        "Files", "Generate", "ConvertImage", "ExtractChannel", "Atlas",
        "ConnectedComponents", "CellposeSAM", "LabelOverlaps",
        "InnerJoin", "CrossJoin", "JoinOnColumn", "Concat", "Collect",
        "Mosaic",
    }
    found = {t.name for t in reg.list_tools()}
    missing = expected - found
    assert not missing, (
        f"common-tools registration regression: {missing} not registered. "
        f"Likely cause: package __init__.py uses absolute imports."
    )


