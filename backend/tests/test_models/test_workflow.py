"""Tests for workflow models."""

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.workflow import (
    WorkflowCreate,
    WorkflowFile,
    WorkflowInfo,
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
        data = WorkflowFile(
            workflow={"nodes": [], "edges": []},
            gui={"nodes": {"seg_1": {"position": [100, 200]}}},
        )
        rebuilt = WorkflowFile.model_validate_json(data.model_dump_json())
        assert rebuilt.workflow == data.workflow
        assert rebuilt.gui == data.gui
