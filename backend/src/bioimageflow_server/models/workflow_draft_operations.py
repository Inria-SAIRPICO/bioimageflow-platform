"""Semantic workflow draft operation API models."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from bioimageflow_server.models.workflow_draft import DraftWriter


class _OperationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateNodeOperation(_OperationBase):
    type: Literal["create_node"] = "create_node"
    node_id: str
    tool_name: str
    name: str
    position: tuple[float, float]
    parameters: dict[str, Any] = Field(default_factory=dict)


class DeleteNodeOperation(_OperationBase):
    type: Literal["delete_node"] = "delete_node"
    node_id: str


class RenameNodeOperation(_OperationBase):
    type: Literal["rename_node"] = "rename_node"
    node_id: str
    name: str


class UpdateNodeParametersOperation(_OperationBase):
    type: Literal["update_node_parameters"] = "update_node_parameters"
    node_id: str
    parameters: dict[str, Any]


class SetNodeEnabledOperation(_OperationBase):
    type: Literal["set_node_enabled"] = "set_node_enabled"
    node_id: str
    enabled: bool


class WorkflowDraftOperationScope(_OperationBase):
    sub_workflow_path: list[str] = Field(default_factory=list)


class _LayoutScopeMixin(_OperationBase):
    scope: WorkflowDraftOperationScope = Field(default_factory=WorkflowDraftOperationScope)


class MoveNodeOperation(_LayoutScopeMixin):
    type: Literal["move_node"] = "move_node"
    node_id: str
    position: tuple[float, float]


class MoveNodeItem(_OperationBase):
    node_id: str
    position: tuple[float, float]


class MoveNodesOperation(_LayoutScopeMixin):
    type: Literal["move_nodes"] = "move_nodes"
    moves: list[MoveNodeItem] = Field(min_length=1)


class _PublishedNameMixin(_OperationBase):
    name: str

    @field_validator("name")
    @classmethod
    def _strip_non_empty_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("published name must not be empty")
        return stripped


class _PublishedTargetMixin(_OperationBase):
    internal_node_id: str

    @field_validator("internal_node_id", "internal_field", "internal_output", check_fields=False)
    @classmethod
    def _strip_non_empty_target(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("published target fields must not be empty")
        return stripped


class SetPublishedInputOperation(_PublishedNameMixin, _PublishedTargetMixin):
    type: Literal["set_published_input"] = "set_published_input"
    internal_field: str
    kind: Literal["parameter", "input"]
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    default: Any | None = None


class DeletePublishedInputOperation(_PublishedNameMixin):
    type: Literal["delete_published_input"] = "delete_published_input"


class SetPublishedOutputOperation(_PublishedNameMixin, _PublishedTargetMixin):
    type: Literal["set_published_output"] = "set_published_output"
    internal_output: str
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")


class DeletePublishedOutputOperation(_PublishedNameMixin):
    type: Literal["delete_published_output"] = "delete_published_output"


class ConnectColumnRefOperation(_OperationBase):
    type: Literal["connect_column_ref"] = "connect_column_ref"
    source_node: str
    target_node: str
    source_output: str
    target_input: str
    edge_id: str | None = None


class ConnectPositionalOperation(_OperationBase):
    type: Literal["connect_positional"] = "connect_positional"
    source_node: str
    target_node: str
    positional_index: int = Field(ge=0)
    edge_id: str | None = None


class DeleteEdgeOperation(_OperationBase):
    type: Literal["delete_edge"] = "delete_edge"
    edge_id: str


WorkflowDraftOperation = Annotated[
    CreateNodeOperation
    | DeleteNodeOperation
    | RenameNodeOperation
    | UpdateNodeParametersOperation
    | SetNodeEnabledOperation
    | MoveNodeOperation
    | MoveNodesOperation
    | SetPublishedInputOperation
    | DeletePublishedInputOperation
    | SetPublishedOutputOperation
    | DeletePublishedOutputOperation
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


class WorkflowDraftOperationValidationResponse(BaseModel):
    """Machine-readable semantic operation validation failure."""

    error: Literal["operation_validation_error"] = "operation_validation_error"
    operation_index: int
    code: str
    detail: str
