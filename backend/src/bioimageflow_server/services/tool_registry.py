"""In-memory tool and package registry with filesystem scanning."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bioimageflow_server.models.tools import (
    InputFieldSchema,
    OutputFieldSchema,
    PackageInfo,
    ToolMetadata,
)

logger = logging.getLogger(__name__)


class ToolRegistryService:
    """Dict-backed registry of tools and packages."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolMetadata] = {}
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
        from bioimageflow_core.tool import BaseTool

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

        # Extract input schema
        inputs: dict[str, InputFieldSchema] = {}
        inputs_cls = getattr(tool_cls, "Inputs", None)
        if inputs_cls is not None:
            from bioimageflow_core.types import Connectable, extract_gui_meta

            annotations: dict[str, Any] = {}
            for klass in reversed(inputs_cls.__mro__):
                annotations.update(getattr(klass, "__annotations__", {}))
            for field_name, annotation in annotations.items():
                type_name = _type_display_name(annotation)
                has_default = hasattr(inputs_cls, field_name)
                default = getattr(inputs_cls, field_name, None) if has_default else None
                is_optional = _is_optional_type(annotation)

                gui_meta = extract_gui_meta(annotation)
                connectable = gui_meta.connectable is not Connectable.NEVER if gui_meta else True
                min_val = gui_meta.min if gui_meta else None
                max_val = gui_meta.max if gui_meta else None
                step_val = gui_meta.step if gui_meta else None
                group_val = gui_meta.group if gui_meta else None
                choices_val = _extract_choices(annotation)

                inputs[field_name] = InputFieldSchema(
                    type=type_name,
                    connectable=connectable,
                    default=default,
                    description="",
                    optional=is_optional,
                    min=min_val,
                    max=max_val,
                    step=step_val,
                    group=group_val,
                    choices=choices_val,
                )

        # Extract output schema
        outputs: dict[str, OutputFieldSchema] = {}
        outputs_cls = getattr(tool_cls, "Outputs", None)
        if outputs_cls is not None:
            annotations = getattr(outputs_cls, "__annotations__", {})
            for field_name, annotation in annotations.items():
                default_val = getattr(outputs_cls, field_name, None)
                default_str = default_val if isinstance(default_val, str) else None
                outputs[field_name] = OutputFieldSchema(
                    type=_type_display_name(annotation),
                    default=default_str,
                )

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
                inputs=inputs,
                outputs=outputs,
                environment=environment,
            ),
        )

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


def _is_optional_type(annotation: Any) -> bool:
    """Return True if the annotation is Optional[X] (i.e. X | None)."""
    from typing import get_origin, get_args, Annotated, Union
    import types

    # Unwrap Annotated first
    if get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]

    origin = get_origin(annotation)
    # Python 3.10+ unions use types.UnionType
    if origin is Union or isinstance(annotation, types.UnionType):
        args = get_args(annotation)
        return type(None) in args

    return False


def _extract_choices(annotation: Any) -> list[str] | None:
    """Extract choices from Literal or Enum type annotations."""
    import enum
    import types
    from typing import Annotated, Literal, Union, get_args, get_origin

    # Unwrap Annotated
    if get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]

    # Unwrap Optional (Union[X, None])
    origin = get_origin(annotation)
    if origin is Union or isinstance(annotation, types.UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            annotation = args[0]

    # Handle Literal["a", "b", "c"]
    if get_origin(annotation) is Literal:
        return [str(v) for v in get_args(annotation)]

    # Handle Enum subclasses
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return [str(member.value) for member in annotation]

    return None


def _type_display_name(annotation: Any) -> str:
    """Convert a type annotation to a human-readable string."""
    from typing import get_origin, get_args, Annotated

    if get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]

    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation)
