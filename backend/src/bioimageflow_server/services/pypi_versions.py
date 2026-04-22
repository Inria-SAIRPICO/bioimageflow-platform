"""PyPI version lookup for BioImageFlow tool packages.

See spec v3 §2.5 "Available Package Versions and Known Packages Registry".
Fetches ``https://pypi.org/pypi/{pypi_name}/json`` and returns the full
``releases`` list sorted with :func:`packaging.version.parse`. Python module
names with underscores are normalized to PyPI's hyphen form (e.g.
``bioimageflow_core`` → ``bioimageflow-core``).
"""

from __future__ import annotations

import logging

import httpx
from packaging.version import InvalidVersion, Version, parse as _parse_version

from bioimageflow_server.services.package_installer import (
    PackageNetworkError,
    PackageNotFoundError,
)

logger = logging.getLogger(__name__)


def _pypi_name(name: str) -> str:
    return name.replace("_", "-")


class PyPIVersionService:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        base_url: str = "https://pypi.org/pypi",
        timeout: float = 10.0,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._base_url = base_url.rstrip("/")

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_versions(self, package_name: str) -> list[str]:
        url = f"{self._base_url}/{_pypi_name(package_name)}/json"
        try:
            response = await self._client.get(url)
        except (httpx.TimeoutException, httpx.TransportError, httpx.NetworkError) as exc:
            raise PackageNetworkError(f"PyPI unreachable for {package_name}: {exc}") from exc
        if response.status_code == 404:
            raise PackageNotFoundError(f"Package '{package_name}' not found on PyPI")
        if response.status_code >= 400:
            raise PackageNetworkError(
                f"PyPI returned {response.status_code} for {package_name}"
            )
        try:
            releases = response.json().get("releases", {})
        except ValueError as exc:
            raise PackageNetworkError(
                f"PyPI returned invalid JSON for {package_name}: {exc}"
            ) from exc

        versions = list(releases.keys())
        versions.sort(key=_version_sort_key)
        return versions

    async def get_latest_stable(self, package_name: str) -> str:
        versions = await self.get_versions(package_name)
        if not versions:
            raise PackageNotFoundError(
                f"Package '{package_name}' has no published releases"
            )
        stable = [v for v in versions if not _is_prerelease(v)]
        if stable:
            return stable[-1]
        return versions[-1]


def _version_sort_key(v: str) -> tuple[int, Version | str]:
    try:
        return (0, _parse_version(v))
    except InvalidVersion:
        return (1, v)


def _is_prerelease(v: str) -> bool:
    try:
        return _parse_version(v).is_prerelease
    except InvalidVersion:
        return False
