"""Graph proposal router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from bioimageflow_server.models.graph_proposals import (
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


def get_graph_proposal_manager() -> GraphProposalManager:  # pragma: no cover
    raise RuntimeError("graph_proposal_manager dependency not configured")


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


@router.post("/{proposal_id}/apply")
async def apply_graph_proposal(
    proposal_id: str,
    manager: GraphProposalManager = Depends(get_graph_proposal_manager),
) -> GraphProposalApplyResponse:
    try:
        result = manager.apply_proposal(proposal_id)
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProposalStaleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
