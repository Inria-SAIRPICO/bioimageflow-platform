"""In-memory tool and package registry with filesystem scanning."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bioimageflow.validation import (
    SchemaSerializationError,
    serialize_input_schema,
    serialize_output_schema,
)

from bioimageflow_server.models.tools import (
    PackageInfo,
    ToolMetadata,
)

logger = logging.getLogger(__name__)


class ToolRegistryService:
    """Dict-backed registry of tools and packages."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolMetadata] = {}
        self._tool_classes: dict[str, type] = {}
        self._packages: dict[str, PackageInfo] = {}

    def scan_tool_store(self, store_path: Path | None = None) -> None:
        """Scan the tool store directory and register all discovered tools."""
        from bioimageflow.tool_loader import load_versioned_package
        from bioimageflow.paths import get_tool_store_path
        from bioimageflow_core.tool import BaseTool

        if store_path is None:
            store_path = get_tool_store_path()

        if not store_path.exists():
            logger.warning("Tool store not found: %s", store_path)
            return

        for pkg_dir in sorted(store_path.iterdir()):
            if not pkg_dir.is_dir() or pkg_dir.name.startswith("."):
                continue
            package_name = pkg_dir.name
            installed_versions: list[str] = []
            tools_by_version: dict[str, list[str]] = {}

            for ver_dir in sorted(pkg_dir.iterdir()):
                if not ver_dir.is_dir() or ver_dir.name.startswith("."):
                    continue
                version = ver_dir.name
                installed_versions.append(version)

                try:
                    mod = load_versioned_package(package_name, version, store_path)
                except Exception:
                    logger.exception(
                        "Failed to load %s==%s", package_name, version
                    )
                    continue

                tool_names: list[str] = []
                for attr_name in dir(mod):
                    try:
                        obj = getattr(mod, attr_name)
                    except Exception:
                        continue
                    if (
                        not isinstance(obj, type)
                        or not issubclass(obj, BaseTool)
                        or obj is BaseTool
                    ):
                        continue

                    tool_names.append(attr_name)
                    if attr_name not in self._tools:
                        self._register_tool_from_class(
                            obj, attr_name, package_name, version
                        )
                        self._tool_classes[attr_name] = obj

                tools_by_version[version] = tool_names

            if installed_versions:
                self.register_package(
                    package_name,
                    PackageInfo(
                        name=package_name,
                        installed_versions=installed_versions,
                        available_versions=installed_versions,
                        tools=tools_by_version,
                        environment_status="stopped",
                    ),
                )

        logger.info(
            "Scanned tool store: %d tools, %d packages",
            len(self._tools),
            len(self._packages),
        )

    def _register_tool_from_class(
        self,
        tool_cls: type,
        class_name: str,
        package: str,
        version: str,
    ) -> None:
        """Extract metadata from a tool class and register it."""
        display_name = getattr(tool_cls, "display_name", None) or class_name
        documentation = getattr(tool_cls, "documentation", "") or getattr(tool_cls, "__doc__", "") or ""
        tags = list(getattr(tool_cls, "tags", []))
        category = getattr(tool_cls, "category", None)
        categories = [category.value] if category is not None else []

        # Determine tool type
        try:
            from bioimageflow.dataframe_tool import DataFrameTool

            tool_type = "DataFrameTool" if issubclass(tool_cls, DataFrameTool) else ""
        except ImportError:
            tool_type = ""
        if not tool_type:
            from bioimageflow_core.tool import ProcessingTool

            if issubclass(tool_cls, ProcessingTool):
                tool_type = "ProcessingTool"
            else:
                tool_type = "BaseTool"

        try:
            inputs_dict = serialize_input_schema(tool_cls)
        except SchemaSerializationError as exc:
            logger.warning("Failed to serialize inputs for %s: %s", class_name, exc)
            inputs_dict = {}

        try:
            outputs_dict = serialize_output_schema(tool_cls)
        except SchemaSerializationError as exc:
            logger.warning("Failed to serialize outputs for %s: %s", class_name, exc)
            outputs_dict = {}

        # Extract environment info
        env_spec = getattr(tool_cls, "environment", None)
        environment: dict[str, Any] | None = None
        if env_spec is not None:
            environment = {
                "name": getattr(env_spec, "name", ""),
                "dependencies": getattr(env_spec, "dependencies", {}),
            }

        self.register_tool(
            class_name,
            ToolMetadata(
                name=class_name,
                display_name=display_name,
                package=package,
                package_version=version,
                tool_type=tool_type,
                documentation=documentation.strip(),
                tags=tags,
                categories=categories,
                inputs=inputs_dict,
                outputs=outputs_dict,
                environment=environment,
            ),
        )

    # -- tools --

    def register_tool(
        self,
        class_name: str,
        metadata: ToolMetadata,
        tool_class: type | None = None,
    ) -> None:
        self._tools[class_name] = metadata
        if tool_class is not None:
            self._tool_classes[class_name] = tool_class

    def get_tool(self, class_name: str) -> ToolMetadata | None:
        return self._tools.get(class_name)

    def get_tool_class(self, class_name: str) -> type | None:
        """Return the tool class if registered, or attempt to resolve it from
        the installed tool store. Returns ``None`` if the package/version is
        not installed."""
        cls = self._tool_classes.get(class_name)
        if cls is not None:
            return cls
        metadata = self._tools.get(class_name)
        if metadata is None:
            return None
        try:
            from bioimageflow.tool_loader import load_versioned_package

            module = load_versioned_package(
                metadata.package, metadata.package_version
            )
            resolved = getattr(module, class_name, None)
            if resolved is not None:
                self._tool_classes[class_name] = resolved
            return resolved
        except Exception:
            return None

    def list_tools(self) -> list[ToolMetadata]:
        return list(self._tools.values())

    # -- packages --

    def register_package(self, name: str, info: PackageInfo) -> None:
        self._packages[name] = info

    def get_package(self, name: str) -> PackageInfo | None:
        return self._packages.get(name)

    def list_packages(self) -> list[PackageInfo]:
        return list(self._packages.values())

    def forget_package(self, name: str, version: str | None = None) -> None:
        """Drop a package (or a single version) from the in-memory registry.

        Removes the matching entry from ``_packages`` and any tools whose
        :attr:`ToolMetadata.package` (+ version, if provided) matches. A noop
        for unknown packages.
        """
        pkg = self._packages.get(name)
        if pkg is None:
            return

        if version is None:
            del self._packages[name]
            self._tools = {
                class_name: meta
                for class_name, meta in self._tools.items()
                if meta.package != name
            }
            return

        if version in pkg.installed_versions:
            pkg.installed_versions = [v for v in pkg.installed_versions if v != version]
        pkg.tools.pop(version, None)
        if not pkg.installed_versions:
            del self._packages[name]
        self._tools = {
            class_name: meta
            for class_name, meta in self._tools.items()
            if not (meta.package == name and meta.package_version == version)
        }


