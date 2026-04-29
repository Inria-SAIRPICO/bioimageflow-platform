"""Tests for workflow models."""

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.workflow import (
    MissingPackage,
    MissingTool,
    WorkflowCreate,
    WorkflowFile,
    WorkflowInfo,
    WorkflowSaveBody,
    WorkflowUpdate,
)


class TestWorkflowCreate:
    def test_minimal(self):
        wf = WorkflowCreate(name="my_workflow")
        assert wf.name == "my_workflow"
        assert wf.display_name is None
        assert wf.description is None
        assert wf.storage_path is None

    def test_full(self):
        wf = WorkflowCreate(
            name="seg_pipeline",
            display_name="Segmentation Pipeline",
            description="A pipeline for cell segmentation",
            storage_path="/data/workflows/seg",
        )
        assert wf.display_name == "Segmentation Pipeline"
        assert wf.description == "A pipeline for cell segmentation"
        assert wf.storage_path == "/data/workflows/seg"

    @pytest.mark.parametrize("name", ["-bad", "My Workflow!", ""])
    def test_invalid_name_rejected(self, name: str):
        with pytest.raises(ValidationError):
            WorkflowCreate(name=name)

    def test_valid_name_accepts_hyphen_and_underscore(self):
        wf = WorkflowCreate(name="My_Workflow-1")
        assert wf.name == "My_Workflow-1"


class TestWorkflowInfo:
    def test_construction(self):
        info = WorkflowInfo(
            name="my_wf",
            display_name="My Workflow",
            path="/workflows/my_wf.json",
            last_modified="2026-04-01T12:00:00Z",
        )
        assert info.name == "my_wf"
        assert info.description is None

    def test_with_description(self):
        info = WorkflowInfo(
            name="my_wf",
            display_name="My Workflow",
            path="/workflows/my_wf.json",
            last_modified="2026-04-01T12:00:00Z",
            description="Does things",
        )
        assert info.description == "Does things"

    def test_with_storage_path(self):
        info = WorkflowInfo(
            name="my_wf",
            display_name="My Workflow",
            path="/workflows/my_wf.json",
            last_modified="2026-04-01T12:00:00Z",
            storage_path="/tmp/my_wf",
        )
        assert info.storage_path == "/tmp/my_wf"


class TestWorkflowUpdate:
    def test_update_action(self):
        upd = WorkflowUpdate(action="update", display_name="New Name")
        assert upd.action == "update"
        assert upd.display_name == "New Name"
        assert upd.new_name is None

    def test_duplicate_action(self):
        upd = WorkflowUpdate(action="duplicate", new_name="copy_1")
        assert upd.action == "duplicate"
        assert upd.new_name == "copy_1"

    def test_invalid_action_rejected(self):
        with pytest.raises(ValidationError):
            WorkflowUpdate.model_validate({"action": "delete"})


class TestWorkflowFile:
    def test_roundtrip(self):
        info = WorkflowInfo(
            name="my_wf",
            display_name="My Workflow",
            path="/workflows/my_wf.json",
            last_modified="2026-04-01T12:00:00Z",
        )
        graph = GraphState(nodes=[], edges=[])
        data = WorkflowFile(
            info=info,
            graph=graph,
            gui={"nodes": {"seg_1": {"position": [100, 200]}}},
            missing_packages=[
                MissingPackage(
                    package_name="pkg",
                    required_version="1.0",
                    affected_nodes=["seg_1"],
                )
            ],
            missing_tools=[MissingTool(node_id="seg_1", tool_name="Seg")],
        )
        rebuilt = WorkflowFile.model_validate_json(data.model_dump_json())
        assert rebuilt.info == data.info
        assert rebuilt.graph == data.graph
        assert rebuilt.gui == data.gui
        assert rebuilt.missing_packages == data.missing_packages
        assert rebuilt.missing_tools == data.missing_tools

    def test_defaults(self):
        info = WorkflowInfo(
            name="my_wf",
            display_name="My Workflow",
            path="/workflows/my_wf.json",
            last_modified="2026-04-01T12:00:00Z",
        )
        data = WorkflowFile(info=info, graph=GraphState(nodes=[], edges=[]))
        assert data.gui == {}
        assert data.missing_packages == []
        assert data.missing_tools == []


class TestWorkflowSaveBody:
    def test_with_graph_state(self):
        graph = GraphState(nodes=[], edges=[])
        body = WorkflowSaveBody(graph=graph)
        assert body.graph == graph


class TestMissingModels:
    def test_missing_package_defaults(self):
        missing = MissingPackage(package_name="pkg", required_version="1.0")
        assert missing.installed_versions == []
        assert missing.affected_nodes == []

    def test_missing_tool_defaults(self):
        missing = MissingTool(node_id="node_1", tool_name="MissingTool")
        assert missing.installed_versions == []
