"""Node output data endpoints."""

from __future__ import annotations

import hashlib
import mimetypes
import tempfile
import time
from pathlib import Path
from typing import Annotated, Literal, cast

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from starlette.responses import FileResponse

from bioimageflow_server.models.nodes import NodeDataResponse
from bioimageflow_server.services.result_store import (
    DATAFRAME_RECORD_DIR_ATTR,
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
_OME_TIFF_CACHE_DIR = Path(tempfile.gettempdir()) / "bioimageflow-avivator-cache"
_OME_TIFF_CACHE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
_OFFSET_JSON_SUFFIX = ".offsets.json"


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


def _dataframe_record_dir(df: pd.DataFrame) -> Path | None:
    value = df.attrs.get(DATAFRAME_RECORD_DIR_ATTR)
    if isinstance(value, (str, Path)):
        return Path(value)
    return None


def _coerce_image_path(
    value: object,
    storage_path: Path | None,
    record_dir: Path | None = None,
) -> Path:
    is_missing = value is None
    if not is_missing and not isinstance(value, (str, Path)):
        try:
            is_missing = bool(pd.isna(value))
        except (TypeError, ValueError):
            is_missing = False
    if is_missing:
        raise HTTPException(status_code=422, detail="Selected image path is empty")
    image_path = Path(str(value)).expanduser()
    candidate_paths = [image_path]
    if not image_path.is_absolute():
        candidate_paths = []
        if record_dir is not None:
            candidate_paths.append(record_dir / image_path)
        if storage_path is not None:
            candidate_paths.append(storage_path / image_path)
        candidate_paths.append(image_path)
    for candidate in candidate_paths:
        if candidate.is_file():
            return candidate
    raise HTTPException(status_code=404, detail=f"Image file not found: {candidate_paths[0]}")


def _guess_image_media_type(path: Path) -> str:
    if path.suffix.lower() in _TIFF_SUFFIXES:
        return "image/tiff"
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _is_ome_tiff(path: Path) -> bool:
    if path.suffix.lower() not in _TIFF_SUFFIXES:
        return False
    try:
        import tifffile

        with tifffile.TiffFile(path) as tif:
            return bool(tif.ome_metadata)
    except Exception:
        return False


def _ome_tiff_cache_path(image_path: Path) -> Path:
    stat = image_path.stat()
    source_key = f"{image_path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"
    digest = hashlib.sha256(source_key.encode("utf-8")).hexdigest()
    return _OME_TIFF_CACHE_DIR / f"{digest}.ome.tif"


def _prune_ome_tiff_cache(now: float | None = None) -> None:
    if not _OME_TIFF_CACHE_DIR.is_dir():
        return
    cutoff = (time.time() if now is None else now) - _OME_TIFF_CACHE_MAX_AGE_SECONDS
    for path in _OME_TIFF_CACHE_DIR.iterdir():
        try:
            stat = path.stat()
        except OSError:
            continue
        if not path.is_file() or stat.st_mtime >= cutoff:
            continue
        try:
            path.unlink()
        except OSError:
            pass


def _ome_tiff_filename(filename: str) -> str:
    if filename.lower().endswith((".ome.tif", ".ome.tiff")):
        return filename
    return f"{Path(filename).stem}.ome.tif"


def _is_offsets_filename(filename: str | None) -> bool:
    return filename is not None and filename.lower().endswith(_OFFSET_JSON_SUFFIX)


def _read_image_array(image_path: Path) -> np.ndarray:
    if image_path.suffix.lower() in _TIFF_SUFFIXES:
        try:
            import tifffile

            return np.asarray(tifffile.imread(image_path))
        except Exception:
            pass

    try:
        from PIL import Image, ImageSequence

        with Image.open(image_path) as image:
            frames = [np.asarray(frame.copy()) for frame in ImageSequence.Iterator(image)]
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not read image for Avivator: {image_path.name}",
        ) from exc
    if not frames:
        raise HTTPException(
            status_code=422,
            detail=f"Image has no readable frames: {image_path.name}",
        )
    if len(frames) == 1:
        return np.asarray(frames[0])
    return np.stack(frames, axis=0)


def _ome_axes(data: np.ndarray) -> str:
    if data.ndim == 2:
        return "YX"
    if data.ndim == 3:
        if data.shape[-1] in {3, 4}:
            return "YXS"
        return "ZYX"
    if data.ndim == 4:
        if data.shape[-1] in {3, 4}:
            return "ZYXS"
        return "TZYX"
    raise HTTPException(
        status_code=422,
        detail=f"Avivator export supports 2D, 3D, or 4D images, got {data.ndim}D",
    )


def _as_ome_tiff(image_path: Path) -> Path:
    _prune_ome_tiff_cache()
    if _is_ome_tiff(image_path):
        return image_path

    cache_path = _ome_tiff_cache_path(image_path)
    if cache_path.is_file():
        return cache_path

    data = _read_image_array(image_path)
    axes = _ome_axes(data)
    _OME_TIFF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_path.with_name(f"{cache_path.name}.tmp")
    try:
        import tifffile

        kwargs: dict[str, object] = {
            "ome": True,
            "metadata": {"axes": axes},
        }
        if axes.endswith("S"):
            kwargs["photometric"] = "rgb"
        tifffile.imwrite(tmp_path, data, **kwargs)
        tmp_path.replace(cache_path)
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail=f"Could not convert image to OME-TIFF for Avivator: {image_path.name}",
        ) from exc
    return cache_path


def _tiff_offsets(path: Path) -> list[int]:
    try:
        import tifffile

        with tifffile.TiffFile(path) as tif:
            return [int(page.offset) for page in tif.pages]
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not read TIFF offsets for Avivator: {path.name}",
        ) from exc


@router.get("/{node_id:path}/data", response_model=NodeDataResponse)
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


@router.get("/{node_id:path}/data/csv")
async def download_node_csv(
    node_id: str,
    result_store: Annotated[ResultStoreService, Depends(get_result_store)],
    workflow_store: Annotated[WorkflowStoreService | None, Depends(get_workflow_store)],
    workflow_name: str | None = None,
    columns: Annotated[list[str] | None, Query()] = None,
) -> Response:
    storage_path = _workflow_storage_path(workflow_name, workflow_store)
    filename = f"{node_id}.csv"
    if not columns:
        csv_path = result_store.get_csv_path(node_id, storage_path=storage_path)
        if csv_path is not None:
            return FileResponse(
                path=csv_path,
                media_type="text/csv",
                filename=filename,
            )

    df = _get_node_dataframe(node_id, result_store, storage_path)
    if columns:
        unknown = [column for column in columns if column not in df.columns]
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown column: '{unknown[0]}'",
            )
        df = df.loc[:, columns]
    return Response(
        content=df.to_csv(index=True),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _node_image_response(
    node_id: str,
    result_store: ResultStoreService,
    workflow_store: WorkflowStoreService | None,
    col: str,
    row: int,
    workflow_name: str | None,
    output_format: Literal["ome-tiff"] | None,
    response_filename: str | None = None,
) -> Response:
    storage_path = _workflow_storage_path(workflow_name, workflow_store)
    df = _get_node_dataframe(node_id, result_store, storage_path)
    value = _get_dataframe_cell(df, row, col)
    image_path = _coerce_image_path(value, storage_path, _dataframe_record_dir(df))
    media_type = _guess_image_media_type(image_path)
    filename = response_filename or image_path.name
    if output_format == "ome-tiff":
        image_path = _as_ome_tiff(image_path)
        if _is_offsets_filename(response_filename):
            return JSONResponse(
                content=_tiff_offsets(image_path),
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Access-Control-Expose-Headers": "Content-Length, ETag",
                },
            )
        media_type = "image/tiff"
        filename = _ome_tiff_filename(filename)
    return FileResponse(
        path=image_path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline",
        headers={
            "Accept-Ranges": "bytes",
            "Access-Control-Expose-Headers": "Accept-Ranges, Content-Length, Content-Range, ETag",
        },
    )


@router.get("/{node_id:path}/image/{filename}")
async def get_node_image_with_filename(
    node_id: str,
    filename: str,
    result_store: Annotated[ResultStoreService, Depends(get_result_store)],
    workflow_store: Annotated[WorkflowStoreService | None, Depends(get_workflow_store)],
    col: str,
    row: Annotated[int, Query(ge=0)] = 0,
    workflow_name: str | None = None,
    output_format: Annotated[Literal["ome-tiff"] | None, Query(alias="format")] = None,
) -> FileResponse:
    return _node_image_response(
        node_id=node_id,
        result_store=result_store,
        workflow_store=workflow_store,
        col=col,
        row=row,
        workflow_name=workflow_name,
        output_format=output_format,
        response_filename=filename,
    )


@router.get("/{node_id:path}/image")
async def get_node_image(
    node_id: str,
    result_store: Annotated[ResultStoreService, Depends(get_result_store)],
    workflow_store: Annotated[WorkflowStoreService | None, Depends(get_workflow_store)],
    col: str,
    row: Annotated[int, Query(ge=0)] = 0,
    workflow_name: str | None = None,
    output_format: Annotated[Literal["ome-tiff"] | None, Query(alias="format")] = None,
) -> FileResponse:
    return _node_image_response(
        node_id=node_id,
        result_store=result_store,
        workflow_store=workflow_store,
        col=col,
        row=row,
        workflow_name=workflow_name,
        output_format=output_format,
    )


@router.get("/{node_id:path}/thumbnail")
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
    value = _get_dataframe_cell(df, row, col)
    image_path = _coerce_image_path(value, storage_path, _dataframe_record_dir(df))
    png = await thumbnail_manager.get_or_queue(
        image_path, size, wait_timeout=_THUMBNAIL_WAIT_TIMEOUT_SECONDS
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
