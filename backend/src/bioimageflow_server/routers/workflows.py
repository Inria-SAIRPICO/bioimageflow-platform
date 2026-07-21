"""Workflow CRUD router."""

from __future__ import annotations

import logging
from contextlib import nullcontext
from typing import Any, Never
from uuid import UUID

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
    WorkflowFormatStatus,
    WorkflowInfo,
    WorkflowImportResponse,
    WorkflowSaveBody,
    WorkflowUpdate,
)
from bioimageflow_server.models.workflow_sources import (
    PythonSourcePreviewRequest,
    WorkflowSourceApplyRequest,
    WorkflowSourceApplyResponse,
    WorkflowSourcePreview,
    WorkflowSourceUpdatePreviewRequest,
)
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedWorkflowSnapshotService,
    RootWorkflowSnapshotMove,
)
from bioimageflow_server.services.workflow_store import (
    WorkflowArchiveError,
    WorkflowGenerationChangedError,
    WorkflowIdentityGenerationConflictError,
    WorkflowIdentityMovePlan,
    WorkflowMoveRecoveryError,
    WorkflowStoreService,
)
from bioimageflow_server.services.workflow_sources import (
    WorkflowSourceConflict,
    WorkflowSourceService,
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


def get_workflow_source_service() -> WorkflowSourceService:  # pragma: no cover
    raise RuntimeError("workflow_source_service dependency not configured")


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
    try:
        connection_manager.publish_workflow_tree_changed(
            action=action,
            workflow_id=workflow_id,
            identity_generation=identity_generation,
        )
    except Exception:
        logger.exception(
            "Workflow tree change '%s' committed but could not be published",
            action,
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


def _move_root_workflow_snapshots(
    store: WorkflowStoreService,
    nested_snapshot_service: NestedWorkflowSnapshotService | None,
    move_plans: list[WorkflowIdentityMovePlan],
) -> None:
    """Rewrite retained root ownership after the corresponding filesystem move."""

    if nested_snapshot_service is None or not move_plans:
        return
    nested_snapshot_service.move_root_workflows(
        [
            RootWorkflowSnapshotMove(
                old_workflow_id=plan.old_workflow_id,
                old_identity_generation=plan.old_identity_generation,
                new_workflow_id=plan.new_workflow_id,
                new_identity_generation=store.workflow_generation(plan.new_workflow_id),
            )
            for plan in move_plans
        ]
    )


def _preflight_root_workflow_snapshot_moves(
    nested_snapshot_service: NestedWorkflowSnapshotService | None,
    move_plans: list[WorkflowIdentityMovePlan],
) -> None:
    """Prove retained ownership is readable before the first filesystem rename."""

    if nested_snapshot_service is not None and move_plans:
        nested_snapshot_service.preflight_root_workflow_moves()


def _finish_workflow_move(
    store: WorkflowStoreService,
    nested_snapshot_service: NestedWorkflowSnapshotService | None,
    move_plans: list[WorkflowIdentityMovePlan],
    operation_id: UUID | None,
) -> None:
    """Finish the store-to-snapshot move boundary before clearing its journal."""

    if operation_id is not None:
        store.mark_workflow_move_phase(operation_id, "artifacts_rewritten")
    _move_root_workflow_snapshots(store, nested_snapshot_service, move_plans)
    if operation_id is not None:
        store.mark_workflow_move_phase(operation_id, "snapshots_rewritten")
        store.complete_workflow_move(operation_id)


def _discard_unstarted_workflow_move(
    store: WorkflowStoreService,
    operation_id: UUID | None,
) -> bool:
    """Drop prepared intent only when no durable identity mutation occurred."""

    if operation_id is None:
        return True
    try:
        store.discard_workflow_move_if_unstarted(operation_id)
        return True
    except Exception:
        logger.exception(
            "Could not determine whether prepared workflow move %s was still unstarted",
            operation_id,
        )
        return False


def _raise_move_recovery_required(exc: WorkflowMoveRecoveryError) -> Never:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": "workflow_move_recovery_required",
            "detail": str(exc),
        },
    ) from exc


@router.get("", response_model=list[WorkflowInfo])
async def list_workflows(
    store: WorkflowStoreService = Depends(get_workflow_store),
) -> list[WorkflowInfo]:
    return store.list_workflows()


@router.get("/format-status", response_model=WorkflowFormatStatus)
async def workflow_format_status(
    store: WorkflowStoreService = Depends(get_workflow_store),
) -> WorkflowFormatStatus:
    return store.workflow_format_status()


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
    nested_snapshot_service: NestedWorkflowSnapshotService | None = Depends(
        get_nested_workflow_snapshot_service
    ),
) -> WorkflowFolderInfo | JSONResponse:
    _ensure_unlocked(execution_manager)
    try:
        snapshot_mutation = (
            nested_snapshot_service.snapshot_mutation()
            if nested_snapshot_service is not None
            else nullcontext()
        )
        with snapshot_mutation, store.workflow_structure_mutation():
            move_plans = store.plan_folder_rename_moves(path, body.new_path)
            _preflight_root_workflow_snapshot_moves(
                nested_snapshot_service,
                move_plans,
            )
            operation_id = store.prepare_folder_rename_move(path, body.new_path)
            try:
                folder = store.rename_folder(
                    path,
                    body.new_path,
                    move_operation_id=operation_id,
                )
                _finish_workflow_move(
                    store,
                    nested_snapshot_service,
                    move_plans,
                    operation_id,
                )
            except Exception as exc:
                if not _discard_unstarted_workflow_move(store, operation_id):
                    raise WorkflowMoveRecoveryError(
                        f"Workflow move {operation_id} must recover before further moves"
                    ) from exc
                raise
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
    except WorkflowMoveRecoveryError as exc:
        _raise_move_recovery_required(exc)
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
                move_plans = store.plan_folder_delete_moves(path, body)
                _preflight_root_workflow_snapshot_moves(
                    nested_snapshot_service,
                    move_plans,
                )
                operation_id = (
                    store.prepare_folder_promotion_move(path)
                    if body.policy == "move_children_up"
                    else None
                )
                with store.workflow_mutations(removed_workflow_ids):
                    try:
                        store.delete_folder(
                            path,
                            body,
                            move_operation_id=operation_id,
                        )
                        if nested_snapshot_service is not None:
                            try:
                                nested_snapshot_service.delete_for_root_workflows(
                                    removed_workflow_ids
                                )
                            except Exception:
                                logger.exception(
                                    "Folder '%s' was deleted but retained nested snapshot "
                                    "cleanup failed",
                                    path,
                                )
                        _finish_workflow_move(
                            store,
                            nested_snapshot_service,
                            move_plans,
                            operation_id,
                        )
                    except Exception as exc:
                        if not _discard_unstarted_workflow_move(store, operation_id):
                            raise WorkflowMoveRecoveryError(
                                f"Workflow move {operation_id} must recover before further moves"
                            ) from exc
                        raise
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
    except WorkflowMoveRecoveryError as exc:
        _raise_move_recovery_required(exc)
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
    "/{name:path}/source-update/preview",
    response_model=WorkflowSourcePreview,
)
async def preview_workflow_source_update(
    name: str,
    body: WorkflowSourceUpdatePreviewRequest,
    service: WorkflowSourceService = Depends(get_workflow_source_service),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> WorkflowSourcePreview:
    _ensure_unlocked(execution_manager)
    try:
        return service.preview_source_update(
            name,
            body.workflow_path,
            expected_artifact_hash=body.expected_artifact_hash,
        )
    except WorkflowSourceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/{name:path}/python-source/preview",
    response_model=WorkflowSourcePreview,
)
async def preview_python_source(
    name: str,
    body: PythonSourcePreviewRequest,
    service: WorkflowSourceService = Depends(get_workflow_source_service),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> WorkflowSourcePreview:
    _ensure_unlocked(execution_manager)
    try:
        return service.preview_python_rebuild(
            name,
            expected_artifact_hash=body.expected_artifact_hash,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except WorkflowSourceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (FileNotFoundError, ValueError, ImportError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/{name:path}/source-operations/apply",
    response_model=WorkflowSourceApplyResponse,
)
async def apply_workflow_source_operation(
    name: str,
    body: WorkflowSourceApplyRequest,
    service: WorkflowSourceService = Depends(get_workflow_source_service),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> WorkflowSourceApplyResponse:
    del name  # The immutable preview token carries its exact destination identity.
    _ensure_unlocked(execution_manager)
    try:
        return service.apply(body)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except WorkflowSourceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
    nested_snapshot_service: NestedWorkflowSnapshotService | None = Depends(
        get_nested_workflow_snapshot_service
    ),
) -> WorkflowInfo | JSONResponse:
    _ensure_unlocked(execution_manager)
    try:
        snapshot_mutation = (
            nested_snapshot_service.snapshot_mutation()
            if nested_snapshot_service is not None
            else nullcontext()
        )
        with snapshot_mutation, store.workflow_structure_mutation():
            move_plans = store.plan_workflow_update_moves(name, body)
            _preflight_root_workflow_snapshot_moves(
                nested_snapshot_service,
                move_plans,
            )
            operation_id = store.prepare_workflow_patch_move(name, body)
            try:
                info = store.patch_workflow(
                    name,
                    body,
                    move_operation_id=operation_id,
                )
                _finish_workflow_move(
                    store,
                    nested_snapshot_service,
                    move_plans,
                    operation_id,
                )
            except Exception as exc:
                if not _discard_unstarted_workflow_move(store, operation_id):
                    raise WorkflowMoveRecoveryError(
                        f"Workflow move {operation_id} must recover before further moves"
                    ) from exc
                raise
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
    except WorkflowMoveRecoveryError as exc:
        _raise_move_recovery_required(exc)
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
