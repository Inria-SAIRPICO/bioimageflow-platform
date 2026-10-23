"""Package install/uninstall service (spec v3 §2.5, specs.md §Tool Store).

:class:`PackageInstallerService` is the abstract DI contract. The real
implementation, :class:`PypiPackageInstaller`, delegates to
:func:`bioimageflow.tool_loader.ensure_installed`. Selected generations are
indexed explicitly after install and retired before removal.
"""

from __future__ import annotations

import logging
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from contextlib import ExitStack
from dataclasses import dataclass
from email.parser import Parser
from functools import partial
from pathlib import Path, PureWindowsPath
from urllib.parse import urlparse, urlunparse
from typing import TYPE_CHECKING

import anyio
import anyio.to_thread as anyio_to_thread
from send2trash import send2trash

from bioimageflow.installation import validate_installation_selectors
from bioimageflow.tool_loader import ensure_installed, versioned_package_mutation

if TYPE_CHECKING:
    from bioimageflow_server.services.pypi_versions import PyPIVersionService
    from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService
    from bioimageflow_server.services.tool_registry import ToolRegistryService

logger = logging.getLogger(__name__)


class PackageNotFoundError(Exception):
    """Raised when a requested package cannot be found."""


class PackageNetworkError(Exception):
    """Raised on network/connectivity errors during install/uninstall."""


class PackageInvalidError(Exception):
    """Raised when a package source or stored removal selection is invalid."""


@dataclass(frozen=True)
class PackageInstallResult:
    package: str
    version: str


@dataclass(frozen=True)
class _UninstallSelection:
    configured_root: Path
    root: Path
    package_name: str
    version: str | None
    target: Path
    root_identity: tuple[int, int]
    package_identity: tuple[int, int]
    target_identity: tuple[int, int]


def _validate_uninstall_component(value: str) -> None:
    if (
        not value
        or value != value.strip()
        or value.startswith(".")
        or "/" in value
        or "\\" in value
        or PureWindowsPath(value).drive
        or any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value)
    ):
        raise PackageInvalidError("Package and version must be exact safe stored names")


def _directory_identity(path: Path) -> tuple[int, int]:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise PackageInvalidError("Selected installed target must be a directory, not a link or file")
    if path.resolve(strict=True) != path:
        raise PackageInvalidError("Selected installed directory has redirected ancestry")
    return info.st_dev, info.st_ino


def _select_uninstall_target(
    configured_root: Path, package_name: str, version: str | None,
) -> _UninstallSelection:
    _validate_uninstall_component(package_name)
    if version is not None:
        _validate_uninstall_component(version)
    try:
        # Configuration-level links are supported; links below this root are not.
        root = configured_root.resolve(strict=True)
        root_identity = _directory_identity(root)
        package = root / package_name
        package_identity = _directory_identity(package)
        target = package if version is None else package / version
        target_identity = _directory_identity(target)
    except FileNotFoundError as exc:
        raise PackageNotFoundError("Selected package version is not installed") from exc
    except (OSError, RuntimeError) as exc:
        raise PackageInvalidError("Cannot safely inspect the selected installed target") from exc
    return _UninstallSelection(
        configured_root, root, package_name, version, target,
        root_identity, package_identity, target_identity,
    )


def _recheck_uninstall_selection(selection: _UninstallSelection) -> None:
    try:
        current = _select_uninstall_target(
            selection.configured_root, selection.package_name, selection.version,
        )
    except PackageNotFoundError as exc:
        raise PackageInvalidError("Selected installed target changed before removal") from exc
    if current != selection:
        raise PackageInvalidError("Selected installed target changed before removal")


class PackageInstallerService:
    """DI contract for package install/uninstall.

    Subclass to provide real behaviour; tests typically inject an
    :class:`unittest.mock.AsyncMock` with this spec.
    """

    async def install(self, package_name: str, version: str | None = None) -> None:
        raise NotImplementedError

    async def uninstall(self, package_name: str, version: str | None = None) -> None:
        raise NotImplementedError

    async def install_from_url(self, url: str) -> PackageInstallResult:
        raise NotImplementedError

    async def install_from_archive(self, archive_path: Path) -> PackageInstallResult:
        raise NotImplementedError


def _pypi_name(name: str) -> str:
    return name.replace("_", "-")


_NOT_FOUND_MARKERS = (
    "no matching distribution",
    "could not find a version",
    "no versions found",
    "not found in",
)
_NETWORK_MARKERS = (
    "network",
    "timeout",
    "failed to fetch",
    "could not resolve",
    "connection",
    "dns",
)


def _classify_failure(message: str) -> type[Exception]:
    lowered = message.lower()
    if any(marker in lowered for marker in _NOT_FOUND_MARKERS):
        return PackageNotFoundError
    if any(marker in lowered for marker in _NETWORK_MARKERS):
        return PackageNetworkError
    # Unrecognised failure: default to network error so the router returns 502
    # (a 404 would falsely claim the package doesn't exist).
    return PackageNetworkError


class PypiPackageInstaller(PackageInstallerService):
    """Install and uninstall packages through BioImageFlow's tool loader.

    Delegates to :func:`bioimageflow.tool_loader.ensure_installed`, which
    uses the orchestrator interpreter and creates the layout consumed by
    :func:`bioimageflow.tool_loader.load_versioned_package`.
    """

    def __init__(
        self,
        tool_store: Path,
        registry: "ToolRegistryService",
        pypi: "PyPIVersionService",
        hot_reload: "ToolHotReloadService | None" = None,
    ) -> None:
        self._tool_store = tool_store
        self._registry = registry
        self._pypi = pypi
        self._hot_reload = hot_reload
        self._operation_lock = anyio.Lock()

    async def install(self, package_name: str, version: str | None = None) -> None:
        async with self._operation_lock:
            if version is None:
                version = await self._pypi.get_latest_stable(package_name)

            if self._hot_reload is not None:
                self._hot_reload.suppress()

            try:
                try:
                    await anyio_to_thread.run_sync(
                        partial(
                            ensure_installed, package_name, version,
                            _pypi_name(package_name), self._tool_store,
                            install_dependencies=False,
                        ),
                    )
                except PackageNotFoundError:
                    raise
                except PackageNetworkError:
                    raise
                except Exception as exc:  # noqa: BLE001 — classify then re-raise
                    message = str(exc)
                    logger.warning(
                        "Wetlands install failed for %s==%s: %s",
                        package_name,
                        version,
                        message,
                    )
                    cls = _classify_failure(message)
                    raise cls(
                        f"Failed to install {package_name}=={version}: {message}"
                    ) from exc
            except Exception:
                if self._hot_reload is not None:
                    self._hot_reload.resume(emit_batch=False)
                raise

            await self._index_installed(package_name, version)

    async def _index_installed(self, package_name: str, version: str) -> None:
        try:
            if self._hot_reload is not None:
                await self._hot_reload.resume_after_install(package_name, version)
            else:
                await anyio_to_thread.run_sync(
                    self._registry.index_package, package_name, version, self._tool_store,
                )
        except Exception as exc:
            if self._hot_reload is not None:
                self._hot_reload.resume(emit_batch=False)
            raise PackageInvalidError(
                f"Installed {package_name}=={version} could not load: {exc}"
            ) from exc

    async def install_from_url(self, url: str) -> PackageInstallResult:
        source = _normalize_repository_source(url)
        return await self._install_from_source(source)

    async def install_from_archive(self, archive_path: Path) -> PackageInstallResult:
        if archive_path.suffix.lower() != ".zip":
            raise PackageInvalidError("Tool package archive must be a .zip file")
        return await self._install_from_source(str(archive_path))

    async def _install_from_source(self, source: str) -> PackageInstallResult:
        async with self._operation_lock:
            staging_parent = Path(tempfile.mkdtemp(prefix="bif-tool-package-"))
            staging = staging_parent / "site"

            if self._hot_reload is not None:
                self._hot_reload.suppress()

            try:
                try:
                    await anyio_to_thread.run_sync(_pip_install_source, source, staging)
                except PackageNotFoundError:
                    raise
                except PackageNetworkError:
                    raise
                except Exception as exc:  # noqa: BLE001 — classify then re-raise
                    message = str(exc)
                    logger.warning("Source package install failed for %s: %s", source, message)
                    cls = _classify_failure(message)
                    raise cls(f"Failed to install tool package source: {message}") from exc

                result = _discover_source_install(staging)
                expected_package = staging / result.package
                if not expected_package.exists():
                    raise PackageNotFoundError(
                        f"Installation succeeded but expected module '{result.package}' "
                        f"was not found in {staging}"
                    )

                target = self._tool_store / result.package / result.version
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    await anyio_to_thread.run_sync(shutil.move, str(staging), str(target))
                # Versioned package directories are immutable. Re-importing an
                # already installed package/version is a successful no-op, but
                # still resumes hot reload and refreshes the registry below.
            except Exception:
                if self._hot_reload is not None:
                    self._hot_reload.resume(emit_batch=False)
                raise
            finally:
                await anyio_to_thread.run_sync(shutil.rmtree, staging_parent, True)

            await self._index_installed(result.package, result.version)
            return result

    async def uninstall(self, package_name: str, version: str | None = None) -> None:
        async with self._operation_lock:
            selection = _select_uninstall_target(self._tool_store, package_name, version)

            versions = [version] if version is not None else [
                child.name for child in selection.target.iterdir()
                if child.is_dir() and not child.is_symlink()
            ]
            # Safe legacy directory names remain removable even if the SDK
            # cannot interpret them as Python package/version selectors.
            selectors = []
            for selected_version in versions:
                try:
                    validate_installation_selectors(package_name, selected_version, None)
                except ValueError:
                    continue
                selectors.append((package_name, selected_version))
            previous_package = self._registry.get_package(package_name)
            previous_active = (
                previous_package.active_version
                if previous_package is not None and isinstance(previous_package.active_version, str)
                else None
            )
            entered = False
            try:
                with ExitStack() as mutation:
                    try:
                        # Retirement and namespace reservation are one atomic
                        # entry. Concurrent workflow reads cannot re-admit the
                        # package while offloaded removal is still pending.
                        mutation.enter_context(versioned_package_mutation(selectors, selection.root))
                    except Exception as exc:
                        raise PackageInvalidError(str(exc)) from exc
                    entered = True
                    if self._hot_reload is not None:
                        self._hot_reload.suppress()
                    await anyio_to_thread.run_sync(_remove_tree, selection)
                    self._registry.forget_package(package_name, version)
            except Exception:
                if entered:
                    # Recovery runs after releasing the namespace reservation.
                    # It may re-admit only the unchanged owned selection and
                    # must preserve the original removal error.
                    try:
                        self._registry.forget_package(package_name, version)
                        _recheck_uninstall_selection(selection)
                        for _, selected_version in selectors:
                            self._registry.index_package(package_name, selected_version, selection.root)
                        current_package = self._registry.get_package(package_name)
                        if (
                            previous_active is not None and current_package is not None
                            and current_package.active_version != previous_active
                        ):
                            self._registry.set_active_version(package_name, previous_active)
                    except Exception:
                        logger.exception("Could not re-index package after failed removal")
                    if self._hot_reload is not None:
                        self._hot_reload.resume(emit_batch=False)
                raise
            if self._hot_reload is not None:
                await self._hot_reload.resume_after_uninstall(package_name, versions)


def _normalize_repository_source(url: str) -> str:
    source = url.strip()
    if source.startswith("git+https://"):
        parsed = urlparse(source.removeprefix("git+"))
    else:
        parsed = urlparse(source)

    host = parsed.netloc.lower().removeprefix("www.")
    if parsed.scheme != "https" or host not in {"github.com", "gitlab.com"}:
        raise PackageInvalidError(
            "Tool package URL must be an HTTPS GitHub or GitLab repository URL"
        )

    if source.startswith("git+"):
        return source

    path = parsed.path.rstrip("/")
    if not path.endswith(".git"):
        path = f"{path}.git"
    cleaned = urlunparse(parsed._replace(path=path))
    return f"git+{cleaned}"


def _normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-.]+", "_", name).lower()


def _discover_source_install(target: Path) -> PackageInstallResult:
    dist_infos = sorted(target.glob("*.dist-info"))
    if not dist_infos:
        raise PackageNotFoundError("Installed source did not contain package metadata")
    preferred = [path for path in dist_infos if (path / "direct_url.json").exists()]
    metadata_roots = preferred or dist_infos
    for dist_info in metadata_roots:
        metadata_path = dist_info / "METADATA"
        if not metadata_path.exists():
            continue
        metadata = Parser().parsestr(metadata_path.read_text(encoding="utf-8"))
        name = metadata.get("Name")
        version = metadata.get("Version")
        if name and version:
            return PackageInstallResult(
                package=_normalize_distribution_name(name),
                version=version,
            )
    raise PackageNotFoundError("Installed source did not contain package name/version metadata")


def _pip_install_source(source: str, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                str(target),
                source,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        shutil.rmtree(target, ignore_errors=True)
        details = (
            exc.stderr.strip()
            if isinstance(exc, subprocess.CalledProcessError) and exc.stderr
            else str(exc)
        )
        raise RuntimeError(
            f"Failed to install tool package source into tool store.\n{details}"
        ) from exc


def _remove_tree(selection: _UninstallSelection) -> None:
    # send2trash is ~O(1) on macOS (APFS rename into ~/.Trash) vs
    # shutil.rmtree which unlinks every file in the target tree —
    # slow for site-packages-style directories with thousands of files.
    _recheck_uninstall_selection(selection)
    try:
        send2trash(str(selection.target))
    except Exception:
        # A failed trash call may already have moved the target or an ancestor.
        # Never replay removal against a replacement or newly selected path.
        _recheck_uninstall_selection(selection)
        logger.warning(
            "send2trash failed for %s; falling back to shutil.rmtree",
            selection.target,
            exc_info=True,
        )
        shutil.rmtree(selection.target)
