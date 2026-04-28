"""In-memory tool and package registry backed by the library's ToolRegistry.

The library's :class:`bioimageflow.ToolRegistry` handles package loading
and tool class indexing. This service wraps it with:

- The platform's :class:`ToolMetadata` wire format (richer than the
  library's ``ToolMetadata`` — includes ``tool_type``, ``documentation``,
  ``categories``, ``environment``).
- Package-level bookkeeping (:class:`PackageInfo`) for the frontend.
- A ``get_tool_class`` method that delegates to the library registry.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bioimageflow import ToolRegistry as LibToolRegistry
from bioimageflow.validation import (
    SchemaSerializationError,
    serialize_input_schema,
    serialize_output_schema,
    serialize_tool_metadata,
)

from bioimageflow_server.models.tools import (
    InputFieldSchema,
    PackageInfo,
    ToolMetadata,
)
from bioimageflow_server.services.pypi_versions import _version_sort_key

logger = logging.getLogger(__name__)


class ToolRegistryService:
    """Dict-backed registry of tools and packages.

    Delegates tool class resolution and package scanning to the library's
    :class:`ToolRegistry`. The platform layer enriches tool metadata with
    fields the library does not carry (``tool_type``, ``documentation``,
    ``categories``, ``environment``).
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolMetadata] = {}
        self._lib_registry = LibToolRegistry()
        self._packages: dict[str, PackageInfo] = {}

    def scan_tool_store(self, store_path: Path | None = None) -> None:
        """Scan the tool store directory and register all discovered tools.

        Uses the library's :meth:`ToolRegistry.register_package` for
        package loading (never triggers network installs on the hot path).
        """
        from bioimageflow.paths import get_tool_store_path

        if store_path is not None:
            self._lib_registry = LibToolRegistry(store_path=store_path)

        actual_store = store_path if store_path is not None else get_tool_store_path()

        if not actual_store.exists():
            logger.warning("Tool store not found: %s", actual_store)
            return

        for pkg_dir in sorted(actual_store.iterdir()):
            if not pkg_dir.is_dir() or pkg_dir.name.startswith("."):
                continue
            package_name = pkg_dir.name

            # Sort version directories oldest-first using PEP 440 ordering.
            # Each `lib_registry.register_package(name, version)` call
            # overwrites `_classes[class_name]` with this version's class
            # object — so to leave the NEWEST version active for each
            # class, we load oldest-first and let the newest call win.
            # (Lex sort treats `0.1.10` < `0.1.9`, which is wrong for
            # multi-digit versions.)
            ver_dirs = [
                d for d in pkg_dir.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ]
            ver_dirs.sort(key=lambda d: _version_sort_key(d.name))

            installed_versions: list[str] = []
            tools_by_version: dict[str, list[str]] = {}
            # class_name -> newest version that exports it. The platform
            # registry stores one ToolMetadata per class, so this picks
            # which version's metadata (incl. inputs/outputs schema) we
            # surface to the GUI.
            class_versions: dict[str, str] = {}

            for ver_dir in ver_dirs:
                version = ver_dir.name
                installed_versions.append(version)

                try:
                    lib_metas = self._lib_registry.register_package(
                        package_name, version,
                    )
                except Exception:
                    logger.exception(
                        "Failed to load %s==%s", package_name, version
                    )
                    continue

                tool_names = [m.class_name for m in lib_metas]
                tools_by_version[version] = tool_names

                # Newer iterations overwrite older entries — at the end
                # of the loop each class points at the newest version
                # that exports it.
                for class_name in tool_names:
                    class_versions[class_name] = version

            # Snapshot platform metadata using the lib registry's current
            # bindings (newest version per class, thanks to the load
            # order above).
            for class_name, version in class_versions.items():
                if class_name in self._tools:
                    continue
                tool_cls = self._lib_registry.get_class(class_name)
                if tool_cls is not None:
                    self._register_tool_from_class(
                        tool_cls, class_name, package_name, version,
                    )

            if installed_versions:
                # The lib registry was loaded oldest-first, so the newest
                # version is the one currently bound in `_classes`. Reflect
                # that in `active_version` so the GUI knows which version
                # the workflow will execute against.
                active_version = installed_versions[-1]
                self.register_package(
                    package_name,
                    PackageInfo(
                        name=package_name,
                        installed_versions=installed_versions,
                        available_versions=installed_versions,
                        active_version=active_version,
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

        # Determine tool type, accepts_upstream, and dynamic_outputs from the
        # library's canonical serializer.
        meta = serialize_tool_metadata(tool_cls)
        tool_type = meta["tool_type"]
        accepts_upstream = meta["accepts_upstream"]
        dynamic_outputs = meta["dynamic_outputs"]

        try:
            inputs_raw = serialize_input_schema(tool_cls)
            inputs_dict: dict[str, InputFieldSchema] = {
                name: InputFieldSchema.model_validate(spec)
                for name, spec in inputs_raw.items()
            }
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
                accepts_upstream=accepts_upstream,
                dynamic_outputs=dynamic_outputs,
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
            self._lib_registry._classes[class_name] = tool_class

    def get_tool(self, class_name: str) -> ToolMetadata | None:
        return self._tools.get(class_name)

    def get_tool_class(self, class_name: str) -> type | None:
        """Return the tool class if registered, or attempt to resolve it from
        the installed tool store. Returns ``None`` if the package/version is
        not installed."""
        cls = self._lib_registry.get_class(class_name)
        if cls is not None:
            return cls
        # Fall back to lazy loading via the platform metadata.
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
                self._lib_registry._classes[class_name] = resolved
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

    def set_active_version(self, package_name: str, version: str) -> None:
        """Make ``package_name==version`` the active version for the workflow.

        Re-registers the package via the library registry — that overwrites
        the class binding in :attr:`_lib_registry._classes`, so subsequent
        :meth:`get_tool_class` lookups (and therefore execution) resolve
        to the requested version's class. Platform metadata for tools
        exported by this package is refreshed from the new class so the
        GUI sees the correct schema, version string, etc.

        Raises :class:`ValueError` if the package or version is unknown.
        Soft-fails (logs and returns) if the package directory is missing
        on disk — covers test fixtures that register a fake PackageInfo
        without copying real files into the tool store.
        """
        pkg = self._packages.get(package_name)
        if pkg is None:
            raise ValueError(f"Package '{package_name}' is not registered")
        if version not in pkg.installed_versions:
            raise ValueError(
                f"Version '{version}' is not installed for "
                f"'{package_name}'"
            )

        try:
            lib_metas = self._lib_registry.register_package(package_name, version)
        except FileNotFoundError:
            logger.warning(
                "set_active_version: %s==%s not found on disk; "
                "skipping lib registry refresh",
                package_name, version,
            )
            # Still record the user's choice on the package info so the GUI
            # reflects the requested active version even when the lib
            # registry can't actually load the class (test fixtures).
            pkg.active_version = version
            return

        pkg.active_version = version

        # Refresh platform metadata for every class in this version so the
        # GUI's tool list reflects the new schema/version.
        for lib_meta in lib_metas:
            class_name = lib_meta.class_name
            tool_cls = self._lib_registry.get_class(class_name)
            if tool_cls is None:
                continue
            # Drop the stale entry so _register_tool_from_class refills it.
            self._tools.pop(class_name, None)
            self._register_tool_from_class(
                tool_cls, class_name, package_name, version,
            )

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
            for class_name, meta in list(self._tools.items()):
                if meta.package == name:
                    del self._tools[class_name]
                    self._lib_registry.forget(class_name)
            return

        if version in pkg.installed_versions:
            pkg.installed_versions = [v for v in pkg.installed_versions if v != version]
        pkg.tools.pop(version, None)
        if not pkg.installed_versions:
            del self._packages[name]
        for class_name, meta in list(self._tools.items()):
            if meta.package == name and meta.package_version == version:
                del self._tools[class_name]
                self._lib_registry.forget(class_name)
