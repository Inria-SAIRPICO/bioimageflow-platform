"""Node output data endpoints."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Annotated, Literal, cast

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from starlette.responses import FileResponse

from bioimageflow_server.models.nodes import NodeDataResponse
from bioimageflow_server.services.result_store import (
    ResultDataNotReadyError,
    ResultStoreService,
)
from bioimageflow_server.services.thumbnail_manager import ThumbnailManager
from bioimageflow_server.services.workflow_context import resolve_workflow_storage_path
from bioimageflow_server.services.workflow_store import WorkflowStoreService

router = APIRouter(prefix="/nodes", tags=["nodes"])


# Bounded wait the endpoint applies on a cache miss. The Wetlands env
# stays warm after the first call, so most renders complete inside this
# window and the response carries the real PNG. Callers that time out
# get a placeholder + ``X-Thumbnail-Status: pending`` so the frontend
# can retry.
_THUMBNAIL_WAIT_TIMEOUT_SECONDS = 3.0
_TIFF_SUFFIXES = {".tif", ".tiff"}


def get_result_store() -> ResultStoreService:
    raise RuntimeError("ResultStoreService dependency is not configured")


def get_thumbnail_manager() -> ThumbnailManager:
    raise RuntimeError("ThumbnailManager dependency is not configured")


def get_workflow_store() -> WorkflowStoreService | None:
    return None


def _workflow_storage_path(
    workflow_name: str | None,
    workflow_store: WorkflowStoreService | None,
) -> Path | None:
    try:
        return resolve_workflow_storage_path(workflow_name, workflow_store, None)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{workflow_name}' not found",
        ) from exc


def _get_node_dataframe(
    node_id: str,
    result_store: ResultStoreService,
    storage_path: Path | None,
) -> pd.DataFrame:
    try:
        df = result_store.get_latest_dataframe(node_id, storage_path=storage_path)
    except ResultDataNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if df is None:
        raise HTTPException(status_code=404, detail=f"No output data for node '{node_id}'")
    return df


def _get_dataframe_cell(df: pd.DataFrame, row: int, col: str) -> object:
    if col not in df.columns:
        raise HTTPException(status_code=422, detail=f"Unknown column: '{col}'")
    if row >= len(df):
        raise HTTPException(status_code=422, detail=f"Row out of range: {row}")
    return df.iloc[row][col]


def _coerce_image_path(value: object, storage_path: Path | None) -> Path:
    is_missing = value is None
    if not is_missing and not isinstance(value, (str, Path)):
        try:
            is_missing = bool(pd.isna(value))
        except (TypeError, ValueError):
            is_missing = False
    if is_missing:
        raise HTTPException(status_code=422, detail="Selected image path is empty")
    image_path = Path(str(value)).expanduser()
    if not image_path.is_absolute() and storage_path is not None:
        image_path = storage_path / image_path
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail=f"Image file not found: {image_path}")
    return image_path


def _guess_image_media_type(path: Path) -> str:
    if path.suffix.lower() in _TIFF_SUFFIXES:
        return "image/tiff"
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


@router.get("/{node_id}/data", response_model=NodeDataResponse)
async def get_node_data(
    node_id: str,
    result_store: Annotated[ResultStoreService, Depends(get_result_store)],
    workflow_store: Annotated[WorkflowStoreService | None, Depends(get_workflow_store)],
    page: Annotated[int, Query(ge=0)] = 0,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    sort_by: str | None = None,
    sort_order: Literal["asc", "desc"] = "asc",
    tool_name: str | None = None,
    workflow_name: str | None = None,
) -> NodeDataResponse:
    storage_path = _workflow_storage_path(workflow_name, workflow_store)
    df = _get_node_dataframe(node_id, result_store, storage_path)

    df = df.copy()
    df.columns = [str(column) for column in df.columns]
    original_positions = list(range(len(df)))
    if sort_by is not None:
        if sort_by not in df.columns:
            raise HTTPException(status_code=422, detail=f"Unknown sort column: '{sort_by}'")
        sort_series = cast(pd.Series, df[sort_by])
        sorted_positions = sort_series.reset_index(drop=True).sort_values(
            ascending=(sort_order == "asc"),
            kind="mergesort",
        ).index.tolist()
        df = df.iloc[sorted_positions]
        original_positions = sorted_positions

    total_rows = len(df)
    start = page * page_size
    end = start + page_size
    page_df = df.iloc[start:end]
    page_positions = original_positions[start:end]

    columns = df.columns.tolist()
    rows = page_df.to_dict(orient="records")
    index = [str(i) for i in page_df.index.tolist()]
    column_types = result_store.get_column_types(page_df, tool_name=tool_name)

    return NodeDataResponse(
        columns=columns,
        index=index,
        rows=rows,
        absolute_rows=page_positions,
        total_rows=total_rows,
        page=page,
        page_size=page_size,
        column_types=column_types,
    )


@router.get("/{node_id}/data/csv")
async def download_node_csv(
    node_id: str,
    result_store: Annotated[ResultStoreService, Depends(get_result_store)],
    workflow_store: Annotated[WorkflowStoreService | None, Depends(get_workflow_store)],
    workflow_name: str | None = None,
) -> FileResponse:
    storage_path = _workflow_storage_path(workflow_name, workflow_store)
    csv_path = result_store.get_csv_path(node_id, storage_path=storage_path)
    if csv_path is None:
        raise HTTPException(status_code=404, detail=f"No output data for node '{node_id}'")
    return FileResponse(
        path=csv_path,
        media_type="text/csv",
        filename=f"{node_id}.csv",
    )


@router.get("/{node_id}/image")
async def get_node_image(
    node_id: str,
    result_store: Annotated[ResultStoreService, Depends(get_result_store)],
    workflow_store: Annotated[WorkflowStoreService | None, Depends(get_workflow_store)],
    col: str,
    row: Annotated[int, Query(ge=0)] = 0,
    workflow_name: str | None = None,
) -> FileResponse:
    storage_path = _workflow_storage_path(workflow_name, workflow_store)
    df = _get_node_dataframe(node_id, result_store, storage_path)
    value = _get_dataframe_cell(df, row, col)
    image_path = _coerce_image_path(value, storage_path)
    return FileResponse(
        path=image_path,
        media_type=_guess_image_media_type(image_path),
        filename=image_path.name,
        headers={"Accept-Ranges": "bytes"},
    )


@router.get("/{node_id}/thumbnail")
async def get_node_thumbnail(
    node_id: str,
    result_store: Annotated[ResultStoreService, Depends(get_result_store)],
    thumbnail_manager: Annotated[ThumbnailManager, Depends(get_thumbnail_manager)],
    workflow_store: Annotated[WorkflowStoreService | None, Depends(get_workflow_store)],
    col: str,
    row: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=16, le=1024)] = 128,
    workflow_name: str | None = None,
) -> Response:
    storage_path = _workflow_storage_path(workflow_name, workflow_store)
    df = _get_node_dataframe(node_id, result_store, storage_path)
    value = str(_get_dataframe_cell(df, row, col))
    png = await thumbnail_manager.get_or_queue(
        value, size, wait_timeout=_THUMBNAIL_WAIT_TIMEOUT_SECONDS
    )

    # Tell the frontend whether the body is the rendered thumbnail or a
    # placeholder still warming up — placeholders must not be cached or
    # a stale "pending" image sticks until the user hard-reloads.
    is_placeholder = png == thumbnail_manager.placeholder_png(size)
    headers = {
        "X-Thumbnail-Status": "pending" if is_placeholder else "ready",
        "Cache-Control": "no-store" if is_placeholder else "public, max-age=86400",
    }
    return Response(content=png, media_type="image/png", headers=headers)
