"""Workflow CRUD router."""

from __future__ import annotations

import asyncio
import logging
import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, nullcontext
from pathlib import Path
from typing import Any, Never
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse, Response
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from bioimageflow_server.models.workflow import (
    WorkflowCreate,
    WorkflowDeleteResponse,
    WorkflowFile,
    WorkflowFolderDelete,
    WorkflowFolderCreate,
    WorkflowFolderInfo,
    WorkflowFolderUpdate,
    WorkflowFormatStatus,
    WorkflowFormatMigrationApply,
    WorkflowInfo,
    WorkflowImportResponse,
    ViewingRequirementsManifest,
    WorkflowSaveBody,
    WorkflowUpdate,
)
from bioimageflow_server.models.workflow_export import (
    WorkflowResultsFolderExportRequest,
    WorkflowResultsFolderExportResponse,
)
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.routers.filesystem import reveal_in_file_browser
from bioimageflow_server.models.workflow_sources import (
    PythonSourcePreviewRequest,
    WorkflowEmbeddingRequest,
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
    WorkflowFormatPlanStaleError,
    WorkflowFormatUpdateRequiredError,
    WorkflowStoreService,
    WorkflowResultsBundleImportError,
)
from bioimageflow_server.services.workflow_exports import (
    PreparedDownload,
    WorkflowExportError,
    WorkflowExportService,
)
from bioimageflow_server.services.workflow_sources import (
    WorkflowSourceConflict,
    WorkflowSourceService,
)
from bioimageflow_server.services.workflow_artifacts import WorkflowSourceMissingError
from bioimageflow_server.services.viewer_preferences import (
    ViewerPreferenceStore,
    ensure_workspace_identity,
)
from bioimageflow_server.services.execution import ExecutionConflictError

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


def get_viewer_preference_store() -> ViewerPreferenceStore | None:
    return None


def get_settings() -> Settings | None:
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


@asynccontextmanager
async def _idle_mutation_lease(
    execution_manager: Any | None,
) -> AsyncIterator[None]:
    """Serialize an ordinary workflow mutation with execution admission."""

    if execution_manager is None:
        yield
        return
    lease = getattr(execution_manager, "exclusive_idle_mutation", None)
    if lease is None:
        _ensure_unlocked(execution_manager)
        yield
        return
    async with lease():
        yield


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
    viewer_preferences: ViewerPreferenceStore | None = None,
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
        if viewer_preferences is not None:
            viewer_preferences.clear_workflow_generation(
                workspace_id=ensure_workspace_identity(store.workspace_dir),
                workflow_id=workflow_id,
                identity_generation=identity_generation,
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
    viewer_preferences: ViewerPreferenceStore | None = None,
) -> None:
    """Finish the store-to-snapshot move boundary before clearing its journal."""

    if operation_id is not None:
        store.mark_workflow_move_phase(operation_id, "artifacts_rewritten")
    _move_root_workflow_snapshots(store, nested_snapshot_service, move_plans)
    if operation_id is not None:
        store.mark_workflow_move_phase(operation_id, "snapshots_rewritten")
        journal = store.pending_workflow_move()
        if journal is None or journal.operation_id != operation_id:
            raise WorkflowMoveRecoveryError(
                f"Workflow move journal {operation_id} disappeared before preferences"
            )
        if viewer_preferences is not None:
            workspace_id = ensure_workspace_identity(store.workspace_dir)
            for move in journal.moves:
                viewer_preferences.move_workflow_generation(
                    workspace_id=workspace_id,
                    source_workflow_id=move.source_workflow_id,
                    source_generation=move.source_generation_before,
                    destination_workflow_id=move.destination_workflow_id,
                    destination_generation=move.destination_generation_after,
                )
        store.mark_workflow_move_phase(operation_id, "preferences_rewritten")
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


def _raise_export_error(exc: WorkflowExportError) -> Never:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"error": exc.code, "detail": exc.detail},
    ) from exc


def _export_not_found(exc: FileNotFoundError) -> Never:
    raise HTTPException(
        status_code=404,
        detail={"error": "workflow_not_found", "detail": "Workflow not found"},
    ) from exc


def _download_response(prepared: PreparedDownload) -> FileResponse:
    return FileResponse(
        prepared.path,
        media_type="application/zip",
        filename=prepared.filename,
        background=BackgroundTask(
            shutil.rmtree,
            prepared.cleanup_root,
            ignore_errors=True,
        ),
    )


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


@router.post("/format-migrations/apply", response_model=WorkflowFormatStatus)
async def apply_workflow_format_migrations(
    body: WorkflowFormatMigrationApply,
    store: WorkflowStoreService = Depends(get_workflow_store),
    connection_manager: Any | None = Depends(get_connection_manager),
) -> WorkflowFormatStatus:
    try:
        result = store.apply_workflow_format_migrations(body.pending_plan_id)
    except WorkflowFormatPlanStaleError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "workflow_format_plan_stale", "detail": str(exc)},
        ) from exc
    _publish_workflow_tree_changed(connection_manager, action="format_migrated")
    return result


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
    viewer_preferences: ViewerPreferenceStore | None = Depends(get_viewer_preference_store),
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
                    viewer_preferences,
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
    viewer_preferences: ViewerPreferenceStore | None = Depends(get_viewer_preference_store),
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
                removed_generations = {
                    workflow_id: store.workflow_generation(workflow_id)
                    for workflow_id in removed_workflow_ids
                }
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
                        if viewer_preferences is not None:
                            workspace_id = ensure_workspace_identity(store.workspace_dir)
                            for workflow_id, generation in removed_generations.items():
                                viewer_preferences.clear_workflow_generation(
                                    workspace_id=workspace_id,
                                    workflow_id=workflow_id,
                                    identity_generation=generation,
                                )
                        _finish_workflow_move(
                            store,
                            nested_snapshot_service,
                            move_plans,
                            operation_id,
                            viewer_preferences,
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


@router.post("/{name:path}/outputs/latest/reveal")
async def reveal_latest_workflow_outputs(
    name: str,
    store: WorkflowStoreService = Depends(get_workflow_store),
    settings: Settings | None = Depends(get_settings),
) -> dict[str, str]:
    """Open the authoritative per-node latest output projection."""
    if settings is not None and settings.deployment_mode != "desktop":
        raise HTTPException(
            status_code=403,
            detail="Opening a server filesystem folder is available only in desktop mode",
        )
    try:
        output_path = Path(store.get_storage_path(name)) / "outputs" / "latest"
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    try:
        await asyncio.to_thread(output_path.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(reveal_in_file_browser, str(output_path))
    except OSError as exc:
        logger.error("Could not reveal latest outputs for %s", name, exc_info=exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "ok", "path": str(output_path)}


@router.get(
    "/{name:path}/viewing-readiness",
    response_model=ViewingRequirementsManifest,
)
async def workflow_viewing_readiness(
    name: str,
    store: WorkflowStoreService = Depends(get_workflow_store),
) -> ViewingRequirementsManifest:
    try:
        return store.viewing_requirements(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc


@router.get("/{name:path}", response_model=WorkflowFile)
async def get_workflow(
    name: str,
    store: WorkflowStoreService = Depends(get_workflow_store),
) -> WorkflowFile:
    try:
        return store.get_workflow(name)
    except WorkflowSourceMissingError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "workflow_source_missing", "detail": str(exc)},
        ) from exc
    except WorkflowFormatUpdateRequiredError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "workflow_format_update_required",
                "detail": str(exc),
                "workflow_id": exc.workflow_id,
            },
        ) from exc
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


@router.post("/{name:path}/exports/latest-results")
async def export_latest_workflow_results(
    name: str,
    store: WorkflowStoreService = Depends(get_workflow_store),
) -> FileResponse:
    try:
        prepared = await asyncio.to_thread(
            WorkflowExportService(store).prepare_latest_results,
            name,
        )
    except FileNotFoundError as exc:
        _export_not_found(exc)
    except WorkflowExportError as exc:
        _raise_export_error(exc)
    except OSError as exc:
        logger.error("Could not export latest results for %s", name, exc_info=exc)
        raise HTTPException(
            status_code=500,
            detail={"error": "results_export_failed", "detail": str(exc)},
        ) from exc
    return _download_response(prepared)


@router.post(
    "/{name:path}/exports/latest-results-folder",
    response_model=WorkflowResultsFolderExportResponse,
)
async def export_latest_workflow_results_folder(
    name: str,
    body: WorkflowResultsFolderExportRequest,
    store: WorkflowStoreService = Depends(get_workflow_store),
    settings: Settings | None = Depends(get_settings),
) -> WorkflowResultsFolderExportResponse:
    if settings is not None and settings.deployment_mode != "desktop":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "desktop_export_required",
                "detail": "Folder export is available only in desktop mode",
            },
        )
    try:
        exported = await asyncio.to_thread(
            WorkflowExportService(store).export_latest_results_folder,
            name,
            destination_parent=body.destination_parent,
            replace=body.replace,
        )
    except FileNotFoundError as exc:
        _export_not_found(exc)
    except WorkflowExportError as exc:
        _raise_export_error(exc)
    except OSError as exc:
        logger.error("Could not export latest results folder for %s", name, exc_info=exc)
        raise HTTPException(
            status_code=500,
            detail={"error": "results_export_failed", "detail": str(exc)},
        ) from exc
    return WorkflowResultsFolderExportResponse(
        destination=str(exported.destination),
        exported_items=exported.exported_items,
    )


@router.post("/{name:path}/exports/workflow-run-bundle")
async def export_workflow_run_bundle(
    name: str,
    store: WorkflowStoreService = Depends(get_workflow_store),
) -> FileResponse:
    try:
        prepared = await asyncio.to_thread(
            WorkflowExportService(store).prepare_workflow_run_bundle,
            name,
        )
    except FileNotFoundError as exc:
        _export_not_found(exc)
    except WorkflowExportError as exc:
        _raise_export_error(exc)
    except WorkflowArchiveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        logger.error("Could not export workflow results bundle for %s", name, exc_info=exc)
        raise HTTPException(
            status_code=500,
            detail={"error": "results_export_failed", "detail": str(exc)},
        ) from exc
    return _download_response(prepared)


@router.post(
    "/{name:path}/prepare-embedding",
    response_model=WorkflowFile,
)
async def prepare_workflow_embedding(
    name: str,
    body: WorkflowEmbeddingRequest,
    service: WorkflowSourceService = Depends(get_workflow_source_service),
) -> WorkflowFile:
    # Only fresh, unreferenced source files are added here. The subsequent
    # canvas insertion uses the ordinary revision- and execution-guarded draft API.
    try:
        return await asyncio.to_thread(
            service.prepare_embedding,
            name,
            body.source_workflow_id,
            identity_generation=body.identity_generation,
        )
    except WorkflowSourceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, SyntaxError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
    except WorkflowResultsBundleImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "error": "results_bundle_not_importable",
                "detail": str(exc),
            },
        ) from exc
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
    try:
        async with _idle_mutation_lease(execution_manager):
            return store.save_workflow(name, body)
    except ExecutionConflictError as exc:
        raise HTTPException(
            status_code=423,
            detail="Workflow editing is locked while execution is in progress",
        ) from exc
    except WorkflowFormatUpdateRequiredError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "workflow_format_update_required",
                "detail": str(exc),
                "workflow_id": exc.workflow_id,
            },
        ) from exc
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
    viewer_preferences: ViewerPreferenceStore | None = Depends(get_viewer_preference_store),
) -> WorkflowDeleteResponse:
    _ensure_unlocked(execution_manager)
    try:
        identity_generation = _delete_workflow_with_snapshots(
            store,
            nested_snapshot_service,
            name,
            expected_identity_generation,
            viewer_preferences,
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
    viewer_preferences: ViewerPreferenceStore | None = Depends(get_viewer_preference_store),
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
                    viewer_preferences,
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
    except WorkflowIdentityGenerationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
