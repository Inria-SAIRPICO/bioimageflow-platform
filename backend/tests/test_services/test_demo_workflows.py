"""Bundled demo workflow installation and provenance tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowSaveBody
from bioimageflow_server.services.demo_workflows import (
    DemoWorkflowConflictError,
    DemoWorkflowService,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService


def _service(tmp_path: Path) -> tuple[DemoWorkflowService, WorkflowStoreService]:
    registry = ToolRegistryService()
    store = WorkflowStoreService(
        tmp_path / "workflows",
        registry,
        storage_base_dir=tmp_path / "outputs",
    )
    return DemoWorkflowService(store, registry), store


def test_install_publishes_exact_self_contained_demo_identities(tmp_path: Path) -> None:
    service, store = _service(tmp_path)

    assert service.status().status == "missing"
    installed = service.install()

    assert installed.status == "installed"
    assert [item.workflow_id for item in installed.workflows] == [
        "Demo/Fish Analysis",
        "Demo/Parameters Space Exploration",
    ]
    for item in installed.workflows:
        document = store.read_workflow_document(item.workflow_id)
        assert document.metadata.bundled_template is not None
        assert document.metadata.bundled_template.id == item.id
        assert document.metadata.storage_path == str(
            tmp_path / "outputs" / Path(item.workflow_id)
        )
        assert list(store.workflow_tools_dir(item.workflow_id).glob("*.py"))
        assert all(node.source_module is None for node in document.graph.nodes if node.type == "tool")
    assert store.get_workflow("Demo/Fish Analysis").graph.interface.inputs == []
    parameter_inputs = store.get_workflow(
        "Demo/Parameters Space Exploration"
    ).graph.interface.inputs
    assert [item.name for item in parameter_inputs] == ["marker_channel"]
    fish = store.get_workflow("Demo/Fish Analysis")
    assert {item.package_name for item in fish.missing_packages} == {
        "bioimageflow_common_tools",
        "bioimageflow_segmentation_tools",
        "bioimageflow_spot_tools",
    }
    assert "DownloadImages" not in {item.tool_name for item in fish.missing_tools}
    assert "AverageSpotsPerNucleus" not in {
        item.tool_name for item in fish.missing_tools
    }


def test_install_is_idempotent_and_never_overwrites_installed_demo(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    service.install()
    fish_path = store.workflow_dir("Demo/Fish Analysis") / "workflow.json"
    before = fish_path.read_bytes()
    fish = store.get_workflow("Demo/Fish Analysis")
    edited = fish.graph.model_copy(update={"display_name": "My edited demo"})
    store.save_workflow("Demo/Fish Analysis", WorkflowSaveBody(graph=edited))
    edited_bytes = fish_path.read_bytes()

    result = service.install()

    assert result.status == "installed"
    assert fish_path.read_bytes() == edited_bytes
    assert fish_path.read_bytes() != before


def test_missing_demo_can_be_reinstalled_without_touching_other_demo(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    service.install()
    fish_path = store.workflow_dir("Demo/Fish Analysis") / "workflow.json"
    fish_bytes = fish_path.read_bytes()
    store.delete_workflow("Demo/Parameters Space Exploration")

    assert service.status().status == "partial"
    assert service.install().status == "installed"
    assert fish_path.read_bytes() == fish_bytes


def test_unrelated_workflow_at_canonical_path_is_a_visible_conflict(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    store.create_workflow(
        WorkflowCreate(name="Demo/Fish Analysis", display_name="Unrelated workflow")
    )

    status = service.status()

    assert status.status == "conflict"
    assert status.can_install is False
    with pytest.raises(DemoWorkflowConflictError):
        service.install()
