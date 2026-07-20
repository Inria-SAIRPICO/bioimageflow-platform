"""Tests for workspace workflow and canonical document models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.workflow import (
    MissingPackage,
    MissingTool,
    PythonAuthoringProvenance,
    WorkflowCreate,
    WorkflowDocument,
    WorkflowFile,
    WorkflowInfo,
    WorkflowSaveBody,
    WorkflowUpdate,
    WorkspaceWorkflowMetadata,
)


def _graph() -> GraphState:
    return GraphState.model_validate(
        {
            "schema_version": 1,
            "name": "workflow",
            "display_name": "Workflow",
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


@pytest.mark.parametrize("name", ["-bad", "bad!", "bad/ name", "bad/name ", ""])
def test_invalid_workspace_identity_is_rejected(name: str) -> None:
    with pytest.raises(ValidationError):
        WorkflowCreate(name=name)


@pytest.mark.parametrize("name", ["workflow", "My_Workflow-1", "folder/workflow"])
def test_valid_workspace_identity(name: str) -> None:
    assert WorkflowCreate(name=name).name == name


def test_update_actions_are_strict() -> None:
    assert WorkflowUpdate(action="update", display_name="New").display_name == "New"
    assert WorkflowUpdate(action="duplicate", new_name="copy").new_name == "copy"
    with pytest.raises(ValidationError):
        WorkflowUpdate.model_validate({"action": "remove"})


def test_canonical_document_round_trip() -> None:
    document = WorkflowDocument(
        graph=_graph(),
        metadata=WorkspaceWorkflowMetadata(
            description="Description", storage_path="/tmp/output"
        ),
        authoring_source=PythonAuthoringProvenance(
            source_id="workflow.py",
            source_hash="sha256:" + "a" * 64,
        ),
        artifact_hash="sha256:" + "b" * 64,
    )

    rebuilt = WorkflowDocument.model_validate_json(document.model_dump_json())

    assert rebuilt == document
    assert rebuilt.authoring_source is not None
    assert rebuilt.authoring_source.factory == "build_workflow"


def test_canonical_document_rejects_competing_sections() -> None:
    payload = WorkflowDocument(
        graph=_graph(),
        metadata=WorkspaceWorkflowMetadata(storage_path="/tmp/output"),
        artifact_hash="sha256:" + "b" * 64,
    ).model_dump(mode="json")
    payload["secondary_graph"] = {}

    with pytest.raises(ValidationError):
        WorkflowDocument.model_validate(payload)


def test_workflow_file_projects_graph_and_artifact_identity() -> None:
    info = WorkflowInfo(
        name="workflow",
        display_name="Workflow",
        path="/workflows/workflow/workflow.json",
        last_modified="2026-04-01T12:00:00Z",
    )
    data = WorkflowFile(
        info=info,
        graph=_graph(),
        artifact_hash="sha256:" + "a" * 64,
        missing_packages=[
            MissingPackage(
                package_name="package",
                required_version="1.0",
                affected_nodes=["child/tool"],
            )
        ],
        missing_tools=[MissingTool(node_id="child/tool", tool_name="Tool")],
    )

    rebuilt = WorkflowFile.model_validate_json(data.model_dump_json())

    assert rebuilt == data
    assert rebuilt.missing_packages[0].affected_nodes == ["child/tool"]


def test_save_body_carries_only_the_canonical_graph() -> None:
    body = WorkflowSaveBody(graph=_graph())
    assert body.model_dump().keys() == {"graph"}
