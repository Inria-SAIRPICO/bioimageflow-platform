"""Consolidated Data Table query and CSV endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from bioimageflow_server.models.data_table import (
    DataTableCsvRequest,
    DataTableQueryRequest,
    DataTableQueryResponse,
    DataTableStackedResponse,
)
from bioimageflow_server.routers.nodes import get_result_store, get_workflow_store
from bioimageflow_server.services.data_table_projection import (
    DataTableProjectionInputError,
    DataTableProjectionService,
)
from bioimageflow_server.services.result_store import ResultDataNotReadyError, ResultStoreService
from bioimageflow_server.services.workflow_context import resolve_workflow_storage_path
from bioimageflow_server.services.workflow_store import WorkflowStoreService

router = APIRouter(prefix="/data-table", tags=["data-table"])


def _storage_path(
    workflow_id: str | None, workflow_store: WorkflowStoreService | None
):
    try:
        return resolve_workflow_storage_path(workflow_id, workflow_store, None)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found") from exc


@router.post("/query", response_model=DataTableQueryResponse)
async def query_data_table(
    request: DataTableQueryRequest,
    result_store: Annotated[ResultStoreService, Depends(get_result_store)],
    workflow_store: Annotated[WorkflowStoreService | None, Depends(get_workflow_store)],
) -> DataTableQueryResponse:
    service = DataTableProjectionService(result_store)
    try:
        return service.query(
            request.sources,
            storage_path=_storage_path(request.workflow_id, workflow_store),
            page=request.page,
            page_size=request.page_size,
            sort_by=request.sort_by,
            sort_order=request.sort_order,
        )
    except ResultDataNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DataTableProjectionInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/csv")
async def download_data_table_csv(
    request: DataTableCsvRequest,
    result_store: Annotated[ResultStoreService, Depends(get_result_store)],
    workflow_store: Annotated[WorkflowStoreService | None, Depends(get_workflow_store)],
) -> Response:
    service = DataTableProjectionService(result_store)
    try:
        projection = service.csv(
            request.sources,
            storage_path=_storage_path(request.workflow_id, workflow_store),
            sort_by=request.sort_by,
            sort_order=request.sort_order,
        )
    except ResultDataNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DataTableProjectionInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(projection, DataTableStackedResponse):
        raise HTTPException(status_code=409, detail=projection.message)
    return Response(
        content=projection.dataframe.to_csv(index=True),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="data-table.csv"'},
    )
