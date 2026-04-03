"""In-memory tool and package registry."""

from __future__ import annotations

from bioimageflow_server.models.tools import PackageInfo, ToolMetadata


class ToolRegistryService:
    """Dict-backed registry of tools and packages."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolMetadata] = {}
        self._packages: dict[str, PackageInfo] = {}

    # -- tools --

    def register_tool(self, class_name: str, metadata: ToolMetadata) -> None:
        self._tools[class_name] = metadata

    def get_tool(self, class_name: str) -> ToolMetadata | None:
        return self._tools.get(class_name)

    def list_tools(self) -> list[ToolMetadata]:
        return list(self._tools.values())

    # -- packages --

    def register_package(self, name: str, info: PackageInfo) -> None:
        self._packages[name] = info

    def get_package(self, name: str) -> PackageInfo | None:
        return self._packages.get(name)

    def list_packages(self) -> list[PackageInfo]:
        return list(self._packages.values())
