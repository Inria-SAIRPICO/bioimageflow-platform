"""Napari viewer router.

Endpoints:
- ``POST /napari/open``: launch (lazy) and open the given paths.
- ``GET /napari/status``: lock-free status snapshot.
- ``POST /napari/shutdown``: terminate the manager process.

All path validation lives in ``NapariLauncher.open()`` — the router
does not re-validate. Errors map:
- ``FileNotFoundError`` -> 400 ``path_not_found``
- ``NapariLaunchError`` -> 503 ``napari_launch_failed``
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from bioimageflow_server.models.napari import NapariOpenRequest, NapariStatus
from bioimageflow_server.routers.nodes import (
    _coerce_image_path,
    _dataframe_record_dir,
    _get_dataframe_cell,
    _get_node_dataframe,
)
from bioimageflow_server.services.napari_launcher import (
    NapariLauncher,
    NapariLaunchError,
)
from bioimageflow_server.services.result_store import ResultStoreService
from bioimageflow_server.services.workflow_context import resolve_workflow_storage_path
from bioimageflow_server.services.workflow_store import WorkflowStoreService


router = APIRouter(prefix="/napari", tags=["napari"])
_logger = logging.getLogger(__name__)


def get_napari_launcher() -> NapariLauncher:  # pragma: no cover
    """Stub overridden by ``create_app`` via ``dependency_overrides``."""
    raise NotImplementedError


def get_result_store() -> ResultStoreService:  # pragma: no cover
    """Stub overridden by ``create_app`` via ``dependency_overrides``."""
    raise RuntimeError("ResultStoreService dependency is not configured")


def get_workflow_store() -> WorkflowStoreService | None:  # pragma: no cover
    return None


def _context_fields(request: NapariOpenRequest) -> tuple[object, ...]:
    return (request.node_id, request.row, request.col)


def _resolve_workflow_storage_path(
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


def _resolve_open_paths(
    request: NapariOpenRequest,
    result_store: ResultStoreService,
    workflow_store: WorkflowStoreService | None,
) -> list[str]:
    context_values = _context_fields(request)
    has_context = any(value is not None for value in context_values)
    if not has_context:
        return request.paths
    if not all(value is not None for value in context_values):
        raise HTTPException(
            status_code=422,
            detail="node_id, row, and col are required together for path resolution",
        )
    if len(request.paths) != 1:
        raise HTTPException(
            status_code=422,
            detail="context-based Napari open supports exactly one selected path",
        )

    storage_path = _resolve_workflow_storage_path(request.workflow_name, workflow_store)
    assert request.node_id is not None
    assert request.row is not None
    assert request.col is not None
    df = _get_node_dataframe(request.node_id, result_store, storage_path)
    value = _get_dataframe_cell(df, request.row, request.col)
    try:
        image_path = _coerce_image_path(value, storage_path, _dataframe_record_dir(df))
    except HTTPException as exc:
        if exc.status_code == 404:
            raise FileNotFoundError(str(exc.detail)) from exc
        raise
    return [str(image_path)]


@router.post("/open")
async def open_in_napari(
    request: NapariOpenRequest,
    launcher: NapariLauncher = Depends(get_napari_launcher),
    result_store: ResultStoreService = Depends(get_result_store),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
) -> dict[str, str]:
    try:
        paths = _resolve_open_paths(request, result_store, workflow_store)
        await launcher.open(paths, request.clear_layers)
    except HTTPException as exc:
        _logger.warning(
            "Napari open request rejected with HTTP %s: %s",
            exc.status_code,
            exc.detail,
        )
        raise
    except FileNotFoundError as exc:
        _logger.warning(
            "Napari open request rejected because paths were not found: %s",
            exc,
        )
        raise HTTPException(
            status_code=400,
            detail={"error": "path_not_found", "detail": str(exc)},
        ) from exc
    except NapariLaunchError as exc:
        _logger.error(
            "Napari open request failed while launching or contacting Napari: %s",
            exc,
            exc_info=exc,
        )
        raise HTTPException(
            status_code=503,
            detail={"error": "napari_launch_failed", "detail": str(exc)},
        ) from exc
    return {"status": "ok"}


@router.get("/status", response_model=NapariStatus)
def napari_status(
    launcher: NapariLauncher = Depends(get_napari_launcher),
) -> NapariStatus:
    # Lock-free: safe to call concurrently with a long-running launch.
    return launcher.status()


@router.post("/shutdown")
async def shutdown_napari(
    launcher: NapariLauncher = Depends(get_napari_launcher),
) -> dict[str, str]:
    await launcher.shutdown()
    return {"status": "ok"}
