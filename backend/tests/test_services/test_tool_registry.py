"""Tests for ToolRegistryService."""

import sys
from pathlib import Path

import pytest

from bioimageflow_server.models.tools import (
    InputFieldSchema,
    OutputFieldSchema,
    PackageInfo,
    ToolMetadata,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from tests.common_tools import COMMON_TOOLS_MARK, PACKAGE_NAME, load_common_tools_class

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
    cls, _version = load_common_tools_class(class_name)
    return cls


def _register(class_name: str) -> ToolMetadata:
    cls, version = load_common_tools_class(class_name)
    reg = ToolRegistryService()
    reg._register_tool_from_class(cls, class_name, PACKAGE_NAME, version)
    meta = reg.get_tool(class_name)
    assert meta is not None
    return meta


@COMMON_TOOLS_MARK
def test_files_accepts_upstream_is_false():
    meta = _register("Files")
    assert meta.tool_type == "DataFrameTool"
    assert meta.accepts_upstream is False
    assert meta.inputs["path"].path_picker == "folder"


@COMMON_TOOLS_MARK
def test_inner_join_accepts_upstream_is_true():
    meta = _register("InnerJoin")
    assert meta.tool_type == "DataFrameTool"
    assert meta.accepts_upstream is True


@COMMON_TOOLS_MARK
def test_processing_tool_atlas_has_correct_type_and_accepts_upstream():
    meta = _register("Atlas")
    assert meta.tool_type == "ProcessingTool"
    assert meta.accepts_upstream is True
    assert meta.dataframe_output is True


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
        package_dir = pkg_dir / v / "fakepkg"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")

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


def test_scan_tool_store_records_failed_versions_without_hiding_package(
    tmp_path, _cleanup_dummy_modules
):
    """A bad installed package version should not make the package vanish.

    Startup scans are best-effort: the GUI still needs to show installed
    versions so users can uninstall or replace stale packages that no longer
    import under the current BioImageFlow runtime.
    """
    _write_dummy_pkg(tmp_path, "1.0.0", syntax_error=True)

    reg = _scan(tmp_path)

    info = reg.get_package(DUMMY_PKG)
    assert info is not None
    assert info.installed_versions == ["1.0.0"]
    assert info.available_versions == ["1.0.0"]
    assert info.active_version == "1.0.0"
    assert info.tools == {"1.0.0": []}
    assert "1.0.0" in info.load_errors
    assert "SyntaxError" in info.load_errors["1.0.0"]
    assert reg.list_tools() == []


def test_scan_tool_store_prefers_newest_successfully_loaded_version(
    tmp_path, _cleanup_dummy_modules
):
    _write_dummy_pkg(tmp_path, "1.0.0")
    _write_dummy_pkg(tmp_path, "2.0.0", syntax_error=True)

    reg = _scan(tmp_path)

    info = reg.get_package(DUMMY_PKG)
    assert info is not None
    assert info.installed_versions == ["1.0.0", "2.0.0"]
    assert info.active_version == "1.0.0"
    assert info.tools["1.0.0"] == ["GaussianSmooth"]
    assert info.tools["2.0.0"] == []
    assert "2.0.0" in info.load_errors


def test_set_active_version_rejects_failed_version(tmp_path, _cleanup_dummy_modules):
    _write_dummy_pkg(tmp_path, "1.0.0")
    _write_dummy_pkg(tmp_path, "2.0.0", syntax_error=True)
    reg = _scan(tmp_path)

    with pytest.raises(ValueError, match="failed to load"):
        reg.set_active_version(DUMMY_PKG, "2.0.0")


# ---------------------------------------------------------------------------
# Tests: reload_package / snapshot / resolve_package_for_path
# ---------------------------------------------------------------------------

DUMMY_PKG = "dummy_reload_tools"


def _write_dummy_pkg(
    store: Path,
    version: str,
    *,
    diameter_default: float = 1.0,
    extra_field: str | None = None,
    sibling_helper_value: int = 42,
    omit_class: bool = False,
    syntax_error: bool = False,
    add_class: str | None = None,
) -> None:
    """Write a minimal versioned dummy_tools package to ``store``.

    Always writes a ``GaussianSmooth`` ProcessingTool unless ``omit_class`` is
    set (used to test removal). ``extra_field`` adds an extra input. The
    ``sibling_helper_value`` ends up in ``utils/helpers.py`` and is used by
    GaussianSmooth's ``process_row`` — change it to verify a sibling-only
    edit produces no source-hash change for GaussianSmooth itself.
    ``add_class`` injects a second ProcessingTool with that class name.
    ``syntax_error`` writes a malformed source file (used to test rollback).
    """
    pkg_dir = store / DUMMY_PKG / version / DUMMY_PKG
    pkg_dir.mkdir(parents=True, exist_ok=True)

    init_lines = []
    if not omit_class:
        init_lines.append("from .filters import GaussianSmooth\n")
    if add_class is not None:
        init_lines.append(f"from .extras import {add_class}\n")
    (pkg_dir / "__init__.py").write_text("".join(init_lines))

    if syntax_error:
        (pkg_dir / "filters.py").write_text(
            "from .utils.helpers import helper_value\n"
            "this is not valid python !!!\n"
        )
    elif not omit_class:
        extra_input = ""
        if extra_field is not None:
            extra_input = f"\n        {extra_field}: float = 3.0"
        (pkg_dir / "filters.py").write_text(
            "from bioimageflow_core import ProcessingTool, IOModel, "
            "Arguments, EnvironmentSpec\n"
            "from .utils.helpers import helper_value\n\n"
            "_env = EnvironmentSpec(name='dummy', dependencies={'pip': []})\n\n"
            "class GaussianSmooth(ProcessingTool):\n"
            "    display_name = 'Gaussian Smooth'\n"
            "    environment = _env\n"
            "    class Inputs(IOModel):\n"
            f"        diameter: float = {diameter_default}{extra_input}\n"
            "    class Outputs(IOModel):\n"
            "        result: str\n"
            "    def process_row(self, arguments: Arguments):\n"
            "        return self.Outputs(result=str(helper_value()))\n"
        )

    if add_class is not None:
        (pkg_dir / "extras.py").write_text(
            "from bioimageflow_core import ProcessingTool, IOModel, "
            "Arguments, EnvironmentSpec\n\n"
            "_env = EnvironmentSpec(name='dummy', dependencies={'pip': []})\n\n"
            f"class {add_class}(ProcessingTool):\n"
            f"    display_name = '{add_class}'\n"
            "    environment = _env\n"
            "    class Inputs(IOModel):\n"
            "        x: int = 0\n"
            "    class Outputs(IOModel):\n"
            "        result: str\n"
            "    def process_row(self, arguments: Arguments):\n"
            "        return self.Outputs(result='hi')\n"
        )

    utils_dir = pkg_dir / "utils"
    utils_dir.mkdir(exist_ok=True)
    (utils_dir / "__init__.py").write_text(
        "from .helpers import helper_value\n"
    )
    (utils_dir / "helpers.py").write_text(
        f"def helper_value():\n    return {sibling_helper_value}\n"
    )


@pytest.fixture
def _cleanup_dummy_modules() -> None:
    """Strip dummy tool packages out of sys.modules / sys.path between tests.

    Reload tests rebuild the same scoped modules many times across separate
    tmp_path stores. Without this fixture, leftover entries from a prior test
    short-circuit the loader's ``if scoped_name in sys.modules`` cache and
    leak references back into subsequent tests.
    """
    yield
    to_remove = [k for k in sys.modules if DUMMY_PKG in k]
    for k in to_remove:
        del sys.modules[k]
    sys.path[:] = [p for p in sys.path if DUMMY_PKG not in p]


def _scan(store: Path) -> ToolRegistryService:
    reg = ToolRegistryService()
    reg.scan_tool_store(store_path=store)
    return reg


def test_reload_package_picks_up_new_input_field(tmp_path, _cleanup_dummy_modules):
    _write_dummy_pkg(tmp_path, "1.0.0")
    reg = _scan(tmp_path)
    before = reg.get_tool("GaussianSmooth")
    assert before is not None
    assert "diameter" in before.inputs
    assert "truncate" not in before.inputs

    _write_dummy_pkg(tmp_path, "1.0.0", extra_field="truncate")
    reg.reload_package(DUMMY_PKG, "1.0.0")

    snap = reg.snapshot(DUMMY_PKG, "1.0.0")
    assert "GaussianSmooth" in snap
    assert "truncate" in snap["GaussianSmooth"].inputs
    # Service-wide ``get_tool`` reflects the reloaded metadata.
    after = reg.get_tool("GaussianSmooth")
    assert after is not None
    assert "truncate" in after.inputs


def test_reload_package_uses_unload_then_load_primitives(
    tmp_path, monkeypatch, _cleanup_dummy_modules
):
    _write_dummy_pkg(tmp_path, "1.0.0")
    reg = _scan(tmp_path)

    calls: list[tuple[str, tuple]] = []

    real_unload = sys.modules["bioimageflow.tool_loader"].unload_versioned_package
    real_load = sys.modules["bioimageflow.tool_loader"].load_versioned_package

    def _spy_unload(*args, **kwargs):
        calls.append(("unload", args))
        return real_unload(*args, **kwargs)

    def _spy_load(*args, **kwargs):
        calls.append(("load", args))
        return real_load(*args, **kwargs)

    monkeypatch.setattr(
        "bioimageflow_server.services.tool_registry.unload_versioned_package",
        _spy_unload,
        raising=False,
    )
    monkeypatch.setattr(
        "bioimageflow_server.services.tool_registry.load_versioned_package",
        _spy_load,
        raising=False,
    )

    reg.reload_package(DUMMY_PKG, "1.0.0")

    kinds = [c[0] for c in calls]
    assert kinds == ["unload", "load"], (
        f"Expected unload then load; got {kinds!r}"
    )


def test_reload_stamps_version_metadata_on_classes(
    tmp_path, _cleanup_dummy_modules
):
    _write_dummy_pkg(tmp_path, "1.0.0")
    reg = _scan(tmp_path)

    reg.reload_package(DUMMY_PKG, "1.0.0")
    cls = reg.get_tool_class("GaussianSmooth")
    assert cls is not None
    assert getattr(cls, "_bif_package") == DUMMY_PKG
    assert getattr(cls, "_bif_package_version") == "1.0.0"
    assert getattr(cls, "_bif_canonical_module") == f"{DUMMY_PKG}.filters"


def test_resolve_tool_class_after_reload(tmp_path, _cleanup_dummy_modules):
    from bioimageflow.tool_loader import resolve_tool_class

    _write_dummy_pkg(tmp_path, "1.0.0")
    reg = _scan(tmp_path)
    reg.reload_package(DUMMY_PKG, "1.0.0")

    cls = resolve_tool_class(
        DUMMY_PKG, "1.0.0", f"{DUMMY_PKG}.filters", "GaussianSmooth"
    )
    assert cls is not None
    assert cls.__name__ == "GaussianSmooth"


def test_active_version_preserved_across_inactive_reload(
    tmp_path, _cleanup_dummy_modules
):
    """Reloading an inactive version must not steal the lib registry's
    binding from the active version."""
    _write_dummy_pkg(tmp_path, "1.0.0")
    _write_dummy_pkg(tmp_path, "2.0.0", extra_field="truncate")
    reg = _scan(tmp_path)

    reg.set_active_version(DUMMY_PKG, "1.0.0")
    active_class_before = reg._lib_registry.get_class("GaussianSmooth")
    assert active_class_before is not None
    assert active_class_before._bif_package_version == "1.0.0"

    # Edit the source of the *inactive* v2.0.0 and reload it.
    _write_dummy_pkg(
        tmp_path, "2.0.0", extra_field="truncate", sibling_helper_value=99
    )
    reg.reload_package(DUMMY_PKG, "2.0.0")

    active_class_after = reg._lib_registry.get_class("GaussianSmooth")
    assert active_class_after is not None
    # The lib registry's class binding still points at v1.0.0 — the
    # active version is preserved.
    assert active_class_after._bif_package_version == "1.0.0"


def test_active_version_preserved_when_reloading_active(
    tmp_path, _cleanup_dummy_modules
):
    _write_dummy_pkg(tmp_path, "1.0.0")
    _write_dummy_pkg(tmp_path, "2.0.0")
    reg = _scan(tmp_path)
    reg.set_active_version(DUMMY_PKG, "1.0.0")

    # Edit the active v1.0.0 source and reload it.
    _write_dummy_pkg(tmp_path, "1.0.0", extra_field="truncate")
    reg.reload_package(DUMMY_PKG, "1.0.0")

    cls = reg._lib_registry.get_class("GaussianSmooth")
    assert cls is not None
    assert cls._bif_package_version == "1.0.0"


def test_reload_failure_rolls_back_to_prior_snapshot(
    tmp_path, _cleanup_dummy_modules
):
    _write_dummy_pkg(tmp_path, "1.0.0")
    reg = _scan(tmp_path)
    prior_class = reg._lib_registry.get_class("GaussianSmooth")
    prior_meta = reg.get_tool("GaussianSmooth")
    assert prior_class is not None
    assert prior_meta is not None

    # Introduce a syntax error in the source.
    _write_dummy_pkg(tmp_path, "1.0.0", syntax_error=True)

    with pytest.raises(Exception):
        reg.reload_package(DUMMY_PKG, "1.0.0")

    # Snapshot is unchanged.
    snap = reg.snapshot(DUMMY_PKG, "1.0.0")
    assert "GaussianSmooth" in snap
    # Lib registry binding still resolves to the prior class.
    assert reg._lib_registry.get_class("GaussianSmooth") is prior_class
    # Service-level metadata is preserved (not zeroed out).
    after = reg.get_tool("GaussianSmooth")
    assert after is not None
    assert after.inputs == prior_meta.inputs


def test_resolve_package_for_path_inside_store(tmp_path):
    reg = ToolRegistryService()
    reg._store_path = tmp_path  # type: ignore[attr-defined]
    target = tmp_path / DUMMY_PKG / "1.0.0" / DUMMY_PKG / "filters.py"
    pair = reg.resolve_package_for_path(target)
    assert pair == (DUMMY_PKG, "1.0.0")


def test_resolve_package_for_path_nested_subdir(tmp_path):
    reg = ToolRegistryService()
    reg._store_path = tmp_path  # type: ignore[attr-defined]
    target = tmp_path / DUMMY_PKG / "1.0.0" / DUMMY_PKG / "utils" / "helpers.py"
    pair = reg.resolve_package_for_path(target)
    assert pair == (DUMMY_PKG, "1.0.0")


def test_resolve_package_for_path_outside_store(tmp_path):
    reg = ToolRegistryService()
    reg._store_path = tmp_path  # type: ignore[attr-defined]
    pair = reg.resolve_package_for_path(Path("/etc/hosts"))
    assert pair is None


def test_resolve_package_for_path_too_shallow(tmp_path):
    reg = ToolRegistryService()
    reg._store_path = tmp_path  # type: ignore[attr-defined]
    # Only one component below the store root.
    target = tmp_path / DUMMY_PKG / "README.md"
    pair = reg.resolve_package_for_path(target)
    assert pair is None


def test_snapshot_returns_only_matching_version(tmp_path, _cleanup_dummy_modules):
    _write_dummy_pkg(tmp_path, "1.0.0")
    _write_dummy_pkg(tmp_path, "2.0.0", extra_field="truncate")
    reg = _scan(tmp_path)

    s1 = reg.snapshot(DUMMY_PKG, "1.0.0")
    s2 = reg.snapshot(DUMMY_PKG, "2.0.0")
    # Both snapshots have GaussianSmooth, but the service only stores one
    # ToolMetadata per class — the latest version wins. Snapshot must
    # filter by package_version.
    assert "GaussianSmooth" in s1 or "GaussianSmooth" in s2
    if "GaussianSmooth" in s1:
        assert s1["GaussianSmooth"].package_version == "1.0.0"
    if "GaussianSmooth" in s2:
        assert s2["GaussianSmooth"].package_version == "2.0.0"


def test_snapshot_unknown_version_is_empty(tmp_path):
    reg = ToolRegistryService()
    assert reg.snapshot("nonexistent", "0.0.0") == {}


def test_no_leaked_sys_path_after_repeated_reloads(
    tmp_path, _cleanup_dummy_modules
):
    _write_dummy_pkg(tmp_path, "1.0.0")
    reg = _scan(tmp_path)

    for _ in range(5):
        reg.reload_package(DUMMY_PKG, "1.0.0")

    suffix = str(Path(DUMMY_PKG) / "1.0.0")
    matches = [p for p in sys.path if p.endswith(suffix)]
    # At most one entry — load adds it; unload removes it; the live
    # post-reload state has exactly one.
    assert len(matches) <= 1


def test_scan_tool_store_refreshes_existing_entries(
    tmp_path, _cleanup_dummy_modules
):
    """Calling scan_tool_store twice should refresh metadata, not skip
    classes that are already in ``_tools``. The legacy ``if class_name in
    self._tools: continue`` guard made re-scans a no-op and is incompatible
    with reload semantics."""
    _write_dummy_pkg(tmp_path, "1.0.0")
    reg = _scan(tmp_path)
    before = reg.get_tool("GaussianSmooth")
    assert before is not None
    assert "truncate" not in before.inputs

    # Need to unload first since load_versioned_package caches by sys.modules.
    from bioimageflow.tool_loader import unload_versioned_package
    unload_versioned_package(DUMMY_PKG, "1.0.0")

    _write_dummy_pkg(tmp_path, "1.0.0", extra_field="truncate")
    reg.scan_tool_store(store_path=tmp_path)

    after = reg.get_tool("GaussianSmooth")
    assert after is not None
    assert "truncate" in after.inputs


@COMMON_TOOLS_MARK
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
        load_common_tools_class("Files")

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
    pkg = reg.get_package(PACKAGE_NAME)
    if missing and pkg is not None and pkg.load_errors and not found:
        pytest.skip(
            f"{PACKAGE_NAME} is installed but no version loads under the "
            f"current runtime: {pkg.load_errors}"
        )
    assert not missing, (
        f"common-tools registration regression: {missing} not registered. "
        f"Likely cause: package __init__.py uses absolute imports."
    )
