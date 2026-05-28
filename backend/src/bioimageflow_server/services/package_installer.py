"""Package install/uninstall service (spec v3 §2.5, specs.md §Tool Store).

:class:`PackageInstallerService` is the abstract DI contract. The real
implementation, :class:`PypiPackageInstaller`, delegates to
:func:`bioimageflow.tool_loader.ensure_installed`, which runs
``pip install --target <tool_store>/<pkg>/<version>/`` through Wetlands'
shared pixi-backed :class:`EnvironmentManager` (no system ``uv`` or ``pip``
required on ``PATH``). The registry is re-scanned on success.
"""

from __future__ import annotations

import logging
import re
import shlex
import shutil
import tempfile
import tomllib
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from typing import TYPE_CHECKING

import anyio
import anyio.to_thread as anyio_to_thread
from send2trash import send2trash

from bioimageflow.tool_loader import ensure_installed

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
    """Raised when an import source is not a supported package source."""


@dataclass(frozen=True)
class PackageInstallResult:
    package: str
    version: str


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
    """Install/uninstall packages via bioimageflow's Wetlands-backed installer.

    Delegates to :func:`bioimageflow.tool_loader.ensure_installed`, which
    runs ``pip install --target <target>`` through the shared Wetlands pixi
    :class:`~wetlands.environment_manager.EnvironmentManager`. This matches
    the mechanism used by :func:`bioimageflow.tool_loader.load_versioned_package`
    so installed packages are layout-compatible with the rest of the library.
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
            if package_name == "bioimageflow_common_tools":
                await self._install_local_common_tools()
                return

            if version is None:
                version = await self._pypi.get_latest_stable(package_name)

            if self._hot_reload is not None:
                self._hot_reload.suppress()

            try:
                try:
                    await anyio_to_thread.run_sync(
                        ensure_installed,
                        package_name,
                        version,
                        _pypi_name(package_name),
                        self._tool_store,
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

            if self._hot_reload is not None:
                # resume(emit_batch=True) discovers the new (pkg, ver) pair
                # and broadcasts one tool_reload per discovered tool.
                self._hot_reload.resume(emit_batch=True)
            else:
                await anyio_to_thread.run_sync(
                    self._registry.scan_tool_store, self._tool_store
                )

    async def _install_local_common_tools(self) -> None:
        source_root = _local_common_tools_root()
        if source_root is None:
            raise PackageNotFoundError("Local bioimageflow-common-tools checkout not found")
        version = _project_version(source_root)
        package_name = "bioimageflow_common_tools"
        target_root = self._tool_store / package_name / version
        target_package = target_root / package_name

        if self._hot_reload is not None:
            self._hot_reload.suppress()

        try:
            if target_root.exists():
                await anyio_to_thread.run_sync(shutil.rmtree, target_root)
            await anyio_to_thread.run_sync(
                shutil.copytree,
                source_root / package_name,
                target_package,
            )
        except Exception:
            if self._hot_reload is not None:
                self._hot_reload.resume(emit_batch=False)
            raise

        if self._hot_reload is not None:
            self._hot_reload.resume(emit_batch=True)
        else:
            await anyio_to_thread.run_sync(self._registry.scan_tool_store, self._tool_store)


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

            if self._hot_reload is not None:
                self._hot_reload.resume(emit_batch=True)
            else:
                await anyio_to_thread.run_sync(
                    self._registry.scan_tool_store, self._tool_store
                )
            return result

    async def uninstall(self, package_name: str, version: str | None = None) -> None:
        async with self._operation_lock:
            pkg_root = self._tool_store / package_name
            if version is None:
                target: Path = pkg_root
            else:
                target = pkg_root / version

            if self._hot_reload is not None:
                self._hot_reload.suppress()

            try:
                if not target.exists():
                    raise PackageNotFoundError(
                        f"Package '{package_name}'"
                        + (f"=={version}" if version else "")
                        + " is not installed"
                    )

                await anyio_to_thread.run_sync(_remove_tree, target)
                self._registry.forget_package(package_name, version)
            except Exception:
                if self._hot_reload is not None:
                    self._hot_reload.resume(emit_batch=False)
                raise

            if self._hot_reload is not None:
                self._hot_reload.resume(emit_batch=True)
            else:
                await anyio_to_thread.run_sync(
                    self._registry.scan_tool_store, self._tool_store
                )


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

    from bioimageflow.env_manager import get_shared_environment_manager

    manager = get_shared_environment_manager()
    executor = manager.command_executor
    generator = manager.command_generator
    conda_bin = manager.settings_manager.conda_bin

    commands = generator.get_activate_conda_commands()
    commands += [
        f'{conda_bin} exec --spec "pip" -- '
        f'pip install --target {shlex.quote(str(target))} {shlex.quote(source)}'
    ]

    try:
        executor.execute_commands_and_get_output(
            commands, exit_if_command_error=True,
        )
    except Exception as exc:
        shutil.rmtree(target, ignore_errors=True)
        raise RuntimeError(
            f"Failed to install tool package source into tool store.\n{exc}"
        ) from exc


def _remove_tree(target: Path) -> None:
    # send2trash is ~O(1) on macOS (APFS rename into ~/.Trash) vs
    # shutil.rmtree which unlinks every file in the target tree —
    # slow for site-packages-style directories with thousands of files.
    try:
        send2trash(str(target))
    except Exception:
        logger.warning(
            "send2trash failed for %s; falling back to shutil.rmtree",
            target,
            exc_info=True,
        )
        shutil.rmtree(target)


def _local_common_tools_root() -> Path | None:
    root = Path(__file__).resolve()
    for parent in root.parents:
        candidate = parent / "bioimageflow" / "packages" / "bioimageflow-common-tools"
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "bioimageflow_common_tools" / "__init__.py"
        ).is_file():
            return candidate
    return None


def _project_version(project_root: Path) -> str:
    data = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    version = data.get("project", {}).get("version")
    if not isinstance(version, str) or not version:
        raise PackageNotFoundError(f"Cannot read version from {project_root / 'pyproject.toml'}")
    return version
