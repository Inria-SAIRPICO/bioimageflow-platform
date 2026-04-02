"""Graph state models: nodes, edges, and the full graph."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Discriminator


class NodeState(BaseModel):
    """A single node in the processing graph."""

    id: str
    name: str
    tool_name: str
    position: tuple[float, float]
    parameters: dict[str, Any]
    resources: dict[str, Any] = {}
    output_templates: dict[str, str] = {}
    enabled: bool = True
    collapsed: bool = False


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

    nodes: list[NodeState]
    edges: list[Edge]
