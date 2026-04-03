"""Stub package installer service."""

from __future__ import annotations


class PackageNotFoundError(Exception):
    """Raised when a requested package cannot be found."""


class PackageNetworkError(Exception):
    """Raised on network/connectivity errors during install/uninstall."""


class PackageInstallerService:
    """Stub installer — subclass or mock for real behaviour."""

    async def install(self, package_name: str, version: str | None = None) -> None:
        raise NotImplementedError

    async def uninstall(self, package_name: str, version: str | None = None) -> None:
        raise NotImplementedError
