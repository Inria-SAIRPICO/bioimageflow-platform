"""Workflow discovery stops at saved authorities and stays fresh per request."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from bioimageflow_server.models.workflow import WorkflowCreate
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService


def _store(tmp_path: Path) -> WorkflowStoreService:
    return WorkflowStoreService(tmp_path / "workflows", ToolRegistryService())


@pytest.mark.parametrize("operation", [
    "list_workflows", "workflow_tree", "workflow_format_status",
    "_plan_schema_v2_workflows", "migrate_legacy_workflows",
])
def test_catalog_never_enumerates_saved_or_private_subtrees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="Folder/Visible"))
    store.create_folder("Empty/Sub")
    visible = store.workflow_dir("Folder/Visible")
    document = (visible / "workflow.json").read_bytes()
    broken = store.root_dir / "Folder/Broken"
    broken.mkdir()
    (broken / "workflow.json").write_text("{invalid json")
    private = [store.root_dir / ".worktrees", store.root_dir / "Folder/.private"]
    for root in [visible, broken]:
        for owned in ("results", "tools", ".bioimageflow"):
            nested = root / owned / "deep/Shadow"
            nested.mkdir(parents=True)
            (nested / "workflow.json").write_bytes(document)
    for root in private:
        nested = root / "checkout/Shadow"
        nested.mkdir(parents=True)
        (nested / "workflow.json").write_bytes(document)

    forbidden = [visible, broken, *private]
    enumerated: list[Path] = []
    scandir = os.scandir

    def bounded_scandir(path):
        current = Path(path)
        assert not any(current.is_relative_to(root) for root in forbidden), (
            f"Catalog enumerated a saved workflow or private subtree: {current}"
        )
        enumerated.append(current)
        return scandir(path)

    monkeypatch.setattr(os, "scandir", bounded_scandir)
    result = getattr(store, operation)()

    if operation == "list_workflows":
        assert [workflow.id for workflow in result] == ["Folder/Visible"]
    elif operation == "workflow_tree":
        assert [folder.path for folder in result.folders] == ["Empty", "Folder"]
        assert [folder.path for folder in result.folders[0].folders] == ["Empty/Sub"]
        folder = result.folders[1]
        assert folder.folders == []
        assert [workflow.id for workflow in folder.workflows] == ["Folder/Visible"]
    elif operation == "workflow_format_status":
        assert [(notice.workflow_id, notice.status) for notice in result.notices] == [
            ("Folder/Broken", "error")
        ]
    elif operation == "_plan_schema_v2_workflows":
        assert result == (None, [], set(), [])
    else:
        assert result == []
    # A single operation shares one scan between migration admission and its
    # catalog projection; workflow-owned directory count cannot increase it.
    assert sorted(enumerated) == sorted([
        store.root_dir, store.root_dir / "Folder", store.root_dir / "Empty",
        store.root_dir / "Empty/Sub",
    ])
    assert (broken / "workflow.json").read_text() == "{invalid json"


def test_catalog_observes_external_changes_on_the_next_call(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="Initial"))
    assert [workflow.id for workflow in store.list_workflows()] == ["Initial"]
    assert store.workflow_tree().folders == []
    assert store.workflow_format_status().notices == []
    source = (store.workflow_dir("Initial") / "workflow.json").read_bytes()

    added = store.root_dir / "Added/Nested"
    added.mkdir(parents=True)
    (added / "workflow.json").write_bytes(source)
    (store.root_dir / "ExternalEmpty/Child").mkdir(parents=True)
    invalid = store.root_dir / "Broken"
    invalid.mkdir()
    (invalid / "workflow.json").write_text("not json")

    assert [workflow.id for workflow in store.list_workflows()] == ["Added/Nested", "Initial"]
    tree = store.workflow_tree()
    assert [folder.path for folder in tree.folders] == ["Added", "ExternalEmpty"]
    assert [workflow.id for workflow in tree.folders[0].workflows] == ["Added/Nested"]
    assert tree.folders[1].folders[0].path == "ExternalEmpty/Child"
    assert [notice.workflow_id for notice in store.workflow_format_status().notices] == ["Broken"]

    (added / "workflow.json").unlink()
    assert [workflow.id for workflow in store.list_workflows()] == ["Initial"]
    assert store.workflow_tree().folders[0].folders[0].path == "Added/Nested"


def test_catalog_keeps_valid_folder_names_and_pending_migration_ownership(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="results/tools/runtime/Current"))
    current_path = store.workflow_dir("results/tools/runtime/Current") / "workflow.json"
    current = json.loads(current_path.read_text())
    pending = store.root_dir / "Folder/Pending"
    pending.mkdir(parents=True)
    legacy = json.loads(current_path.read_text())
    legacy["graph"]["schema_version"] = 1
    (pending / "workflow.json").write_text(json.dumps(legacy))
    nested = pending / "results/ShouldNotMigrate"
    nested.mkdir(parents=True)
    nested_path = nested / "workflow.json"
    nested_path.write_text(json.dumps(legacy))
    nested_before = nested_path.read_bytes()

    assert [workflow.id for workflow in store.list_workflows()] == ["results/tools/runtime/Current"]
    status = store.workflow_format_status()
    assert status.pending_plan_id is not None
    assert [notice.workflow_id for notice in status.notices] == ["Folder/Pending"]
    assert json.loads(current_path.read_text()) == current
    assert nested_path.read_bytes() == nested_before
    assert store.workflow_tree().folders[1].path == "results"


def test_catalog_does_not_follow_directory_links_but_keeps_file_link_authority(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="Folder/Actual"))
    actual = store.workflow_dir("Folder/Actual")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "workflow.json").write_bytes((actual / "workflow.json").read_bytes())
    (store.root_dir / "LinkedFolder").symlink_to(actual.parent, target_is_directory=True)
    (store.root_dir / "LinkedWorkflow").symlink_to(actual, target_is_directory=True)
    (store.root_dir / "External").symlink_to(outside, target_is_directory=True)
    linked_file = store.root_dir / "LinkedFile"
    linked_file.mkdir()
    (linked_file / "workflow.json").symlink_to(actual / "workflow.json")

    assert [workflow.id for workflow in store.list_workflows()] == ["Folder/Actual", "LinkedFile"]
    tree = store.workflow_tree()
    assert [folder.path for folder in tree.folders] == ["External", "Folder", "LinkedFolder"]
    assert tree.folders[0].workflows == tree.folders[0].folders == []
    assert tree.folders[2].workflows == tree.folders[2].folders == []
    assert [workflow.id for workflow in tree.workflows] == ["LinkedFile"]
    assert store.workflow_format_status().notices == []
