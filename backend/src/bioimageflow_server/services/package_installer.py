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
import shutil
from pathlib import Path
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


class PackageInstallerService:
    """DI contract for package install/uninstall.

    Subclass to provide real behaviour; tests typically inject an
    :class:`unittest.mock.AsyncMock` with this spec.
    """

    async def install(self, package_name: str, version: str | None = None) -> None:
        raise NotImplementedError

    async def uninstall(self, package_name: str, version: str | None = None) -> None:
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

    async def install(self, package_name: str, version: str | None = None) -> None:
        if version is None:
            version = await self._pypi.get_latest_stable(package_name)

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
            raise cls(f"Failed to install {package_name}=={version}: {message}") from exc

        self._registry.scan_tool_store(self._tool_store)

    async def uninstall(self, package_name: str, version: str | None = None) -> None:
        pkg_root = self._tool_store / package_name
        if version is None:
            target: Path = pkg_root
        else:
            target = pkg_root / version

        if not target.exists():
            raise PackageNotFoundError(
                f"Package '{package_name}'"
                + (f"=={version}" if version else "")
                + " is not installed"
            )

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
        self._registry.forget_package(package_name, version)
        self._registry.scan_tool_store(self._tool_store)
