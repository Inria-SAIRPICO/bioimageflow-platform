"""In-memory workflow draft state."""

from __future__ import annotations

from uuid import uuid4

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.workflow_draft import WorkflowDraftState


class WorkflowDraftNotFoundError(KeyError):
    """Raised when a draft id is unknown."""


class StaleWorkflowDraftError(ValueError):
    """Raised when a mutation targets an old draft revision."""

    def __init__(self, *, current_revision: int, requested_revision: int) -> None:
        super().__init__("Stale draft base_revision")
        self.current_revision = current_revision
        self.requested_revision = requested_revision


class WorkflowDraftManager:
    """Simple in-memory revisioned draft store."""

    def __init__(self) -> None:
        self._drafts: dict[str, WorkflowDraftState] = {}

    def create(
        self,
        graph: GraphState | None = None,
        *,
        workflow_name: str | None = None,
    ) -> WorkflowDraftState:
        draft_id = uuid4().hex
        state = WorkflowDraftState(
            draft_id=draft_id,
            revision=1,
            graph=(graph or GraphState(nodes=[], edges=[])).model_copy(deep=True),
            workflow_name=workflow_name,
            dirty=False,
        )
        self._drafts[draft_id] = state
        return state.model_copy(deep=True)

    def get(self, draft_id: str, *, revision: int | None = None) -> WorkflowDraftState:
        state = self._drafts.get(draft_id)
        if state is None:
            raise WorkflowDraftNotFoundError(draft_id)
        if revision is not None and revision != state.revision:
            raise StaleWorkflowDraftError(
                current_revision=state.revision,
                requested_revision=revision,
            )
        return state.model_copy(deep=True)

    def update(
        self,
        draft_id: str,
        graph: GraphState,
        *,
        base_revision: int,
        client_seq: int | None = None,
    ) -> WorkflowDraftState:
        state = self._require_current(draft_id, base_revision)
        state.graph = graph.model_copy(deep=True)
        state.revision += 1
        state.client_seq = client_seq
        state.dirty = True
        return state.model_copy(deep=True)

    def patch_parameters(
        self,
        draft_id: str,
        node_id: str,
        parameters: dict,
        *,
        base_revision: int,
        client_seq: int | None = None,
    ) -> WorkflowDraftState:
        state = self._drafts.get(draft_id)
        if state is None:
            raise WorkflowDraftNotFoundError(draft_id)
        if base_revision != state.revision:
            raise StaleWorkflowDraftError(
                current_revision=state.revision,
                requested_revision=base_revision,
            )
        graph = state.graph.model_copy(deep=True)
        for node in graph.nodes:
            if node.id == node_id:
                node.parameters.update(parameters)
                break
        else:
            raise KeyError(node_id)
        state.graph = graph
        state.revision += 1
        state.client_seq = client_seq
        state.dirty = True
        return state.model_copy(deep=True)

    def _require_current(
        self,
        draft_id: str,
        base_revision: int,
    ) -> WorkflowDraftState:
        state = self._drafts.get(draft_id)
        if state is None:
            raise WorkflowDraftNotFoundError(draft_id)
        if base_revision != state.revision:
            raise StaleWorkflowDraftError(
                current_revision=state.revision,
                requested_revision=base_revision,
            )
        return state
