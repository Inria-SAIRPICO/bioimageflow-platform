"""Package catalog — merges registry (installed) + known list + PyPI versions.

The catalog is the single read model used by ``GET /tools/packages``. It
holds an in-memory snapshot refreshed at server startup, after each
install/uninstall, and on demand via ``POST /tools/packages/refresh`` (spec
v3 §2.5).
"""

from __future__ import annotations

import logging

import anyio
from packaging.version import InvalidVersion, Version, parse as _parse_version

from bioimageflow_server.models.tools import PackageInfo
from bioimageflow_server.services.known_packages import KnownPackagesService
from bioimageflow_server.services.package_installer import (
    PackageNetworkError,
    PackageNotFoundError,
)
from bioimageflow_server.services.pypi_versions import PyPIVersionService
from bioimageflow_server.services.tool_registry import ToolRegistryService

logger = logging.getLogger(__name__)


class PackageCatalogService:
    def __init__(
        self,
        registry: ToolRegistryService,
        known: KnownPackagesService,
        pypi: PyPIVersionService,
    ) -> None:
        self._registry = registry
        self._known = known
        self._pypi = pypi
        self._snapshot: dict[str, PackageInfo] | None = None

    def list_packages(self) -> list[PackageInfo]:
        """Return the latest snapshot (sync, never calls PyPI).

        If :meth:`refresh` has never succeeded, fall back to the raw registry
        view so the app is usable even before the first network call returns.
        """
        if self._snapshot is None:
            return self._registry.list_packages()
        return list(self._snapshot.values())

    async def refresh(self) -> None:
        """Rebuild the snapshot from registry + known list + PyPI.

        PyPI is queried for every name in the union of installed and known
        packages so upgrades for installed-but-unlisted packages are still
        discoverable. Lookups fail-isolated per-name: a 404 or network
        error is logged, and that package falls back to its installed
        versions.
        """
        installed = {pkg.name: pkg for pkg in self._registry.list_packages()}
        known_names = list(self._known.list_known_packages())

        names = list({*installed.keys(), *known_names})

        pypi_versions: dict[str, list[str]] = {name: [] for name in names}

        async def _lookup(name: str) -> None:
            try:
                pypi_versions[name] = list(await self._pypi.get_versions(name))
            except (PackageNetworkError, PackageNotFoundError) as exc:
                logger.warning("PyPI lookup failed for %s: %s", name, exc)
            except Exception as exc:  # noqa: BLE001 — best-effort isolation
                logger.warning("PyPI lookup crashed for %s: %r", name, exc)

        async with anyio.create_task_group() as tg:
            for name in names:
                tg.start_soon(_lookup, name)

        snapshot: dict[str, PackageInfo] = {}
        for name in names:
            base = installed.get(name)
            installed_versions = list(base.installed_versions) if base else []
            tools = dict(base.tools) if base else {}
            env_status = base.environment_status if base else "stopped"

            merged = _merge_versions(installed_versions, pypi_versions.get(name, []))

            snapshot[name] = PackageInfo(
                name=name,
                installed_versions=installed_versions,
                available_versions=merged,
                tools=tools,
                environment_status=env_status,
            )

        self._snapshot = snapshot


def _merge_versions(installed: list[str], available: list[str]) -> list[str]:
    merged = list({*installed, *available})
    merged.sort(key=_version_sort_key)
    return merged


def _version_sort_key(v: str) -> tuple[int, Version | str]:
    try:
        return (0, _parse_version(v))
    except InvalidVersion:
        return (1, v)
