"""Editor API router."""

from __future__ import annotations

import logging
from functools import partial
from pathlib import Path

from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException

from bioimageflow_server.models.errors import mark_exception_logged
from bioimageflow_server.models.editor import (
    EditorOpenRequest,
    EditorOpenResponse,
    EditorOpenToolRequest,
    EditorStatus,
    EditorOpenNodeRequest,
    EditorOpenNodeResponse,
)
from bioimageflow_server.models.graph import ToolNodeState
from bioimageflow_server.models.nested_workflow_snapshot import NestedWorkflowSnapshotResponse
from bioimageflow_server.routers.workflow_drafts import get_workflow_draft_service
from bioimageflow_server.routers.nested_workflow_snapshots import (
    get_nested_workflow_snapshot_service,
)
from bioimageflow_server.services.workflow_draft import WorkflowDraftService
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedWorkflowSnapshotService,
    NestedSnapshotRevisionConflict,
)
from bioimageflow_server.services.workflow_artifacts import OwnedWorkflowSources
from bioimageflow_server.routers.tools import (
    get_tool_registry,
    get_workflow_root,
    get_workflow_store,
    resolve_tool_project_open_paths,
    get_deployment_mode,
    get_unsafe_webapp_features_enabled,
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
logger = logging.getLogger(__name__)


def get_editor_service() -> EditorService:  # pragma: no cover
    raise RuntimeError("editor service dependency not configured")


@router.post("/open-node", response_model=EditorOpenNodeResponse)
async def open_node_script(
    body: EditorOpenNodeRequest,
    service: EditorService = Depends(get_editor_service),
    registry: ToolRegistryService = Depends(get_tool_registry),
    store: WorkflowStoreService = Depends(get_workflow_store),
    drafts: WorkflowDraftService = Depends(get_workflow_draft_service),
    snapshots: NestedWorkflowSnapshotService = Depends(get_nested_workflow_snapshot_service),
    mode: str = Depends(get_deployment_mode),
    unsafe: bool = Depends(get_unsafe_webapp_features_enabled),
) -> EditorOpenNodeResponse:
    if mode == "webapp" and not unsafe:
        raise HTTPException(
            status_code=403, detail="Tool source editing is disabled in webapp mode"
        )

    def resolve() -> tuple[Path, Path, NestedWorkflowSnapshotResponse | None]:
        with snapshots.snapshot_mutation(), store.workflow_mutation(body.workflow_id):
            if store.workflow_generation(body.workflow_id) != body.identity_generation:
                raise HTTPException(status_code=409, detail="Workflow identity changed")
            snapshot = None
            if body.session_id is not None:
                snapshot = snapshots.prepare_source_edit(
                    body.session_id,
                    body.workflow_id,
                    body.node_id,
                    body.expected_revision,
                )
                graph = snapshot.graph
            else:
                draft = drafts.get_draft_authority_snapshot(body.workflow_id)
                if draft.draft_revision != body.expected_revision:
                    raise HTTPException(status_code=409, detail="Workflow draft changed")
                graph = draft.graph
            node = next((node for node in graph.nodes if node.id == body.node_id), None)
            if not isinstance(node, ToolNodeState):
                raise HTTPException(status_code=404, detail="Tool node not found")
            if node.source_module:
                source = OwnedWorkflowSources(store.workflow_dir(body.workflow_id)).source_path(
                    node.source_module,
                    node.tool_module,
                )
                return store.root_dir.parent, source, snapshot
            project, source = resolve_tool_project_open_paths(
                tool_name=node.tool_name,
                workflow_name=body.workflow_id,
                workflow_root=store.root_dir,
                registry=registry,
                workflow_store=store,
            )
            return project, source, snapshot

    try:
        project, source, snapshot = await to_thread.run_sync(resolve)
        response = await to_thread.run_sync(
            partial(
                service.open_path,
                str(project),
                str(source),
                workspace=True,
            )
        )
        return EditorOpenNodeResponse(**response.model_dump(), snapshot=snapshot)
    except NestedSnapshotRevisionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Workflow tool source is missing: {exc}"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EditorPathNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Path not found: {exc}") from exc
    except EditorPathError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EditorLaunchError as exc:
        logger.exception("Could not launch editor for node %s", body.node_id)
        raise mark_exception_logged(
            HTTPException(status_code=503, detail=f"Could not launch editor: {exc}")
        ) from exc


@router.get("/status", response_model=EditorStatus)
async def get_editor_status(
    launch: bool = False,
    workspace: bool = False,
    service: EditorService = Depends(get_editor_service),
) -> EditorStatus:
    return await to_thread.run_sync(partial(service.get_status, launch=launch, workspace=workspace))


@router.post("/open", response_model=EditorOpenResponse)
async def open_editor_path(
    body: EditorOpenRequest,
    service: EditorService = Depends(get_editor_service),
) -> EditorOpenResponse:
    logger.info("Editor open requested: path=%s focus_path=%s", body.path, body.focus_path)
    try:
        response = await to_thread.run_sync(service.open_path, body.path, body.focus_path)
        logger.info(
            "Editor open completed: method=%s opened=%s path=%s error_code=%s",
            response.method,
            response.opened,
            response.path,
            response.error_code,
        )
        return response
    except EditorPathNotFoundError as exc:
        logger.warning(
            "Editor open rejected because path was not found: path=%s focus_path=%s detail=%s",
            body.path,
            body.focus_path,
            exc,
        )
        raise HTTPException(status_code=404, detail=f"Path not found: {exc}") from exc
    except EditorPathError as exc:
        logger.warning(
            "Editor open rejected because path is invalid: path=%s focus_path=%s detail=%s",
            body.path,
            body.focus_path,
            exc,
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EditorLaunchError as exc:
        logger.error(
            "Editor open failed to launch: path=%s focus_path=%s detail=%s",
            body.path,
            body.focus_path,
            exc,
            exc_info=exc,
        )
        raise mark_exception_logged(
            HTTPException(status_code=503, detail=f"Could not launch editor: {exc}")
        ) from exc


@router.post("/open-tool", response_model=EditorOpenResponse)
async def open_tool_script(
    body: EditorOpenToolRequest,
    service: EditorService = Depends(get_editor_service),
    registry: ToolRegistryService = Depends(get_tool_registry),
    workflow_root: Path | None = Depends(get_workflow_root),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
) -> EditorOpenResponse:
    workflow_name = body.workflow_id or body.workflow_name
    logger.info(
        "Editor open-tool requested: tool=%s workflow=%s",
        body.tool_name,
        workflow_name,
    )
    try:
        project_path, source_path = resolve_tool_project_open_paths(
            tool_name=body.tool_name,
            workflow_name=workflow_name,
            workflow_root=workflow_root,
            registry=registry,
            workflow_store=workflow_store,
        )
        logger.info(
            "Editor open-tool resolved: tool=%s project_path=%s focus_path=%s",
            body.tool_name,
            project_path,
            source_path,
        )
        response = await to_thread.run_sync(
            partial(
                service.open_path,
                str(project_path),
                str(source_path),
                workspace=True,
            )
        )
        logger.info(
            "Editor open-tool completed: tool=%s method=%s opened=%s path=%s error_code=%s",
            body.tool_name,
            response.method,
            response.opened,
            response.path,
            response.error_code,
        )
        return response
    except EditorPathNotFoundError as exc:
        logger.warning(
            "Editor open-tool rejected because path was not found: tool=%s workflow=%s detail=%s",
            body.tool_name,
            workflow_name,
            exc,
        )
        raise HTTPException(status_code=404, detail=f"Path not found: {exc}") from exc
    except EditorPathError as exc:
        logger.warning(
            "Editor open-tool rejected because path is invalid: tool=%s workflow=%s detail=%s",
            body.tool_name,
            workflow_name,
            exc,
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EditorLaunchError as exc:
        logger.error(
            "Editor open-tool failed to launch: tool=%s workflow=%s detail=%s",
            body.tool_name,
            workflow_name,
            exc,
            exc_info=exc,
        )
        raise mark_exception_logged(
            HTTPException(status_code=503, detail=f"Could not launch editor: {exc}")
        ) from exc
