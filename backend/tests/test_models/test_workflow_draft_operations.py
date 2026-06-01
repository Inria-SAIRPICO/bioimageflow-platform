"""Tests for semantic workflow draft operation models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.workflow_draft_operations import (
    WorkflowDraftOperationsRequest,
)


def test_operations_request_accepts_small_batch_with_agent_defaults() -> None:
    request = WorkflowDraftOperationsRequest.model_validate(
        {
            "expected_revision": 3,
            "operations": [
                {
                    "type": "create_node",
                    "node_id": "blur_1",
                    "tool_name": "GaussianBlur",
                    "name": "Blur",
                    "position": [10, 20],
                    "parameters": {"sigma": 2},
                },
                {
                    "type": "set_node_enabled",
                    "node_id": "blur_1",
                    "enabled": False,
                },
            ],
        }
    )

    assert request.expected_revision == 3
    assert request.updated_by == "agent"
    assert request.validate_ is True
    assert [operation.type for operation in request.operations] == [
        "create_node",
        "set_node_enabled",
    ]


@pytest.mark.parametrize(
    "operations",
    [
        [],
        [{"type": "delete_node", "node_id": f"n{i}"} for i in range(11)],
    ],
)
def test_operations_request_rejects_empty_and_oversized_batches(
    operations: list[dict[str, object]],
) -> None:
    with pytest.raises(ValidationError):
        WorkflowDraftOperationsRequest.model_validate(
            {"expected_revision": 0, "operations": operations}
        )


def test_create_node_requires_explicit_node_id() -> None:
    with pytest.raises(ValidationError):
        WorkflowDraftOperationsRequest.model_validate(
            {
                "expected_revision": 0,
                "operations": [
                    {
                        "type": "create_node",
                        "tool_name": "GaussianBlur",
                        "name": "Blur",
                        "position": [0, 0],
                        "parameters": {},
                    }
                ],
            }
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


def test_published_interface_operations_parse_schema_aliases() -> None:
    request = WorkflowDraftOperationsRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {
                    "type": "set_published_input",
                    "name": "image",
                    "internal_node_id": "n1",
                    "internal_field": "input_image",
                    "kind": "input",
                    "schema": {"type": "ImageFile"},
                    "default": None,
                },
                {"type": "delete_published_input", "name": "image"},
                {
                    "type": "set_published_output",
                    "name": "mask",
                    "internal_node_id": "n1",
                    "internal_output": "output_image",
                    "schema": {"type": "ImageFile"},
                },
                {"type": "delete_published_output", "name": "mask"},
            ],
        }
    )

    assert [operation.type for operation in request.operations] == [
        "set_published_input",
        "delete_published_input",
        "set_published_output",
        "delete_published_output",
    ]
    assert request.model_dump(by_alias=True)["operations"][0]["schema"] == {
        "type": "ImageFile"
    }


def test_move_nodes_operation_parses_multiple_moves() -> None:
    request = WorkflowDraftOperationsRequest.model_validate(
        {
            "expected_revision": 1,
            "operations": [
                {
                    "type": "move_nodes",
                    "moves": [
                        {"node_id": "a", "position": [10, 20]},
                        {"node_id": "b", "position": [30.5, 40]},
                    ],
                }
            ],
        }
    )

    operation = request.operations[0]
    assert operation.type == "move_nodes"
    assert [(move.node_id, move.position) for move in operation.moves] == [
        ("a", (10, 20)),
        ("b", (30.5, 40)),
    ]


@pytest.mark.parametrize(
    "moves",
    [
        [],
        [{"node_id": "a", "position": [10]}],
        [{"node_id": "a", "position": [10, 20, 30]}],
    ],
)
def test_move_nodes_operation_rejects_invalid_move_payloads(
    moves: list[dict[str, object]],
) -> None:
    with pytest.raises(ValidationError):
        WorkflowDraftOperationsRequest.model_validate(
            {
                "expected_revision": 1,
                "operations": [{"type": "move_nodes", "moves": moves}],
            }
        )


def test_published_interface_operations_reject_empty_names() -> None:
    with pytest.raises(ValidationError):
        WorkflowDraftOperationsRequest.model_validate(
            {
                "expected_revision": 1,
                "operations": [
                    {
                        "type": "set_published_output",
                        "name": "   ",
                        "internal_node_id": "n1",
                        "internal_output": "output_image",
                        "schema": {"type": "ImageFile"},
                    }
                ],
            }
        )


@pytest.mark.parametrize(
    "operation",
    [
        {
            "type": "set_published_input",
            "name": "image",
            "internal_node_id": "n1",
            "internal_field": "   ",
            "kind": "input",
            "schema": {"type": "ImageFile"},
        },
        {
            "type": "set_published_output",
            "name": "mask",
            "internal_node_id": "n1",
            "internal_output": "",
            "schema": {"type": "ImageFile"},
        },
        {
            "type": "set_published_output",
            "name": "mask",
            "internal_node_id": " ",
            "internal_output": "output_image",
            "schema": {"type": "ImageFile"},
        },
    ],
)
def test_published_interface_operations_reject_blank_internal_targets(
    operation: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        WorkflowDraftOperationsRequest.model_validate(
            {
                "expected_revision": 1,
                "operations": [operation],
            }
        )
