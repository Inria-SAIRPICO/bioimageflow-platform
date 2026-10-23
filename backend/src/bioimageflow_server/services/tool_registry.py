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
import hashlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from bioimageflow import ToolRegistry as LibToolRegistry
from bioimageflow.installation import validate_installation_selectors
from bioimageflow.registry import ToolMetadata as LibToolMetadata
from bioimageflow.tool_loader import (
    load_versioned_package,
    unload_versioned_package,
    unload_versioned_packages,
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
        self._owned_source_roots: dict[Path, set[str]] = {}
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

        actual_store = Path(store_path if store_path is not None else get_tool_store_path()).resolve()
        self._select_tool_store(actual_store)

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
            ver_dirs = []
            for directory in pkg_dir.iterdir():
                if not directory.is_dir() or directory.name.startswith("."):
                    continue
                try:
                    validate_installation_selectors(package_name, directory.name, None)
                except ValueError:
                    logger.warning("Ignoring unsupported tool-store directory: %s", directory)
                    continue
                ver_dirs.append(directory)
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
                    try:
                        unload_versioned_package(package_name, version, self._store_path)
                    except Exception:
                        logger.exception("Failed to unload rejected %s==%s", package_name, version)
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
                tool_cls = self._lib_registry.get_class(class_name, package=package_name, version=version)
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
        row_consumption = meta["row_consumption"]

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
                "allow_flexible_versions": env_spec.allow_flexible_versions,
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
                row_consumption=row_consumption,
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
        """Resolve the catalog's exact binding, never a retired or alternate version."""
        metadata = self._tools.get(class_name)
        if metadata is None:
            return None
        package = self._packages.get(metadata.package)
        if package is not None and metadata.package_version in package.load_errors:
            return None
        cls = self._lib_registry.get_class(
            class_name, package=metadata.package, version=metadata.package_version,
        )
        if cls is not None:
            return cls
        try:
            module = load_versioned_package(
                metadata.package, metadata.package_version, self.tool_store_path(),
            )
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
        source = resolved.read_bytes()
        digest = hashlib.sha256(str(resolved).encode() + b"\0" + source).hexdigest()
        module_name = f"bioimageflow_custom_{digest}"
        spec = importlib.util.spec_from_file_location(module_name, resolved)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load custom tool source: {resolved}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            # Timestamp-based .pyc validation misses same-size rapid editor saves.
            exec(compile(source, str(resolved), "exec", dont_inherit=True), module.__dict__)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
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
            exec(compile(resolved.read_bytes(), str(resolved), "exec", dont_inherit=True), module.__dict__)
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
        """Stage every class in one source before publishing a successful edit."""
        source = self._sources.get(class_name)
        if source is None:
            candidate = Path(class_name)
            if not candidate.is_absolute() or not self._is_under_custom_root(candidate):
                raise FileNotFoundError(class_name)
            source = candidate
        prior = {name for name, path in self._sources.items() if path == source}
        staged = ToolRegistryService()
        if source.exists():
            for name in self._discover_tool_class_names(source):
                staged.register_custom_tool_file(source, name)
        current = {meta.name: meta for meta in staged.list_tools()}
        for name in prior - current.keys():
            self.unregister_custom_tool(name)
        for name, metadata in current.items():
            self._lib_registry.forget(name, package="__custom__", version="local")
            self.register_tool(name, metadata, staged.get_tool_class(name))
            self._sources[name] = source
        if current:
            package = self._packages.get("__custom__")
            if package is None:
                package = staged.get_package("__custom__")
                assert package is not None
                self._packages["__custom__"] = package
            package.tools["local"] = sorted(self.snapshot("__custom__", "local"))
        return current

    def custom_source_fingerprints(self) -> dict[Path, str]:
        """Inspect only editable source directories, never workflow results."""
        fingerprints: dict[Path, str] = {}
        for root in tuple(self._custom_roots):
            for path in root.glob("*.py"):
                if path.name.startswith(".") or path.is_symlink():
                    continue
                try:
                    fingerprints[path] = hashlib.sha256(path.read_bytes()).hexdigest()
                except FileNotFoundError:
                    continue
        for root in tuple(self._owned_source_roots):
            for path in root.rglob("*"):
                if not path.is_file() or path.is_symlink() or "__pycache__" in path.parts or path.name.startswith("."):
                    continue
                try:
                    fingerprints[path] = hashlib.sha256(path.read_bytes()).hexdigest()
                except FileNotFoundError:
                    continue
        return fingerprints

    def watch_owned_sources(self, workflow_dir: Path, graph: Any) -> None:
        from bioimageflow_server.models.graph import WorkflowNodeState
        from bioimageflow_server.services.workflow_artifacts import OwnedWorkflowSources

        for node in graph.nodes:
            if isinstance(node, WorkflowNodeState):
                self.watch_owned_sources(workflow_dir, node.workflow)
            elif node.source_module:
                root = OwnedWorkflowSources(workflow_dir)._path(node.source_module).parent
                self._owned_source_roots.setdefault(root, set()).add(node.tool_name)

    def owned_source_tools(self, path: Path) -> set[str]:
        return set().union(*(names for root, names in self._owned_source_roots.items() if path.is_relative_to(root)))

    @classmethod
    def metadata_for_class(
        cls, tool_class: type, *, package: str = "__custom__",
        version: str = "local", editable: bool = True,
    ) -> ToolMetadata:
        """Describe a resolved node without modifying the workspace registry."""
        registry = cls()
        registry._register_tool_from_class(
            tool_class, tool_class.__name__, package, version,
            source_kind="custom" if editable else "package", editable=editable,
        )
        metadata = registry.get_tool(tool_class.__name__)
        assert metadata is not None
        return metadata

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

    def tool_store_path(self) -> Path:
        """Return one explicit installed root, selecting the global default once."""
        if self._store_path is None:
            from bioimageflow.paths import get_tool_store_path

            self._select_tool_store(get_tool_store_path())
        assert self._store_path is not None
        return self._store_path

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
            tool_cls = self._lib_registry.get_class(class_name, package=package_name, version=version)
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
            source = Path(version)
            return {
                name: meta for name, meta in self._tools.items()
                if meta.source_kind == "custom" and self._sources.get(name) == source
            }
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
        resolved = Path(path).resolve()
        if resolved.suffix == ".py" and self._is_under_custom_root(resolved):
            return "__custom__", str(resolved)
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
        try:
            validate_installation_selectors(parts[0], parts[1], None)
        except ValueError:
            # Owned installer staging and unrelated directories are not
            # published package versions, even after their files disappear.
            return None
        return parts[0], parts[1]

    def _select_tool_store(self, store_path: Path) -> None:
        """Change installed selection only after its held generations can retire."""
        selected = Path(store_path).resolve()
        if self._store_path is not None and self._store_path.resolve() == selected:
            return
        changing = self._store_path is not None
        installed = set(self._packages) - {"__custom__"} if changing else set()
        if changing:
            selections: set[tuple[str, str]] = set()
            for name in installed:
                info = self._packages[name]
                for version in info.installed_versions:
                    if version in info.load_errors:
                        continue
                    try:
                        validate_installation_selectors(name, version, None)
                    except ValueError:
                        continue
                    selections.add((name, version))
            # Carried workflow references can admit an already published
            # package without adding it to the catalog. Root changes are rare;
            # include published selectors here without importing their code.
            if self._store_path.is_dir():
                for directory in self._store_path.iterdir():
                    if not directory.is_dir() or directory.is_symlink() or directory.name.startswith("."):
                        continue
                    for version_dir in directory.iterdir():
                        if not version_dir.is_dir() or version_dir.is_symlink():
                            continue
                        try:
                            validate_installation_selectors(directory.name, version_dir.name, None)
                        except ValueError:
                            continue
                        info = self._packages.get(directory.name)
                        if info is None or version_dir.name not in info.load_errors:
                            selections.add((directory.name, version_dir.name))
            unload_versioned_packages(sorted(selections), self._store_path)
        retained = {
            name: (meta, self._lib_registry.get_class(
                name, package=meta.package, version=meta.package_version,
            ))
            for name, meta in self._tools.items() if meta.package not in installed
        }
        self._lib_registry = LibToolRegistry(store_path=selected)
        self._store_path = selected
        for name in installed:
            self._packages.pop(name, None)
        self._tools = {name: metadata for name, (metadata, _) in retained.items()}
        for name, (metadata, tool_class) in retained.items():
            if tool_class is not None:
                self._register_lib_class(name, metadata, tool_class)

    def index_package(
        self, package: str, version: str, store_path: Path | None = None,
    ) -> dict[str, ToolMetadata]:
        """Index an installed generation without retiring an unchanged live selection."""
        from bioimageflow.paths import get_tool_store_path

        self._select_tool_store(store_path or self._store_path or get_tool_store_path())
        return self._index_package(package, version)

    def reload_package(self, package: str, version: str) -> dict[str, ToolMetadata]:
        """Explicitly retire and reload installed code; failed generations stay unavailable."""
        if package == "__custom__":
            return self.reload_custom_tool(version)
        from bioimageflow.paths import get_tool_store_path

        self._select_tool_store(self._store_path or get_tool_store_path())
        # Refusal precedes all registry mutation. Retired class objects cannot
        # be restored after failure: they no longer authorize new execution.
        unload_versioned_package(package, version, self._store_path)
        importlib.invalidate_caches()
        return self._index_package(package, version)

    def _index_package(self, package: str, version: str) -> dict[str, ToolMetadata]:
        validate_installation_selectors(package, version, None)
        info = self._packages.get(package)
        previous_names = set(info.tools.get(version, [])) if info is not None else set()
        try:
            lib_metas = self._lib_registry.register_package(package, version)
            staged = {}
            for meta in lib_metas:
                tool_class = self._lib_registry.get_class(
                    meta.class_name, package=package, version=version,
                )
                if tool_class is not None:
                    staged[meta.class_name] = self.metadata_for_class(
                        tool_class, package=package, version=version, editable=False,
                    )
        except Exception as primary:
            try:
                unload_versioned_package(package, version, self._store_path)
            except Exception:
                logger.exception("Could not retire rejected %s==%s", package, version)
            rejected_names = previous_names | {
                meta.class_name for meta in self._lib_registry.list_tools()
                if (meta.package, meta.version) == (package, version)
            }
            for name in rejected_names:
                self._lib_registry.forget(name, package=package, version=version)
                metadata = self._tools.get(name)
                if metadata is not None and (metadata.package, metadata.package_version) == (package, version):
                    self._tools.pop(name, None)
            if info is None:
                info = PackageInfo(name=package, installed_versions=[version], active_version=version)
                self._packages[package] = info
            elif version not in info.installed_versions:
                info.installed_versions.append(version)
                info.installed_versions.sort(key=_version_sort_key)
            info.tools[version] = []
            info.load_errors[version] = _format_package_load_error(primary)
            raise
        for name in previous_names - staged.keys():
            self._lib_registry.forget(name, package=package, version=version)
            metadata = self._tools.get(name)
            if metadata is not None and (metadata.package, metadata.package_version) == (package, version):
                self._tools.pop(name, None)
        if info is None:
            info = PackageInfo(name=package, installed_versions=[], active_version=version)
            self._packages[package] = info
        if version not in info.installed_versions:
            info.installed_versions.append(version)
            info.installed_versions.sort(key=_version_sort_key)
        if version not in info.available_versions:
            info.available_versions.append(version)
            info.available_versions.sort(key=_version_sort_key)
        info.tools[version] = sorted(staged)
        info.load_errors.pop(version, None)
        if info.active_version is None:
            info.active_version = version
        active_names = set(info.tools.get(info.active_version, []))
        for name, metadata in staged.items():
            if info.active_version == version or name not in active_names:
                self._tools[name] = metadata
        if info.active_version != version:
            # Preserve the library registry's unqualified active-class view
            # for callers which display the selected catalog version.
            self.set_active_version(package, info.active_version)
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
            for class_name in {tool for tools in pkg.tools.values() for tool in tools}:
                self._lib_registry.forget(class_name, package=name)
            for class_name, meta in list(self._tools.items()):
                if meta.package == name:
                    del self._tools[class_name]
            return

        for class_name in pkg.tools.get(version, []):
            self._lib_registry.forget(class_name, package=name, version=version)
        if version in pkg.installed_versions:
            pkg.installed_versions = [v for v in pkg.installed_versions if v != version]
        pkg.tools.pop(version, None)
        pkg.load_errors.pop(version, None)
        if not pkg.installed_versions:
            del self._packages[name]
        for class_name, meta in list(self._tools.items()):
            if meta.package == name and meta.package_version == version:
                del self._tools[class_name]
                self._lib_registry.forget(class_name, package=name, version=version)
        if pkg.installed_versions and pkg.active_version == version:
            available = [item for item in pkg.installed_versions if item not in pkg.load_errors]
            pkg.active_version = available[-1] if available else None
            if pkg.active_version is not None:
                self.set_active_version(name, pkg.active_version)

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
            row_consumption=metadata.row_consumption,
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
