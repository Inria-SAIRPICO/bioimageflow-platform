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

import inspect
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from bioimageflow import ToolRegistry as LibToolRegistry
from bioimageflow.registry import ToolMetadata as LibToolMetadata
from bioimageflow.tool_loader import (
    load_versioned_package,
    unload_versioned_package,
)
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
        self._sources: dict[str, Path] = {}
        self._custom_roots: set[Path] = set()
        # Tracked from the most recent ``scan_tool_store`` call. Used by
        # ``resolve_package_for_path`` to map watchdog file events back to
        # ``(package, version)`` pairs.
        self._store_path: Path | None = None

    def scan_tool_store(self, store_path: Path | None = None) -> None:
        """Scan the tool store directory and register all discovered tools.

        Uses the library's :meth:`ToolRegistry.register_package` for
        package loading (never triggers network installs on the hot path).
        """
        from bioimageflow.paths import get_tool_store_path

        if store_path is not None:
            self._lib_registry = LibToolRegistry(store_path=store_path)

        actual_store = store_path if store_path is not None else get_tool_store_path()
        self._store_path = actual_store

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
            ver_dirs = [d for d in pkg_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
            ver_dirs.sort(key=lambda d: _version_sort_key(d.name))

            installed_versions: list[str] = []
            loaded_versions: list[str] = []
            tools_by_version: dict[str, list[str]] = {}
            load_errors: dict[str, str] = {}
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
                        package_name,
                        version,
                    )
                except Exception as exc:
                    logger.exception("Failed to load %s==%s", package_name, version)
                    load_errors[version] = _format_package_load_error(exc)
                    unload_versioned_package(package_name, version)
                    tools_by_version.setdefault(version, [])
                    continue

                tool_names = [m.class_name for m in lib_metas]
                tools_by_version[version] = tool_names
                loaded_versions.append(version)

                # Newer iterations overwrite older entries — at the end
                # of the loop each class points at the newest version
                # that exports it.
                for class_name in tool_names:
                    class_versions[class_name] = version

            # Snapshot platform metadata using the lib registry's current
            # bindings (newest version per class, thanks to the load
            # order above).
            for class_name, version in class_versions.items():
                tool_cls = self._lib_registry.get_class(class_name)
                if tool_cls is not None:
                    self._register_tool_from_class(
                        tool_cls,
                        class_name,
                        package_name,
                        version,
                    )

            if installed_versions:
                # The lib registry was loaded oldest-first, so the newest
                # version is the one currently bound in `_classes`. Reflect
                # that in `active_version` so the GUI knows which version
                # the workflow will execute against.
                active_version = (
                    loaded_versions[-1]
                    if loaded_versions
                    else installed_versions[-1]
                )
                self.register_package(
                    package_name,
                    PackageInfo(
                        name=package_name,
                        installed_versions=installed_versions,
                        available_versions=installed_versions,
                        active_version=active_version,
                        tools=tools_by_version,
                        load_errors=load_errors,
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
        *,
        source_kind: str = "package",
        editable: bool = False,
        source_path: Path | None = None,
    ) -> None:
        """Extract metadata from a tool class and register it."""
        display_name = getattr(tool_cls, "display_name", None) or class_name
        documentation = (
            getattr(tool_cls, "documentation", "") or getattr(tool_cls, "__doc__", "") or ""
        )
        tags = list(getattr(tool_cls, "tags", []))
        category = getattr(tool_cls, "category", None)
        categories = [category.value] if category is not None else []

        # Determine tool type, accepts_upstream, and dynamic_outputs from the
        # library's canonical serializer.
        meta = serialize_tool_metadata(tool_cls)
        tool_type = meta["tool_type"]
        accepts_upstream = meta["accepts_upstream"]
        dynamic_outputs = meta["dynamic_outputs"]
        dataframe_output = bool(meta.get("dataframe_output", True))

        try:
            inputs_raw = serialize_input_schema(tool_cls)
            inputs_dict: dict[str, InputFieldSchema] = {
                name: InputFieldSchema.model_validate(spec) for name, spec in inputs_raw.items()
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
                dataframe_output=dataframe_output,
                documentation=documentation.strip(),
                tags=tags,
                categories=categories,
                inputs=inputs_dict,
                outputs=outputs_dict,
                environment=environment,
                source_kind=source_kind,  # type: ignore[arg-type]
                editable=editable,
            ),
            tool_class=tool_cls,
        )
        if source_path is not None:
            self._sources[class_name] = source_path.resolve()

    # -- tools --

    def register_tool(
        self,
        class_name: str,
        metadata: ToolMetadata,
        tool_class: type | None = None,
    ) -> None:
        self._tools[class_name] = metadata
        if tool_class is not None:
            self._register_lib_class(class_name, metadata, tool_class)

    def forget_tool(self, class_name: str) -> None:
        self._tools.pop(class_name, None)
        self._sources.pop(class_name, None)
        self._lib_registry.forget(class_name)

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

            module = load_versioned_package(metadata.package, metadata.package_version)
            resolved = getattr(module, class_name, None)
            if resolved is not None:
                self._register_lib_class(class_name, metadata, resolved)
            return resolved
        except Exception:
            return None

    def list_tools(self) -> list[ToolMetadata]:
        return list(self._tools.values())

    def register_custom_tools_directory(self, root: Path) -> dict[str, ToolMetadata]:
        """Load all importable custom tool files under ``root``."""
        resolved_root = root.resolve()
        self._custom_roots.add(resolved_root)
        registered: dict[str, ToolMetadata] = {}
        if not resolved_root.exists():
            return registered

        for path in sorted(resolved_root.glob("*.py")):
            if path.name.startswith("."):
                continue
            try:
                for class_name in self._discover_tool_class_names(path):
                    registered[class_name] = self.register_custom_tool_file(path, class_name)
            except Exception:
                logger.exception("Failed to load custom tool source: %s", path)
        return registered

    def register_custom_tool_file(self, path: Path, class_name: str) -> ToolMetadata:
        """Load one custom tool source file and register its metadata."""
        resolved = path.resolve()
        self._custom_roots.add(resolved.parent)
        module_name = f"bioimageflow_custom_{resolved.stem}_{resolved.stat().st_mtime_ns}"
        spec = importlib.util.spec_from_file_location(module_name, resolved)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load custom tool source: {resolved}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        tool_cls = getattr(module, class_name, None)
        if not isinstance(tool_cls, type):
            raise ImportError(f"Tool class '{class_name}' not found in {resolved}")
        self._register_tool_from_class(
            tool_cls,
            class_name,
            "__custom__",
            "local",
            source_kind="custom",
            editable=True,
            source_path=resolved,
        )
        package = self._packages.get("__custom__")
        if package is None:
            package = PackageInfo(
                name="__custom__",
                installed_versions=["local"],
                available_versions=["local"],
                active_version="local",
                tools={"local": []},
                environment_status="stopped",
            )
            self.register_package("__custom__", package)
        tools = package.tools.setdefault("local", [])
        if class_name not in tools:
            tools.append(class_name)
            tools.sort()
        return self._tools[class_name]

    def unregister_custom_tool(self, class_name: str) -> None:
        self.forget_tool(class_name)
        package = self._packages.get("__custom__")
        if package is None:
            return
        tools = package.tools.get("local", [])
        package.tools["local"] = [name for name in tools if name != class_name]
        if not package.tools["local"]:
            self._packages.pop("__custom__", None)

    def resolve_custom_tool_for_path(self, path: Path) -> str | None:
        try:
            resolved = Path(path).resolve()
        except OSError:
            return None
        for class_name, source in self._sources.items():
            if source != resolved:
                continue
            meta = self._tools.get(class_name)
            if meta is not None and meta.source_kind == "custom":
                return class_name
        if resolved.suffix != ".py" or not resolved.exists():
            return None
        if not self._is_under_custom_root(resolved):
            return None
        discovered = self._discover_tool_class_names(resolved)
        if not discovered:
            return None
        class_name = discovered[0]
        self._sources[class_name] = resolved
        return class_name

    def _is_under_custom_root(self, path: Path) -> bool:
        for root in self._custom_roots:
            try:
                path.relative_to(root)
            except ValueError:
                continue
            return True
        return False

    def _discover_tool_class_names(self, path: Path) -> list[str]:
        """Return tool class names defined by a custom source file."""
        resolved = path.resolve()
        module_name = f"bioimageflow_custom_discovery_{resolved.stem}_{resolved.stat().st_mtime_ns}"
        spec = importlib.util.spec_from_file_location(module_name, resolved)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load custom tool source: {resolved}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
            from bioimageflow import DataFrameTool
            from bioimageflow_core import ProcessingTool

            names: list[str] = []
            for name, value in vars(module).items():
                if not isinstance(value, type):
                    continue
                if getattr(value, "__module__", None) != module.__name__:
                    continue
                if issubclass(value, (ProcessingTool, DataFrameTool)):
                    names.append(name)
            return names
        finally:
            sys.modules.pop(module_name, None)

    def reload_custom_tool(self, class_name: str) -> dict[str, ToolMetadata]:
        source = self._sources.get(class_name)
        if source is None:
            raise FileNotFoundError(class_name)
        if not source.exists():
            self.unregister_custom_tool(class_name)
            raise FileNotFoundError(source)
        prior_metadata = self._tools.get(class_name)
        prior_source = self._sources.get(class_name)
        prior_class = self._lib_registry.get_class(class_name)
        prior_package = self._packages.get("__custom__")
        prior_package = prior_package.model_copy(deep=True) if prior_package is not None else None
        self.unregister_custom_tool(class_name)
        try:
            metadata = self.register_custom_tool_file(source, class_name)
        except Exception:
            if prior_metadata is not None:
                self._tools[class_name] = prior_metadata
            if prior_source is not None:
                self._sources[class_name] = prior_source
            if prior_package is not None:
                self._packages["__custom__"] = prior_package
            if prior_class is not None and prior_metadata is not None:
                self._register_lib_class(class_name, prior_metadata, prior_class)
            raise
        return {class_name: metadata}

    def resolve_tool_source(self, class_name: str) -> Path | None:
        source = self._sources.get(class_name)
        if source is not None:
            return source
        tool_cls = self.get_tool_class(class_name)
        if tool_cls is None:
            return None
        try:
            source_file = inspect.getsourcefile(tool_cls)
        except TypeError:
            return None
        if source_file is None:
            return None
        return Path(source_file).resolve()

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
            raise ValueError(f"Version '{version}' is not installed for '{package_name}'")
        if version in pkg.load_errors:
            raise ValueError(
                f"Version '{version}' for '{package_name}' failed to load: "
                f"{pkg.load_errors[version]}"
            )

        try:
            for class_name in pkg.tools.get(version, []):
                self._lib_registry.forget(
                    class_name,
                    package=package_name,
                    version=version,
                )
            lib_metas = self._lib_registry.register_package(package_name, version)
        except FileNotFoundError:
            logger.warning(
                "set_active_version: %s==%s not found on disk; skipping lib registry refresh",
                package_name,
                version,
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
                tool_cls,
                class_name,
                package_name,
                version,
            )

    # -- hot reload --

    def snapshot(self, package: str, version: str) -> dict[str, ToolMetadata]:
        """Return the current platform metadata for tools matching
        ``(package, version)``. Empty if nothing is loaded for that pair.
        """
        if package == "__custom__" and version != "local":
            meta = self._tools.get(version)
            if meta is not None and meta.source_kind == "custom":
                return {version: meta}
            return {}
        return {
            name: meta
            for name, meta in self._tools.items()
            if meta.package == package and meta.package_version == version
        }

    def resolve_package_for_path(self, path: Path) -> tuple[str, str] | None:
        """Map a filesystem path to ``(package, version)`` if it lives
        under the tool store and has at least two components below the
        store root, else ``None``.

        Parsing rule: the first two path components below the tracked
        store root are ``(package_name, version)``. Anything shallower
        (e.g. a stray README directly under ``<store>/<pkg>``) is treated
        as out-of-scope.
        """
        custom_class = self.resolve_custom_tool_for_path(path)
        if custom_class is not None:
            return "__custom__", custom_class
        if self._store_path is None:
            return None
        try:
            relative = Path(path).resolve().relative_to(self._store_path.resolve())
        except ValueError:
            return None
        parts = relative.parts
        # Need at least <pkg>/<ver>/<file> — anything shallower is at
        # the store root or the package level and isn't a hot-reloadable
        # source path.
        if len(parts) < 3:
            return None
        return parts[0], parts[1]

    def reload_package(self, package: str, version: str) -> dict[str, ToolMetadata]:
        """Unload + load + re-index a single ``(package, version)`` pair.

        Preserves the user's chosen ``active_version`` for the package by
        re-applying it after the lib registry's class bindings have been
        rebuilt for the reloaded version. On any exception during the
        load + index phase, restores the prior class bindings and
        platform metadata, then re-raises so the caller can broadcast
        a ``system_error`` and surface the failure in the GUI.
        """
        if package == "__custom__":
            return self.reload_custom_tool(version)

        if self._store_path is None:
            from bioimageflow.paths import get_tool_store_path

            self._store_path = get_tool_store_path()

        # Snapshot prior state for rollback. We hold strong refs to the
        # prior class objects so they remain resolvable even after
        # ``unload_versioned_package`` strips ``sys.modules`` entries.
        prior_snapshot = self.snapshot(package, version)
        prior_classes: dict[str, type] = {}
        for class_name in prior_snapshot:
            prior = self._lib_registry.get_class(class_name)
            if prior is not None:
                prior_classes[class_name] = prior

        # Capture the active version BEFORE the reload — register_package
        # rebinds ``_lib_registry._classes`` for every class in the
        # version it loads, so an inactive-version reload would clobber
        # the active version's bindings unless we restore them below.
        pkg_info = self._packages.get(package)
        active_version = pkg_info.active_version if pkg_info is not None else None

        unload_versioned_package(package, version)

        try:
            load_versioned_package(package, version, self._store_path)
            # Drop stale ToolMetadata entries for this package/version so
            # the re-register loop below produces a fresh snapshot. Tools
            # that disappear from the source land outside this set and
            # are removed by the caller (the hot-reload service diff).
            for class_name in list(prior_snapshot):
                self._tools.pop(class_name, None)
                self._lib_registry.forget(class_name)

            # Reload metadata for every class actually present in the new
            # version. Re-register through the lib registry so its
            # _classes binding is fresh.
            lib_metas = self._lib_registry.register_package(package, version)
            for lib_meta in lib_metas:
                class_name = lib_meta.class_name
                tool_cls = self._lib_registry.get_class(class_name)
                if tool_cls is None:
                    continue
                self._register_tool_from_class(
                    tool_cls,
                    class_name,
                    package,
                    version,
                )
        except Exception:
            # Restore prior state — hold the prior class objects strongly
            # so callers don't see "tools vanished" because of a bad edit.
            self._tools.clear()
            self._tools.update(prior_snapshot)
            for class_name, cls in prior_classes.items():
                metadata = prior_snapshot.get(class_name)
                if metadata is not None:
                    self._register_lib_class(class_name, metadata, cls)
            raise

        # Restore active-version binding if we just reloaded an inactive
        # version: the call to ``register_package(package, version)``
        # above clobbered ``_classes[class_name]`` for every class shared
        # with the active version.
        if active_version is not None and active_version != version:
            try:
                active_tools = (
                    pkg_info.tools.get(active_version, [])
                    if pkg_info is not None
                    else []
                )
                for class_name in active_tools:
                    self._lib_registry.forget(
                        class_name,
                        package=package,
                        version=active_version,
                    )
                self._lib_registry.register_package(package, active_version)
            except FileNotFoundError:
                logger.warning(
                    "reload_package: could not restore active version "
                    "%s==%s after reloading inactive %s",
                    package,
                    active_version,
                    version,
                )

        return self.snapshot(package, version)

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
        pkg.load_errors.pop(version, None)
        if not pkg.installed_versions:
            del self._packages[name]
        for class_name, meta in list(self._tools.items()):
            if meta.package == name and meta.package_version == version:
                del self._tools[class_name]
                self._lib_registry.forget(class_name)

    def _register_lib_class(
        self,
        class_name: str,
        metadata: ToolMetadata,
        tool_class: type,
    ) -> None:
        """Register an already-imported class in the library registry.

        The library registry indexes classes by package/version/module/name.
        Tests and custom registrations often already have the class object in
        memory, so they bypass ``register_package`` but still need a canonical
        registry entry for Workflow.from_dict validation.
        """
        module = getattr(tool_class, "__module__", "") or "__main__"
        lib_meta = LibToolMetadata(
            package=metadata.package,
            version=metadata.package_version,
            module=module,
            class_name=class_name,
            inputs_schema={
                name: field.model_dump(mode="json", exclude_none=True)
                for name, field in metadata.inputs.items()
            },
            outputs_schema={
                name: (
                    field.model_dump(mode="json", exclude_none=True)
                    if hasattr(field, "model_dump")
                    else field
                )
                for name, field in metadata.outputs.items()
            },
            display_name=metadata.display_name,
            tags=tuple(metadata.tags),
        )
        key = self._lib_registry._key(lib_meta)
        self._lib_registry._classes[key] = tool_class
        self._lib_registry._metadata[key] = lib_meta


def _format_package_load_error(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return f"{type(exc).__name__}: {message}"
    return type(exc).__name__
