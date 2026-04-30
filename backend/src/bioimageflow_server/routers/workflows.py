"""Workflow CRUD router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from bioimageflow_server.models.workflow import (
    WorkflowCreate,
    WorkflowFile,
    WorkflowInfo,
    WorkflowSaveBody,
    WorkflowUpdate,
)
from bioimageflow_server.services.workflow_store import WorkflowStoreService

router = APIRouter(prefix="/workflows", tags=["workflows"])


def get_workflow_store() -> WorkflowStoreService:  # pragma: no cover
    raise RuntimeError("workflow_store dependency not configured")


def get_execution_manager() -> Any | None:
    return None


def _ensure_unlocked(execution_manager: Any | None) -> None:
    if execution_manager is None:
        return
    if getattr(execution_manager, "is_running", False):
        raise HTTPException(
            status_code=423,
            detail="Workflow editing is locked while execution is in progress",
        )


@router.get("", response_model=list[WorkflowInfo])
async def list_workflows(
    store: WorkflowStoreService = Depends(get_workflow_store),
) -> list[WorkflowInfo]:
    return store.list_workflows()


@router.post("", response_model=WorkflowInfo, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    body: WorkflowCreate,
    store: WorkflowStoreService = Depends(get_workflow_store),
) -> WorkflowInfo | JSONResponse:
    try:
        return store.create_workflow(body)
    except FileExistsError:
        return JSONResponse(
            status_code=409,
            content={
                "error": "conflict",
                "detail": f"Workflow '{body.name}' already exists",
                "suggested_name": store.suggest_name(body.name),
            },
        )


@router.get("/{name}", response_model=WorkflowFile)
async def get_workflow(
    name: str,
    store: WorkflowStoreService = Depends(get_workflow_store),
) -> WorkflowFile:
    try:
        return store.get_workflow(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc


@router.put("/{name}", response_model=WorkflowInfo)
async def save_workflow(
    name: str,
    body: WorkflowSaveBody,
    store: WorkflowStoreService = Depends(get_workflow_store),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> WorkflowInfo:
    _ensure_unlocked(execution_manager)
    try:
        return store.save_workflow(name, body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc


@router.delete("/{name}")
async def delete_workflow(
    name: str,
    store: WorkflowStoreService = Depends(get_workflow_store),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> dict[str, bool]:
    _ensure_unlocked(execution_manager)
    try:
        store.delete_workflow(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    return {"deleted": True}


@router.patch("/{name}", response_model=WorkflowInfo)
async def patch_workflow(
    name: str,
    body: WorkflowUpdate,
    store: WorkflowStoreService = Depends(get_workflow_store),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> WorkflowInfo | JSONResponse:
    _ensure_unlocked(execution_manager)
    try:
        return store.patch_workflow(name, body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    except FileExistsError as exc:
        new_name = str(exc.args[0]) if exc.args else body.new_name or name
        return JSONResponse(
            status_code=409,
            content={
                "error": "conflict",
                "detail": f"Workflow '{new_name}' already exists",
                "suggested_name": store.suggest_name(new_name),
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{name}/rebind-versions", response_model=WorkflowFile)
async def rebind_workflow_versions(
    name: str,
    store: WorkflowStoreService = Depends(get_workflow_store),
) -> WorkflowFile:
    try:
        return store.rebind_versions(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
