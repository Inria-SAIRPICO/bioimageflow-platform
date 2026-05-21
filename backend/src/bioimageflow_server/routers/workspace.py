"""Workspace router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from bioimageflow_server.models.workspace import WorkspaceInfo, WorkspaceUpdate
from bioimageflow_server.services.workspace import WorkspacePermissionError, WorkspaceService


router = APIRouter(prefix="/workspace", tags=["workspace"])


def get_workspace_service() -> WorkspaceService:  # pragma: no cover
    raise RuntimeError("workspace_service dependency not configured")


@router.get("", response_model=WorkspaceInfo)
async def get_workspace(
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceInfo:
    return service.info()


@router.patch("", response_model=WorkspaceInfo)
async def patch_workspace(
    body: WorkspaceUpdate,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceInfo:
    try:
        return service.update_workspace_path(body.workspace_path)
    except WorkspacePermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
