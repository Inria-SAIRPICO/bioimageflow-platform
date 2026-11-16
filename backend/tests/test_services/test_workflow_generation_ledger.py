"""Durability regressions for workflow identity generations."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from tests.graph_factory import graph_state

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
    )


def _ledger_path(tmp_path: Path) -> Path:
    return tmp_path / "workspace" / ".bioimageflow" / "workflow-identity-generations.json"


def test_unchanged_workflow_keeps_its_generation_after_restart(tmp_path: Path) -> None:
    identities: dict[str, str] = {}
    first = _store(tmp_path)
    identities.update({item.relative_path: item.id for item in first.list_workflows()})
    created = first.create_workflow(WorkflowCreate(name="wf"))
    identities[created.relative_path] = created.id

    restarted = _store(tmp_path)
    identities.update({item.relative_path: item.id for item in restarted.list_workflows()})
    loaded = restarted.get_workflow(identities["wf"])

    assert created.identity_generation == 1
    assert loaded.info.identity_generation == created.identity_generation
    assert restarted.workflow_generation(identities["wf"]) == created.identity_generation


def test_delete_tombstone_and_stale_token_survive_restart(tmp_path: Path) -> None:
    first = _store(tmp_path)
    created = first.create_workflow(WorkflowCreate(name="wf"))
    deleted_generation = first.delete_workflow(created.id)
    restarted = _store(tmp_path)
    assert restarted.workflow_generation(created.id) == deleted_generation
    recreated = restarted.create_workflow(WorkflowCreate(name="wf"))
    assert recreated.id != created.id
    assert recreated.identity_generation == 1
    with pytest.raises(WorkflowGenerationChangedError):
        restarted.ensure_workflow_generation(created.id, created.identity_generation)
    with pytest.raises(FileNotFoundError):
        restarted.get_workflow(created.id)
    restarted_again = _store(tmp_path)
    assert restarted_again.get_workflow(recreated.id).info.identity_generation == 1
    assert restarted_again.workflow_generation(created.id) == deleted_generation


def test_multiple_stores_share_generation_state_and_cannot_overwrite_newer_ledger(tmp_path: Path) -> None:
    current = _store(tmp_path)
    original = current.create_workflow(WorkflowCreate(name="wf"))
    stale = _store(tmp_path)
    assert current._workflow_locks is stale._workflow_locks
    assert current._workflow_locks_guard is stale._workflow_locks_guard
    assert current._workflow_structure_lock is stale._workflow_structure_lock
    assert current._workflow_generations is stale._workflow_generations
    assert current._workflow_generations_guard is stale._workflow_generations_guard
    assert current.delete_workflow(original.id) == 2
    recreated = current.create_workflow(WorkflowCreate(name="wf"))
    assert recreated.id != original.id
    assert recreated.identity_generation == 1
    assert stale.delete_workflow(recreated.id) == 2
    restarted = _store(tmp_path)
    assert restarted.workflow_generation(original.id) == 2
    assert restarted.workflow_generation(recreated.id) == 2


def test_multiple_stores_serialize_saved_write_against_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identities: dict[str, str] = {}
    writer = _store(tmp_path)
    identities.update({item.relative_path: item.id for item in writer.list_workflows()})
    created_104 = writer.create_workflow(WorkflowCreate(name="wf"))
    identities[created_104.relative_path] = created_104.id
    deleter = _store(tmp_path)
    identities.update({item.relative_path: item.id for item in deleter.list_workflows()})
    workflow_path = writer.workflow_dir(identities["wf"]) / "workflow.json"
    workflow_dir = writer.workflow_dir(identities["wf"])
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
            identities["wf"],
            WorkflowSaveBody(graph=graph_state(nodes=[], edges=[])),
        )
        assert save_entered.wait(timeout=5)
        delete_future = pool.submit(deleter.delete_workflow, identities["wf"])
        try:
            assert not delete_entered.wait(timeout=0.1)
        finally:
            release_save.set()

        assert save_future.result(timeout=5).identity_generation == 1
        assert delete_future.result(timeout=5) == 2

    assert delete_entered.is_set()
    assert not workflow_dir.exists()


def test_direct_move_preserves_uuid_generation_and_allows_new_owner_at_old_path(tmp_path: Path) -> None:
    first = _store(tmp_path)
    created = first.create_workflow(WorkflowCreate(name="project/wf"))
    moved = _patch_workflow(first, created.id, WorkflowUpdate(action="update", new_id="archive/wf"))
    assert moved.id == created.id
    assert moved.identity_generation == created.identity_generation
    restarted = _store(tmp_path)
    assert restarted.get_workflow(created.id).info.relative_path == "archive/wf"
    assert restarted.workflow_generation(created.id) == created.identity_generation
    replacement = restarted.create_workflow(WorkflowCreate(name="project/wf"))
    assert replacement.id != created.id
    assert restarted.get_workflow(created.id).info.relative_path == "archive/wf"
    assert restarted.get_workflow(replacement.id).info.relative_path == "project/wf"


def test_folder_move_uuids_and_generations_survive_restart(tmp_path: Path) -> None:
    first = _store(tmp_path)
    created = [first.create_workflow(WorkflowCreate(name=path)) for path in ("project/a", "project/nested/b")]
    _rename_folder(first, "project", "archive")
    restarted = _store(tmp_path)
    for original in created:
        current = restarted.get_workflow(original.id).info
        assert current.id == original.id
        assert current.relative_path == original.relative_path.replace("project/", "archive/", 1)
        assert current.identity_generation == original.identity_generation


def test_create_duplicate_and_import_generations_survive_restart(tmp_path: Path) -> None:
    identities: dict[str, str] = {}
    first = _store(tmp_path)
    identities.update({item.relative_path: item.id for item in first.list_workflows()})
    source = first.create_workflow(WorkflowCreate(name="source"))
    identities[source.relative_path] = source.id
    duplicate = _patch_workflow(
        first,
        identities["source"],
        WorkflowUpdate(action="duplicate", new_name="copy"),
    )
    filename, exported = first.export_workflow_archive(identities["source"])
    imported = first.import_workflow_archive(
        exported,
        filename=filename,
        name_override="imported",
    )

    restarted = _store(tmp_path)
    identities.update({item.relative_path: item.id for item in restarted.list_workflows()})

    assert restarted.get_workflow(identities["source"]).info.identity_generation == source.identity_generation
    assert restarted.get_workflow(identities["copy"]).info.identity_generation == duplicate.identity_generation
    assert (
        restarted.get_workflow(identities["imported"]).info.identity_generation
        == imported.info.identity_generation
    )


def test_duplicate_import_and_move_cannot_reuse_retired_destination_identities(tmp_path: Path) -> None:
    store = _store(tmp_path)
    source = store.create_workflow(WorkflowCreate(name="source"))
    filename, exported = store.export_workflow_archive(source.id)
    retired = {}
    for destination in ("copy", "imported", "moved"):
        previous = store.create_workflow(WorkflowCreate(name=destination))
        retired[destination] = (previous.id, store.delete_workflow(previous.id))
    duplicate = _patch_workflow(store, source.id, WorkflowUpdate(action="duplicate", new_name="copy"))
    imported = store.import_workflow_archive(exported, filename=filename, name_override="imported").info
    move_source = store.create_workflow(WorkflowCreate(name="move-source"))
    moved = _patch_workflow(store, move_source.id, WorkflowUpdate(action="update", new_id="moved"))
    assert moved.id == move_source.id
    restarted = _store(tmp_path)
    for current in (duplicate, imported, moved):
        old_id, tombstone = retired[current.relative_path]
        assert current.id != old_id
        assert current.identity_generation == 1
        assert restarted.get_workflow(current.id).info.identity_generation == 1
        assert restarted.workflow_generation(old_id) == tombstone
        with pytest.raises(FileNotFoundError):
            restarted.get_workflow(old_id)


def test_folder_move_preserves_source_identity_and_destination_tombstone(tmp_path: Path) -> None:
    first = _store(tmp_path)
    former = first.create_workflow(WorkflowCreate(name="archive/a"))
    tombstone = first.delete_workflow(former.id)
    first.delete_folder("archive")
    source = first.create_workflow(WorkflowCreate(name="project/a"))
    _rename_folder(first, "project", "archive")
    restarted = _store(tmp_path)
    moved = restarted.get_workflow(source.id).info
    assert moved.relative_path == "archive/a"
    assert moved.identity_generation == source.identity_generation
    assert restarted.workflow_generation(former.id) == tombstone
    with pytest.raises(FileNotFoundError):
        restarted.get_workflow(former.id)


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
    identities: dict[str, str] = {}
    store = _store(tmp_path)
    identities.update({item.relative_path: item.id for item in store.list_workflows()})
    created = store.create_workflow(WorkflowCreate(name="wf"))
    identities[created.relative_path] = created.id

    def fail_ledger_write(_generations: dict[str, int]) -> None:
        raise OSError("ledger unavailable")

    monkeypatch.setattr(store, "_write_workflow_generation_ledger", fail_ledger_write)

    with pytest.raises(OSError, match="ledger unavailable"):
        store.delete_workflow(identities["wf"])

    assert store.get_workflow(identities["wf"]).info.identity_generation == created.identity_generation
    assert store.workflow_dir(identities["wf"]).exists()


def test_workflow_removal_failure_before_commit_still_propagates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identities: dict[str, str] = {}
    store = _store(tmp_path)
    identities.update({item.relative_path: item.id for item in store.list_workflows()})
    created_330 = store.create_workflow(WorkflowCreate(name="wf"))
    identities[created_330.relative_path] = created_330.id
    workflow_dir = store.workflow_dir(identities["wf"])
    original_rmtree = workflow_store_module.shutil.rmtree

    def fail_workflow_removal(path: str | Path, *args: Any, **kwargs: Any) -> None:
        if Path(path) == workflow_dir:
            raise OSError("workflow removal failed")
        original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(workflow_store_module.shutil, "rmtree", fail_workflow_removal)

    with pytest.raises(OSError, match="workflow removal failed"):
        store.delete_workflow(identities["wf"])

    assert store.get_workflow(identities["wf"]).info.id == identities["wf"]


def test_collision_preflight_does_not_consume_generation(tmp_path: Path) -> None:
    identities: dict[str, str] = {}
    store = _store(tmp_path)
    identities.update({item.relative_path: item.id for item in store.list_workflows()})
    created = store.create_workflow(WorkflowCreate(name="wf"))
    identities[created.relative_path] = created.id
    ledger_before = _ledger_path(tmp_path).read_bytes()

    with pytest.raises(FileExistsError):
        created_353 = store.create_workflow(WorkflowCreate(name="wf"))
        identities[created_353.relative_path] = created_353.id

    assert store.workflow_generation(identities["wf"]) == created.identity_generation
    assert _ledger_path(tmp_path).read_bytes() == ledger_before


def test_failure_after_reservation_retires_only_its_unpublished_uuid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path)
    original_write = store._write_raw
    attempted: list[str] = []
    def fail_workflow_write(_name: str, raw: dict[str, object], **_kwargs: Any) -> None:
        attempted.append(str(raw["workflow_id"]))
        raise OSError("workflow write failed")
    monkeypatch.setattr(store, "_write_raw", fail_workflow_write)
    with pytest.raises(OSError, match="workflow write failed"):
        store.create_workflow(WorkflowCreate(name="wf"))
    assert len(attempted) == 1
    assert store.workflow_generation(attempted[0]) == 1
    monkeypatch.setattr(store, "_write_raw", original_write)
    restarted = _store(tmp_path)
    created = restarted.create_workflow(WorkflowCreate(name="wf"))
    assert created.id != attempted[0]
    assert created.identity_generation == 1
    assert restarted.workflow_generation(attempted[0]) == 1
