"""Models for graph agent proposals."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Discriminator

from bioimageflow_server.models.graph import Edge, GraphState, NodeState
from bioimageflow_server.models.validation import ValidationResult


class AfterNodePlacement(BaseModel):
    """Place a new node after an existing node."""

    type: Literal["after_node"] = "after_node"
    node_id: str


class BetweenNodesPlacement(BaseModel):
    """Place a new node between two existing nodes."""

    type: Literal["between_nodes"] = "between_nodes"
    source_node: str
    target_node: str


class EndOfBranchPlacement(BaseModel):
    """Place a new node at the terminal end of a branch."""

    type: Literal["end_of_branch"] = "end_of_branch"
    node_id: str


GraphProposalPlacement = Annotated[
    AfterNodePlacement | BetweenNodesPlacement | EndOfBranchPlacement,
    Discriminator("type"),
]


class AddNodeOperation(BaseModel):
    """Add a node, optionally using semantic placement."""

    type: Literal["add_node"] = "add_node"
    node: NodeState
    placement: GraphProposalPlacement | None = None


class ConnectOperation(BaseModel):
    """Add an edge between existing nodes."""

    type: Literal["connect"] = "connect"
    edge: Edge


class DisconnectOperation(BaseModel):
    """Remove an edge by id."""

    type: Literal["disconnect"] = "disconnect"
    edge_id: str


class UpdateParametersOperation(BaseModel):
    """Merge parameter edits into an existing node."""

    type: Literal["update_parameters"] = "update_parameters"
    node_id: str
    parameters: dict[str, Any]


class ReplaceGraphOperation(BaseModel):
    """Replace the graph state before applying subsequent operations."""

    type: Literal["replace_graph"] = "replace_graph"
    graph: GraphState


GraphProposalOperation = Annotated[
    AddNodeOperation
    | ConnectOperation
    | DisconnectOperation
    | UpdateParametersOperation
    | ReplaceGraphOperation,
    Discriminator("type"),
]


class GraphProposalCreateRequest(BaseModel):
    """Request to create a proposal tied to a draft revision."""

    draft_id: str
    base_revision: int
    operations: list[GraphProposalOperation]
    title: str | None = None


class GraphProposal(BaseModel):
    """Stored graph proposal."""

    id: str
    draft_id: str
    base_revision: int
    operations: list[GraphProposalOperation]
    title: str | None = None


class GraphProposalApplyResponse(BaseModel):
    """Response returned after a proposal is applied."""

    draft_id: str
    revision: int
    graph: GraphState
    validation: ValidationResult
