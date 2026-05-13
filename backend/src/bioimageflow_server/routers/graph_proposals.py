"""Graph proposal router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from bioimageflow_server.models.graph_proposals import (
    DraftGraphProposalCreateRequest,
    GraphProposal,
    GraphProposalApplyResponse,
    GraphProposalCreateRequest,
)
from bioimageflow_server.services.graph_proposal_manager import (
    GraphProposalManager,
    ProposalNotFoundError,
    ProposalOperationError,
    ProposalStaleError,
    ProposalValidationError,
)

router = APIRouter(prefix="/graph/proposals", tags=["graph"])
draft_router = APIRouter(
    prefix="/workflow-drafts/{draft_id}/agent-proposals",
    tags=["workflow-drafts"],
)


def get_graph_proposal_manager() -> GraphProposalManager:  # pragma: no cover
    raise RuntimeError("graph_proposal_manager dependency not configured")


def get_execution_manager() -> Any | None:
    return None


def _ensure_unlocked(execution_manager: Any | None) -> None:
    if execution_manager is None:
        return
    if getattr(execution_manager, "is_running", False):
        raise HTTPException(
            status_code=423,
            detail="Graph editing is locked while execution is in progress",
        )


def _raise_stale(exc: ProposalStaleError) -> None:
    raise HTTPException(
        status_code=409,
        detail={
            "error": "conflict",
            "detail": str(exc),
            "field": "base_revision",
            "current_revision": exc.current_revision,
        },
    ) from exc


@router.post("")
async def create_graph_proposal(
    body: GraphProposalCreateRequest,
    manager: GraphProposalManager = Depends(get_graph_proposal_manager),
) -> GraphProposal:
    return manager.create_proposal(
        draft_id=body.draft_id,
        base_revision=body.base_revision,
        operations=body.operations,
        title=body.title,
    )


@draft_router.post("", response_model=GraphProposal)
async def create_draft_graph_proposal(
    draft_id: str,
    body: DraftGraphProposalCreateRequest,
    manager: GraphProposalManager = Depends(get_graph_proposal_manager),
) -> GraphProposal:
    return manager.create_proposal(
        draft_id=draft_id,
        base_revision=body.base_revision,
        operations=body.operations,
        title=body.title,
    )


async def _apply_graph_proposal(
    proposal_id: str,
    draft_id: str | None,
    manager: GraphProposalManager = Depends(get_graph_proposal_manager),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> GraphProposalApplyResponse:
    _ensure_unlocked(execution_manager)
    try:
        if draft_id is not None and manager.get_proposal(proposal_id).draft_id != draft_id:
            raise ProposalNotFoundError(f"Proposal {proposal_id!r} not found")
        result = manager.apply_proposal(proposal_id)
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProposalStaleError as exc:
        _raise_stale(exc)
    except ProposalOperationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProposalValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "graph_validation_failed",
                "detail": "Proposal graph failed validation",
                "validation": exc.validation.model_dump(mode="json"),
            },
        ) from exc

    return GraphProposalApplyResponse(
        draft_id=result.draft_id,
        revision=result.revision,
        graph=result.graph,
        validation=result.validation,
    )


@router.post("/{proposal_id}/apply")
async def apply_graph_proposal(
    proposal_id: str,
    manager: GraphProposalManager = Depends(get_graph_proposal_manager),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> GraphProposalApplyResponse:
    return await _apply_graph_proposal(
        proposal_id,
        None,
        manager=manager,
        execution_manager=execution_manager,
    )


@draft_router.post("/{proposal_id}/apply", response_model=GraphProposalApplyResponse)
async def apply_draft_graph_proposal(
    draft_id: str,
    proposal_id: str,
    manager: GraphProposalManager = Depends(get_graph_proposal_manager),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> GraphProposalApplyResponse:
    return await _apply_graph_proposal(
        proposal_id,
        draft_id,
        manager=manager,
        execution_manager=execution_manager,
    )


async def _reject_graph_proposal(
    proposal_id: str,
    draft_id: str | None,
    manager: GraphProposalManager,
) -> GraphProposal:
    try:
        proposal = manager.get_proposal(proposal_id)
        if draft_id is not None and proposal.draft_id != draft_id:
            raise ProposalNotFoundError(f"Proposal {proposal_id!r} not found")
        return manager.reject_proposal(proposal_id)
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{proposal_id}/reject", response_model=GraphProposal)
async def reject_graph_proposal(
    proposal_id: str,
    manager: GraphProposalManager = Depends(get_graph_proposal_manager),
) -> GraphProposal:
    return await _reject_graph_proposal(proposal_id, None, manager)


@draft_router.post("/{proposal_id}/reject", response_model=GraphProposal)
async def reject_draft_graph_proposal(
    draft_id: str,
    proposal_id: str,
    manager: GraphProposalManager = Depends(get_graph_proposal_manager),
) -> GraphProposal:
    return await _reject_graph_proposal(proposal_id, draft_id, manager)
