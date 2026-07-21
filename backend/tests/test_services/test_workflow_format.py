"""Legacy workflow migration and invalid-format diagnostics tests."""

from __future__ import annotations

import json
from pathlib import Path

from bioimageflow_server.models.workflow import WorkflowDocument
from bioimageflow_server.models.workflow_draft import WorkflowDraftResponse
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService


def _legacy_graph(*, parameter: int = 3) -> dict:
    return {
        "nodes": [
            {
                "id": "example_1",
                "name": "Example 1",
                "tool_name": "ExampleTool",
                "position": [12.0, 34.0],
                "parameters": {"threshold": parameter},
                "resources": {},
                "output_templates": {"result": "{node_name}.tif"},
                "enabled": True,
                "collapsed": False,
                "sub_workflow": None,
            }
        ],
        "edges": [],
        "published_inputs": [],
        "published_outputs": [],
    }


def _legacy_document() -> dict:
    return {
        "graph": _legacy_graph(),
        "gui": {"zoom": 1},
        "metadata": {
            "display_name": "Legacy example",
            "description": "Saved by the previous platform format.",
            "storage_path": "/tmp/example-output",
        },
        "workflow": {
            "nodes": [
                {
                    "name": "example_1",
                    "tool_module": "example_tools",
                    "tool_class": "ExampleTool",
                    "tool_package": "example-tools",
                    "tool_package_version": "1.2.3",
                }
            ],
            "edges": [],
            "config": {
                "storage_path": "/tmp/example-output",
                "engine": "wetlands",
                "execution": "sequential",
            },
        },
    }


def _store(tmp_path: Path) -> WorkflowStoreService:
    return WorkflowStoreService(tmp_path / "workflows", ToolRegistryService())


def test_migrates_legacy_workflow_and_dirty_draft_with_backups(tmp_path: Path) -> None:
    store = _store(tmp_path)
    workflow_dir = store.root_dir / "Folder" / "legacy"
    workflow_dir.mkdir(parents=True)
    workflow_path = workflow_dir / "workflow.json"
    legacy = _legacy_document()
    workflow_path.write_text(json.dumps(legacy), encoding="utf-8")
    draft_path = workflow_dir / ".bioimageflow" / "draft.json"
    draft_path.parent.mkdir()
    draft_path.write_text(
        json.dumps(
            {
                "draft_version": 1,
                "workflow_id": "Folder/legacy",
                "base_saved_revision": "sha256:" + "0" * 64,
                "draft_revision": 7,
                "updated_at": "2026-07-20T12:00:00Z",
                "updated_by": "frontend",
                "dirty_against_saved": True,
                "graph": _legacy_graph(parameter=9),
                "validation": {"valid": False, "node_statuses": {}, "errors": []},
            }
        ),
        encoding="utf-8",
    )

    notices = store.migrate_legacy_workflows()

    assert [notice.workflow_id for notice in notices] == ["Folder/legacy"]
    document = WorkflowDocument.model_validate_json(workflow_path.read_text())
    draft = WorkflowDraftResponse.model_validate_json(draft_path.read_text())
    assert document.graph.nodes[0].parameters == {"threshold": 3}
    assert document.graph.nodes[0].tool_package_version == "1.2.3"
    assert draft.graph.nodes[0].parameters == {"threshold": 9}
    assert draft.dirty_against_saved is True
    assert draft.draft_revision == 7
    assert draft.base_saved_revision == document.artifact_hash
    assert draft.validation.valid is True
    assert len(list((workflow_dir / ".bioimageflow" / "backups").glob("*.json"))) == 2
    assert [workflow.id for workflow in store.list_workflows()] == ["Folder/legacy"]
    assert store.workflow_format_status().notices == notices


def test_leaves_unrecognized_workflow_unchanged_and_reports_it(tmp_path: Path) -> None:
    store = _store(tmp_path)
    workflow_dir = store.root_dir / "broken"
    workflow_dir.mkdir(parents=True)
    workflow_path = workflow_dir / "workflow.json"
    original = {"graph": {"nodes": []}, "unexpected": True}
    workflow_path.write_text(json.dumps(original), encoding="utf-8")

    assert store.migrate_legacy_workflows() == []
    assert json.loads(workflow_path.read_text()) == original
    assert store.list_workflows() == []
    status = store.workflow_format_status()
    assert len(status.notices) == 1
    assert status.notices[0].status == "error"
    assert status.notices[0].workflow_id == "broken"
    assert "hidden" in status.notices[0].detail


def test_recovers_legacy_draft_when_saved_workflow_is_already_current(tmp_path: Path) -> None:
    store = _store(tmp_path)
    workflow_dir = store.root_dir / "legacy"
    workflow_dir.mkdir(parents=True)
    legacy = _legacy_document()
    workflow_path = workflow_dir / "workflow.json"
    workflow_path.write_text(json.dumps(legacy), encoding="utf-8")
    store.migrate_legacy_workflows()

    draft_path = workflow_dir / ".bioimageflow" / "draft.json"
    draft_path.write_text(
        json.dumps(
            {
                "draft_version": 1,
                "workflow_id": "legacy",
                "base_saved_revision": "sha256:" + "0" * 64,
                "draft_revision": 2,
                "updated_at": "2026-07-20T12:00:00Z",
                "updated_by": "frontend",
                "dirty_against_saved": True,
                "graph": _legacy_graph(parameter=11),
                "validation": {"valid": False, "node_statuses": {}, "errors": []},
            }
        ),
        encoding="utf-8",
    )

    notices = store.migrate_legacy_workflows()

    assert len(notices) == 1
    assert "live draft" in notices[0].detail
    draft = WorkflowDraftResponse.model_validate_json(draft_path.read_text())
    assert draft.graph.nodes[0].parameters == {"threshold": 11}
    assert draft.draft_revision == 2


def test_refuses_ambiguous_legacy_published_interfaces(tmp_path: Path) -> None:
    store = _store(tmp_path)
    workflow_dir = store.root_dir / "published"
    workflow_dir.mkdir(parents=True)
    workflow_path = workflow_dir / "workflow.json"
    legacy = _legacy_document()
    legacy["graph"]["published_inputs"] = [
        {
            "name": "threshold",
            "internal_node_id": "example_1",
            "internal_field": "threshold",
            "kind": "parameter",
        }
    ]
    workflow_path.write_text(json.dumps(legacy), encoding="utf-8")

    assert store.migrate_legacy_workflows() == []
    assert json.loads(workflow_path.read_text()) == legacy
    assert store.workflow_format_status().notices[0].status == "error"
