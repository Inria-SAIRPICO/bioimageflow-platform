"""Install and inspect immutable demo templates bundled with the application."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from bioimageflow_server.models.demo_workflows import (
    DemoWorkflowStatus,
    DemoWorkflowsStatus,
)
from bioimageflow_server.models.workflow import WorkflowDocument
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import (
    WorkflowStoreService,
    WorkflowTemplate,
)


class DemoWorkflowConflictError(FileExistsError):
    """Raised when a canonical demo identity is occupied by unrelated content."""

    def __init__(self, workflow_ids: list[str]) -> None:
        self.workflow_ids = workflow_ids
        super().__init__(", ".join(workflow_ids))


@dataclass(frozen=True)
class _TemplateDefinition:
    id: str
    version: int
    workflow_id: str
    directory: str


class DemoWorkflowService:
    """Derive demo state from canonical paths and install missing templates."""

    def __init__(
        self,
        store: WorkflowStoreService,
        registry: ToolRegistryService,
        *,
        resource_root: Path | None = None,
    ) -> None:
        self.store = store
        self.registry = registry
        self.resource_root = resource_root or Path(
            str(files("bioimageflow_server.data").joinpath("demo_workflows", "v1"))
        )
        manifest = self._read_json(self.resource_root / "manifest.json")
        self.bundle_version = int(manifest["bundle_version"])
        self.templates = tuple(
            _TemplateDefinition(
                id=str(item["id"]),
                version=int(item["version"]),
                workflow_id=str(item["workflow_id"]),
                directory=str(item["directory"]),
            )
            for item in manifest["workflows"]
        )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"Bundled demo resource must contain an object: {path}")
        return value

    def _template_document(self, template: _TemplateDefinition) -> WorkflowDocument:
        document = WorkflowDocument.model_validate(
            self._read_json(self.resource_root / template.directory / "workflow.json")
        )
        provenance = document.metadata.bundled_template
        if (
            provenance is None
            or provenance.id != template.id
            or provenance.version != template.version
        ):
            raise ValueError(f"Bundled demo provenance mismatch for {template.id}")
        return document

    def _item_status(self, template: _TemplateDefinition) -> DemoWorkflowStatus:
        display_name = self._template_document(template).graph.display_name
        if not self.store.has_workflow_collision(template.workflow_id):
            return DemoWorkflowStatus(
                id=template.id,
                version=template.version,
                workflow_id=template.workflow_id,
                display_name=display_name,
                status="missing",
            )
        try:
            document = self.store.read_workflow_document(template.workflow_id)
        except (FileNotFoundError, OSError, ValueError):
            return DemoWorkflowStatus(
                id=template.id,
                version=template.version,
                workflow_id=template.workflow_id,
                display_name=display_name,
                status="conflict",
            )
        provenance = document.metadata.bundled_template
        if provenance is None or provenance.id != template.id:
            return DemoWorkflowStatus(
                id=template.id,
                version=template.version,
                workflow_id=template.workflow_id,
                display_name=display_name,
                status="conflict",
            )
        return DemoWorkflowStatus(
            id=template.id,
            version=template.version,
            workflow_id=template.workflow_id,
            display_name=display_name,
            status="installed",
            installed_version=provenance.version,
            identity_generation=self.store.workflow_generation(template.workflow_id),
        )

    def status(self) -> DemoWorkflowsStatus:
        items = [self._item_status(template) for template in self.templates]
        states = {item.status for item in items}
        if "conflict" in states:
            aggregate = "conflict"
        elif states == {"installed"}:
            aggregate = "installed"
        elif states == {"missing"}:
            aggregate = "missing"
        else:
            aggregate = "partial"
        return DemoWorkflowsStatus(
            bundle_version=self.bundle_version,
            status=aggregate,
            workflows=items,
            can_install="missing" in states and "conflict" not in states,
            can_remove="installed" in states,
        )

    def _workflow_template(self, template: _TemplateDefinition) -> WorkflowTemplate:
        directory = self.resource_root / template.directory
        tools_dir = directory / "tools"
        tool_files = {
            path.name: path.read_bytes()
            for path in sorted(tools_dir.glob("*.py"))
            if not path.name.startswith(".")
        }
        return WorkflowTemplate(
            workflow_id=template.workflow_id,
            document=self._template_document(template),
            tool_files=tool_files,
        )

    def install(self) -> DemoWorkflowsStatus:
        current = self.status()
        conflicts = [
            item.workflow_id for item in current.workflows if item.status == "conflict"
        ]
        if conflicts:
            raise DemoWorkflowConflictError(conflicts)
        missing_ids = {
            item.id for item in current.workflows if item.status == "missing"
        }
        templates = [
            self._workflow_template(template)
            for template in self.templates
            if template.id in missing_ids
        ]
        installed = self.store.install_workflow_templates(templates)
        for info in installed:
            self.registry.register_custom_tools_directory(
                self.store.workflow_tools_dir(info.id or info.name)
            )
        return self.status()
