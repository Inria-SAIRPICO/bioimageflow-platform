"""Explicit independent-copy resolution preserves both workflow directories."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowSaveBody
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_draft import WorkflowDraftService
from bioimageflow_server.services.workflow_store import (
    WorkflowIdentityConflictError,
    WorkflowMoveRecoveryError,
    WorkflowStoreService,
)


def _copies(tmp_path: Path) -> tuple[WorkflowStoreService, str]:
    store = WorkflowStoreService(tmp_path / "workflows", ToolRegistryService())
    original = store.create_workflow(WorkflowCreate(name="original"))
    draft = WorkflowDraftService(lambda: store)
    pending = store.get_workflow(original.id).graph.model_copy(update={"display_name": "Pending edit"})
    draft.put_draft(original.id, graph=pending, expected_revision=0, should_validate=False)
    original_dir = store.workflow_dir(original.id)
    (original_dir / "results").mkdir()
    (original_dir / "results" / "retained.bin").write_bytes(b"copied result sentinel")
    (original_dir / "tools" / "retained.txt").write_bytes(b"copied source sentinel")
    shutil.copytree(original_dir, store.root_dir / "copy")
    return store, original.id


def _copy_hash(store: WorkflowStoreService) -> str:
    [conflict] = store.workflow_format_status().identity_conflicts
    return next(copy.document_hash for copy in conflict.copies if copy.relative_path == "copy")


def test_confirmed_copy_gets_fresh_uuid_and_keeps_files_hash_and_draft(tmp_path: Path) -> None:
    store, original_id = _copies(tmp_path)
    directory = store.root_dir / "copy"
    original_bytes = (store.root_dir / "original" / "workflow.json").read_bytes()
    copied = json.loads((directory / "workflow.json").read_text())
    draft_path = directory / ".bioimageflow" / "draft.json"
    draft = json.loads(draft_path.read_text())
    result = store.resolve_identity_copy("copy", original_id, _copy_hash(store))
    assert result.id != original_id
    assert result.relative_path == "copy"
    assert json.loads((directory / "workflow.json").read_text()) == {**copied, "workflow_id": result.id}
    assert json.loads(draft_path.read_text()) == {**draft, "workflow_id": result.id}
    assert (directory / "results" / "retained.bin").read_bytes() == b"copied result sentinel"
    assert (directory / "tools" / "retained.txt").read_bytes() == b"copied source sentinel"
    assert (store.root_dir / "original" / "workflow.json").read_bytes() == original_bytes
    assert store.get_workflow(result.id).artifact_hash == store.get_workflow(original_id).artifact_hash
    assert store.get_workflow(original_id).info.relative_path == "original"
    assert store.workflow_format_status().identity_conflicts == []
    backups = list((store.workspace_dir / ".bioimageflow" / "backups" / "workflow-format").glob("**/workflow.json"))
    assert any(json.loads(path.read_text()) == copied for path in backups)


def test_stale_copy_confirmation_changes_nothing(tmp_path: Path) -> None:
    store, original_id = _copies(tmp_path)
    digest = _copy_hash(store)
    path = store.root_dir / "copy" / "workflow.json"
    raw = json.loads(path.read_text())
    raw["metadata"]["description"] = "Changed after review"
    path.write_text(json.dumps(raw))
    before = path.read_bytes()
    with pytest.raises(WorkflowIdentityConflictError, match="document changed"):
        store.resolve_identity_copy("copy", original_id, digest)
    assert path.read_bytes() == before
    assert not store._schema_v2_migration_journal_path.exists()


def test_resolution_requires_a_current_duplicate_identity(tmp_path: Path) -> None:
    store, original_id = _copies(tmp_path)
    digest = _copy_hash(store)
    shutil.rmtree(store.root_dir / "original")
    before = (store.root_dir / "copy" / "workflow.json").read_bytes()
    with pytest.raises(WorkflowIdentityConflictError, match="no longer has multiple"):
        store.resolve_identity_copy("copy", original_id, digest)
    assert (store.root_dir / "copy" / "workflow.json").read_bytes() == before


def test_interrupted_copy_resolution_recovers_same_uuid_and_blocks_other_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, original_id = _copies(tmp_path)
    digest = _copy_hash(store)
    draft_path = store.root_dir / "copy" / ".bioimageflow" / "draft.json"
    original_draft = json.loads(draft_path.read_text())
    writer = store._write_schema_v2_json
    def interrupted(path: Path, payload: dict) -> None:
        if path == draft_path:
            raise OSError("copy resolution interrupted")
        writer(path, payload)
    monkeypatch.setattr(store, "_write_schema_v2_json", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        store.resolve_identity_copy("copy", original_id, digest)
    assigned = json.loads((store.root_dir / "copy" / "workflow.json").read_text())["workflow_id"]
    assert assigned != original_id
    with pytest.raises(WorkflowMoveRecoveryError, match="must recover"):
        store.save_workflow(original_id, WorkflowSaveBody(graph=store.get_workflow(original_id).graph))
    reopened = WorkflowStoreService(store.root_dir, store.tool_registry)
    reopened.recover_workflow_format_migration()
    assert json.loads(draft_path.read_text()) == {**original_draft, "workflow_id": assigned}
    assert reopened.get_workflow(assigned).info.relative_path == "copy"
    assert not reopened._schema_v2_migration_journal_path.exists()
