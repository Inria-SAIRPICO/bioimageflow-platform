"""Explicit saved-source refresh and trusted Python materialization tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowSaveBody
from bioimageflow_server.models.workflow_sources import WorkflowSourceApplyRequest
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_sources import (
    WorkflowSourceConflict,
    WorkflowSourceService,
)
from bioimageflow_server.services.workflow_store import WorkflowStoreService


def _store(tmp_path: Path) -> WorkflowStoreService:
    return WorkflowStoreService(tmp_path / "workflows", ToolRegistryService())


def _graph(name: str, display_name: str | None = None) -> GraphState:
    return GraphState.model_validate(
        {
            "schema_version": 1,
            "name": name,
            "display_name": display_name or name.title(),
            "nodes": [],
            "edges": [],
            "interface": {"inputs": [], "outputs": []},
            "config": {
                "storage_path": "./bif_data",
                "engine": "direct",
                "execution": "parallel",
            },
        }
    )


def _parent_graph(source_graph: GraphState, source_hash: str) -> GraphState:
    return GraphState.model_validate(
        {
            **_graph("parent").model_dump(mode="json", by_alias=True),
            "nodes": [
                {
                    "type": "workflow",
                    "id": "child",
                    "name": "Child instance",
                    "workflow": source_graph.model_dump(mode="json", by_alias=True),
                    "bindings": {},
                    "position": [0, 0],
                    "source": {
                        "kind": "workspace",
                        "workflow_id": "child",
                        "artifact_hash": source_hash,
                    },
                }
            ],
        }
    )


def test_source_refresh_is_previewed_and_applied_explicitly(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="child"))
    child = store.get_workflow("child")
    store.create_workflow(WorkflowCreate(name="parent"))
    store.save_workflow(
        "parent", WorkflowSaveBody(graph=_parent_graph(child.graph, child.artifact_hash))
    )
    store.save_workflow(
        "child", WorkflowSaveBody(graph=_graph("child", "Updated child"))
    )
    parent = store.get_workflow("parent")
    service = WorkflowSourceService(lambda: store)

    preview = service.preview_source_update(
        "parent", ["child"], expected_artifact_hash=parent.artifact_hash
    )

    assert preview.replacement.display_name == "Updated child"
    assert store.get_workflow("parent").graph.nodes[0].workflow.display_name == "child"  # type: ignore[union-attr]

    result = service.apply(
        WorkflowSourceApplyRequest(
            token=preview.token,
            confirm_effects=preview.destructive_effects,
        )
    )

    updated = store.get_workflow("parent")
    assert result.artifact_hash == updated.artifact_hash
    assert updated.graph.nodes[0].workflow.display_name == "Updated child"  # type: ignore[union-attr]
    assert updated.graph.nodes[0].source.artifact_hash == store.get_workflow(  # type: ignore[union-attr]
        "child"
    ).artifact_hash


def test_source_refresh_conflicts_when_parent_changes_after_preview(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="child"))
    child = store.get_workflow("child")
    store.create_workflow(WorkflowCreate(name="parent"))
    parent_graph = _parent_graph(child.graph, child.artifact_hash)
    store.save_workflow("parent", WorkflowSaveBody(graph=parent_graph))
    service = WorkflowSourceService(lambda: store)
    parent = store.get_workflow("parent")
    preview = service.preview_source_update(
        "parent", ["child"], expected_artifact_hash=parent.artifact_hash
    )
    store.save_workflow(
        "parent",
        WorkflowSaveBody(
            graph=parent_graph.model_copy(update={"display_name": "Changed parent"})
        ),
    )

    with pytest.raises(WorkflowSourceConflict, match="Parent workflow artifact changed"):
        service.apply(
            WorkflowSourceApplyRequest(
                token=preview.token,
                confirm_effects=preview.destructive_effects,
            )
        )


def test_python_materialization_uses_workflow_local_factory_and_fresh_helpers(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="python-authored"))
    workflow_dir = store.workflow_dir("python-authored")
    (workflow_dir / "helper.py").write_text('LABEL = "First"\n', encoding="utf-8")
    (workflow_dir / "workflow.py").write_text(
        "from bioimageflow import Workflow\n"
        "from helper import LABEL\n\n"
        "def build_workflow():\n"
        "    return Workflow(name='python_definition', display_name=LABEL, engine='direct')\n",
        encoding="utf-8",
    )
    service = WorkflowSourceService(lambda: store)
    current = store.get_workflow("python-authored")
    first = service.preview_python_rebuild(
        "python-authored", expected_artifact_hash=current.artifact_hash
    )
    service.apply(
        WorkflowSourceApplyRequest(
            token=first.token,
            confirm_effects=first.destructive_effects,
        )
    )
    saved = store.get_workflow("python-authored")

    assert saved.graph.name == "python_definition"
    assert saved.graph.display_name == "First"
    assert saved.authoring_source is not None
    assert saved.authoring_source.factory == "build_workflow"

    (workflow_dir / "helper.py").write_text('LABEL = "Second"\n', encoding="utf-8")
    second = service.preview_python_rebuild(
        "python-authored", expected_artifact_hash=saved.artifact_hash
    )

    assert second.source_artifact_hash != first.source_artifact_hash
    assert second.replacement.display_name == "Second"


def test_python_materialization_is_disabled_in_webapp_mode(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="python-authored"))
    service = WorkflowSourceService(
        lambda: store,
        deployment_mode_provider=lambda: "webapp",
        unsafe_webapp_features_provider=lambda: False,
    )

    with pytest.raises(PermissionError):
        service.preview_python_rebuild(
            "python-authored",
            expected_artifact_hash=store.get_workflow("python-authored").artifact_hash,
        )
