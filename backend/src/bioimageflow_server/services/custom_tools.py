"""Filesystem-backed custom tool management."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Literal

from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def name_to_snake(name: str) -> str:
    return _CAMEL_BOUNDARY.sub("_", name).lower().replace(" ", "_")


def name_to_display(name: str) -> str:
    spaced = _CAMEL_BOUNDARY.sub(" ", name)
    return spaced.replace("_", " ").strip()


_PROCESSING_TEMPLATE = '''\
"""Custom ProcessingTool: {display_name}."""

from bioimageflow_core import (
    Arguments,
    GENERAL_ENV,
    IOModel,
    ImagePath,
    ProcessingTool,
    Semantic,
    Template,
)


class {class_name}(ProcessingTool):
    """Processing tool that operates on individual rows."""

    display_name = "{display_name}"
    environment = GENERAL_ENV

    class Inputs(IOModel):
        input_image: ImagePath(semantics=Semantic.INTENSITY)

    class Outputs(IOModel):
        output_image: ImagePath(semantics=Semantic.INTENSITY) = Template("{{input_image.stem}}_out{{ext}}")

    def process_row(self, arguments: Arguments) -> "Outputs":
        raise NotImplementedError("Implement {class_name}.process_row")
'''

_DATAFRAME_TEMPLATE = '''\
"""Custom DataFrameTool: {display_name}."""

from bioimageflow import DataFrameTool, Passthrough
from bioimageflow_core import Arguments, IOModel


class {class_name}(DataFrameTool):
    """DataFrame tool that transforms an entire dataframe."""

    display_name = "{display_name}"

    class Inputs(IOModel):
        pass

    class Outputs(Passthrough):
        pass

    def transform(self, df, arguments: Arguments):
        raise NotImplementedError("Implement {class_name}.transform")
'''

_TEMPLATES = {
    "ProcessingTool": _PROCESSING_TEMPLATE,
    "DataFrameTool": _DATAFRAME_TEMPLATE,
}


class CustomToolService:
    """Create, rename, delete, and register tools under ``workflow_root/tools``."""

    def __init__(self, workflow_root: Path, registry: ToolRegistryService) -> None:
        self.workflow_root = Path(workflow_root)
        self.registry = registry

    @property
    def root(self) -> Path:
        return self.workflow_root / "tools"

    def render_template(
        self,
        class_name: str,
        tool_type: Literal["ProcessingTool", "DataFrameTool"],
    ) -> str:
        return _TEMPLATES[tool_type].format(
            class_name=class_name,
            display_name=name_to_display(class_name),
        )

    def path_for(self, class_name: str) -> Path:
        return self._resolve_under_root(f"{name_to_snake(class_name)}.py")

    def create(
        self,
        class_name: str,
        tool_type: Literal["ProcessingTool", "DataFrameTool"],
    ) -> Path:
        if self.registry.get_tool(class_name) is not None:
            raise FileExistsError(class_name)
        path = self.path_for(class_name)
        if path.exists():
            raise FileExistsError(path.name)
        self.root.mkdir(parents=True, exist_ok=True)
        self._atomic_write(path, self.render_template(class_name, tool_type))
        self.registry.register_custom_tool_file(path, class_name)
        return path

    def rename(self, old_name: str, new_name: str) -> Path:
        old_meta = self.registry.get_tool(old_name)
        if old_meta is not None and not old_meta.editable:
            raise PermissionError(old_name)
        new_meta = self.registry.get_tool(new_name)
        if new_meta is not None:
            raise FileExistsError(new_name)

        old_path = self.registry.resolve_tool_source(old_name) if old_meta is not None else None
        if old_path is None:
            old_path = self.path_for(old_name)
        if not old_path.exists():
            if old_meta is not None:
                raise FileNotFoundError(old_name)
            raise FileNotFoundError(old_name)
        self._require_custom_path(old_path)

        new_path = self.path_for(new_name)
        if new_path.exists():
            raise FileExistsError(new_path.name)
        self._require_custom_path(new_path)

        source = self._rewrite_class_name(old_path.read_text(encoding="utf-8"), old_name, new_name)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(old_path.parent),
            prefix=f".{new_path.stem}.",
            suffix=".tmp.py",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(source)
            os.replace(tmp_name, new_path)
            old_path.unlink()
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise

        self.registry.unregister_custom_tool(old_name)
        self.registry.register_custom_tool_file(new_path, new_name)
        return new_path

    def delete(self, class_name: str) -> Path:
        meta = self.registry.get_tool(class_name)
        if meta is not None and not meta.editable:
            raise PermissionError(class_name)
        path = self.registry.resolve_tool_source(class_name) if meta is not None else None
        if path is None:
            path = self.path_for(class_name)
        if not path.exists():
            if meta is not None:
                raise FileNotFoundError(class_name)
            raise FileNotFoundError(class_name)
        self._require_custom_path(path)
        path.unlink()
        self.registry.unregister_custom_tool(class_name)
        return path

    def usage(
        self,
        class_name: str,
        workflow_store: WorkflowStoreService | None,
    ) -> list[str]:
        if workflow_store is None:
            return []
        affected: list[str] = []
        for info in workflow_store.list_workflows():
            try:
                workflow = workflow_store.get_workflow(info.name)
            except Exception:
                continue
            if any(node.tool_name == class_name for node in workflow.graph.nodes):
                affected.append(info.name)
        return affected

    def _resolve_under_root(self, relative_name: str) -> Path:
        root = self.root.resolve()
        candidate = (self.root / relative_name).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("Custom tool path escapes workflow_root/tools") from exc
        return candidate

    def _require_custom_path(self, path: Path) -> None:
        root = self.root.resolve()
        resolved = path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise PermissionError(f"{path} is outside custom tools root") from exc

    def _atomic_write(self, path: Path, content: str) -> None:
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=f".{path.stem}.",
            suffix=".tmp.py",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise

    def _rewrite_class_name(self, source: str, old_name: str, new_name: str) -> str:
        source = re.sub(
            rf"(^\s*class\s+){re.escape(old_name)}(\s*\()",
            rf"\g<1>{new_name}\2",
            source,
            count=1,
            flags=re.MULTILINE,
        )
        source = re.sub(
            rf'(^\s*display_name\s*=\s*)"{re.escape(name_to_display(old_name))}"',
            rf'\g<1>"{name_to_display(new_name)}"',
            source,
            count=1,
            flags=re.MULTILINE,
        )
        source = source.replace(
            f"Implement {old_name}.process_row",
            f"Implement {new_name}.process_row",
        )
        source = source.replace(
            f"Implement {old_name}.transform",
            f"Implement {new_name}.transform",
        )
        return source


__all__ = ["CustomToolService", "name_to_display", "name_to_snake"]
