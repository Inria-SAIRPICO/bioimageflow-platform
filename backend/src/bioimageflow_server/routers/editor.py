"""Editor API router."""

from __future__ import annotations

from functools import partial
from pathlib import Path

from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException

from bioimageflow_server.models.editor import (
    EditorOpenRequest,
    EditorOpenResponse,
    EditorOpenToolRequest,
    EditorStatus,
)
from bioimageflow_server.routers.tools import (
    get_tool_registry,
    get_workflow_root,
    get_workflow_store,
    resolve_tool_project_open_paths,
)
from bioimageflow_server.services.editor import (
    EditorLaunchError,
    EditorPathError,
    EditorPathNotFoundError,
    EditorService,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService

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
        return await to_thread.run_sync(service.open_path, body.path, body.focus_path)
    except EditorPathNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Path not found: {exc}") from exc
    except EditorPathError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EditorLaunchError as exc:
        raise HTTPException(status_code=503, detail=f"Could not launch editor: {exc}") from exc


@router.post("/open-tool", response_model=EditorOpenResponse)
async def open_tool_script(
    body: EditorOpenToolRequest,
    service: EditorService = Depends(get_editor_service),
    registry: ToolRegistryService = Depends(get_tool_registry),
    workflow_root: Path | None = Depends(get_workflow_root),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
) -> EditorOpenResponse:
    try:
        project_path, source_path = resolve_tool_project_open_paths(
            tool_name=body.tool_name,
            workflow_name=body.workflow_id or body.workflow_name,
            workflow_root=workflow_root,
            registry=registry,
            workflow_store=workflow_store,
        )
        return await to_thread.run_sync(
            service.open_path,
            str(project_path),
            str(source_path),
        )
    except EditorPathNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Path not found: {exc}") from exc
    except EditorPathError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EditorLaunchError as exc:
        raise HTTPException(status_code=503, detail=f"Could not launch editor: {exc}") from exc
