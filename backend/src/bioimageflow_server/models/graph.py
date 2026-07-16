"""Graph state models: nodes, edges, and the full graph."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field


class PublishedInput(BaseModel):
    """An internal sub-workflow field exposed as an outer input pin."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    name: str
    internal_node_id: str
    internal_field: str
    kind: Literal["parameter", "input"]
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    default: Any | None = None


class PublishedOutput(BaseModel):
    """An internal sub-workflow output exposed as an outer output pin."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    name: str
    internal_node_id: str
    internal_output: str
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")


class NodeState(BaseModel):
    """A single node in the processing graph."""

    model_config = ConfigDict(json_schema_mode_override="validation")

    id: str
    name: str
    tool_name: str
    position: tuple[float, float]
    parameters: dict[str, Any]
    resources: dict[str, Any] = Field(default_factory=dict)
    output_templates: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    collapsed: bool = False
    sub_workflow: GraphState | None = None
    published_inputs: list[PublishedInput] = Field(default_factory=list)
    published_outputs: list[PublishedOutput] = Field(default_factory=list)
    sub_workflow_readonly_reason: str | None = None
    source_workflow_name: str | None = None


class ColumnRefEdge(BaseModel):
    """Edge that maps a named output column to a named input."""

    type: Literal["column_ref"] = "column_ref"
    id: str
    source_node: str
    target_node: str
    source_output: str
    target_input: str


class PositionalEdge(BaseModel):
    """Edge that connects nodes by positional index."""

    type: Literal["positional"] = "positional"
    id: str
    source_node: str
    target_node: str
    positional_index: int


Edge = Annotated[ColumnRefEdge | PositionalEdge, Discriminator("type")]


class GraphState(BaseModel):
    """Complete graph state with nodes and edges."""

    model_config = ConfigDict(json_schema_mode_override="validation")

    nodes: list[NodeState]
    edges: list[Edge]
    published_inputs: list[PublishedInput] = Field(default_factory=list)
    published_outputs: list[PublishedOutput] = Field(default_factory=list)


class GraphValidationRequest(BaseModel):
    """Request to validate a graph in an optional workflow context."""

    graph: GraphState
    workflow_name: str | None = None


class NodeOutputSchemaResponse(BaseModel):
    """Response for ``POST /graph/nodes/{node_id}/output_schema``."""

    resolved: bool
    columns: dict[str, Any]
