"""Deterministic concurrency regressions for workflow identity mutations."""

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
from bioimageflow_server.routers.workflows import _delete_workflow_with_snapshots
from bioimageflow_server.services import workflow_draft as workflow_draft_module
from bioimageflow_server.services import workflow_store as workflow_store_module
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedWorkflowSnapshotService,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_draft import WorkflowDraftService
from bioimageflow_server.services.workflow_store import (
    WorkflowGenerationChangedError,
    WorkflowStoreService,
)
from tests.workflow_move_helpers import (
    patch_workflow as _patch_workflow,
    rename_folder as _rename_folder,
)


@pytest.fixture
def store(tmp_path: Path) -> WorkflowStoreService:
    return WorkflowStoreService(
        root_dir=tmp_path / "workspace" / "workflows",
        tool_registry=ToolRegistryService(),
        storage_base_dir=tmp_path / "workspace" / "outputs",
    )


def _put_empty_draft(service: WorkflowDraftService, workflow_id: str) -> Any:
    return service.put_draft(
        workflow_id,
        graph=graph_state(nodes=[], edges=[]),
        expected_revision=0,
        should_validate=False,
    )


def test_delete_waits_for_in_flight_draft_write_and_cannot_be_resurrected(
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store.create_workflow(WorkflowCreate(name="wf", display_name="Workflow"))
    drafts = WorkflowDraftService(lambda: store)
    draft_path = store.workflow_dir("wf") / ".bioimageflow" / "draft.json"
    workflow_dir = store.workflow_dir("wf")
    write_entered = threading.Event()
    release_write = threading.Event()
    delete_started = threading.Event()
    delete_entered = threading.Event()
    original_dump = workflow_draft_module._json_dump_atomic
    original_rmtree = workflow_store_module.shutil.rmtree

    def blocking_dump(path: Path, payload: dict[str, Any]) -> None:
        if path == draft_path:
            write_entered.set()
            assert release_write.wait(timeout=5)
        original_dump(path, payload)

    def monitored_rmtree(path: str | Path, *args: Any, **kwargs: Any) -> None:
        if Path(path) == workflow_dir:
            delete_entered.set()
        original_rmtree(path, *args, **kwargs)

    def delete() -> None:
        delete_started.set()
        store.delete_workflow("wf")

    monkeypatch.setattr(workflow_draft_module, "_json_dump_atomic", blocking_dump)
    monkeypatch.setattr(workflow_store_module.shutil, "rmtree", monitored_rmtree)

    with ThreadPoolExecutor(max_workers=2) as pool:
        put_future = pool.submit(_put_empty_draft, drafts, "wf")
        assert write_entered.wait(timeout=5)
        delete_future = pool.submit(delete)
        assert delete_started.wait(timeout=5)
        assert not delete_entered.wait(timeout=0.1)
        release_write.set()

        assert put_future.result(timeout=5).draft_revision == 1
        delete_future.result(timeout=5)

    assert delete_entered.is_set()
    assert not workflow_dir.exists()


def test_draft_write_waits_for_delete_and_fails_without_recreating_identity(
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store.create_workflow(WorkflowCreate(name="wf", display_name="Workflow"))
    drafts = WorkflowDraftService(lambda: store)
    workflow_dir = store.workflow_dir("wf")
    delete_entered = threading.Event()
    release_delete = threading.Event()
    put_started = threading.Event()
    draft_write_entered = threading.Event()
    original_dump = workflow_draft_module._json_dump_atomic
    original_rmtree = workflow_store_module.shutil.rmtree

    def blocking_rmtree(path: str | Path, *args: Any, **kwargs: Any) -> None:
        if Path(path) == workflow_dir:
            delete_entered.set()
            assert release_delete.wait(timeout=5)
        original_rmtree(path, *args, **kwargs)

    def monitored_dump(path: Path, payload: dict[str, Any]) -> None:
        if path.name == "draft.json":
            draft_write_entered.set()
        original_dump(path, payload)

    def put() -> Any:
        put_started.set()
        return _put_empty_draft(drafts, "wf")

    monkeypatch.setattr(workflow_store_module.shutil, "rmtree", blocking_rmtree)
    monkeypatch.setattr(workflow_draft_module, "_json_dump_atomic", monitored_dump)

    with ThreadPoolExecutor(max_workers=2) as pool:
        delete_future = pool.submit(store.delete_workflow, "wf")
        assert delete_entered.wait(timeout=5)
        put_future = pool.submit(put)
        assert put_started.wait(timeout=5)
        assert not draft_write_entered.wait(timeout=0.1)
        release_delete.set()

        delete_future.result(timeout=5)
        with pytest.raises(FileNotFoundError):
            put_future.result(timeout=5)

    assert not workflow_dir.exists()
    assert not draft_write_entered.is_set()


def test_delete_waits_for_saved_workflow_write_and_removes_accepted_state(
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store.create_workflow(WorkflowCreate(name="wf", display_name="Workflow"))
    workflow_path = store.workflow_dir("wf") / "workflow.json"
    workflow_dir = store.workflow_dir("wf")
    save_replace_entered = threading.Event()
    release_save = threading.Event()
    delete_entered = threading.Event()
    original_replace = workflow_store_module.os.replace
    original_rmtree = workflow_store_module.shutil.rmtree

    def blocking_replace(source: str | Path, target: str | Path) -> None:
        if Path(target) == workflow_path:
            save_replace_entered.set()
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
            store.save_workflow,
            "wf",
            WorkflowSaveBody(graph=graph_state(nodes=[], edges=[])),
        )
        assert save_replace_entered.wait(timeout=5)
        delete_future = pool.submit(store.delete_workflow, "wf")
        try:
            assert not delete_entered.wait(timeout=0.1)
        finally:
            release_save.set()

        assert save_future.result(timeout=5).identity_generation == 1
        assert delete_future.result(timeout=5) == 2

    assert delete_entered.is_set()
    assert not workflow_dir.exists()


def test_delete_captured_before_workflow_move_cannot_delete_moved_identity(
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_id = "project/wf"
    new_id = "archive/wf"
    store.create_workflow(WorkflowCreate(name=old_id, display_name="Workflow"))
    old_dir = store.workflow_dir(old_id)
    new_dir = store.workflow_dir(new_id)
    delete_generation_captured = threading.Event()
    release_delete = threading.Event()
    delete_thread_id: list[int] = []
    original_capture = store._capture_workflow_generations

    def observed_capture(names: list[str]) -> dict[str, int]:
        generations = original_capture(names)
        if delete_thread_id and threading.get_ident() == delete_thread_id[0]:
            delete_generation_captured.set()
            assert release_delete.wait(timeout=5)
        return generations

    def delete_old_identity() -> int:
        delete_thread_id.append(threading.get_ident())
        return store.delete_workflow(old_id)

    monkeypatch.setattr(store, "_capture_workflow_generations", observed_capture)

    with ThreadPoolExecutor(max_workers=1) as pool:
        delete_future = pool.submit(delete_old_identity)
        assert delete_generation_captured.wait(timeout=5)
        try:
            moved = _patch_workflow(
                store,
                old_id,
                WorkflowUpdate(action="update", new_id=new_id),
            )
        finally:
            release_delete.set()

        with pytest.raises(WorkflowGenerationChangedError):
            delete_future.result(timeout=5)

    assert moved.id == new_id
    assert not old_dir.exists()
    assert new_dir.exists()


def test_folder_move_waits_for_draft_write_and_rewrites_the_accepted_identity(
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store.create_workflow(WorkflowCreate(name="project/wf", display_name="Workflow"))
    drafts = WorkflowDraftService(lambda: store)
    draft_path = store.workflow_dir("project/wf") / ".bioimageflow" / "draft.json"
    old_folder = store.root_dir / "project"
    new_folder = store.root_dir / "archive"
    write_entered = threading.Event()
    release_write = threading.Event()
    rename_started = threading.Event()
    rename_entered = threading.Event()
    original_dump = workflow_draft_module._json_dump_atomic
    original_rename = Path.rename

    def blocking_dump(path: Path, payload: dict[str, Any]) -> None:
        if path == draft_path:
            write_entered.set()
            assert release_write.wait(timeout=5)
        original_dump(path, payload)

    def monitored_rename(path: Path, target: str | Path) -> Path:
        if path == old_folder and Path(target) == new_folder:
            rename_entered.set()
        return original_rename(path, target)

    def rename() -> None:
        rename_started.set()
        _rename_folder(store, "project", "archive")

    monkeypatch.setattr(workflow_draft_module, "_json_dump_atomic", blocking_dump)
    monkeypatch.setattr(Path, "rename", monitored_rename)

    with ThreadPoolExecutor(max_workers=2) as pool:
        put_future = pool.submit(_put_empty_draft, drafts, "project/wf")
        assert write_entered.wait(timeout=5)
        rename_future = pool.submit(rename)
        assert rename_started.wait(timeout=5)
        assert not rename_entered.wait(timeout=0.1)
        release_write.set()

        assert put_future.result(timeout=5).draft_revision == 1
        rename_future.result(timeout=5)

    moved = drafts.get_draft_snapshot("archive/wf")
    assert moved.workflow_id == "archive/wf"
    assert moved.draft_revision == 1
    assert rename_entered.is_set()
    assert not old_folder.exists()
    assert new_folder.exists()


def test_request_from_deleted_generation_cannot_mutate_same_id_recreation(
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store.create_workflow(WorkflowCreate(name="wf", display_name="Original"))
    drafts = WorkflowDraftService(lambda: store)
    captured_generation = threading.Event()
    release_stale_request = threading.Event()
    stale_thread_id: list[int] = []
    did_block = False
    original_capture = store._capture_workflow_generations

    def blocking_capture(names: list[str]) -> dict[str, int]:
        nonlocal did_block
        generations = original_capture(names)
        if stale_thread_id and threading.get_ident() == stale_thread_id[0] and not did_block:
            did_block = True
            captured_generation.set()
            assert release_stale_request.wait(timeout=5)
        return generations

    stale_graph = graph_state(
            nodes=[
                {
                    "type": "tool",
                    "id": "stale",
                    "name": "Stale request",
                    "tool_name": "MissingTool",
                    "position": [0, 0],
                    "parameters": {},
                }
            ]
    )

    def stale_put() -> Any:
        stale_thread_id.append(threading.get_ident())
        return drafts.put_draft(
            "wf",
            graph=stale_graph,
            expected_revision=0,
            should_validate=False,
        )

    monkeypatch.setattr(store, "_capture_workflow_generations", blocking_capture)

    with ThreadPoolExecutor(max_workers=1) as pool:
        stale_future = pool.submit(stale_put)
        assert captured_generation.wait(timeout=5)

        store.delete_workflow("wf")
        store.create_workflow(WorkflowCreate(name="wf", display_name="Fresh"))
        release_stale_request.set()

        with pytest.raises(WorkflowGenerationChangedError):
            stale_future.result(timeout=5)

    fresh = store.get_workflow("wf")
    assert fresh.info.display_name == "Fresh"
    assert fresh.graph.nodes == []
    assert not (store.workflow_dir("wf") / ".bioimageflow" / "draft.json").exists()


def test_workflow_info_tracks_delete_and_same_id_recreation_generation(
    store: WorkflowStoreService,
) -> None:
    created = store.create_workflow(WorkflowCreate(name="wf"))
    assert created.identity_generation == 1
    assert store.get_workflow("wf").info.identity_generation == 1

    deleted_generation = store.delete_workflow("wf")
    assert deleted_generation == 2

    recreated = store.create_workflow(WorkflowCreate(name="wf"))
    assert recreated.identity_generation == 3
    assert recreated.identity_generation > deleted_generation


@pytest.mark.parametrize("reader", ["get", "list"])
def test_workflow_info_read_is_coherent_with_its_identity_generation(
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
    reader: str,
) -> None:
    store.create_workflow(WorkflowCreate(name="wf", display_name="Original"))
    old_read = threading.Event()
    release_old_read = threading.Event()
    replacement_complete = threading.Event()
    original_read = store._read_raw
    should_block = True

    def blocking_read(name: str) -> dict[str, Any]:
        nonlocal should_block
        raw = original_read(name)
        if should_block:
            should_block = False
            old_read.set()
            assert release_old_read.wait(timeout=5)
        return raw

    def read_info() -> Any:
        if reader == "get":
            return store.get_workflow("wf").info
        return store.list_workflows()[0]

    def replace_identity() -> Any:
        store.delete_workflow("wf")
        result = store.create_workflow(WorkflowCreate(name="wf", display_name="Replacement"))
        replacement_complete.set()
        return result

    monkeypatch.setattr(store, "_read_raw", blocking_read)

    with ThreadPoolExecutor(max_workers=2) as pool:
        read_future = pool.submit(read_info)
        assert old_read.wait(timeout=5)
        replace_future = pool.submit(replace_identity)
        assert not replacement_complete.wait(timeout=0.1)
        release_old_read.set()

        old_info = read_future.result(timeout=5)
        replacement = replace_future.result(timeout=5)

    assert old_info.display_name == "Original"
    assert old_info.identity_generation == 1
    assert replacement.display_name == "Replacement"
    assert replacement.identity_generation == 3


def test_workflow_delete_waits_for_snapshot_boundary_before_identity_mutation(
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store.create_workflow(WorkflowCreate(name="wf"))
    snapshots = NestedWorkflowSnapshotService(lambda: store)
    snapshot_locked = threading.Event()
    release_snapshot = threading.Event()
    store_delete_started = threading.Event()
    original_delete = store.delete_workflow

    def hold_snapshot_boundary() -> None:
        with snapshots.snapshot_mutation():
            snapshot_locked.set()
            assert release_snapshot.wait(timeout=5)

    def observed_delete(
        name: str,
        *,
        expected_identity_generation: int | None = None,
    ) -> int:
        store_delete_started.set()
        return original_delete(
            name,
            expected_identity_generation=expected_identity_generation,
        )

    monkeypatch.setattr(store, "delete_workflow", observed_delete)

    with ThreadPoolExecutor(max_workers=2) as pool:
        snapshot_future = pool.submit(hold_snapshot_boundary)
        assert snapshot_locked.wait(timeout=5)
        delete_future = pool.submit(
            _delete_workflow_with_snapshots,
            store,
            snapshots,
            "wf",
        )
        try:
            assert not store_delete_started.wait(timeout=0.1)
        finally:
            release_snapshot.set()

        snapshot_future.result(timeout=5)
        assert delete_future.result(timeout=5) == 2

    assert store_delete_started.is_set()
