"""Crash-recovery coverage for folder workflow identity moves."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest

from bioimageflow_server.models.workflow import WorkflowCreate
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import (
    WorkflowMoveRecoveryError,
    WorkflowStoreService,
)
from tests.graph_factory import graph_document


def _store(tmp_path: Path) -> WorkflowStoreService:
    return WorkflowStoreService(
        root_dir=tmp_path / "workflows",
        tool_registry=ToolRegistryService(),
        storage_base_dir=tmp_path / "outputs",
    )


def _workflow_json(store: WorkflowStoreService, workflow_id: str) -> Path:
    return store.workflow_dir(workflow_id) / "workflow.json"


def _draft_json(store: WorkflowStoreService, workflow_id: str) -> Path:
    return store.workflow_dir(workflow_id) / ".bioimageflow" / "draft.json"


def _draft_payload(workflow_id: str, revision: int) -> dict[str, object]:
    return {
        "draft_version": 1,
        "workflow_id": workflow_id,
        "base_saved_revision": f"sha256:saved-{revision}",
        "draft_revision": revision,
        "updated_at": "2026-07-17T12:00:00Z",
        "updated_by": "frontend",
        "dirty_against_saved": True,
        "graph": graph_document(name="draft", display_name="Draft"),
        "validation": {"valid": True, "node_statuses": {}, "errors": []},
    }


def _seed_workflow(
    store: WorkflowStoreService,
    workflow_id: str,
    *,
    revision: int,
) -> tuple[int, bytes]:
    created = store.create_workflow(WorkflowCreate(name=workflow_id))
    storage_path = Path(created.storage_path or "")
    storage_path.mkdir(parents=True)
    payload = f"result for {workflow_id}".encode()
    (storage_path / "result.bin").write_bytes(payload)
    draft_path = _draft_json(store, workflow_id)
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(
        json.dumps(_draft_payload(workflow_id, revision), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return created.identity_generation, payload


def _generation_snapshot(
    store: WorkflowStoreService,
    workflow_ids: list[str],
) -> dict[str, int]:
    return {workflow_id: store.workflow_generation(workflow_id) for workflow_id in workflow_ids}


def _assert_recovered_workflow(
    store: WorkflowStoreService,
    *,
    old_id: str,
    new_id: str,
    revision: int,
    payload: bytes,
) -> None:
    assert not store.workflow_dir(old_id).exists()
    workflow = store.get_workflow(new_id)
    expected_storage = store.storage_base_dir.joinpath(*new_id.split("/"))
    assert workflow.info.id == new_id
    assert Path(workflow.info.storage_path or "") == expected_storage
    assert (expected_storage / "result.bin").read_bytes() == payload
    assert not store.storage_base_dir.joinpath(*old_id.split("/")).exists()

    draft = json.loads(_draft_json(store, new_id).read_text(encoding="utf-8"))
    assert draft == _draft_payload(new_id, revision)
    assert not _draft_json(store, old_id).exists()

    raw = json.loads(_workflow_json(store, new_id).read_text(encoding="utf-8"))
    assert raw["metadata"]["storage_path"] == str(expected_storage)
    assert raw["graph"]["config"]["storage_path"] == "./bif_data"


def _finish_recovery_twice(
    store: WorkflowStoreService,
    operation_id: UUID,
    workflow_ids: list[str],
) -> dict[str, int]:
    first = store.recover_pending_workflow_move()
    assert first is not None
    assert first.operation_id == operation_id
    generations = _generation_snapshot(store, workflow_ids)

    repeated = store.recover_pending_workflow_move()
    assert repeated is not None
    assert repeated.operation_id == operation_id
    assert _generation_snapshot(store, workflow_ids) == generations

    store.mark_workflow_move_phase(operation_id, "snapshots_rewritten")
    store.complete_workflow_move(operation_id)
    assert store.pending_workflow_move() is None
    assert store.recover_pending_workflow_move() is None
    return generations


def test_folder_rename_recovers_after_whole_tree_rename_before_artifact_rewrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    first_generation, first_payload = _seed_workflow(
        store,
        "project/a",
        revision=3,
    )
    second_generation, second_payload = _seed_workflow(
        store,
        "project/nested/b",
        revision=4,
    )
    old_ids = ["project/a", "project/nested/b"]
    new_ids = ["archive/a", "archive/nested/b"]
    all_ids = [*old_ids, *new_ids]
    generations_before = _generation_snapshot(store, all_ids)
    operation_id = store.prepare_folder_rename_move("project", "archive")
    assert operation_id is not None

    def fail_before_first_artifact(_old_id: str, _new_id: str) -> None:
        assert not (store.root_dir / "project").exists()
        assert (store.root_dir / "archive").exists()
        raise OSError("injected failure after whole-tree rename")

    with monkeypatch.context() as patch:
        patch.setattr(store, "_rewrite_moved_workflow_metadata", fail_before_first_artifact)
        with pytest.raises(OSError, match="after whole-tree rename"):
            store.rename_folder(
                "project",
                "archive",
                move_operation_id=operation_id,
            )

    assert not (store.root_dir / "project").exists()
    assert (store.root_dir / "archive").exists()
    assert store.pending_workflow_move() is not None
    generations_after_failure = _generation_snapshot(store, all_ids)
    assert generations_after_failure == {
        "project/a": first_generation + 1,
        "project/nested/b": second_generation + 1,
        "archive/a": generations_before["archive/a"] + 1,
        "archive/nested/b": generations_before["archive/nested/b"] + 1,
    }

    restarted = _store(tmp_path)
    recovered_generations = _finish_recovery_twice(restarted, operation_id, all_ids)

    assert recovered_generations == generations_after_failure
    _assert_recovered_workflow(
        restarted,
        old_id="project/a",
        new_id="archive/a",
        revision=3,
        payload=first_payload,
    )
    _assert_recovered_workflow(
        restarted,
        old_id="project/nested/b",
        new_id="archive/nested/b",
        revision=4,
        payload=second_payload,
    )


def test_folder_rename_recovers_second_workflow_after_storage_moved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    first_generation, first_payload = _seed_workflow(store, "project/a", revision=5)
    second_generation, second_payload = _seed_workflow(store, "project/b", revision=6)
    old_ids = ["project/a", "project/b"]
    new_ids = ["archive/a", "archive/b"]
    all_ids = [*old_ids, *new_ids]
    generations_before = _generation_snapshot(store, all_ids)
    operation_id = store.prepare_folder_rename_move("project", "archive")
    assert operation_id is not None
    original_move_storage = store._move_managed_storage

    def fail_after_second_storage(old_id: str, new_id: str) -> str:
        moved_path = original_move_storage(old_id, new_id)
        if old_id == "project/b":
            raise OSError("injected failure after second managed-storage rename")
        return moved_path

    with monkeypatch.context() as patch:
        patch.setattr(store, "_move_managed_storage", fail_after_second_storage)
        with pytest.raises(OSError, match="second managed-storage rename"):
            store.rename_folder(
                "project",
                "archive",
                move_operation_id=operation_id,
            )

    assert (
        json.loads(_draft_json(store, "archive/b").read_text(encoding="utf-8"))["workflow_id"]
        == "archive/b"
    )
    assert (store.storage_base_dir / "archive" / "b" / "result.bin").exists()
    second_raw = json.loads(_workflow_json(store, "archive/b").read_text(encoding="utf-8"))
    assert second_raw["metadata"]["storage_path"] == str(store.storage_base_dir / "project" / "b")
    generations_after_failure = _generation_snapshot(store, all_ids)
    assert generations_after_failure == {
        "project/a": first_generation + 1,
        "project/b": second_generation + 1,
        "archive/a": generations_before["archive/a"] + 1,
        "archive/b": generations_before["archive/b"] + 1,
    }

    restarted = _store(tmp_path)
    recovered_generations = _finish_recovery_twice(restarted, operation_id, all_ids)

    assert recovered_generations == generations_after_failure
    _assert_recovered_workflow(
        restarted,
        old_id="project/a",
        new_id="archive/a",
        revision=5,
        payload=first_payload,
    )
    _assert_recovered_workflow(
        restarted,
        old_id="project/b",
        new_id="archive/b",
        revision=6,
        payload=second_payload,
    )


def test_folder_promotion_recovers_after_first_immediate_child_move(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    first_generation, first_payload = _seed_workflow(store, "project/a", revision=7)
    second_generation, second_payload = _seed_workflow(
        store,
        "project/nested/b",
        revision=8,
    )
    source_folder = store.root_dir / "project"
    (source_folder / "notes.txt").write_text("keep me", encoding="utf-8")
    (source_folder / "empty").mkdir()
    child_names = {path.name for path in source_folder.iterdir()}
    old_ids = ["project/a", "project/nested/b"]
    new_ids = ["a", "nested/b"]
    all_ids = [*old_ids, *new_ids]
    generations_before = _generation_snapshot(store, all_ids)
    operation_id = store.prepare_folder_promotion_move("project")
    assert operation_id is not None
    original_rename = Path.rename
    moved_children = 0

    def fail_after_first_child(path: Path, target: Path) -> Path:
        nonlocal moved_children
        target_path = Path(target)
        if path.parent == source_folder and target_path.parent == source_folder.parent:
            if moved_children == 1:
                raise OSError("injected failure after first promoted child")
            moved_children += 1
        return original_rename(path, target_path)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "rename", fail_after_first_child)
        with pytest.raises(OSError, match="first promoted child"):
            store.delete_folder(
                "project",
                "move_children_up",
                move_operation_id=operation_id,
            )

    assert moved_children == 1
    assert source_folder.exists()
    promoted_count = sum(int((store.root_dir / child_name).exists()) for child_name in child_names)
    assert promoted_count == 1
    assert store.pending_workflow_move() is not None
    generations_after_failure = _generation_snapshot(store, all_ids)
    assert generations_after_failure == {
        "project/a": first_generation + 1,
        "project/nested/b": second_generation + 1,
        "a": generations_before["a"] + 1,
        "nested/b": generations_before["nested/b"] + 1,
    }

    restarted = _store(tmp_path)
    recovered_generations = _finish_recovery_twice(restarted, operation_id, all_ids)

    assert recovered_generations == generations_after_failure
    assert not source_folder.exists()
    assert (store.root_dir / "notes.txt").read_text(encoding="utf-8") == "keep me"
    assert (store.root_dir / "empty").is_dir()
    assert list((store.root_dir / "empty").iterdir()) == []
    assert not (store.root_dir / "project" / "notes.txt").exists()
    assert not (store.root_dir / "project" / "empty").exists()
    _assert_recovered_workflow(
        restarted,
        old_id="project/a",
        new_id="a",
        revision=7,
        payload=first_payload,
    )
    _assert_recovered_workflow(
        restarted,
        old_id="project/nested/b",
        new_id="nested/b",
        revision=8,
        payload=second_payload,
    )


def test_folder_promotion_recovery_fails_closed_for_unexpected_source_child(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    created_generation, _ = _seed_workflow(store, "project/a", revision=9)
    operation_id = store.prepare_folder_promotion_move("project")
    assert operation_id is not None
    unexpected = store.root_dir / "project" / "arrived-after-prepare.txt"
    unexpected.write_text("do not move implicitly", encoding="utf-8")

    with pytest.raises(WorkflowMoveRecoveryError):
        store.recover_pending_workflow_move()

    assert store.workflow_dir("project/a").exists()
    assert not store.workflow_dir("a").exists()
    assert unexpected.read_text(encoding="utf-8") == "do not move implicitly"
    assert store.workflow_generation("project/a") == created_generation
    assert store.workflow_generation("a") == 0
    assert store.pending_workflow_move() is not None


def test_folder_rename_recovery_fails_closed_when_source_and_destination_exist(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    created_generation, _ = _seed_workflow(store, "project/a", revision=10)
    operation_id = store.prepare_folder_rename_move("project", "archive")
    assert operation_id is not None
    destination = store.root_dir / "archive"
    destination.mkdir(parents=True)
    marker = destination / "unrelated.txt"
    marker.write_text("collision", encoding="utf-8")

    with pytest.raises(WorkflowMoveRecoveryError):
        store.recover_pending_workflow_move()

    assert store.workflow_dir("project/a").exists()
    assert marker.read_text(encoding="utf-8") == "collision"
    assert store.workflow_generation("project/a") == created_generation
    assert store.workflow_generation("archive/a") == 0
    assert store.pending_workflow_move() is not None
