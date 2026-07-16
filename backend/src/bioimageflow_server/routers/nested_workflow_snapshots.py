"""Private nested-workflow snapshot routes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response

from bioimageflow_server.models.nested_workflow_snapshot import (
    NestedWorkflowSnapshotConflictResponse,
    NestedWorkflowSnapshotLockedResponse,
    NestedWorkflowSnapshotOpenRequest,
    NestedWorkflowSnapshotPutRequest,
    NestedWorkflowSnapshotResponse,
)
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedSnapshotRevisionConflict,
    NestedWorkflowSnapshotService,
)

router = APIRouter(
    prefix="/nested-workflow-snapshots",
    tags=["nested-workflow-snapshots"],
)


def get_nested_workflow_snapshot_service() -> NestedWorkflowSnapshotService:
    raise RuntimeError("nested_workflow_snapshot_service dependency not configured")


def get_execution_manager() -> Any | None:
    return None


def _locked_response(execution_manager: Any | None) -> JSONResponse | None:
    if execution_manager is None or not getattr(execution_manager, "is_running", False):
        return None
    body = NestedWorkflowSnapshotLockedResponse(
        detail="Workflow editing is locked while execution is in progress"
    )
    return JSONResponse(status_code=423, content=body.model_dump())


def _conflict_response(exc: NestedSnapshotRevisionConflict) -> JSONResponse:
    body = NestedWorkflowSnapshotConflictResponse(
        detail=str(exc),
        expected_revision=exc.expected_revision,
        current_revision=exc.current.snapshot_revision,
    )
    return JSONResponse(status_code=409, content=body.model_dump())


@router.post(
    "/open",
    response_model=NestedWorkflowSnapshotResponse,
    status_code=201,
    responses={423: {"model": NestedWorkflowSnapshotLockedResponse}},
)
async def open_nested_workflow_snapshot(
    body: NestedWorkflowSnapshotOpenRequest,
    service: NestedWorkflowSnapshotService = Depends(
        get_nested_workflow_snapshot_service
    ),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> NestedWorkflowSnapshotResponse | JSONResponse:
    locked = _locked_response(execution_manager)
    if locked is not None:
        return locked
    try:
        return service.open_snapshot(body.owner, body.parent_node_id, body.graph)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{session_id}", response_model=NestedWorkflowSnapshotResponse)
async def get_nested_workflow_snapshot(
    session_id: UUID,
    service: NestedWorkflowSnapshotService = Depends(
        get_nested_workflow_snapshot_service
    ),
) -> NestedWorkflowSnapshotResponse:
    try:
        return service.get_snapshot(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put(
    "/{session_id}",
    response_model=NestedWorkflowSnapshotResponse,
    responses={
        409: {"model": NestedWorkflowSnapshotConflictResponse},
        423: {"model": NestedWorkflowSnapshotLockedResponse},
    },
)
async def put_nested_workflow_snapshot(
    session_id: UUID,
    body: NestedWorkflowSnapshotPutRequest,
    service: NestedWorkflowSnapshotService = Depends(
        get_nested_workflow_snapshot_service
    ),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> NestedWorkflowSnapshotResponse | JSONResponse:
    locked = _locked_response(execution_manager)
    if locked is not None:
        return locked
    try:
        return service.put_snapshot(
            session_id,
            expected_revision=body.expected_revision,
            graph=body.graph,
        )
    except NestedSnapshotRevisionConflict as exc:
        return _conflict_response(exc)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete(
    "/{session_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
    responses={
        409: {"model": NestedWorkflowSnapshotConflictResponse},
        423: {"model": NestedWorkflowSnapshotLockedResponse},
    },
)
async def delete_nested_workflow_snapshot(
    session_id: UUID,
    expected_revision: int = Query(ge=0),
    service: NestedWorkflowSnapshotService = Depends(
        get_nested_workflow_snapshot_service
    ),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> Response:
    locked = _locked_response(execution_manager)
    if locked is not None:
        return locked
    try:
        service.delete_snapshot(session_id, expected_revision=expected_revision)
    except NestedSnapshotRevisionConflict as exc:
        return _conflict_response(exc)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)
