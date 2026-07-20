"""Typed semantic mutations for recursive workflow drafts."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from bioimageflow_server.models.graph import (
    GraphState,
    SerializedConstant,
    WorkflowInput,
    WorkflowOutput,
    WorkspaceWorkflowSource,
)
from bioimageflow_server.models.workflow_draft import DraftWriter


class OperationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkflowDraftOperationScope(OperationModel):
    """Structural workflow-node IDs from the root to the edited graph."""

    workflow_path: list[str] = Field(default_factory=list)


class ScopedOperation(OperationModel):
    scope: WorkflowDraftOperationScope = Field(default_factory=WorkflowDraftOperationScope)


class CreateToolNodeOperation(ScopedOperation):
    type: Literal["create_tool_node"] = "create_tool_node"
    node_id: str
    tool_name: str
    name: str
    position: tuple[float, float]
    parameters: dict[str, Any] = Field(default_factory=dict)


class CreateWorkflowNodeOperation(ScopedOperation):
    type: Literal["create_workflow_node"] = "create_workflow_node"
    node_id: str
    name: str
    position: tuple[float, float]
    workflow: GraphState
    bindings: dict[str, SerializedConstant] = Field(default_factory=dict)
    source: WorkspaceWorkflowSource | None = None


class DeleteNodeOperation(ScopedOperation):
    type: Literal["delete_node"] = "delete_node"
    node_id: str


class RenameNodeOperation(ScopedOperation):
    type: Literal["rename_node"] = "rename_node"
    node_id: str
    name: str


class UpdateToolParametersOperation(ScopedOperation):
    type: Literal["update_tool_parameters"] = "update_tool_parameters"
    node_id: str
    parameters: dict[str, Any]


class SetNodeEnabledOperation(ScopedOperation):
    type: Literal["set_node_enabled"] = "set_node_enabled"
    node_id: str
    enabled: bool


class MoveNodeOperation(ScopedOperation):
    type: Literal["move_node"] = "move_node"
    node_id: str
    position: tuple[float, float]


class MoveNodeItem(OperationModel):
    node_id: str
    position: tuple[float, float]


class MoveNodesOperation(ScopedOperation):
    type: Literal["move_nodes"] = "move_nodes"
    moves: list[MoveNodeItem] = Field(min_length=1)


class ExposeWorkflowInputOperation(ScopedOperation):
    type: Literal["expose_workflow_input"] = "expose_workflow_input"
    input: WorkflowInput


class DeleteWorkflowInputOperation(ScopedOperation):
    type: Literal["delete_workflow_input"] = "delete_workflow_input"
    input_id: str


class ExposeWorkflowOutputOperation(ScopedOperation):
    type: Literal["expose_workflow_output"] = "expose_workflow_output"
    output: WorkflowOutput


class DeleteWorkflowOutputOperation(ScopedOperation):
    type: Literal["delete_workflow_output"] = "delete_workflow_output"
    output_id: str


class ConnectColumnEdgeOperation(ScopedOperation):
    type: Literal["connect_column_edge"] = "connect_column_edge"
    source_node: str
    target_node: str
    source_output: str
    target_input: str
    edge_id: str | None = None


class ConnectDataFrameEdgeOperation(ScopedOperation):
    type: Literal["connect_dataframe_edge"] = "connect_dataframe_edge"
    source_node: str
    target_node: str
    target_position: int | None = Field(default=None, ge=0)
    target_input: str | None = None
    edge_id: str | None = None


class DeleteEdgeOperation(ScopedOperation):
    type: Literal["delete_edge"] = "delete_edge"
    edge_id: str


class DetachWorkflowSourceOperation(ScopedOperation):
    type: Literal["detach_workflow_source"] = "detach_workflow_source"
    node_id: str


WorkflowDraftOperation = Annotated[
    CreateToolNodeOperation
    | CreateWorkflowNodeOperation
    | DeleteNodeOperation
    | RenameNodeOperation
    | UpdateToolParametersOperation
    | SetNodeEnabledOperation
    | MoveNodeOperation
    | MoveNodesOperation
    | ExposeWorkflowInputOperation
    | DeleteWorkflowInputOperation
    | ExposeWorkflowOutputOperation
    | DeleteWorkflowOutputOperation
    | ConnectColumnEdgeOperation
    | ConnectDataFrameEdgeOperation
    | DeleteEdgeOperation
    | DetachWorkflowSourceOperation,
    Field(discriminator="type"),
]


class WorkflowDraftOperationsRequest(OperationModel):
    expected_revision: int
    updated_by: DraftWriter = "agent"
    validate_: bool = Field(default=True, alias="validate")
    operations: list[WorkflowDraftOperation] = Field(min_length=1, max_length=10)


class WorkflowDraftOperationValidationResponse(OperationModel):
    error: Literal["operation_validation_error"] = "operation_validation_error"
    operation_index: int
    code: str
    detail: str
