"""Tests for PypiPackageInstaller (spec v3 §2.5, specs.md §Tool Store).

The real installer delegates versioned installs to
:func:`bioimageflow.tool_loader.ensure_installed`. Tests monkeypatch that
function so they do not invoke pip.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import sys
import anyio

import pytest

from bioimageflow_server.services import package_installer as installer_module
from bioimageflow_server.services.package_installer import (
    PackageInvalidError,
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
        *, install_dependencies: bool,
    ) -> None:
        assert install_dependencies is False
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
        *, install_dependencies: bool,
    ) -> None:
        assert install_dependencies is False
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


@pytest.fixture(autouse=True)
def disposable_trash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Removal tests own their trash and never use the user's OS Trash."""
    trash = tmp_path / "trash"

    def move_to_trash(target: str) -> None:
        path = Path(target)
        trash.mkdir(exist_ok=True)
        path.rename(trash / f"{len(list(trash.iterdir()))}-{path.name}")

    monkeypatch.setattr(installer_module, "send2trash", move_to_trash)


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
    registry.index_package.assert_called_once()


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


async def test_install_common_tools_delegates_selected_version_to_package_index(
    installer: PypiPackageInstaller,
    tool_store: Path,
    registry: MagicMock,
    pypi: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[str, str, str, Path]] = []
    monkeypatch.setattr(
        installer_module,
        "ensure_installed",
        _ensure_installed_success_factory(calls),
    )

    await installer.install("bioimageflow_common_tools", version="0.1.6")

    pypi.get_latest_stable.assert_not_called()
    assert calls == [
        (
            "bioimageflow_common_tools",
            "0.1.6",
            "bioimageflow-common-tools",
            tool_store,
        )
    ]
    registry.index_package.assert_called_once()


async def test_install_common_tools_resolves_latest_from_package_index(
    installer: PypiPackageInstaller,
    tool_store: Path,
    pypi: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[str, str, str, Path]] = []
    pypi.get_latest_stable.return_value = "0.1.6"
    monkeypatch.setattr(
        installer_module,
        "ensure_installed",
        _ensure_installed_success_factory(calls),
    )

    await installer.install("bioimageflow_common_tools", version=None)

    pypi.get_latest_stable.assert_awaited_once_with("bioimageflow_common_tools")
    assert calls == [
        (
            "bioimageflow_common_tools",
            "0.1.6",
            "bioimageflow-common-tools",
            tool_store,
        )
    ]


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
# import URL / archive sources
# ---------------------------------------------------------------------------


def _populate_source_install(
    target: Path,
    *,
    dist_name: str = "demo-tools",
    version: str = "1.2.3",
    module_name: str = "demo_tools",
) -> None:
    pkg_dir = target / module_name
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    dist_info = target / f"{module_name}-{version}.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {dist_name}\nVersion: {version}\n",
        encoding="utf-8",
    )


async def test_install_from_url_normalizes_github_url_and_moves_package(
    installer: PypiPackageInstaller,
    tool_store: Path,
    registry: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []

    def _fake_install(source: str, target: Path) -> None:
        calls.append(source)
        _populate_source_install(target)

    monkeypatch.setattr(installer_module, "_pip_install_source", _fake_install)

    result = await installer.install_from_url("https://github.com/example/demo-tools")

    assert result.package == "demo_tools"
    assert result.version == "1.2.3"
    assert calls == ["git+https://github.com/example/demo-tools.git"]
    assert (tool_store / "demo_tools" / "1.2.3" / "demo_tools" / "__init__.py").exists()
    registry.index_package.assert_called_once()


async def test_install_from_url_accepts_gitlab_url(
    installer: PypiPackageInstaller,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []

    def _fake_install(source: str, target: Path) -> None:
        calls.append(source)
        _populate_source_install(target)

    monkeypatch.setattr(installer_module, "_pip_install_source", _fake_install)

    await installer.install_from_url("https://gitlab.com/example/demo-tools.git")

    assert calls == ["git+https://gitlab.com/example/demo-tools.git"]


async def test_install_from_url_preserves_repository_url_fragment(
    installer: PypiPackageInstaller,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []

    def _fake_install(source: str, target: Path) -> None:
        calls.append(source)
        _populate_source_install(target)

    monkeypatch.setattr(installer_module, "_pip_install_source", _fake_install)

    await installer.install_from_url(
        "https://github.com/example/demo-tools#subdirectory=tools"
    )

    assert calls == [
        "git+https://github.com/example/demo-tools.git#subdirectory=tools"
    ]


async def test_install_from_url_rejects_non_github_gitlab_url(
    installer: PypiPackageInstaller,
):
    with pytest.raises(installer_module.PackageInvalidError):
        await installer.install_from_url("https://example.com/demo-tools")


async def test_install_from_archive_installs_zip_source(
    installer: PypiPackageInstaller,
    tool_store: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    archive = tool_store / "demo-tools.zip"
    archive.write_bytes(b"zip")
    calls: list[str] = []

    def _fake_install(source: str, target: Path) -> None:
        calls.append(source)
        _populate_source_install(target, dist_name="archive-tools", version="0.4.0", module_name="archive_tools")

    monkeypatch.setattr(installer_module, "_pip_install_source", _fake_install)

    result = await installer.install_from_archive(archive)

    assert result.package == "archive_tools"
    assert result.version == "0.4.0"
    assert calls == [str(archive)]
    assert (tool_store / "archive_tools" / "0.4.0" / "archive_tools" / "__init__.py").exists()


async def test_install_source_without_metadata_raises_not_found(
    installer: PypiPackageInstaller,
    monkeypatch: pytest.MonkeyPatch,
):
    def _fake_install(source: str, target: Path) -> None:
        (target / "demo_tools").mkdir(parents=True)

    monkeypatch.setattr(installer_module, "_pip_install_source", _fake_install)

    with pytest.raises(PackageNotFoundError):
        await installer.install_from_url("https://github.com/example/demo-tools")


async def test_install_source_without_expected_module_raises_not_found(
    installer: PypiPackageInstaller,
    monkeypatch: pytest.MonkeyPatch,
):
    def _fake_install(source: str, target: Path) -> None:
        _populate_source_install(target, module_name="other_module")

    monkeypatch.setattr(installer_module, "_pip_install_source", _fake_install)

    with pytest.raises(PackageNotFoundError):
        await installer.install_from_url("https://github.com/example/demo-tools")


async def test_install_source_failure_resumes_hot_reload_false(
    installer_with_hot_reload: PypiPackageInstaller,
    hot_reload: _FakeHotReload,
    monkeypatch: pytest.MonkeyPatch,
):
    def _fake_install(source: str, target: Path) -> None:
        raise RuntimeError("network timeout")

    monkeypatch.setattr(installer_module, "_pip_install_source", _fake_install)

    with pytest.raises(PackageNetworkError):
        await installer_with_hot_reload.install_from_url("https://github.com/example/demo-tools")

    assert ("suppress", None) in hot_reload.calls
    assert ("resume", False) in hot_reload.calls
    assert ("resume", True) not in hot_reload.calls


async def test_source_install_uses_orchestrator_python_and_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = MagicMock()
    monkeypatch.setattr(installer_module.subprocess, "run", run)
    target = tmp_path / "site"

    installer_module._pip_install_source("git+https://example.test/tools.git", target)

    run.assert_called_once_with(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(target),
            "git+https://example.test/tools.git",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# uninstall()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", [
    "absolute_version", "absolute_package", "traversal_version", "traversal_package",
    "backslash", "drive", "empty", "dot", "hidden", "nul", "padded",
    "symlink_package", "symlink_version", "file_version",
])
async def test_uninstall_rejects_unowned_target(
    case: str,
    installer_with_hot_reload: PypiPackageInstaller,
    tool_store: Path,
    registry: MagicMock,
    hot_reload: _FakeHotReload,
    monkeypatch: pytest.MonkeyPatch,
):
    unrelated = tool_store.parent / "unrelated"
    unrelated.mkdir()
    sentinel = unrelated / "sentinel"
    sentinel.write_bytes(b"unrelated bytes")
    sibling = tool_store / "foo" / "1.0" / "sentinel"
    sibling.parent.mkdir(parents=True)
    sibling.write_bytes(b"installed sibling")
    attempted: list[object] = []
    monkeypatch.setattr(installer_module, "_remove_tree", attempted.append)
    package, version = "foo", "1.0"
    if case == "absolute_package":
        package, version = str(unrelated), None
    elif case == "traversal_package":
        package, version = "../unrelated", None
    elif case == "symlink_package":
        package = "linked"
        (tool_store / package).symlink_to(unrelated, target_is_directory=True)
    elif case in {"symlink_version", "file_version"}:
        version = "selected"
        entry = tool_store / package / version
        if case == "symlink_version":
            entry.symlink_to(sibling.parent, target_is_directory=True)
        else:
            entry.write_bytes(b"not a directory")
    else:
        version = {
            "absolute_version": str(unrelated), "traversal_version": "../../unrelated",
            "backslash": "..\\unrelated", "drive": "C:unrelated", "empty": "",
            "dot": ".", "hidden": ".hidden", "nul": "1\x00", "padded": " 1.0",
        }[case]

    with pytest.raises(PackageInvalidError):
        await installer_with_hot_reload.uninstall(package, version)

    assert attempted == []
    assert hot_reload.calls == []
    registry.forget_package.assert_not_called()
    registry.scan_tool_store.assert_not_called()
    assert sentinel.read_bytes() == b"unrelated bytes"
    assert sibling.read_bytes() == b"installed sibling"


@pytest.mark.parametrize("changed", ["root", "package", "version"])
async def test_uninstall_rechecks_ancestor_and_target_at_worker_entry(
    changed: str, installer_with_hot_reload: PypiPackageInstaller, tool_store: Path,
    registry: MagicMock, hot_reload: _FakeHotReload, monkeypatch: pytest.MonkeyPatch,
):
    selected = tool_store / "foo" / "1.0"
    selected.mkdir(parents=True)
    (selected / "sentinel").write_bytes(b"original")
    remove = installer_module._remove_tree
    old = tool_store.parent / "old"

    def substitute_then_remove(selection):
        if changed == "version":
            selected.rename(old)
            selected.mkdir()
        elif changed == "root":
            tool_store.rename(old)
            tool_store.mkdir()
            # Preserve package and selected inodes: only the root changes.
            (old / "foo").rename(tool_store / "foo")
        else:
            (tool_store / "foo").rename(old)
            selected.mkdir(parents=True)
            # Retain the selected version inode to distinguish ancestor ownership.
            selected.rmdir()
            (old / "1.0").rename(selected)
        (selected / "replacement").write_bytes(b"replacement")
        remove(selection)

    monkeypatch.setattr(installer_module, "_remove_tree", substitute_then_remove)
    with pytest.raises(PackageInvalidError, match="changed"):
        await installer_with_hot_reload.uninstall("foo", "1.0")
    assert (selected / "replacement").read_bytes() == b"replacement"
    original = old / "sentinel" if changed == "version" else selected / "sentinel"
    assert original.read_bytes() == b"original"
    registry.forget_package.assert_called_once_with("foo", "1.0")
    registry.index_package.assert_not_called()
    assert hot_reload.calls == [("suppress", None), ("resume", False)]


@pytest.mark.parametrize("redirected", ["package", "version"])
async def test_uninstall_rejects_redirected_directory(
    redirected: str, installer_with_hot_reload: PypiPackageInstaller, tool_store: Path,
    registry: MagicMock, hot_reload: _FakeHotReload, monkeypatch: pytest.MonkeyPatch,
):
    selected = tool_store / "foo" / "1.0"
    selected.mkdir(parents=True)
    (selected / "sentinel").write_bytes(b"selected")
    outside = tool_store.parent / "unrelated"
    outside.mkdir()
    (outside / "sentinel").write_bytes(b"unrelated")
    redirected_path = selected.parent if redirected == "package" else selected
    resolve = Path.resolve

    def redirected_resolution(path: Path, strict: bool = False) -> Path:
        # Model directory redirection (e.g. a junction) that lstat reports as
        # a directory. No native junction or outside-root removal is performed.
        if path == redirected_path:
            return outside
        return resolve(path, strict=strict)

    attempted: list[object] = []
    monkeypatch.setattr(Path, "resolve", redirected_resolution)
    monkeypatch.setattr(installer_module, "_remove_tree", attempted.append)
    with pytest.raises(PackageInvalidError):
        await installer_with_hot_reload.uninstall("foo", "1.0")
    assert attempted == []
    assert hot_reload.calls == []
    registry.forget_package.assert_not_called()
    registry.scan_tool_store.assert_not_called()
    assert (selected / "sentinel").read_bytes() == b"selected"
    assert (outside / "sentinel").read_bytes() == b"unrelated"


@pytest.mark.parametrize("outcome", ["unchanged", "replacement", "missing"])
async def test_uninstall_trash_failure_rechecks_before_fallback(
    outcome: str, installer: PypiPackageInstaller, tool_store: Path,
    registry: MagicMock, monkeypatch: pytest.MonkeyPatch,
):
    selected = tool_store / "foo" / "1.0"
    selected.mkdir(parents=True)
    (selected / "sentinel").write_bytes(b"original")
    old = tool_store.parent / "moved"

    def failed_trash(target: str):
        assert Path(target) == selected
        if outcome != "unchanged":
            selected.rename(old)
        if outcome == "replacement":
            selected.mkdir()
            (selected / "sentinel").write_bytes(b"replacement")
        raise OSError("trash failed")

    monkeypatch.setattr(installer_module, "send2trash", failed_trash)
    if outcome == "unchanged":
        await installer.uninstall("foo", "1.0")
        assert not selected.exists()
        registry.forget_package.assert_called_once_with("foo", "1.0")
    else:
        with pytest.raises(PackageInvalidError, match="changed"):
            await installer.uninstall("foo", "1.0")
        assert (old / "sentinel").read_bytes() == b"original"
        if outcome == "replacement":
            assert (selected / "sentinel").read_bytes() == b"replacement"
        registry.forget_package.assert_called_once_with("foo", "1.0")


async def test_uninstall_removal_failure_can_retry_same_owned_target(
    installer_with_hot_reload: PypiPackageInstaller, tool_store: Path, registry: MagicMock,
    hot_reload: _FakeHotReload, monkeypatch: pytest.MonkeyPatch,
):
    selected = tool_store / "foo" / "1.0"
    selected.mkdir(parents=True)
    (selected / "sentinel").write_bytes(b"original")
    trash = installer_module.send2trash
    remove = installer_module.shutil.rmtree

    def fail(*args):
        raise OSError("removal denied")

    monkeypatch.setattr(installer_module, "send2trash", fail)
    monkeypatch.setattr(installer_module.shutil, "rmtree", fail)
    with pytest.raises(OSError, match="removal denied"):
        await installer_with_hot_reload.uninstall("foo", "1.0")
    assert (selected / "sentinel").read_bytes() == b"original"
    registry.forget_package.assert_called_once_with("foo", "1.0")
    assert hot_reload.calls == [("suppress", None), ("resume", False)]
    monkeypatch.setattr(installer_module, "send2trash", trash)
    monkeypatch.setattr(installer_module.shutil, "rmtree", remove)
    await installer_with_hot_reload.uninstall("foo", "1.0")
    assert not selected.exists()
    assert registry.forget_package.call_count == 2
    assert hot_reload.calls[-2:] == [("suppress", None), ("uninstall:foo@1.0", None)]


async def test_uninstall_configured_root_link_preserves_exact_stored_version(
    tool_store: Path, registry: MagicMock, pypi: AsyncMock,
):
    configured = tool_store.parent / "configured"
    configured.symlink_to(tool_store, target_is_directory=True)
    for version in ["1.0", "1.0.0", "legacy-build+label"]:
        target = tool_store / "foo" / version
        target.mkdir(parents=True)
        (target / "__init__.py").write_text("raise RuntimeError('broken import')")
    installer = PypiPackageInstaller(configured, registry, pypi)
    await installer.uninstall("foo", "1.0")
    assert not (tool_store / "foo" / "1.0").exists()
    assert (tool_store / "foo" / "1.0.0").is_dir()
    await installer.uninstall("foo", "legacy-build+label")
    assert not (tool_store / "foo" / "legacy-build+label").exists()
    assert configured.is_symlink()
    pypi.get_latest_stable.assert_not_awaited()


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
    registry.scan_tool_store.assert_not_called()


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
    """Records package-operation lifecycle calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, bool | None]] = []

    def suppress(self) -> None:
        self.calls.append(("suppress", None))

    def resume(self, emit_batch: bool = True) -> None:
        self.calls.append(("resume", emit_batch))

    async def resume_after_install(self, package: str, version: str) -> None:
        self.calls.append((f"install:{package}@{version}", None))

    async def resume_after_uninstall(self, package: str, versions: list[str]) -> None:
        self.calls.append((f"uninstall:{package}@{','.join(versions)}", None))


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


async def test_install_success_suppresses_then_indexes_installed_version(
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

    assert hot_reload.calls == [
        ("suppress", None),
        ("install:foo@1.0", None),
    ]


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

    assert hot_reload.calls == [("suppress", None), ("uninstall:foo@1.0", None)]


async def test_uninstall_missing_target_does_not_suppress(
    installer_with_hot_reload: PypiPackageInstaller,
    hot_reload: _FakeHotReload,
):
    with pytest.raises(PackageNotFoundError):
        await installer_with_hot_reload.uninstall("ghost", "1.0")

    # Missing targets are refused during admission, before suppression begins.
    assert hot_reload.calls == []


async def test_install_uses_hot_reload_indexing_instead_of_full_store_scan(
    installer_with_hot_reload: PypiPackageInstaller,
    registry: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
):
    """The awaited hot-reload path performs the targeted load and index."""
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

    registry.index_package.assert_called_once()


async def test_uninstall_skips_scan_tool_store_when_hot_reload_wired(
    installer_with_hot_reload: PypiPackageInstaller,
    tool_store: Path,
    registry: MagicMock,
):
    pkg_root = tool_store / "foo" / "1.0"
    (pkg_root / "foo").mkdir(parents=True)

    await installer_with_hot_reload.uninstall("foo", "1.0")

    registry.scan_tool_store.assert_not_called()


async def test_uninstall_updates_registry_without_full_scan(
    installer: PypiPackageInstaller,
    tool_store: Path,
    registry: MagicMock,
):
    pkg_root = tool_store / "foo" / "1.0"
    (pkg_root / "foo").mkdir(parents=True)

    await installer.uninstall("foo", "1.0")

    registry.scan_tool_store.assert_not_called()
    registry.forget_package.assert_called_once_with("foo", "1.0")


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

    def _slow_ensure(pkg_name, version, pypi_name, store_path, **kwargs) -> None:
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


async def test_selected_install_index_failure_is_invalid_with_original_detail(
    installer, registry, monkeypatch,
):
    monkeypatch.setattr(installer_module, "ensure_installed", _ensure_installed_success_factory([]))
    registry.index_package.side_effect = ImportError("host dependency conflict: expected core 0.5")
    with pytest.raises(PackageInvalidError, match="host dependency conflict: expected core 0.5"):
        await installer.install("foo", "1.0")


async def test_retirement_refusal_precedes_suppression_and_physical_removal(
    installer_with_hot_reload, tool_store, registry, hot_reload, monkeypatch,
):
    selected = tool_store / "foo" / "1.0"
    selected.mkdir(parents=True)
    (selected / "sentinel").write_text("unchanged")
    retirement = MagicMock(side_effect=RuntimeError("active admitted operations still own this generation"))
    monkeypatch.setattr(installer_module, "versioned_package_mutation", retirement)
    removal = MagicMock()
    monkeypatch.setattr(installer_module, "_remove_tree", removal)
    with pytest.raises(PackageInvalidError, match="active admitted operations"):
        await installer_with_hot_reload.uninstall("foo", "1.0")
    retirement.assert_called_once_with([("foo", "1.0")], tool_store)
    assert (selected / "sentinel").read_text() == "unchanged"
    removal.assert_not_called()
    registry.forget_package.assert_not_called()
    assert hot_reload.calls == []


async def test_whole_package_retirement_preflights_all_supported_versions(
    installer, tool_store, monkeypatch,
):
    for version in ["1.0", "2.0", "legacy-build+label"]:
        (tool_store / "foo" / version).mkdir(parents=True)
    retirement = MagicMock()
    monkeypatch.setattr(installer_module, "versioned_package_mutation", retirement)
    await installer.uninstall("foo")
    pairs, root = retirement.call_args.args
    assert set(pairs) == {("foo", "1.0"), ("foo", "2.0")}
    assert root == tool_store
    assert not (tool_store / "foo").exists()


def _write_retained_package(tool_store: Path, package: str, version: str) -> Path:
    from tests.fixtures.package_metadata import write_package_metadata

    source = tool_store / package / version / package
    source.mkdir(parents=True)
    (source / "__init__.py").write_text(
        "from bioimageflow_core import ProcessingTool, EnvironmentSpec, IOModel, RowConsumption\n"
        "class Retained(ProcessingTool):\n"
        "    environment = EnvironmentSpec(name='declared', dependencies={'pip': []})\n"
        "    row_consumption = RowConsumption.MAPPED\n"
        "    class Outputs(IOModel):\n"
        "        result: str\n"
        "    def process_row(self, arguments):\n"
        "        raise AssertionError('Uninstall must not run scientific callbacks')\n"
    )
    write_package_metadata(source, version)
    return source


async def test_real_admitted_operation_blocks_uninstall_until_release(tool_store, pypi):
    from bioimageflow.cache.identity import deterministic_serialize
    from bioimageflow.worker_origins import ExecutableMetadata, capture_tool_executable
    from bioimageflow.tool_loader import unload_versioned_package

    package, version = "platform_active_uninstall", "1.0"
    source = _write_retained_package(tool_store, package, version)
    registry = ToolRegistryService()
    registry.scan_tool_store(tool_store)
    installer = PypiPackageInstaller(tool_store, registry, pypi)
    klass = registry.get_tool_class("Retained")
    operation = ExecutableMetadata()
    try:
        capture_tool_executable(klass(), managed=True, canonicalize=deterministic_serialize, metadata=operation)
        with pytest.raises(PackageInvalidError, match="active admitted operations"):
            await installer.uninstall(package, version)
        assert source.is_dir()
        assert registry.get_tool_class("Retained") is klass
        operation.clear()
        await installer.uninstall(package, version)
        assert not source.exists()
        assert registry.get_tool_class("Retained") is None
        with pytest.raises(RuntimeError, match="retired.*recompile"):
            capture_tool_executable(klass(), managed=True, canonicalize=deterministic_serialize, metadata=operation)
    finally:
        operation.clear()
        unload_versioned_package(package, version, tool_store)


async def test_carried_workflow_get_cannot_readmit_during_physical_uninstall(tool_store, pypi, tmp_path, monkeypatch):
    import asyncio
    import threading

    import httpx
    from bioimageflow.tool_loader import load_versioned_package, unload_versioned_package
    from bioimageflow_server.app import create_app
    from bioimageflow_server.models.tools import AppConfig
    from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowSaveBody
    from bioimageflow_server.services.workflow_store import WorkflowStoreService
    from tests.graph_factory import graph_state

    package, version = "platform_reserved_uninstall", "1.0"
    source = _write_retained_package(tool_store, package, version)
    registry = ToolRegistryService()
    registry.scan_tool_store(tool_store)
    workflows = WorkflowStoreService(tmp_path / "workspace" / "workflows", registry)
    workflows.create_workflow(WorkflowCreate(name="Carried"))
    workflows.save_workflow("Carried", WorkflowSaveBody(graph=graph_state(nodes=[{
        "type": "tool", "id": "subject", "name": "Subject", "tool_name": "Retained",
        "position": [0, 0], "parameters": {}, "tool_module": package,
        "tool_class": "Retained", "tool_package": package, "tool_package_version": version,
    }])))
    installer = PypiPackageInstaller(tool_store, registry, pypi)
    app = create_app(AppConfig(
        tool_registry=registry, workflow_store=workflows,
        workflow_root=workflows.root_dir, workspace_path=workflows.workspace_dir,
        package_installer=installer, disable_hot_reload=True,
    ))
    entered, release = threading.Event(), threading.Event()
    remove = installer_module._remove_tree

    def paused_remove(selection):
        entered.set()
        if not release.wait(timeout=5):
            raise AssertionError("Test did not release physical package removal")
        remove(selection)

    monkeypatch.setattr(installer_module, "_remove_tree", paused_remove)
    task = None
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            initial = await client.get("/api/v1/workflows/Carried")
            assert initial.status_code == 200 and initial.json()["missing_tools"] == []
            task = asyncio.create_task(installer.uninstall(package, version))
            assert await asyncio.to_thread(entered.wait, 3)
            # The directory still exists, but retirement reserves its namespace
            # until removal and registry publication have physically settled.
            assert source.is_dir()
            during = await client.get("/api/v1/workflows/Carried")
            assert during.status_code == 200
            assert [tool["tool_name"] for tool in during.json()["missing_tools"]] == ["Retained"]
            with pytest.raises(RuntimeError, match="package mutation is in progress"):
                load_versioned_package(package, version, tool_store)
            release.set()
            await task
            assert not source.exists()
            assert registry.get_tool_class("Retained") is None
    finally:
        release.set()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        unload_versioned_package(package, version, tool_store)


async def test_failed_physical_uninstall_readmits_after_reservation_release(tool_store, pypi, monkeypatch):
    from bioimageflow.tool_loader import unload_versioned_package

    package, version = "platform_failed_uninstall", "1.0"
    source = _write_retained_package(tool_store, package, version)
    registry = ToolRegistryService()
    registry.scan_tool_store(tool_store)
    previous_class = registry.get_tool_class("Retained")
    installer = PypiPackageInstaller(tool_store, registry, pypi)

    def fail_remove(selection):
        raise OSError("original physical removal failure")

    monkeypatch.setattr(installer_module, "_remove_tree", fail_remove)
    try:
        with pytest.raises(OSError, match="original physical removal failure"):
            await installer.uninstall(package, version)
        assert source.is_dir()
        # Recovery needs a new generation, which admission would refuse while
        # the physical mutation namespace was still reserved.
        replacement = registry.get_tool_class("Retained")
        assert replacement is not None and replacement is not previous_class
        assert registry.get_package(package).load_errors == {}
    finally:
        unload_versioned_package(package, version, tool_store)


@pytest.mark.parametrize("partially_removed", [False, True])
async def test_failed_uninstall_preserves_active_version_only_for_unchanged_selection(
    partially_removed, tool_store, pypi, monkeypatch,
):
    import shutil
    from bioimageflow.tool_loader import unload_versioned_packages

    package = "platform_active_recovery"
    source = _write_retained_package(tool_store, package, "1.0")
    _write_retained_package(tool_store, package, "2.0")
    registry = ToolRegistryService()
    registry.scan_tool_store(tool_store)
    registry.set_active_version(package, "1.0")
    previous_class = registry.get_tool_class("Retained")
    installer = PypiPackageInstaller(tool_store, registry, pypi)

    def fail_remove(selection):
        if partially_removed:
            shutil.rmtree(selection.target)
        raise OSError("original physical removal failure")

    monkeypatch.setattr(installer_module, "_remove_tree", fail_remove)
    try:
        with pytest.raises(OSError, match="original physical removal failure"):
            await installer.uninstall(package, "1.0")
        expected = "2.0" if partially_removed else "1.0"
        assert source.exists() == (not partially_removed)
        assert registry.get_package(package).active_version == expected
        assert registry.get_tool("Retained").package_version == expected
        replacement = registry.get_tool_class("Retained")
        assert replacement is not previous_class
        assert replacement._bif_package_version == expected
    finally:
        unload_versioned_packages([(package, "1.0"), (package, "2.0")], tool_store)
