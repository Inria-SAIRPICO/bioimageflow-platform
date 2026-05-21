"""Workflow CRUD router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from bioimageflow_server.models.workflow import (
    WorkflowCreate,
    WorkflowFile,
    WorkflowFolderDelete,
    WorkflowFolderCreate,
    WorkflowFolderInfo,
    WorkflowFolderUpdate,
    WorkflowInfo,
    WorkflowImportResponse,
    WorkflowSaveBody,
    WorkflowUpdate,
)
from bioimageflow_server.services.workflow_store import (
    WorkflowArchiveError,
    WorkflowImportParseError,
    WorkflowImportValidationError,
    WorkflowStoreService,
)

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


@router.get("/tree", response_model=WorkflowFolderInfo)
async def workflow_tree(
    store: WorkflowStoreService = Depends(get_workflow_store),
) -> WorkflowFolderInfo:
    return store.workflow_tree()


@router.post(
    "/folders",
    response_model=WorkflowFolderInfo,
    status_code=status.HTTP_201_CREATED,
)
async def create_folder(
    body: WorkflowFolderCreate,
    store: WorkflowStoreService = Depends(get_workflow_store),
) -> WorkflowFolderInfo | JSONResponse:
    try:
        return store.create_folder(body.path)
    except FileExistsError:
        return JSONResponse(
            status_code=409,
            content={"error": "conflict", "detail": f"Folder '{body.path}' already exists"},
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/folders/{path:path}", response_model=WorkflowFolderInfo)
async def rename_folder(
    path: str,
    body: WorkflowFolderUpdate,
    store: WorkflowStoreService = Depends(get_workflow_store),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> WorkflowFolderInfo | JSONResponse:
    _ensure_unlocked(execution_manager)
    try:
        return store.rename_folder(path, body.new_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Folder not found") from exc
    except FileExistsError:
        return JSONResponse(
            status_code=409,
            content={"error": "conflict", "detail": f"Folder '{body.new_path}' already exists"},
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/folders/{path:path}")
async def delete_folder(
    path: str,
    body: WorkflowFolderDelete = Body(default_factory=WorkflowFolderDelete),
    store: WorkflowStoreService = Depends(get_workflow_store),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> Any:
    _ensure_unlocked(execution_manager)
    try:
        store.delete_folder(path, body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Folder not found") from exc
    except FileExistsError:
        return JSONResponse(
            status_code=409,
            content={
                "error": "folder_delete_conflict",
                "detail": "Folder is not empty or contains colliding child names",
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"deleted": True}


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


@router.get("/{name:path}", response_model=WorkflowFile)
async def get_workflow(
    name: str,
    store: WorkflowStoreService = Depends(get_workflow_store),
) -> WorkflowFile:
    try:
        return store.get_workflow(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc


@router.post("/{name:path}/export")
async def export_workflow(
    name: str,
    store: WorkflowStoreService = Depends(get_workflow_store),
) -> Response:
    try:
        filename, payload = store.export_workflow_archive(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    except WorkflowArchiveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post(
    "/import",
    response_model=WorkflowImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_workflow(
    file: UploadFile = File(...),
    name_override: str | None = Form(default=None),
    store: WorkflowStoreService = Depends(get_workflow_store),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> WorkflowImportResponse | JSONResponse:
    _ensure_unlocked(execution_manager)
    raw_upload = await file.read()
    try:
        if file.filename and file.filename.endswith(".zip"):
            return store.import_workflow_archive(
                raw_upload,
                filename=file.filename,
                name_override=name_override,
            )
        document = store.parse_import_document(raw_upload)
        return store.import_workflow(document, name_override=name_override)
    except WorkflowImportParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (WorkflowArchiveError, WorkflowImportValidationError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileExistsError as exc:
        workflow_name = str(exc.args[0]) if exc.args else name_override or "workflow"
        return JSONResponse(
            status_code=409,
            content={
                "error": "conflict",
                "detail": f"Workflow '{workflow_name}' already exists",
                "suggested_name": store.suggest_name(workflow_name),
            },
        )


@router.put("/{name:path}", response_model=WorkflowInfo)
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


@router.delete("/{name:path}")
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


@router.patch("/{name:path}", response_model=WorkflowInfo)
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


@router.post("/{name:path}/rebind-versions", response_model=WorkflowFile)
async def rebind_workflow_versions(
    name: str,
    store: WorkflowStoreService = Depends(get_workflow_store),
) -> WorkflowFile:
    try:
        return store.rebind_versions(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
