"""Tests for durable private nested-workflow snapshots."""

from __future__ import annotations

from pathlib import Path

import pytest

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.nested_workflow_snapshot import (
    NestedSnapshotOwner,
)
from bioimageflow_server.models.workflow import WorkflowCreate
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedSnapshotRevisionConflict,
    NestedWorkflowSnapshotService,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService


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
    root_a = NestedSnapshotOwner(
        kind="root", canvas_id="workflow:root-a", workflow_id="root-a"
    )
    root_b = NestedSnapshotOwner(
        kind="root", canvas_id="workflow:root-b", workflow_id="root-b"
    )

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
        NestedSnapshotOwner(
            kind="root", canvas_id="workflow:root-a", workflow_id="root-a"
        ),
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
        NestedSnapshotOwner(
            kind="root", canvas_id="workflow:root-a", workflow_id="root-a"
        ),
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
