"""Service for creating and applying graph agent proposals."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from bioimageflow_server.models.graph import GraphState, NodeState
from bioimageflow_server.models.graph_proposals import (
    AddNodeOperation,
    AfterNodePlacement,
    BetweenNodesPlacement,
    ConnectOperation,
    DisconnectOperation,
    EndOfBranchPlacement,
    GraphProposal,
    GraphProposalOperation,
    ReplaceGraphOperation,
    UpdateParametersOperation,
)
from bioimageflow_server.models.validation import ValidationResult
from bioimageflow_server.services.graph_layout import place_node
from bioimageflow_server.services.workflow_drafts import (
    StaleWorkflowDraftError,
    WorkflowDraftManager,
)


@dataclass(frozen=True)
class DraftSnapshot:
    """Draft graph snapshot at a concrete revision."""

    draft_id: str
    revision: int
    graph: GraphState


class ProposalDraftStore(Protocol):
    """Narrow interface expected from the backend draft manager."""

    def get_snapshot(self, draft_id: str) -> DraftSnapshot:
        """Return the draft graph and current revision."""

    def save_graph(
        self,
        draft_id: str,
        graph: GraphState,
        base_revision: int,
    ) -> DraftSnapshot:
        """Persist a graph if ``base_revision`` is still current."""


class InMemoryProposalDraftStore:
    """Small local draft store used until the draft manager is wired in."""

    def __init__(self) -> None:
        self._drafts: dict[str, DraftSnapshot] = {}

    def get_snapshot(self, draft_id: str) -> DraftSnapshot:
        snapshot = self._drafts.get(draft_id)
        if snapshot is None:
            snapshot = DraftSnapshot(
                draft_id=draft_id,
                revision=1,
                graph=GraphState(nodes=[], edges=[]),
            )
            self._drafts[draft_id] = snapshot
        return DraftSnapshot(
            draft_id=snapshot.draft_id,
            revision=snapshot.revision,
            graph=snapshot.graph.model_copy(deep=True),
        )

    def save_graph(
        self,
        draft_id: str,
        graph: GraphState,
        base_revision: int,
    ) -> DraftSnapshot:
        current = self.get_snapshot(draft_id)
        if current.revision != base_revision:
            raise ProposalStaleError(
                draft_id=draft_id,
                expected_revision=base_revision,
                current_revision=current.revision,
            )
        next_snapshot = DraftSnapshot(
            draft_id=draft_id,
            revision=current.revision + 1,
            graph=graph.model_copy(deep=True),
        )
        self._drafts[draft_id] = next_snapshot
        return next_snapshot


class WorkflowDraftProposalStore:
    """Adapter from ``WorkflowDraftManager`` to the proposal draft interface."""

    def __init__(self, manager: WorkflowDraftManager) -> None:
        self._manager = manager

    def get_snapshot(self, draft_id: str) -> DraftSnapshot:
        state = self._manager.get(draft_id)
        return DraftSnapshot(
            draft_id=state.draft_id,
            revision=state.revision,
            graph=state.graph,
        )

    def save_graph(
        self,
        draft_id: str,
        graph: GraphState,
        base_revision: int,
    ) -> DraftSnapshot:
        try:
            state = self._manager.update(
                draft_id,
                graph,
                base_revision=base_revision,
            )
        except StaleWorkflowDraftError as exc:
            raise ProposalStaleError(
                draft_id=draft_id,
                expected_revision=exc.requested_revision,
                current_revision=exc.current_revision,
            ) from exc
        return DraftSnapshot(
            draft_id=state.draft_id,
            revision=state.revision,
            graph=state.graph,
        )


@dataclass(frozen=True)
class ProposalApplyResult:
    """Applied proposal result."""

    draft_id: str
    revision: int
    graph: GraphState
    validation: ValidationResult


class ProposalError(RuntimeError):
    """Base proposal error."""


class ProposalNotFoundError(ProposalError):
    """Raised when a proposal id is unknown."""


class ProposalOperationError(ProposalError):
    """Raised when an operation cannot be applied to the graph."""


class ProposalValidationError(ProposalError):
    """Raised when a proposal produces an invalid graph."""

    def __init__(self, validation: ValidationResult) -> None:
        super().__init__("proposal graph failed validation")
        self.validation = validation


class ProposalStaleError(ProposalError):
    """Raised when the proposal base revision no longer matches the draft."""

    def __init__(
        self,
        *,
        draft_id: str,
        expected_revision: int,
        current_revision: int,
    ) -> None:
        super().__init__(
            f"Draft {draft_id!r} is at revision {current_revision}, "
            f"proposal targets revision {expected_revision}"
        )
        self.draft_id = draft_id
        self.expected_revision = expected_revision
        self.current_revision = current_revision


def _noop_validator(graph: GraphState) -> ValidationResult:
    return ValidationResult(valid=True, node_statuses={}, errors=[])


class GraphProposalManager:
    """Creates proposals and applies them to draft graph snapshots."""

    def __init__(
        self,
        *,
        draft_store: ProposalDraftStore,
        validator: Callable[[GraphState], ValidationResult] = _noop_validator,
    ) -> None:
        self._draft_store = draft_store
        self._validator = validator
        self._proposals: dict[str, GraphProposal] = {}

    def create_proposal(
        self,
        *,
        draft_id: str,
        base_revision: int,
        operations: list[GraphProposalOperation],
        title: str | None = None,
    ) -> GraphProposal:
        proposal = GraphProposal(
            id=str(uuid4()),
            draft_id=draft_id,
            base_revision=base_revision,
            operations=operations,
            title=title,
        )
        self._proposals[proposal.id] = proposal
        return proposal

    def get_proposal(self, proposal_id: str) -> GraphProposal:
        try:
            return self._proposals[proposal_id]
        except KeyError as exc:
            raise ProposalNotFoundError(f"Proposal {proposal_id!r} not found") from exc

    def reject_proposal(self, proposal_id: str) -> GraphProposal:
        proposal = self.get_proposal(proposal_id)
        del self._proposals[proposal_id]
        return proposal

    def apply_proposal(self, proposal_id: str) -> ProposalApplyResult:
        proposal = self.get_proposal(proposal_id)
        snapshot = self._draft_store.get_snapshot(proposal.draft_id)
        if snapshot.revision != proposal.base_revision:
            raise ProposalStaleError(
                draft_id=proposal.draft_id,
                expected_revision=proposal.base_revision,
                current_revision=snapshot.revision,
            )

        graph = apply_operations(snapshot.graph, proposal.operations)
        validation = self._validator(graph)
        if not validation.valid:
            raise ProposalValidationError(validation)

        saved = self._draft_store.save_graph(
            proposal.draft_id,
            graph,
            proposal.base_revision,
        )
        return ProposalApplyResult(
            draft_id=saved.draft_id,
            revision=saved.revision,
            graph=saved.graph,
            validation=validation,
        )


def apply_operations(
    graph: GraphState,
    operations: list[GraphProposalOperation],
) -> GraphState:
    """Apply proposal operations to a copy of ``graph``."""

    working = graph.model_copy(deep=True)
    for operation in operations:
        if isinstance(operation, ReplaceGraphOperation):
            working = operation.graph.model_copy(deep=True)
        elif isinstance(operation, AddNodeOperation):
            _add_node(working, operation)
        elif isinstance(operation, ConnectOperation):
            _connect(working, operation)
        elif isinstance(operation, DisconnectOperation):
            _disconnect(working, operation)
        elif isinstance(operation, UpdateParametersOperation):
            _update_parameters(working, operation)
    return working


def _add_node(graph: GraphState, operation: AddNodeOperation) -> None:
    if any(node.id == operation.node.id for node in graph.nodes):
        raise ProposalOperationError(f"Node {operation.node.id!r} already exists")
    node = operation.node.model_copy(deep=True)
    if operation.placement is not None:
        _ensure_placement_anchors(graph, operation.placement)
        node.position = place_node(graph, operation.placement)
    graph.nodes.append(node)


def _ensure_placement_anchors(graph: GraphState, placement: object) -> None:
    node_ids = {node.id for node in graph.nodes}
    if isinstance(placement, AfterNodePlacement) and placement.node_id not in node_ids:
        raise ProposalOperationError(
            f"Placement anchor node {placement.node_id!r} does not exist"
        )
    if isinstance(placement, EndOfBranchPlacement) and placement.node_id not in node_ids:
        raise ProposalOperationError(
            f"Placement branch node {placement.node_id!r} does not exist"
        )
    if isinstance(placement, BetweenNodesPlacement):
        missing = [
            node_id
            for node_id in (placement.source_node, placement.target_node)
            if node_id not in node_ids
        ]
        if missing:
            raise ProposalOperationError(f"Placement node {missing[0]!r} does not exist")


def _connect(graph: GraphState, operation: ConnectOperation) -> None:
    edge = operation.edge.model_copy(deep=True)
    if any(existing.id == edge.id for existing in graph.edges):
        raise ProposalOperationError(f"Edge {edge.id!r} already exists")
    node_ids = {node.id for node in graph.nodes}
    if edge.source_node not in node_ids:
        raise ProposalOperationError(f"Source node {edge.source_node!r} does not exist")
    if edge.target_node not in node_ids:
        raise ProposalOperationError(f"Target node {edge.target_node!r} does not exist")
    graph.edges.append(edge)


def _disconnect(graph: GraphState, operation: DisconnectOperation) -> None:
    before = len(graph.edges)
    graph.edges = [edge for edge in graph.edges if edge.id != operation.edge_id]
    if len(graph.edges) == before:
        raise ProposalOperationError(f"Edge {operation.edge_id!r} does not exist")


def _update_parameters(
    graph: GraphState,
    operation: UpdateParametersOperation,
) -> None:
    node = _get_node(graph, operation.node_id)
    node.parameters = {**node.parameters, **operation.parameters}


def _get_node(graph: GraphState, node_id: str) -> NodeState:
    for node in graph.nodes:
        if node.id == node_id:
            return node
    raise ProposalOperationError(f"Node {node_id!r} does not exist")
