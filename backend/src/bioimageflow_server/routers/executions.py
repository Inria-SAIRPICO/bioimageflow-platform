"""Retained execution and distributed-preflight API."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse

from bioimageflow_server.models.execution_preflight import (
    ApplyPreparedExecutionRequest,
    ExecutionPreflightRequest,
    ExecutionPreflightResponse,
    ResultDownloadRequest,
    RetryExecutionRequest,
)
from bioimageflow_server.models.execution_runtime import (
    ExecutionActionResponse,
    ExecutionPage,
    ExecutionSnapshot,
)
from bioimageflow_server.services.execution_preflight import (
    DistributedPreflightService,
    PreparedTokenConflict,
    PreparedTokenError,
    PreparedTokenExpired,
    invocation_binding,
)
from bioimageflow_server.services.execution_registry import ExecutionNotFoundError
from bioimageflow_server.services.execution_runtime import ExecutionCoordinator

router = APIRouter(prefix="/executions", tags=["executions"])
preflight_router = APIRouter(prefix="/execution", tags=["execution"])


class PreparedRunRegistrar(Protocol):
    async def register_prepared_run(
        self,
        request: ApplyPreparedExecutionRequest,
        run_handle: object,
    ) -> ExecutionSnapshot: ...


class DownloadDestinationResolver(Protocol):
    def resolve(self, request: ResultDownloadRequest, execution_id: str) -> Path: ...


def get_execution_coordinator() -> ExecutionCoordinator:  # pragma: no cover
    raise RuntimeError("execution coordinator dependency is not configured")


def get_preflight_service() -> DistributedPreflightService:  # pragma: no cover
    raise RuntimeError("distributed preflight dependency is not configured")


def get_prepared_run_registrar() -> PreparedRunRegistrar:  # pragma: no cover
    raise RuntimeError("prepared-run registrar dependency is not configured")


def get_download_destination_resolver() -> DownloadDestinationResolver:  # pragma: no cover
    raise RuntimeError("download destination resolver dependency is not configured")


@preflight_router.post("/preflight", response_model=ExecutionPreflightResponse)
async def preflight_execution(
    request: ExecutionPreflightRequest,
    service: DistributedPreflightService = Depends(get_preflight_service),
) -> ExecutionPreflightResponse:
    try:
        return await service.preflight(request)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("", response_model=ExecutionSnapshot, status_code=202)
async def apply_prepared_execution(
    request: ApplyPreparedExecutionRequest,
    service: DistributedPreflightService = Depends(get_preflight_service),
    registrar: PreparedRunRegistrar = Depends(get_prepared_run_registrar),
) -> ExecutionSnapshot:
    binding = invocation_binding(
        workflow_id=request.workflow_id,
        draft_revision=request.draft_revision,
        target_id=request.target_id,
        requested_nodes=request.requested_nodes,
    )
    try:
        handle = await service.tokens.consume(request.token, binding=binding)
    except PreparedTokenExpired as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except PreparedTokenConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PreparedTokenError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await registrar.register_prepared_run(request, handle)


@router.get("", response_model=ExecutionPage)
async def list_executions(
    workflow_id: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    coordinator: ExecutionCoordinator = Depends(get_execution_coordinator),
) -> ExecutionPage:
    return await asyncio.to_thread(
        coordinator.registry.list,
        workflow_id=workflow_id,
        offset=offset,
        limit=limit,
    )


@router.get("/{execution_id}", response_model=ExecutionSnapshot)
async def get_execution(
    execution_id: str,
    coordinator: ExecutionCoordinator = Depends(get_execution_coordinator),
) -> ExecutionSnapshot:
    try:
        return await coordinator.get(execution_id)
    except (ExecutionNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc


@router.post("/{execution_id}/cancel", response_model=ExecutionActionResponse, status_code=202)
async def cancel_execution(
    execution_id: str,
    coordinator: ExecutionCoordinator = Depends(get_execution_coordinator),
) -> ExecutionActionResponse:
    try:
        snapshot = await coordinator.cancel(execution_id)
    except (ExecutionNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ExecutionActionResponse(execution_id=execution_id, state=snapshot.state)


@router.post("/{execution_id}/retry", response_model=ExecutionSnapshot, status_code=202)
async def retry_execution(
    execution_id: str,
    request: RetryExecutionRequest,
    coordinator: ExecutionCoordinator = Depends(get_execution_coordinator),
) -> ExecutionSnapshot:
    try:
        return await coordinator.retry(execution_id, target_id=request.target_id)
    except ExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{execution_id}/logs", response_class=PlainTextResponse)
async def execution_logs(
    execution_id: str,
    coordinator: ExecutionCoordinator = Depends(get_execution_coordinator),
) -> str:
    try:
        return await coordinator.logs(execution_id)
    except ExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc


@router.post("/{execution_id}/result", response_class=FileResponse)
async def download_execution_result(
    execution_id: str,
    request: ResultDownloadRequest,
    coordinator: ExecutionCoordinator = Depends(get_execution_coordinator),
    destinations: DownloadDestinationResolver = Depends(get_download_destination_resolver),
) -> FileResponse:
    try:
        destination = destinations.resolve(request, execution_id)
        path = await coordinator.download_result(execution_id, destination)
    except ExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return FileResponse(path)
