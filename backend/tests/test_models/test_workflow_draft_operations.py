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
