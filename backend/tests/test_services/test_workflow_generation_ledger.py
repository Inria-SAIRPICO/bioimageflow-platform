"""Durability regressions for workflow identity generations."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.workflow import (
    WorkflowCreate,
    WorkflowSaveBody,
    WorkflowUpdate,
)
from bioimageflow_server.services import workflow_store as workflow_store_module
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import (
    WorkflowGenerationChangedError,
    WorkflowGenerationLedgerError,
    WorkflowStoreService,
)
from tests.workflow_move_helpers import (
    patch_workflow as _patch_workflow,
    rename_folder as _rename_folder,
)


def _store(tmp_path: Path) -> WorkflowStoreService:
    workspace = tmp_path / "workspace"
    return WorkflowStoreService(
        root_dir=workspace / "workflows",
        tool_registry=ToolRegistryService(),
        storage_base_dir=workspace / "outputs",
    )


def _ledger_path(tmp_path: Path) -> Path:
    return tmp_path / "workspace" / ".bioimageflow" / "workflow-identity-generations.json"


def test_unchanged_workflow_keeps_its_generation_after_restart(tmp_path: Path) -> None:
    first = _store(tmp_path)
    created = first.create_workflow(WorkflowCreate(name="wf"))

    restarted = _store(tmp_path)
    loaded = restarted.get_workflow("wf")

    assert created.identity_generation == 1
    assert loaded.info.identity_generation == created.identity_generation
    assert restarted.workflow_generation("wf") == created.identity_generation


def test_delete_tombstone_and_stale_token_survive_restart(tmp_path: Path) -> None:
    first = _store(tmp_path)
    created = first.create_workflow(WorkflowCreate(name="wf"))
    deleted_generation = first.delete_workflow("wf")

    restarted = _store(tmp_path)
    assert restarted.workflow_generation("wf") == deleted_generation
    recreated = restarted.create_workflow(WorkflowCreate(name="wf"))

    assert created.identity_generation < deleted_generation
    assert deleted_generation < recreated.identity_generation
    with pytest.raises(WorkflowGenerationChangedError):
        restarted.ensure_workflow_generation("wf", created.identity_generation)

    restarted_again = _store(tmp_path)
    assert (
        restarted_again.get_workflow("wf").info.identity_generation == recreated.identity_generation
    )


def test_multiple_stores_share_generation_state_and_cannot_overwrite_newer_ledger(
    tmp_path: Path,
) -> None:
    current = _store(tmp_path)
    current.create_workflow(WorkflowCreate(name="wf"))
    stale = _store(tmp_path)

    assert current._workflow_locks is stale._workflow_locks
    assert current._workflow_locks_guard is stale._workflow_locks_guard
    assert current._workflow_structure_lock is stale._workflow_structure_lock
    assert current._workflow_generations is stale._workflow_generations
    assert current._workflow_generations_guard is stale._workflow_generations_guard

    assert current.delete_workflow("wf") == 2
    recreated = current.create_workflow(WorkflowCreate(name="wf"))
    assert recreated.identity_generation == 3

    deleted_by_previously_stale_store = stale.delete_workflow("wf")

    assert deleted_by_previously_stale_store == 4
    restarted = _store(tmp_path)
    assert restarted.workflow_generation("wf") == 4


def test_multiple_stores_serialize_saved_write_against_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = _store(tmp_path)
    writer.create_workflow(WorkflowCreate(name="wf"))
    deleter = _store(tmp_path)
    workflow_path = writer.workflow_dir("wf") / "workflow.json"
    workflow_dir = writer.workflow_dir("wf")
    save_entered = threading.Event()
    release_save = threading.Event()
    delete_entered = threading.Event()
    original_replace = workflow_store_module.os.replace
    original_rmtree = workflow_store_module.shutil.rmtree

    def blocking_replace(source: str | Path, target: str | Path) -> None:
        if Path(target) == workflow_path:
            save_entered.set()
            assert release_save.wait(timeout=5)
        original_replace(source, target)

    def monitored_rmtree(path: str | Path, *args: Any, **kwargs: Any) -> None:
        if Path(path) == workflow_dir:
            delete_entered.set()
        original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(workflow_store_module.os, "replace", blocking_replace)
    monkeypatch.setattr(workflow_store_module.shutil, "rmtree", monitored_rmtree)

    with ThreadPoolExecutor(max_workers=2) as pool:
        save_future = pool.submit(
            writer.save_workflow,
            "wf",
            WorkflowSaveBody(graph=GraphState(nodes=[], edges=[])),
        )
        assert save_entered.wait(timeout=5)
        delete_future = pool.submit(deleter.delete_workflow, "wf")
        try:
            assert not delete_entered.wait(timeout=0.1)
        finally:
            release_save.set()

        assert save_future.result(timeout=5).identity_generation == 1
        assert delete_future.result(timeout=5) == 2

    assert delete_entered.is_set()
    assert not workflow_dir.exists()


def test_direct_move_preserves_old_tombstone_and_new_generation_after_restart(
    tmp_path: Path,
) -> None:
    first = _store(tmp_path)
    created = first.create_workflow(WorkflowCreate(name="project/wf"))
    moved = _patch_workflow(
        first,
        "project/wf",
        WorkflowUpdate(action="update", new_id="archive/wf"),
    )
    old_tombstone = first.workflow_generation("project/wf")

    restarted = _store(tmp_path)

    assert old_tombstone > created.identity_generation
    assert restarted.workflow_generation("project/wf") == old_tombstone
    assert (
        restarted.get_workflow("archive/wf").info.identity_generation == moved.identity_generation
    )
    recreated_old = restarted.create_workflow(WorkflowCreate(name="project/wf"))
    assert recreated_old.identity_generation > old_tombstone


def test_folder_move_generations_and_tombstones_survive_restart(tmp_path: Path) -> None:
    first = _store(tmp_path)
    first.create_workflow(WorkflowCreate(name="project/a"))
    first.create_workflow(WorkflowCreate(name="project/nested/b"))

    _rename_folder(first, "project", "archive")
    old_generations = {
        workflow_id: first.workflow_generation(workflow_id)
        for workflow_id in ("project/a", "project/nested/b")
    }
    new_generations = {
        workflow_id: first.workflow_generation(workflow_id)
        for workflow_id in ("archive/a", "archive/nested/b")
    }

    restarted = _store(tmp_path)

    assert restarted.workflow_generation("project/a") == old_generations["project/a"]
    assert restarted.workflow_generation("project/nested/b") == old_generations["project/nested/b"]
    assert (
        restarted.get_workflow("archive/a").info.identity_generation == new_generations["archive/a"]
    )
    assert (
        restarted.get_workflow("archive/nested/b").info.identity_generation
        == new_generations["archive/nested/b"]
    )


def test_create_duplicate_and_import_generations_survive_restart(tmp_path: Path) -> None:
    first = _store(tmp_path)
    source = first.create_workflow(WorkflowCreate(name="source"))
    duplicate = _patch_workflow(
        first,
        "source",
        WorkflowUpdate(action="duplicate", new_name="copy"),
    )
    exported = first.export_workflow("source")
    imported = first.import_workflow(exported, name_override="imported")

    restarted = _store(tmp_path)

    assert restarted.get_workflow("source").info.identity_generation == source.identity_generation
    assert restarted.get_workflow("copy").info.identity_generation == duplicate.identity_generation
    assert (
        restarted.get_workflow("imported").info.identity_generation
        == imported.info.identity_generation
    )


def test_tombstoned_targets_advance_for_duplicate_import_and_move(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="source"))
    exported = store.export_workflow("source")

    tombstones: dict[str, int] = {}
    for target in ("copy", "imported", "moved"):
        store.create_workflow(WorkflowCreate(name=target))
        tombstones[target] = store.delete_workflow(target)

    duplicate = _patch_workflow(
        store,
        "source",
        WorkflowUpdate(action="duplicate", new_name="copy"),
    )
    imported = store.import_workflow(exported, name_override="imported")
    store.create_workflow(WorkflowCreate(name="move-source"))
    moved = _patch_workflow(
        store,
        "move-source",
        WorkflowUpdate(action="update", new_id="moved"),
    )

    assert duplicate.identity_generation > tombstones["copy"]
    assert imported.info.identity_generation > tombstones["imported"]
    assert moved.identity_generation > tombstones["moved"]

    restarted = _store(tmp_path)
    assert restarted.get_workflow("copy").info.identity_generation == duplicate.identity_generation
    assert (
        restarted.get_workflow("imported").info.identity_generation
        == imported.info.identity_generation
    )
    assert restarted.get_workflow("moved").info.identity_generation == moved.identity_generation


def test_folder_move_advances_tombstoned_destination_after_restart(
    tmp_path: Path,
) -> None:
    first = _store(tmp_path)
    first.create_workflow(WorkflowCreate(name="archive/a"))
    destination_tombstone = first.delete_workflow("archive/a")
    first.delete_folder("archive")
    first.create_workflow(WorkflowCreate(name="project/a"))

    _rename_folder(first, "project", "archive")
    moved_generation = first.workflow_generation("archive/a")

    assert moved_generation > destination_tombstone
    restarted = _store(tmp_path)
    assert restarted.get_workflow("archive/a").info.identity_generation == moved_generation


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not json\n", "Cannot read"),
        ('{"version": 2, "generations": {}}\n', "Invalid workflow identity"),
        (
            '{"version": 1, "generations": {"folder\\\\wf": 1}}\n',
            "Non-canonical workflow identity",
        ),
        ('{"version": 1, "generations": {"wf": -1}}\n', "Invalid workflow generation"),
    ],
)
def test_generation_ledger_corruption_fails_store_initialization(
    tmp_path: Path,
    payload: str,
    message: str,
) -> None:
    ledger_path = _ledger_path(tmp_path)
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text(payload, encoding="utf-8")

    with pytest.raises(WorkflowGenerationLedgerError, match=message):
        _store(tmp_path)


def test_ledger_write_failure_prevents_workflow_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    created = store.create_workflow(WorkflowCreate(name="wf"))

    def fail_ledger_write(_generations: dict[str, int]) -> None:
        raise OSError("ledger unavailable")

    monkeypatch.setattr(store, "_write_workflow_generation_ledger", fail_ledger_write)

    with pytest.raises(OSError, match="ledger unavailable"):
        store.delete_workflow("wf")

    assert store.get_workflow("wf").info.identity_generation == created.identity_generation
    assert store.workflow_dir("wf").exists()


def test_workflow_removal_failure_before_commit_still_propagates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="wf"))
    workflow_dir = store.workflow_dir("wf")
    original_rmtree = workflow_store_module.shutil.rmtree

    def fail_workflow_removal(path: str | Path, *args: Any, **kwargs: Any) -> None:
        if Path(path) == workflow_dir:
            raise OSError("workflow removal failed")
        original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(workflow_store_module.shutil, "rmtree", fail_workflow_removal)

    with pytest.raises(OSError, match="workflow removal failed"):
        store.delete_workflow("wf")

    assert store.get_workflow("wf").info.id == "wf"


def test_collision_preflight_does_not_consume_generation(tmp_path: Path) -> None:
    store = _store(tmp_path)
    created = store.create_workflow(WorkflowCreate(name="wf"))
    ledger_before = _ledger_path(tmp_path).read_bytes()

    with pytest.raises(FileExistsError):
        store.create_workflow(WorkflowCreate(name="wf"))

    assert store.workflow_generation("wf") == created.identity_generation
    assert _ledger_path(tmp_path).read_bytes() == ledger_before


def test_failure_after_reservation_leaves_durable_harmless_gap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    original_write = store._write_raw

    def fail_workflow_write(_name: str, _raw: dict[str, object]) -> None:
        raise OSError("workflow write failed")

    monkeypatch.setattr(store, "_write_raw", fail_workflow_write)

    with pytest.raises(OSError, match="workflow write failed"):
        store.create_workflow(WorkflowCreate(name="wf"))

    assert store.workflow_generation("wf") == 1
    monkeypatch.setattr(store, "_write_raw", original_write)

    restarted = _store(tmp_path)
    created = restarted.create_workflow(WorkflowCreate(name="wf"))
    assert created.identity_generation == 2
