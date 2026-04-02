"""Test that all models are importable from the top-level package."""

from bioimageflow_server.models import (
    ColumnRefEdge,
    ErrorResponse,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    GraphState,
    GraphValidationError,
    NodeState,
    NodeStatus,
    OMEROInstance,
    PositionalEdge,
    ProgressInfo,
    Settings,
    ValidationResult,
    WorkflowCreate,
    WorkflowFile,
    WorkflowInfo,
    WorkflowUpdate,
)


def test_all_models_importable():
    expected = [
        ColumnRefEdge,
        ErrorResponse,
        ExecutionRequest,
        ExecutionResult,
        ExecutionStatus,
        GraphState,
        GraphValidationError,
        NodeState,
        NodeStatus,
        OMEROInstance,
        PositionalEdge,
        ProgressInfo,
        Settings,
        ValidationResult,
        WorkflowCreate,
        WorkflowFile,
        WorkflowInfo,
        WorkflowUpdate,
    ]
    for cls in expected:
        assert hasattr(cls, "model_fields"), f"{cls.__name__} is not a Pydantic model"
