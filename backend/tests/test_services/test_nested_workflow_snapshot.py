"""Tests for durable private nested workflow editor snapshots."""

from __future__ import annotations

from pathlib import Path

import pytest

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.nested_workflow_snapshot import NestedSnapshotOwner
from bioimageflow_server.models.workflow import WorkflowCreate
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedSnapshotHasDependents,
    NestedSnapshotRevisionConflict,
    NestedWorkflowSnapshotService,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService
from tests.graph_factory import graph_state


def _graph(node_id: str, input_name: str = "image") -> GraphState:
    return graph_state(
        name=f"{node_id}_workflow",
        display_name=f"{node_id} workflow",
        nodes=[
            {
                "type": "tool",
                "id": node_id,
                "name": node_id,
                "tool_name": "MissingTool",
                "position": [0, 0],
                "parameters": {},
            }
        ],
        interface={
            "inputs": [
                {
                    "id": "input-1",
                    "name": input_name,
                    "kind": "field",
                    "schema": {"type": "Path"},
                    "targets": [
                        {
                            "node": node_id,
                            "port": {"kind": "field", "name": "image"},
                        }
                    ],
                }
            ],
            "outputs": [],
        },
    )


@pytest.fixture
def store(tmp_path: Path) -> WorkflowStoreService:
    result = WorkflowStoreService(
        root_dir=tmp_path / "workspace" / "workflows",
        tool_registry=ToolRegistryService(),
        storage_base_dir=tmp_path / "workspace" / "outputs",
    )
    result.create_workflow(WorkflowCreate(name="root-a", display_name="Root A"))
    result.create_workflow(WorkflowCreate(name="root-b", display_name="Root B"))
    return result


@pytest.fixture
def service(store: WorkflowStoreService) -> NestedWorkflowSnapshotService:
    return NestedWorkflowSnapshotService(lambda: store)


def _root(workflow_id: str) -> NestedSnapshotOwner:
    return NestedSnapshotOwner(
        kind="root",
        canvas_id=f"workflow:{workflow_id}",
        workflow_id=workflow_id,
    )


def test_open_is_idempotent_and_root_owners_do_not_collide(
    service: NestedWorkflowSnapshotService,
) -> None:
    first = service.open_snapshot(_root("root-a"), "child_1", _graph("inner_a"))
    reopened = service.open_snapshot(_root("root-a"), "child_1", _graph("ignored"))
    other = service.open_snapshot(_root("root-b"), "child_1", _graph("inner_b"))

    assert reopened.session_id == first.session_id
    assert reopened.graph.nodes[0].id == "inner_a"
    assert other.session_id != first.session_id


def test_nested_owner_identity_is_hierarchical(
    service: NestedWorkflowSnapshotService,
) -> None:
    parent = service.open_snapshot(_root("root-a"), "child_1", _graph("inner"))
    child = service.open_snapshot(
        NestedSnapshotOwner(kind="nested", session_id=parent.session_id),
        "grandchild_1",
        _graph("deep"),
    )

    assert child.owner.session_id == parent.session_id
    assert service.has_open_at_or_below("root-a", ["child_1"])
    assert service.has_open_at_or_below("root-a", ["child_1", "grandchild_1"])
    assert not service.has_open_at_or_below("root-b", ["child_1"])


def test_complete_graph_and_interface_survive_service_restart(
    store: WorkflowStoreService,
) -> None:
    first_service = NestedWorkflowSnapshotService(lambda: store)
    opened = first_service.open_snapshot(
        _root("root-a"), "child_1", _graph("inner", "source")
    )

    recovered = NestedWorkflowSnapshotService(lambda: store).get_snapshot(
        opened.session_id
    )

    assert recovered.graph == opened.graph
    assert recovered.graph.interface.inputs[0].id == "input-1"
    assert recovered.graph.interface.inputs[0].name == "source"


def test_replace_and_delete_are_revision_checked(
    service: NestedWorkflowSnapshotService,
) -> None:
    opened = service.open_snapshot(_root("root-a"), "child_1", _graph("inner"))
    replaced = service.put_snapshot(
        opened.session_id,
        expected_revision=0,
        graph=_graph("inner", "renamed"),
    )
    assert replaced.snapshot_revision == 1

    with pytest.raises(NestedSnapshotRevisionConflict):
        service.put_snapshot(
            opened.session_id,
            expected_revision=0,
            graph=_graph("stale"),
        )
    with pytest.raises(NestedSnapshotRevisionConflict):
        service.delete_snapshot(opened.session_id, expected_revision=0)

    service.delete_snapshot(opened.session_id, expected_revision=1)
    with pytest.raises(FileNotFoundError):
        service.get_snapshot(opened.session_id)


def test_parent_delete_requires_descendant_cleanup(
    service: NestedWorkflowSnapshotService,
) -> None:
    parent = service.open_snapshot(_root("root-a"), "child_1", _graph("inner"))
    child = service.open_snapshot(
        NestedSnapshotOwner(kind="nested", session_id=parent.session_id),
        "grandchild_1",
        _graph("deep"),
    )

    with pytest.raises(NestedSnapshotHasDependents) as error:
        service.delete_snapshot(parent.session_id, expected_revision=0)
    assert error.value.dependent_session_ids == [child.session_id]

    service.delete_snapshot(child.session_id, expected_revision=0)
    service.delete_snapshot(parent.session_id, expected_revision=0)


def test_root_cleanup_removes_exact_snapshot_tree(
    service: NestedWorkflowSnapshotService,
) -> None:
    parent = service.open_snapshot(_root("root-a"), "child_1", _graph("inner"))
    child = service.open_snapshot(
        NestedSnapshotOwner(kind="nested", session_id=parent.session_id),
        "grandchild_1",
        _graph("deep"),
    )
    unrelated = service.open_snapshot(
        _root("root-b"), "child_1", _graph("other")
    )

    removed = service.delete_for_root_workflow("root-a")

    assert set(removed) == {parent.session_id, child.session_id}
    assert service.get_snapshot(unrelated.session_id) == unrelated


def test_unsaved_root_canvas_is_stable(service: NestedWorkflowSnapshotService) -> None:
    owner = NestedSnapshotOwner(kind="root", canvas_id="workflow:new")
    opened = service.open_snapshot(owner, "child_1", _graph("inner"))
    assert opened.owner == owner
    assert service.open_snapshot(owner, "child_1", _graph("ignored")) == opened
