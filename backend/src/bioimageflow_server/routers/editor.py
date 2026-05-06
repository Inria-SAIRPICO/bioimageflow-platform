"""Editor API router."""

from __future__ import annotations

from functools import partial

from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException

from bioimageflow_server.models.editor import (
    EditorOpenRequest,
    EditorOpenResponse,
    EditorStatus,
)
from bioimageflow_server.services.editor import (
    EditorLaunchError,
    EditorPathError,
    EditorPathNotFoundError,
    EditorService,
)

router = APIRouter(prefix="/editor", tags=["editor"])


def get_editor_service() -> EditorService:  # pragma: no cover
    raise RuntimeError("editor service dependency not configured")


@router.get("/status", response_model=EditorStatus)
async def get_editor_status(
    launch: bool = False,
    service: EditorService = Depends(get_editor_service),
) -> EditorStatus:
    return await to_thread.run_sync(partial(service.get_status, launch=launch))


@router.post("/open", response_model=EditorOpenResponse)
async def open_editor_path(
    body: EditorOpenRequest,
    service: EditorService = Depends(get_editor_service),
) -> EditorOpenResponse:
    try:
        return await to_thread.run_sync(service.open_path, body.path)
    except EditorPathNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Path not found: {exc}") from exc
    except EditorPathError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EditorLaunchError as exc:
        raise HTTPException(status_code=503, detail=f"Could not launch editor: {exc}") from exc
