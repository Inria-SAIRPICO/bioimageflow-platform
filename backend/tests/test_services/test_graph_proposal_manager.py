"""Tests for graph proposal operations and apply semantics."""

import pytest

from bioimageflow_server.models.graph import (
    ColumnRefEdge,
    GraphState,
    NodeState,
    PositionalEdge,
)
from bioimageflow_server.models.graph_proposals import (
    AddNodeOperation,
    AfterNodePlacement,
    ConnectOperation,
    DisconnectOperation,
    ReplaceGraphOperation,
    UpdateParametersOperation,
)
from bioimageflow_server.models.validation import ValidationResult
from bioimageflow_server.services.graph_proposal_manager import (
    DraftSnapshot,
    GraphProposalManager,
    ProposalOperationError,
    ProposalStaleError,
    ProposalValidationError,
)


class RecordingDraftStore:
    def __init__(self, graph: GraphState, revision: int = 1) -> None:
        self.graph = graph
        self.revision = revision
        self.saved_graphs: list[GraphState] = []

    def get_snapshot(self, draft_id: str) -> DraftSnapshot:
        return DraftSnapshot(
            draft_id=draft_id,
            revision=self.revision,
            graph=self.graph.model_copy(deep=True),
        )

    def save_graph(self, draft_id: str, graph: GraphState, base_revision: int) -> DraftSnapshot:
        if base_revision != self.revision:
            raise ProposalStaleError(
                draft_id=draft_id,
                expected_revision=base_revision,
                current_revision=self.revision,
            )
        self.revision += 1
        self.graph = graph.model_copy(deep=True)
        self.saved_graphs.append(self.graph)
        return DraftSnapshot(draft_id=draft_id, revision=self.revision, graph=self.graph)


def _node(node_id: str, x: float = 0, y: float = 0) -> NodeState:
    return NodeState(
        id=node_id,
        name=node_id,
        tool_name="Tool",
        position=(x, y),
        parameters={},
    )


def _valid(graph: GraphState) -> ValidationResult:
    return ValidationResult(valid=True, node_statuses={}, errors=[])


def test_apply_all_operation_types() -> None:
    base = GraphState(
        nodes=[_node("a", 0, 0), _node("b", 280, 0)],
        edges=[
            ColumnRefEdge(
                id="old",
                source_node="a",
                target_node="b",
                source_output="out",
                target_input="input",
            )
        ],
    )
    store = RecordingDraftStore(base)
    manager = GraphProposalManager(draft_store=store, validator=_valid)

    proposal = manager.create_proposal(
        draft_id="draft-1",
        base_revision=1,
        operations=[
            DisconnectOperation(edge_id="old"),
            AddNodeOperation(
                node=_node("c"),
                placement=AfterNodePlacement(node_id="b"),
            ),
            ConnectOperation(
                edge=PositionalEdge(
                    id="new",
                    source_node="b",
                    target_node="c",
                    positional_index=0,
                )
            ),
            UpdateParametersOperation(
                node_id="c",
                parameters={"threshold": 0.75},
            ),
        ],
    )
    result = manager.apply_proposal(proposal.id)

    assert result.revision == 2
    assert [node.id for node in result.graph.nodes] == ["a", "b", "c"]
    assert result.graph.nodes[2].position == (560, 0)
    assert result.graph.nodes[2].parameters == {"threshold": 0.75}
    assert [edge.id for edge in result.graph.edges] == ["new"]


def test_replace_graph_operation_replaces_existing_state() -> None:
    store = RecordingDraftStore(GraphState(nodes=[_node("old")], edges=[]))
    manager = GraphProposalManager(draft_store=store, validator=_valid)
    replacement = GraphState(nodes=[_node("new", 10, 20)], edges=[])

    proposal = manager.create_proposal(
        draft_id="draft-1",
        base_revision=1,
        operations=[ReplaceGraphOperation(graph=replacement)],
    )
    result = manager.apply_proposal(proposal.id)

    assert result.graph == replacement


def test_missing_semantic_placement_anchor_is_rejected() -> None:
    store = RecordingDraftStore(GraphState(nodes=[_node("a")], edges=[]))
    manager = GraphProposalManager(draft_store=store, validator=_valid)
    proposal = manager.create_proposal(
        draft_id="draft-1",
        base_revision=1,
        operations=[
            AddNodeOperation(
                node=_node("new"),
                placement=AfterNodePlacement(node_id="missing"),
            )
        ],
    )

    with pytest.raises(ProposalOperationError):
        manager.apply_proposal(proposal.id)

    assert store.saved_graphs == []


def test_validate_before_apply_prevents_saving_invalid_graph() -> None:
    validation = ValidationResult(
        valid=False,
        node_statuses={},
        errors=[],
    )
    store = RecordingDraftStore(GraphState(nodes=[], edges=[]))
    manager = GraphProposalManager(draft_store=store, validator=lambda graph: validation)
    proposal = manager.create_proposal(
        draft_id="draft-1",
        base_revision=1,
        operations=[AddNodeOperation(node=_node("bad"))],
    )

    with pytest.raises(ProposalValidationError) as exc:
        manager.apply_proposal(proposal.id)

    assert exc.value.validation == validation
    assert store.saved_graphs == []


def test_stale_proposal_rejected_before_validation_or_save() -> None:
    store = RecordingDraftStore(GraphState(nodes=[], edges=[]), revision=2)
    validation_calls = 0

    def validator(graph: GraphState) -> ValidationResult:
        nonlocal validation_calls
        validation_calls += 1
        return _valid(graph)

    manager = GraphProposalManager(draft_store=store, validator=validator)
    proposal = manager.create_proposal(
        draft_id="draft-1",
        base_revision=1,
        operations=[AddNodeOperation(node=_node("n1"))],
    )

    with pytest.raises(ProposalStaleError):
        manager.apply_proposal(proposal.id)

    assert validation_calls == 0
    assert store.saved_graphs == []


def test_apply_proposal_creates_undoable_snapshot() -> None:
    original = GraphState(nodes=[_node("a")], edges=[])
    store = RecordingDraftStore(original)
    manager = GraphProposalManager(draft_store=store, validator=_valid)
    proposal = manager.create_proposal(
        draft_id="draft-1",
        base_revision=1,
        operations=[AddNodeOperation(node=_node("b"))],
    )

    applied = manager.apply_proposal(proposal.id)
    undone = manager.undo_last_apply("draft-1", base_revision=applied.revision)

    assert [node.id for node in applied.graph.nodes] == ["a", "b"]
    assert undone.revision == 3
    assert undone.graph == original
