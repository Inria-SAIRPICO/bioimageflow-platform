"""Tests for durable private nested-workflow snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.nested_workflow_snapshot import (
    NestedSnapshotOwner,
)
from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowUpdate
from bioimageflow_server.services import nested_workflow_snapshot as snapshot_service_module
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedSnapshotHasDependents,
    NestedSnapshotRevisionConflict,
    NestedWorkflowSnapshotService,
    RootWorkflowSnapshotMove,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService
from tests.workflow_move_helpers import (
    execute_workflow_patch,
    finish_move_without_retained_snapshots,
)


def _graph(node_id: str, published_name: str = "image") -> GraphState:
    return GraphState.model_validate(
        {
            "nodes": [
                {
                    "id": node_id,
                    "name": node_id,
                    "tool_name": "MissingTool",
                    "position": [0, 0],
                    "parameters": {},
                }
            ],
            "edges": [],
            "published_inputs": [
                {
                    "name": published_name,
                    "internal_node_id": node_id,
                    "internal_field": "image",
                    "kind": "input",
                    "schema": {"type": "Path"},
                    "default": None,
                }
            ],
            "published_outputs": [],
        }
    )


def _snapshot_path(store: WorkflowStoreService, session_id: UUID) -> Path:
    return (
        store.workspace_dir / ".bioimageflow" / "nested-workflow-snapshots" / f"{session_id}.json"
    )


def _replace_snapshot_owner(
    store: WorkflowStoreService,
    session_id: UUID,
    owner: dict[str, object],
) -> None:
    path = _snapshot_path(store, session_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["owner"] = owner
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_snapshot_clone(
    store: WorkflowStoreService,
    template_session_id: UUID,
    session_id: UUID,
    owner: dict[str, object],
) -> Path:
    template = json.loads(_snapshot_path(store, template_session_id).read_text(encoding="utf-8"))
    template["session_id"] = str(session_id)
    template["owner"] = owner
    path = _snapshot_path(store, session_id)
    path.write_text(json.dumps(template), encoding="utf-8")
    return path


@pytest.fixture
def store(tmp_path: Path) -> WorkflowStoreService:
    registry = ToolRegistryService()
    result = WorkflowStoreService(
        root_dir=tmp_path / "workspace" / "workflows",
        tool_registry=registry,
        storage_base_dir=tmp_path / "workspace" / "outputs",
    )
    result.create_workflow(WorkflowCreate(name="root-a", display_name="Root A"))
    result.create_workflow(WorkflowCreate(name="root-b", display_name="Root B"))
    return result


@pytest.fixture
def service(store: WorkflowStoreService) -> NestedWorkflowSnapshotService:
    return NestedWorkflowSnapshotService(lambda: store)


def test_open_is_idempotent_and_hierarchical_owners_do_not_collide(
    service: NestedWorkflowSnapshotService,
) -> None:
    root_a = NestedSnapshotOwner(kind="root", canvas_id="workflow:root-a", workflow_id="root-a")
    root_b = NestedSnapshotOwner(kind="root", canvas_id="workflow:root-b", workflow_id="root-b")

    first = service.open_snapshot(root_a, "sub_1", _graph("inner_a"))
    reopened = service.open_snapshot(root_a, "sub_1", _graph("ignored"))
    other_root = service.open_snapshot(root_b, "sub_1", _graph("inner_b"))
    nested = service.open_snapshot(
        NestedSnapshotOwner(kind="nested", session_id=first.session_id),
        "sub_1",
        _graph("inner_nested"),
    )

    assert reopened.session_id == first.session_id
    assert reopened.graph == first.graph
    assert len({first.session_id, other_root.session_id, nested.session_id}) == 3


def test_complete_graph_and_interface_survive_service_restart(
    store: WorkflowStoreService,
) -> None:
    service = NestedWorkflowSnapshotService(lambda: store)
    opened = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="workflow:root-a", workflow_id="root-a"),
        "sub_1",
        _graph("inner", "source"),
    )
    accepted = service.put_snapshot(
        opened.session_id,
        expected_revision=0,
        graph=_graph("inner", "renamed_source"),
    )

    restarted = NestedWorkflowSnapshotService(lambda: store)
    recovered = restarted.get_snapshot(opened.session_id)

    assert accepted.snapshot_revision == 1
    assert recovered == accepted
    assert recovered.graph.published_inputs[0].name == "renamed_source"
    assert recovered.validation.node_statuses["inner"].node_id == "inner"


def test_stale_replace_and_delete_do_not_change_the_accepted_file(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
) -> None:
    opened = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="workflow:root-a", workflow_id="root-a"),
        "sub_1",
        _graph("inner"),
    )
    accepted = service.put_snapshot(
        opened.session_id,
        expected_revision=0,
        graph=_graph("inner", "accepted"),
    )
    path = (
        store.workspace_dir
        / ".bioimageflow"
        / "nested-workflow-snapshots"
        / f"{opened.session_id}.json"
    )
    before = path.read_bytes()

    with pytest.raises(NestedSnapshotRevisionConflict):
        service.put_snapshot(
            opened.session_id,
            expected_revision=0,
            graph=_graph("inner", "stale"),
        )
    with pytest.raises(NestedSnapshotRevisionConflict):
        service.delete_snapshot(opened.session_id, expected_revision=0)

    assert path.read_bytes() == before
    service.delete_snapshot(
        opened.session_id,
        expected_revision=accepted.snapshot_revision,
    )
    assert not path.exists()


def test_parent_delete_is_rejected_while_nested_snapshots_depend_on_it(
    service: NestedWorkflowSnapshotService,
) -> None:
    parent = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="workflow:root-a", workflow_id="root-a"),
        "sub_1",
        _graph("inner"),
    )
    child = service.open_snapshot(
        NestedSnapshotOwner(kind="nested", session_id=parent.session_id),
        "sub_2",
        _graph("deep_inner"),
    )

    with pytest.raises(NestedSnapshotHasDependents):
        service.delete_snapshot(parent.session_id, expected_revision=0)

    accepted_child = service.put_snapshot(
        child.session_id,
        expected_revision=0,
        graph=_graph("deep_inner", "still_editable"),
    )
    service.delete_snapshot(
        child.session_id,
        expected_revision=accepted_child.snapshot_revision,
    )
    service.delete_snapshot(parent.session_id, expected_revision=0)


def test_root_cleanup_removes_full_snapshot_tree_and_ignores_unrelated_corruption(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
) -> None:
    parent = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="workflow:root-a", workflow_id="root-a"),
        "sub_1",
        _graph("inner"),
    )
    child = service.open_snapshot(
        NestedSnapshotOwner(kind="nested", session_id=parent.session_id),
        "sub_2",
        _graph("deep_inner"),
    )
    retained = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="workflow:root-b", workflow_id="root-b"),
        "sub_1",
        _graph("other"),
    )
    snapshot_dir = store.workspace_dir / ".bioimageflow" / "nested-workflow-snapshots"
    malformed = snapshot_dir / "malformed.json"
    malformed.write_text("not json", encoding="utf-8")

    removed = service.delete_for_root_workflow("root-a")

    assert set(removed) == {parent.session_id, child.session_id}
    with pytest.raises(FileNotFoundError):
        service.get_snapshot(parent.session_id)
    with pytest.raises(FileNotFoundError):
        service.get_snapshot(child.session_id)
    assert service.get_snapshot(retained.session_id) == retained
    assert malformed.read_text(encoding="utf-8") == "not json"


def test_unsaved_root_canvas_is_a_valid_stable_owner(
    service: NestedWorkflowSnapshotService,
) -> None:
    owner = NestedSnapshotOwner(kind="root", canvas_id="canvas", workflow_id=None)

    opened = service.open_snapshot(owner, "sub_1", _graph("inner"))
    reopened = service.open_snapshot(owner, "sub_1", _graph("ignored"))
    second_canvas = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="canvas-2", workflow_id=None),
        "sub_1",
        _graph("other"),
    )

    assert reopened.session_id == opened.session_id
    assert second_canvas.session_id != opened.session_id


def test_owner_generation_is_only_valid_for_saved_roots() -> None:
    with pytest.raises(ValueError, match="Unsaved root"):
        NestedSnapshotOwner(
            kind="root",
            canvas_id="canvas",
            identity_generation=1,
        )
    with pytest.raises(ValueError, match="parent session_id"):
        NestedSnapshotOwner(
            kind="nested",
            session_id=uuid4(),
            identity_generation=1,
        )


def test_saved_root_owner_is_canonicalized_from_server_authority(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
) -> None:
    created = store.create_workflow(WorkflowCreate(name="folder/root-c", display_name="Root C"))

    opened = service.open_snapshot(
        NestedSnapshotOwner(
            kind="root",
            canvas_id="client-alias",
            workflow_id="folder/root-c",
            identity_generation=999,
        ),
        "sub_1",
        _graph("inner"),
    )
    reopened = service.open_snapshot(
        NestedSnapshotOwner(
            kind="root",
            canvas_id="another-alias",
            workflow_id="folder/root-c",
        ),
        "sub_1",
        _graph("ignored"),
    )

    assert opened.owner == NestedSnapshotOwner(
        kind="root",
        canvas_id="workflow:folder%2Froot-c",
        workflow_id="folder/root-c",
        identity_generation=created.identity_generation,
    )
    assert reopened.session_id == opened.session_id


def test_saved_root_owner_supports_preledger_generation_zero(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
) -> None:
    store._write_raw("legacy", store._empty_raw(WorkflowCreate(name="legacy")))
    assert store.workflow_generation("legacy") == 0

    opened = service.open_snapshot(
        NestedSnapshotOwner(
            kind="root",
            canvas_id="legacy-alias",
            workflow_id="legacy",
        ),
        "sub_1",
        _graph("inner"),
    )

    assert opened.owner == NestedSnapshotOwner(
        kind="root",
        canvas_id="workflow:legacy",
        workflow_id="legacy",
        identity_generation=0,
    )


def test_move_rewrites_only_root_owner_and_descendant_stays_editable(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
) -> None:
    parent = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="alias", workflow_id="root-a"),
        "sub_1",
        _graph("inner"),
    )
    child = service.open_snapshot(
        NestedSnapshotOwner(kind="nested", session_id=parent.session_id),
        "sub_2",
        _graph("deep_inner"),
    )
    child_path = _snapshot_path(store, child.session_id)
    child_before = child_path.read_bytes()
    moved_workflow, operation_id = execute_workflow_patch(
        store,
        "root-a",
        WorkflowUpdate(action="update", new_id="archive/root-a"),
    )

    moved_ids = service.move_root_workflows(
        [
            RootWorkflowSnapshotMove(
                old_workflow_id="root-a",
                old_identity_generation=parent.owner.identity_generation or 0,
                new_workflow_id="archive/root-a",
                new_identity_generation=moved_workflow.identity_generation,
            )
        ]
    )
    finish_move_without_retained_snapshots(store, operation_id)
    recovered_parent = service.get_snapshot(parent.session_id)

    assert moved_ids == [parent.session_id]
    assert recovered_parent.owner == NestedSnapshotOwner(
        kind="root",
        canvas_id="workflow:archive%2Froot-a",
        workflow_id="archive/root-a",
        identity_generation=moved_workflow.identity_generation,
    )
    assert recovered_parent.model_copy(update={"owner": parent.owner}) == parent
    assert child_path.read_bytes() == child_before
    accepted_child = service.put_snapshot(
        child.session_id,
        expected_revision=child.snapshot_revision,
        graph=_graph("deep_inner", "editable_after_move"),
    )
    assert accepted_child.snapshot_revision == child.snapshot_revision + 1


def test_move_normalizes_safe_generationless_root_when_startup_cleanup_was_skipped(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
) -> None:
    parent = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="alias", workflow_id="root-a"),
        "sub_1",
        _graph("inner"),
    )
    _replace_snapshot_owner(
        store,
        parent.session_id,
        {
            "kind": "root",
            "canvas_id": "legacy-alias",
            "workflow_id": "root-a",
        },
    )
    moved_workflow, operation_id = execute_workflow_patch(
        store,
        "root-a",
        WorkflowUpdate(action="update", new_id="archive/root-a"),
    )

    moved_ids = service.move_root_workflows(
        [
            RootWorkflowSnapshotMove(
                old_workflow_id="root-a",
                old_identity_generation=1,
                new_workflow_id="archive/root-a",
                new_identity_generation=moved_workflow.identity_generation,
            )
        ]
    )
    finish_move_without_retained_snapshots(store, operation_id)

    assert moved_ids == [parent.session_id]
    assert service.get_snapshot(parent.session_id).owner == NestedSnapshotOwner(
        kind="root",
        canvas_id="workflow:archive%2Froot-a",
        workflow_id="archive/root-a",
        identity_generation=moved_workflow.identity_generation,
    )


def test_move_resolves_skipped_startup_collision_and_removes_losing_tree(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
) -> None:
    canonical = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="canonical", workflow_id="root-a"),
        "sub_1",
        _graph("canonical_state"),
    )
    canonical_child = service.open_snapshot(
        NestedSnapshotOwner(kind="nested", session_id=canonical.session_id),
        "sub_2",
        _graph("canonical_child"),
    )
    legacy_session_id = uuid4()
    legacy_path = _write_snapshot_clone(
        store,
        canonical.session_id,
        legacy_session_id,
        {
            "kind": "root",
            "canvas_id": "startup-canvas-alias",
            "workflow_id": "root-a",
        },
    )
    legacy_payload = json.loads(legacy_path.read_text(encoding="utf-8"))
    legacy_payload["updated_at"] = "2099-01-01T00:00:00Z"
    legacy_payload["graph"] = _graph("newer_legacy_state").model_dump(mode="json")
    legacy_path.write_text(json.dumps(legacy_payload), encoding="utf-8")
    moved_workflow, operation_id = execute_workflow_patch(
        store,
        "root-a",
        WorkflowUpdate(action="update", new_id="archive/root-a"),
    )

    moved_ids = service.move_root_workflows(
        [
            RootWorkflowSnapshotMove(
                old_workflow_id="root-a",
                old_identity_generation=1,
                new_workflow_id="archive/root-a",
                new_identity_generation=moved_workflow.identity_generation,
            )
        ]
    )
    finish_move_without_retained_snapshots(store, operation_id)

    assert moved_ids == [legacy_session_id]
    assert not _snapshot_path(store, canonical.session_id).exists()
    assert not _snapshot_path(store, canonical_child.session_id).exists()
    recovered = service.get_snapshot(legacy_session_id)
    assert recovered.owner == NestedSnapshotOwner(
        kind="root",
        canvas_id="workflow:archive%2Froot-a",
        workflow_id="archive/root-a",
        identity_generation=moved_workflow.identity_generation,
    )
    assert recovered.graph == _graph("newer_legacy_state")
    reopened = service.open_snapshot(
        NestedSnapshotOwner(
            kind="root",
            canvas_id="ignored",
            workflow_id="archive/root-a",
        ),
        "sub_1",
        _graph("ignored"),
    )
    assert reopened.session_id == legacy_session_id


def test_move_preflight_rejects_temporarily_unreadable_snapshot(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="alias", workflow_id="root-a"),
        "sub_1",
        _graph("inner"),
    )
    parent_path = _snapshot_path(store, parent.session_id)
    before = parent_path.read_bytes()
    original_read_text = Path.read_text

    def intermittently_unreadable(path: Path, *args: object, **kwargs: object) -> str:
        if path == parent_path:
            raise OSError("injected transient snapshot read failure")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", intermittently_unreadable)

    with pytest.raises(OSError, match="retained snapshots are unreadable"):
        service.preflight_root_workflow_moves()

    assert parent_path.read_bytes() == before
    assert store.get_workflow("root-a").info.id == "root-a"


def test_move_replace_failure_keeps_original_and_cleans_temporary_file(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="alias", workflow_id="root-a"),
        "sub_1",
        _graph("inner"),
    )
    sibling = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="another-alias", workflow_id="root-a"),
        "sub_2",
        _graph("sibling"),
    )
    paths = sorted(_snapshot_path(store, item.session_id) for item in (parent, sibling))
    before = {path: path.read_bytes() for path in paths}
    failing_path = paths[1]
    moved_workflow, _operation_id = execute_workflow_patch(
        store,
        "root-a",
        WorkflowUpdate(action="update", new_id="archive/root-a"),
    )
    original_replace = snapshot_service_module.os.replace

    def failing_replace(source: str | Path, target: str | Path) -> None:
        if Path(target) == failing_path:
            raise OSError("injected snapshot replacement failure")
        original_replace(source, target)

    monkeypatch.setattr(snapshot_service_module.os, "replace", failing_replace)

    with pytest.raises(OSError, match="injected snapshot"):
        service.move_root_workflows(
            [
                RootWorkflowSnapshotMove(
                    old_workflow_id="root-a",
                    old_identity_generation=parent.owner.identity_generation or 0,
                    new_workflow_id="archive/root-a",
                    new_identity_generation=moved_workflow.identity_generation,
                )
            ]
        )

    assert {path: path.read_bytes() for path in paths} == before
    assert list(paths[0].parent.glob("*.tmp")) == []


def test_startup_cleanup_retains_valid_crash_tree_byte_for_byte(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
) -> None:
    parent = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="alias", workflow_id="root-a"),
        "sub_1",
        _graph("inner"),
    )
    child = service.open_snapshot(
        NestedSnapshotOwner(kind="nested", session_id=parent.session_id),
        "sub_2",
        _graph("deep_inner"),
    )
    paths = [_snapshot_path(store, item.session_id) for item in (parent, child)]
    before = {path: path.read_bytes() for path in paths}

    restarted = NestedWorkflowSnapshotService(lambda: store)

    assert restarted.cleanup_orphaned_snapshots() == []
    assert {path: path.read_bytes() for path in paths} == before


def test_startup_cleanup_preserves_descendants_when_parent_is_temporarily_unreadable(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="alias", workflow_id="root-a"),
        "sub_1",
        _graph("inner"),
    )
    child = service.open_snapshot(
        NestedSnapshotOwner(kind="nested", session_id=parent.session_id),
        "sub_2",
        _graph("deep_inner"),
    )
    parent_path = _snapshot_path(store, parent.session_id)
    child_path = _snapshot_path(store, child.session_id)
    before = {path: path.read_bytes() for path in (parent_path, child_path)}
    original_read_text = Path.read_text

    def intermittently_unreadable(path: Path, *args: object, **kwargs: object) -> str:
        if path == parent_path:
            raise OSError("injected transient snapshot read failure")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", intermittently_unreadable)

    assert service.cleanup_orphaned_snapshots() == []
    assert {path: path.read_bytes() for path in (parent_path, child_path)} == before


def test_startup_cleanup_preserves_tree_when_workflow_authority_is_unreadable(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="alias", workflow_id="root-a"),
        "sub_1",
        _graph("inner"),
    )
    child = service.open_snapshot(
        NestedSnapshotOwner(kind="nested", session_id=parent.session_id),
        "sub_2",
        _graph("deep_inner"),
    )
    paths = [_snapshot_path(store, item.session_id) for item in (parent, child)]
    before = {path: path.read_bytes() for path in paths}
    original_get_workflow = store.get_workflow

    def intermittently_unreadable(workflow_id: str):
        if workflow_id == "root-a":
            raise OSError("injected transient workflow read failure")
        return original_get_workflow(workflow_id)

    monkeypatch.setattr(store, "get_workflow", intermittently_unreadable)

    assert service.cleanup_orphaned_snapshots() == []
    assert {path: path.read_bytes() for path in paths} == before


def test_startup_cleanup_resolves_canonical_root_collision_and_losing_tree(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
) -> None:
    canonical = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="canonical", workflow_id="root-a"),
        "sub_1",
        _graph("canonical_state"),
    )
    canonical_child = service.open_snapshot(
        NestedSnapshotOwner(kind="nested", session_id=canonical.session_id),
        "sub_2",
        _graph("canonical_child"),
    )
    legacy_session_id = uuid4()
    legacy_path = _write_snapshot_clone(
        store,
        canonical.session_id,
        legacy_session_id,
        {
            "kind": "root",
            "canvas_id": "startup-canvas-alias",
            "workflow_id": "root-a",
        },
    )
    legacy_payload = json.loads(legacy_path.read_text(encoding="utf-8"))
    legacy_payload["updated_at"] = "2099-01-01T00:00:00Z"
    legacy_payload["graph"] = _graph("newer_legacy_state").model_dump(mode="json")
    legacy_path.write_text(json.dumps(legacy_payload), encoding="utf-8")

    removed = service.cleanup_orphaned_snapshots()

    assert set(removed) == {canonical.session_id, canonical_child.session_id}
    assert not _snapshot_path(store, canonical.session_id).exists()
    assert not _snapshot_path(store, canonical_child.session_id).exists()
    recovered = service.get_snapshot(legacy_session_id)
    assert recovered.owner == NestedSnapshotOwner(
        kind="root",
        canvas_id="workflow:root-a",
        workflow_id="root-a",
        identity_generation=1,
    )
    assert recovered.graph == _graph("newer_legacy_state")
    reopened = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="ignored", workflow_id="root-a"),
        "sub_1",
        _graph("ignored"),
    )
    assert reopened.session_id == legacy_session_id


def test_startup_cleanup_safely_backfills_generation_one_legacy_root(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
) -> None:
    parent = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="alias", workflow_id="root-a"),
        "sub_1",
        _graph("inner"),
    )
    _replace_snapshot_owner(
        store,
        parent.session_id,
        {
            "kind": "root",
            "canvas_id": "legacy-canvas-alias",
            "workflow_id": "root-a",
        },
    )

    assert service.cleanup_orphaned_snapshots() == []
    recovered = service.get_snapshot(parent.session_id)
    assert recovered.owner == NestedSnapshotOwner(
        kind="root",
        canvas_id="workflow:root-a",
        workflow_id="root-a",
        identity_generation=1,
    )
    assert recovered.model_copy(update={"owner": parent.owner}) == parent


def test_startup_cleanup_rejects_generationless_tree_after_delete_recreate(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
) -> None:
    parent = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="alias", workflow_id="root-a"),
        "sub_1",
        _graph("inner"),
    )
    child = service.open_snapshot(
        NestedSnapshotOwner(kind="nested", session_id=parent.session_id),
        "sub_2",
        _graph("deep_inner"),
    )
    _replace_snapshot_owner(
        store,
        parent.session_id,
        {
            "kind": "root",
            "canvas_id": "legacy-canvas-alias",
            "workflow_id": "root-a",
        },
    )
    store.delete_workflow("root-a")
    recreated = store.create_workflow(WorkflowCreate(name="root-a"))
    assert recreated.identity_generation > 1

    removed = service.cleanup_orphaned_snapshots()

    assert set(removed) == {parent.session_id, child.session_id}
    assert not _snapshot_path(store, parent.session_id).exists()
    assert not _snapshot_path(store, child.session_id).exists()


def test_startup_cleanup_removes_corrupt_or_orphaned_inventory(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
) -> None:
    valid = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="alias", workflow_id="root-b"),
        "sub_1",
        _graph("valid"),
    )
    valid_path = _snapshot_path(store, valid.session_id)
    valid_before = valid_path.read_bytes()
    unsaved = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="unsaved"),
        "sub_1",
        _graph("unsaved"),
    )

    missing_root_id = uuid4()
    missing_root_path = _write_snapshot_clone(
        store,
        valid.session_id,
        missing_root_id,
        {
            "kind": "root",
            "canvas_id": "workflow:missing",
            "workflow_id": "missing",
            "identity_generation": 1,
        },
    )
    missing_parent_id = uuid4()
    missing_parent_path = _write_snapshot_clone(
        store,
        valid.session_id,
        missing_parent_id,
        {"kind": "nested", "session_id": str(uuid4())},
    )
    missing_parent_descendant_id = uuid4()
    missing_parent_descendant_path = _write_snapshot_clone(
        store,
        valid.session_id,
        missing_parent_descendant_id,
        {"kind": "nested", "session_id": str(missing_parent_id)},
    )

    cycle_parent = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="alias", workflow_id="root-a"),
        "cycle_parent",
        _graph("cycle_parent"),
    )
    cycle_child = service.open_snapshot(
        NestedSnapshotOwner(kind="nested", session_id=cycle_parent.session_id),
        "cycle_child",
        _graph("cycle_child"),
    )
    cycle_descendant = service.open_snapshot(
        NestedSnapshotOwner(kind="nested", session_id=cycle_child.session_id),
        "cycle_descendant",
        _graph("cycle_descendant"),
    )
    _replace_snapshot_owner(
        store,
        cycle_parent.session_id,
        {"kind": "nested", "session_id": str(cycle_child.session_id)},
    )

    generation_mismatch_id = uuid4()
    generation_mismatch_path = _write_snapshot_clone(
        store,
        valid.session_id,
        generation_mismatch_id,
        {
            "kind": "root",
            "canvas_id": "workflow:root-b",
            "workflow_id": "root-b",
            "identity_generation": 99,
        },
    )
    malformed_id = uuid4()
    malformed_path = _snapshot_path(store, malformed_id)
    malformed_path.write_text("not json", encoding="utf-8")
    malformed_name_path = malformed_path.parent / "malformed.json"
    malformed_name_path.write_text("{}", encoding="utf-8")
    mismatched_filename_id = uuid4()
    mismatched_path = _snapshot_path(store, mismatched_filename_id)
    mismatched_path.write_bytes(valid_before)
    temporary_path = malformed_path.parent / f".{uuid4()}.crash.tmp"
    temporary_path.write_text("partial", encoding="utf-8")

    removed = service.cleanup_orphaned_snapshots()

    expected_removed = {
        unsaved.session_id,
        missing_root_id,
        missing_parent_id,
        missing_parent_descendant_id,
        cycle_parent.session_id,
        cycle_child.session_id,
        cycle_descendant.session_id,
        generation_mismatch_id,
        malformed_id,
        mismatched_filename_id,
    }
    assert set(removed) == expected_removed
    for path in (
        _snapshot_path(store, unsaved.session_id),
        missing_root_path,
        missing_parent_path,
        missing_parent_descendant_path,
        _snapshot_path(store, cycle_parent.session_id),
        _snapshot_path(store, cycle_child.session_id),
        _snapshot_path(store, cycle_descendant.session_id),
        generation_mismatch_path,
        malformed_path,
        malformed_name_path,
        mismatched_path,
        temporary_path,
    ):
        assert not path.exists()
    assert valid_path.read_bytes() == valid_before


def test_cleanup_backfill_replace_failure_keeps_legacy_file_and_cleans_temp(
    service: NestedWorkflowSnapshotService,
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = service.open_snapshot(
        NestedSnapshotOwner(kind="root", canvas_id="alias", workflow_id="root-a"),
        "sub_1",
        _graph("inner"),
    )
    _replace_snapshot_owner(
        store,
        parent.session_id,
        {
            "kind": "root",
            "canvas_id": "legacy",
            "workflow_id": "root-a",
        },
    )
    path = _snapshot_path(store, parent.session_id)
    before = path.read_bytes()
    original_replace = snapshot_service_module.os.replace

    def failing_replace(source: str | Path, target: str | Path) -> None:
        if Path(target) == path:
            raise OSError("injected legacy backfill failure")
        original_replace(source, target)

    monkeypatch.setattr(snapshot_service_module.os, "replace", failing_replace)

    with pytest.raises(OSError, match="legacy backfill"):
        service.cleanup_orphaned_snapshots()

    assert path.read_bytes() == before
    assert list(path.parent.glob("*.tmp")) == []
