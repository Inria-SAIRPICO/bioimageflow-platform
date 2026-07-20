"""Tests for semantic recursive-workflow draft operation models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.workflow_draft_operations import (
    WorkflowDraftOperationsRequest,
)
from tests.graph_factory import graph_document


def test_operations_request_accepts_typed_batch_and_nested_scope() -> None:
    request = WorkflowDraftOperationsRequest.model_validate(
        {
            "expected_revision": 3,
            "operations": [
                {
                    "type": "create_tool_node",
                    "node_id": "blur_1",
                    "tool_name": "GaussianBlur",
                    "name": "Blur",
                    "position": [10, 20],
                    "parameters": {"sigma": 2},
                    "scope": {"workflow_path": ["outer"]},
                },
                {
                    "type": "create_workflow_node",
                    "node_id": "child_1",
                    "name": "Child",
                    "position": [30, 40],
                    "workflow": graph_document(name="child", display_name="Child"),
                },
            ],
        }
    )

    assert request.updated_by == "agent"
    assert request.validate_ is True
    assert request.operations[0].scope.workflow_path == ["outer"]
    assert [operation.type for operation in request.operations] == [
        "create_tool_node",
        "create_workflow_node",
    ]


def test_interface_operations_use_stable_port_ids_and_schema_alias() -> None:
    request = WorkflowDraftOperationsRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {
                    "type": "expose_workflow_input",
                    "input": {
                        "id": "input-1",
                        "name": "image",
                        "kind": "field",
                        "schema": {"type": "ImageFile"},
                        "targets": [
                            {
                                "node": "n1",
                                "port": {"kind": "field", "name": "input_image"},
                            }
                        ],
                    },
                },
                {"type": "delete_workflow_input", "input_id": "input-1"},
                {
                    "type": "expose_workflow_output",
                    "output": {
                        "id": "output-1",
                        "name": "mask",
                        "schema": {"type": "ImageFile"},
                        "source": {"node": "n1", "column": "output_image"},
                    },
                },
                {"type": "delete_workflow_output", "output_id": "output-1"},
            ],
        }
    )

    dumped = request.model_dump(mode="json", by_alias=True)
    assert dumped["operations"][0]["input"]["schema"] == {"type": "ImageFile"}
    assert [operation.type for operation in request.operations] == [
        "expose_workflow_input",
        "delete_workflow_input",
        "expose_workflow_output",
        "delete_workflow_output",
    ]


def test_column_and_dataframe_connection_operations_are_distinct() -> None:
    request = WorkflowDraftOperationsRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {
                    "type": "connect_column_edge",
                    "source_node": "a",
                    "target_node": "b",
                    "source_output": "image",
                    "target_input": "input-1",
                },
                {
                    "type": "connect_dataframe_edge",
                    "source_node": "a",
                    "target_node": "b",
                    "target_input": "table-1",
                },
            ],
        }
    )

    assert request.operations[0].type == "connect_column_edge"
    assert request.operations[1].type == "connect_dataframe_edge"


@pytest.mark.parametrize(
    "operations",
    [
        [],
        [{"type": "delete_node", "node_id": f"n{i}"} for i in range(11)],
        [{"type": "create_node", "node_id": "old"}],
        [
            {
                "type": "move_node",
                "node_id": "n1",
                "position": [0, 0],
                "scope": {"display_path": ["editable-label"]},
            }
        ],
    ],
)
def test_request_rejects_invalid_batches_and_removed_shapes(
    operations: list[dict[str, object]],
) -> None:
    with pytest.raises(ValidationError):
        WorkflowDraftOperationsRequest.model_validate(
            {"expected_revision": 0, "operations": operations}
        )


def test_validate_alias_round_trips() -> None:
    request = WorkflowDraftOperationsRequest.model_validate(
        {
            "expected_revision": 1,
            "updated_by": "frontend",
            "validate": False,
            "operations": [{"type": "delete_node", "node_id": "n1"}],
        }
    )

    assert request.validate_ is False
    assert request.model_dump(by_alias=True)["validate"] is False
