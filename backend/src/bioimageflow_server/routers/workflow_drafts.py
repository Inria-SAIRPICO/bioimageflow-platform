"""Workflow live-draft router."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from bioimageflow_server.models.workflow_draft import (
    WorkflowDraftConflictResponse,
    WorkflowDraftLockedResponse,
    WorkflowDraftPutRequest,
    WorkflowDraftResetRequest,
    WorkflowDraftResponse,
)
from bioimageflow_server.services.workflow_draft import (
    WorkflowDraftRevisionConflict,
    WorkflowDraftService,
)
from bioimageflow_server.services.execution import ExecutionConflictError

router = APIRouter(prefix="/workflow-drafts", tags=["workflow-drafts"])


def get_workflow_draft_service() -> WorkflowDraftService:  # pragma: no cover
    raise RuntimeError("workflow_draft_service dependency not configured")


def get_execution_manager() -> Any | None:
    return None


def get_connection_manager() -> Any | None:
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


@asynccontextmanager
async def _idle_mutation_lease(
    execution_manager: Any | None,
) -> AsyncIterator[None]:
    """Keep Run mutually exclusive with an admitted async draft mutation."""

    if execution_manager is None:
        yield
        return
    lease = getattr(execution_manager, "exclusive_idle_mutation", None)
    if lease is None:
        if getattr(execution_manager, "is_running", False):
            raise ExecutionConflictError("An execution is already running")
        yield
        return
    async with lease():
        yield


def _conflict_response(exc: WorkflowDraftRevisionConflict) -> JSONResponse:
    body = WorkflowDraftConflictResponse(
        detail=str(exc),
        expected_revision=exc.expected_revision,
        current_revision=exc.current.draft_revision,
        current_updated_by=exc.current.updated_by,
        current_updated_at=exc.current.updated_at,
    )
    return JSONResponse(status_code=409, content=body.model_dump())


def _publish_workflow_draft_changed(
    connection_manager: Any | None,
    draft: WorkflowDraftResponse,
) -> None:
    if connection_manager is None:
        return
    connection_manager.publish_workflow_draft_changed(
        workflow_id=draft.workflow_id,
        draft_revision=draft.draft_revision,
        updated_by=draft.updated_by,
        updated_at=draft.updated_at,
        dirty_against_saved=draft.dirty_against_saved,
    )


@router.get("/{workflow_id:path}", response_model=WorkflowDraftResponse)
async def get_workflow_draft(
    workflow_id: str,
    request: Request,
    service: WorkflowDraftService = Depends(get_workflow_draft_service),
) -> WorkflowDraftResponse:
    try:
        return await service.get_draft_async(
            workflow_id,
            api_base_url=_api_base_url(request),
        )
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
    connection_manager: Any | None = Depends(get_connection_manager),
) -> WorkflowDraftResponse | JSONResponse:
    try:
        async with _idle_mutation_lease(execution_manager):
            draft = await service.put_draft_async(
                workflow_id,
                graph=body.graph,
                expected_revision=body.expected_revision,
                updated_by=body.updated_by,
                should_validate=body.validate_,
                api_base_url=_api_base_url(request),
            )
            _publish_workflow_draft_changed(connection_manager, draft)
            return draft
    except ExecutionConflictError:
        return _ensure_unlocked(execution_manager) or JSONResponse(
            status_code=423,
            content=WorkflowDraftLockedResponse(
                detail="Workflow editing is locked while execution is in progress",
            ).model_dump(),
        )
    except WorkflowDraftRevisionConflict as exc:
        return _conflict_response(exc)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/{workflow_id:path}/reset-to-saved",
    response_model=WorkflowDraftResponse,
    responses={
        409: {"model": WorkflowDraftConflictResponse},
        423: {"model": WorkflowDraftLockedResponse},
    },
)
async def reset_workflow_draft_to_saved(
    workflow_id: str,
    body: WorkflowDraftResetRequest,
    request: Request,
    service: WorkflowDraftService = Depends(get_workflow_draft_service),
    execution_manager: Any | None = Depends(get_execution_manager),
    connection_manager: Any | None = Depends(get_connection_manager),
) -> WorkflowDraftResponse | JSONResponse:
    try:
        async with _idle_mutation_lease(execution_manager):
            draft = await service.reset_draft_to_saved_async(
                workflow_id,
                expected_revision=body.expected_revision,
                updated_by=body.updated_by,
                api_base_url=_api_base_url(request),
            )
            _publish_workflow_draft_changed(connection_manager, draft)
            return draft
    except ExecutionConflictError:
        return _ensure_unlocked(execution_manager) or JSONResponse(
            status_code=423,
            content=WorkflowDraftLockedResponse(
                detail="Workflow editing is locked while execution is in progress",
            ).model_dump(),
        )
    except WorkflowDraftRevisionConflict as exc:
        return _conflict_response(exc)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
