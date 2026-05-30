"""Semantic workflow draft operation API models."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from bioimageflow_server.models.workflow_draft import DraftWriter


class CreateNodeOperation(BaseModel):
    type: Literal["create_node"] = "create_node"
    node_id: str
    tool_name: str
    name: str
    position: tuple[float, float]
    parameters: dict[str, Any] = Field(default_factory=dict)


class DeleteNodeOperation(BaseModel):
    type: Literal["delete_node"] = "delete_node"
    node_id: str


class RenameNodeOperation(BaseModel):
    type: Literal["rename_node"] = "rename_node"
    node_id: str
    name: str


class UpdateNodeParametersOperation(BaseModel):
    type: Literal["update_node_parameters"] = "update_node_parameters"
    node_id: str
    parameters: dict[str, Any]


class SetNodeEnabledOperation(BaseModel):
    type: Literal["set_node_enabled"] = "set_node_enabled"
    node_id: str
    enabled: bool


class MoveNodeOperation(BaseModel):
    type: Literal["move_node"] = "move_node"
    node_id: str
    position: tuple[float, float]


class ConnectColumnRefOperation(BaseModel):
    type: Literal["connect_column_ref"] = "connect_column_ref"
    source_node: str
    target_node: str
    source_output: str
    target_input: str
    edge_id: str | None = None


class ConnectPositionalOperation(BaseModel):
    type: Literal["connect_positional"] = "connect_positional"
    source_node: str
    target_node: str
    positional_index: int = Field(ge=0)
    edge_id: str | None = None


class DeleteEdgeOperation(BaseModel):
    type: Literal["delete_edge"] = "delete_edge"
    edge_id: str


WorkflowDraftOperation = Annotated[
    CreateNodeOperation
    | DeleteNodeOperation
    | RenameNodeOperation
    | UpdateNodeParametersOperation
    | SetNodeEnabledOperation
    | MoveNodeOperation
    | ConnectColumnRefOperation
    | ConnectPositionalOperation
    | DeleteEdgeOperation,
    Field(discriminator="type"),
]


class WorkflowDraftOperationsRequest(BaseModel):
    """Request body for applying semantic edits to a workflow draft."""

    model_config = ConfigDict(populate_by_name=True)

    expected_revision: int
    updated_by: DraftWriter = "agent"
    validate_: bool = Field(default=True, alias="validate")
    operations: list[WorkflowDraftOperation] = Field(min_length=1, max_length=10)
