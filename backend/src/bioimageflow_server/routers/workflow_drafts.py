"""Workflow live-draft router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from bioimageflow_server.models.workflow_draft import (
    WorkflowDraftConflictResponse,
    WorkflowDraftLockedResponse,
    WorkflowDraftPutRequest,
    WorkflowDraftResponse,
)
from bioimageflow_server.services.workflow_draft import (
    WorkflowDraftRevisionConflict,
    WorkflowDraftService,
)

router = APIRouter(prefix="/workflow-drafts", tags=["workflow-drafts"])


def get_workflow_draft_service() -> WorkflowDraftService:  # pragma: no cover
    raise RuntimeError("workflow_draft_service dependency not configured")


def get_execution_manager() -> Any | None:
    return None


def _api_base_url(request: Request) -> str:
    return f"{str(request.base_url).rstrip('/')}/api/v1"


def _ensure_unlocked(execution_manager: Any | None) -> JSONResponse | None:
    if execution_manager is None:
        return None
    if getattr(execution_manager, "is_running", False):
        body = WorkflowDraftLockedResponse(
            detail="Workflow editing is locked while execution is in progress",
        )
        return JSONResponse(status_code=423, content=body.model_dump())
    return None


@router.get("/{workflow_id:path}", response_model=WorkflowDraftResponse)
async def get_workflow_draft(
    workflow_id: str,
    request: Request,
    service: WorkflowDraftService = Depends(get_workflow_draft_service),
) -> WorkflowDraftResponse:
    try:
        return service.get_draft(workflow_id, api_base_url=_api_base_url(request))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put(
    "/{workflow_id:path}",
    response_model=WorkflowDraftResponse,
    responses={
        409: {"model": WorkflowDraftConflictResponse},
        423: {"model": WorkflowDraftLockedResponse},
    },
)
async def put_workflow_draft(
    workflow_id: str,
    body: WorkflowDraftPutRequest,
    request: Request,
    service: WorkflowDraftService = Depends(get_workflow_draft_service),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> WorkflowDraftResponse | JSONResponse:
    locked = _ensure_unlocked(execution_manager)
    if locked is not None:
        return locked
    try:
        return service.put_draft(
            workflow_id,
            graph=body.graph,
            expected_revision=body.expected_revision,
            updated_by=body.updated_by,
            should_validate=body.validate_,
            api_base_url=_api_base_url(request),
        )
    except WorkflowDraftRevisionConflict as exc:
        body = WorkflowDraftConflictResponse(
            detail=str(exc),
            expected_revision=exc.expected_revision,
            current_revision=exc.current.draft_revision,
            current_updated_by=exc.current.updated_by,
            current_updated_at=exc.current.updated_at,
        )
        return JSONResponse(status_code=409, content=body.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
