"""Private nested-workflow snapshot routes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response

from bioimageflow_server.models.nested_workflow_snapshot import (
    NestedWorkflowSnapshotConflictResponse,
    NestedWorkflowSnapshotDependencyConflictResponse,
    NestedWorkflowSnapshotLockedResponse,
    NestedWorkflowSnapshotOpenRequest,
    NestedWorkflowSnapshotPutRequest,
    NestedWorkflowSnapshotResponse,
)
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedSnapshotHasDependents,
    NestedSnapshotRevisionConflict,
    NestedWorkflowSnapshotService,
)
from bioimageflow_server.services.execution import ExecutionConflictError

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


@asynccontextmanager
async def _idle_mutation_lease(
    execution_manager: Any | None,
) -> AsyncIterator[None]:
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


def _conflict_response(exc: NestedSnapshotRevisionConflict) -> JSONResponse:
    body = NestedWorkflowSnapshotConflictResponse(
        detail=str(exc),
        expected_revision=exc.expected_revision,
        current_revision=exc.current.snapshot_revision,
    )
    return JSONResponse(status_code=409, content=body.model_dump())


def _dependency_conflict_response(
    exc: NestedSnapshotHasDependents,
) -> JSONResponse:
    body = NestedWorkflowSnapshotDependencyConflictResponse(
        detail=str(exc),
        dependent_session_ids=exc.dependent_session_ids,
    )
    return JSONResponse(status_code=409, content=body.model_dump(mode="json"))


@router.post(
    "/open",
    response_model=NestedWorkflowSnapshotResponse,
    status_code=201,
    responses={423: {"model": NestedWorkflowSnapshotLockedResponse}},
)
async def open_nested_workflow_snapshot(
    body: NestedWorkflowSnapshotOpenRequest,
    service: NestedWorkflowSnapshotService = Depends(get_nested_workflow_snapshot_service),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> NestedWorkflowSnapshotResponse | JSONResponse:
    try:
        async with _idle_mutation_lease(execution_manager):
            return await service.open_snapshot_async(
                body.owner,
                body.parent_node_id,
                body.graph,
            )
    except ExecutionConflictError:
        return _locked_response(execution_manager) or JSONResponse(
            status_code=423,
            content=NestedWorkflowSnapshotLockedResponse(
                detail="Workflow editing is locked while execution is in progress"
            ).model_dump(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{session_id}", response_model=NestedWorkflowSnapshotResponse)
async def get_nested_workflow_snapshot(
    session_id: UUID,
    service: NestedWorkflowSnapshotService = Depends(get_nested_workflow_snapshot_service),
) -> NestedWorkflowSnapshotResponse:
    try:
        return await service.get_snapshot_async(session_id)
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
    service: NestedWorkflowSnapshotService = Depends(get_nested_workflow_snapshot_service),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> NestedWorkflowSnapshotResponse | JSONResponse:
    try:
        async with _idle_mutation_lease(execution_manager):
            return await service.put_snapshot_async(
                session_id,
                expected_revision=body.expected_revision,
                graph=body.graph,
            )
    except ExecutionConflictError:
        return _locked_response(execution_manager) or JSONResponse(
            status_code=423,
            content=NestedWorkflowSnapshotLockedResponse(
                detail="Workflow editing is locked while execution is in progress"
            ).model_dump(),
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
        409: {
            "model": (
                NestedWorkflowSnapshotConflictResponse
                | NestedWorkflowSnapshotDependencyConflictResponse
            )
        },
        423: {"model": NestedWorkflowSnapshotLockedResponse},
    },
)
async def delete_nested_workflow_snapshot(
    session_id: UUID,
    expected_revision: int = Query(ge=0),
    service: NestedWorkflowSnapshotService = Depends(get_nested_workflow_snapshot_service),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> Response:
    try:
        async with _idle_mutation_lease(execution_manager):
            await service.delete_snapshot_async(
                session_id,
                expected_revision=expected_revision,
            )
    except ExecutionConflictError:
        return _locked_response(execution_manager) or JSONResponse(
            status_code=423,
            content=NestedWorkflowSnapshotLockedResponse(
                detail="Workflow editing is locked while execution is in progress"
            ).model_dump(),
        )
    except NestedSnapshotRevisionConflict as exc:
        return _conflict_response(exc)
    except NestedSnapshotHasDependents as exc:
        return _dependency_conflict_response(exc)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)
