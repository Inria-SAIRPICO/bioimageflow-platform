"""Workflow CRUD router."""

from __future__ import annotations

import logging
from contextlib import nullcontext
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse, Response

from bioimageflow_server.models.workflow import (
    WorkflowCreate,
    WorkflowDeleteResponse,
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
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedWorkflowSnapshotService,
)
from bioimageflow_server.services.workflow_store import (
    WorkflowArchiveError,
    WorkflowGenerationChangedError,
    WorkflowIdentityGenerationConflictError,
    WorkflowStoreService,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])
logger = logging.getLogger(__name__)


def get_workflow_store() -> WorkflowStoreService:  # pragma: no cover
    raise RuntimeError("workflow_store dependency not configured")


def get_execution_manager() -> Any | None:
    return None


def get_connection_manager() -> Any | None:
    return None


def get_nested_workflow_snapshot_service() -> NestedWorkflowSnapshotService | None:
    return None


def _ensure_unlocked(execution_manager: Any | None) -> None:
    if execution_manager is None:
        return
    if getattr(execution_manager, "is_running", False):
        raise HTTPException(
            status_code=423,
            detail="Workflow editing is locked while execution is in progress",
        )


def _publish_workflow_tree_changed(
    connection_manager: Any | None,
    *,
    action: str,
    workflow_id: str | None = None,
    identity_generation: int | None = None,
) -> None:
    if connection_manager is None:
        return
    connection_manager.publish_workflow_tree_changed(
        action=action,
        workflow_id=workflow_id,
        identity_generation=identity_generation,
    )


def _publish_active_workflow_changed(
    connection_manager: Any | None,
    *,
    workflow_id: str,
    updated_by: str = "agent",
) -> None:
    if connection_manager is None:
        return
    connection_manager.publish_active_workflow_changed(
        workflow_id=workflow_id,
        updated_by=updated_by,
    )


def _delete_workflow_with_snapshots(
    store: WorkflowStoreService,
    nested_snapshot_service: NestedWorkflowSnapshotService | None,
    workflow_id: str,
    expected_identity_generation: int | None = None,
) -> int:
    """Delete one identity using the shared snapshot-before-workflow lock order."""

    snapshot_mutation = (
        nested_snapshot_service.snapshot_mutation()
        if nested_snapshot_service is not None
        else nullcontext()
    )
    with snapshot_mutation:
        identity_generation = store.delete_workflow(
            workflow_id,
            expected_identity_generation=expected_identity_generation,
        )
        if nested_snapshot_service is not None:
            try:
                nested_snapshot_service.delete_for_root_workflow(workflow_id)
            except Exception:
                logger.exception(
                    "Workflow '%s' was deleted but retained nested snapshot cleanup failed",
                    workflow_id,
                )
    return identity_generation


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
    connection_manager: Any | None = Depends(get_connection_manager),
) -> WorkflowFolderInfo | JSONResponse:
    try:
        folder = store.create_folder(body.path)
        _publish_workflow_tree_changed(
            connection_manager,
            action="folder_created",
        )
        return folder
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
    connection_manager: Any | None = Depends(get_connection_manager),
) -> WorkflowFolderInfo | JSONResponse:
    _ensure_unlocked(execution_manager)
    try:
        folder = store.rename_folder(path, body.new_path)
        _publish_workflow_tree_changed(
            connection_manager,
            action="folder_updated",
        )
        return folder
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
    connection_manager: Any | None = Depends(get_connection_manager),
    nested_snapshot_service: NestedWorkflowSnapshotService | None = Depends(
        get_nested_workflow_snapshot_service
    ),
) -> Any:
    _ensure_unlocked(execution_manager)
    try:
        snapshot_mutation = (
            nested_snapshot_service.snapshot_mutation()
            if nested_snapshot_service is not None
            else nullcontext()
        )
        with snapshot_mutation:
            with store.workflow_structure_mutation():
                removed_workflow_ids = (
                    store.workflow_names_in_folder(path) if body.policy == "delete_children" else []
                )
                with store.workflow_mutations(removed_workflow_ids):
                    store.delete_folder(path, body)
                    if nested_snapshot_service is not None:
                        try:
                            nested_snapshot_service.delete_for_root_workflows(removed_workflow_ids)
                        except Exception:
                            logger.exception(
                                "Folder '%s' was deleted but retained nested snapshot cleanup failed",
                                path,
                            )
        _publish_workflow_tree_changed(
            connection_manager,
            action="folder_deleted",
        )
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
    connection_manager: Any | None = Depends(get_connection_manager),
) -> WorkflowInfo | JSONResponse:
    try:
        info = store.create_workflow(body)
        _publish_workflow_tree_changed(
            connection_manager,
            action="workflow_created",
            workflow_id=info.id,
            identity_generation=info.identity_generation,
        )
        return info
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
    connection_manager: Any | None = Depends(get_connection_manager),
) -> WorkflowImportResponse | JSONResponse:
    _ensure_unlocked(execution_manager)
    raw_upload = await file.read()
    try:
        if not file.filename or not file.filename.endswith(".zip"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Workflow imports must be .bioimageflow.zip archives",
            )
        response = store.import_workflow_archive(
            raw_upload,
            filename=file.filename,
            name_override=name_override,
        )
        _publish_workflow_tree_changed(
            connection_manager,
            action="workflow_imported",
            workflow_id=response.info.id,
            identity_generation=response.info.identity_generation,
        )
        return response
    except WorkflowArchiveError as exc:
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


@router.delete("/{name:path}", response_model=WorkflowDeleteResponse)
async def delete_workflow(
    name: str,
    expected_identity_generation: int | None = Query(default=None, ge=0),
    store: WorkflowStoreService = Depends(get_workflow_store),
    execution_manager: Any | None = Depends(get_execution_manager),
    connection_manager: Any | None = Depends(get_connection_manager),
    nested_snapshot_service: NestedWorkflowSnapshotService | None = Depends(
        get_nested_workflow_snapshot_service
    ),
) -> WorkflowDeleteResponse:
    _ensure_unlocked(execution_manager)
    try:
        identity_generation = _delete_workflow_with_snapshots(
            store,
            nested_snapshot_service,
            name,
            expected_identity_generation,
        )
        _publish_workflow_tree_changed(
            connection_manager,
            action="workflow_deleted",
            workflow_id=name,
            identity_generation=identity_generation,
        )
    except WorkflowIdentityGenerationConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "workflow_identity_generation_conflict",
                "detail": str(exc),
            },
        ) from exc
    except WorkflowGenerationChangedError as exc:
        if expected_identity_generation is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "workflow_identity_generation_conflict",
                    "detail": (
                        f"Workflow '{name}' generation is "
                        f"{store.workflow_generation(name)}, not expected "
                        f"{expected_identity_generation}"
                    ),
                },
            ) from exc
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    return WorkflowDeleteResponse(
        identity_generation=identity_generation,
    )


@router.patch("/{name:path}", response_model=WorkflowInfo)
async def patch_workflow(
    name: str,
    body: WorkflowUpdate,
    store: WorkflowStoreService = Depends(get_workflow_store),
    execution_manager: Any | None = Depends(get_execution_manager),
    connection_manager: Any | None = Depends(get_connection_manager),
) -> WorkflowInfo | JSONResponse:
    _ensure_unlocked(execution_manager)
    try:
        info = store.patch_workflow(name, body)
        _publish_workflow_tree_changed(
            connection_manager,
            action="workflow_updated",
            workflow_id=info.id,
            identity_generation=info.identity_generation,
        )
        return info
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


@router.post("/{name:path}/activate", response_model=WorkflowFile)
async def activate_workflow(
    name: str,
    store: WorkflowStoreService = Depends(get_workflow_store),
    connection_manager: Any | None = Depends(get_connection_manager),
) -> WorkflowFile:
    try:
        workflow = store.get_workflow(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    _publish_active_workflow_changed(
        connection_manager,
        workflow_id=workflow.info.id,
    )
    return workflow
