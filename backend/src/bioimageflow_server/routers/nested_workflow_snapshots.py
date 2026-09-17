"""Private nested-workflow snapshot routes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response

from bioimageflow_server.models.nested_workflow_snapshot import (
    NestedViewerPreferencesFinalizeRequest,
    NestedWorkflowSnapshotConflictResponse,
    NestedWorkflowSnapshotDependencyConflictResponse,
    NestedWorkflowSnapshotLockedResponse,
    NestedWorkflowSnapshotOpenRequest,
    NestedWorkflowSnapshotPutRequest,
    NestedWorkflowSnapshotResponse,
)
from bioimageflow_server.models.graph import GraphState, ToolNodeState, WorkflowNodeState
from bioimageflow_server.models.viewer_preferences import (
    SessionOutputPreferenceKey,
    ViewerPreferencesSnapshot,
)
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedSnapshotHasDependents,
    NestedSnapshotRevisionConflict,
    NestedWorkflowSnapshotService,
)
from bioimageflow_server.services.execution import ExecutionConflictError
from bioimageflow_server.services.viewer_preferences import (
    ViewerPreferenceStore,
    ensure_workspace_identity,
)
from bioimageflow_server.services.workflow_store import WorkflowStoreService
from bioimageflow_server.services.workflow_draft import WorkflowDraftService

router = APIRouter(
    prefix="/nested-workflow-snapshots",
    tags=["nested-workflow-snapshots"],
)


def get_nested_workflow_snapshot_service() -> NestedWorkflowSnapshotService:
    raise RuntimeError("nested_workflow_snapshot_service dependency not configured")


def get_execution_manager() -> Any | None:
    return None


def get_viewer_preference_store() -> ViewerPreferenceStore | None:
    return None


def get_workflow_store() -> WorkflowStoreService | None:
    return None


def get_workflow_draft_service() -> WorkflowDraftService | None:
    return None


def _locked_response(execution_manager: Any | None) -> JSONResponse | None:
    if execution_manager is None or not getattr(execution_manager, "is_running", False):
        return None
    body = NestedWorkflowSnapshotLockedResponse(
        detail="Workflow editing is locked while execution is in progress"
    )
    return JSONResponse(status_code=423, content=body.model_dump())


@asynccontextmanager
async def _idle_mutation_lease(
    execution_manager: Any | None,
) -> AsyncIterator[None]:
    if execution_manager is None:
        yield
        return
    lease = getattr(execution_manager, "exclusive_idle_mutation", None)
    if lease is None:
        if getattr(execution_manager, "is_running", False):
            raise ExecutionConflictError("An execution is already running")
        yield
        return
    async with lease():
        yield


def _conflict_response(exc: NestedSnapshotRevisionConflict) -> JSONResponse:
    body = NestedWorkflowSnapshotConflictResponse(
        detail=str(exc),
        expected_revision=exc.expected_revision,
        current_revision=exc.current.snapshot_revision,
    )
    return JSONResponse(status_code=409, content=body.model_dump())


def _dependency_conflict_response(
    exc: NestedSnapshotHasDependents,
) -> JSONResponse:
    body = NestedWorkflowSnapshotDependencyConflictResponse(
        detail=str(exc),
        dependent_session_ids=exc.dependent_session_ids,
    )
    return JSONResponse(status_code=409, content=body.model_dump(mode="json"))


def _accepted_child_graph(
    parent: GraphState,
    parent_node_id: str,
    child: GraphState,
) -> bool:
    node = next((item for item in parent.nodes if item.id == parent_node_id), None)
    return isinstance(node, WorkflowNodeState) and node.workflow == child


def _structural_output_exists(
    graph: GraphState,
    node_path: tuple[str, ...],
    output_key: str,
    store: WorkflowStoreService,
) -> bool:
    current = graph
    node = None
    for index, node_id in enumerate(node_path):
        node = next((item for item in current.nodes if item.id == node_id), None)
        if node is None:
            return False
        if index < len(node_path) - 1:
            if not isinstance(node, WorkflowNodeState):
                return False
            current = node.workflow
    if isinstance(node, WorkflowNodeState):
        outputs = {item.id for item in node.workflow.interface.outputs}
    elif isinstance(node, ToolNodeState):
        metadata = store.tool_registry.get_tool(node.tool_name)
        schema = metadata.outputs if metadata is not None else None
        outputs = set(node.viewer_additions) | set(node.output_templates)
        if isinstance(schema, dict):
            outputs.update(key for key in schema if key != "_passthrough")
    else:
        return False
    return output_key in outputs


def _surviving_session_outputs(
    preferences: ViewerPreferenceStore,
    workspace_id: UUID,
    session_id: UUID,
    graph: GraphState,
    store: WorkflowStoreService,
) -> set[tuple[tuple[str, ...], str]]:
    result: set[tuple[tuple[str, ...], str]] = set()
    for favorite in preferences.snapshot().favorites:
        key = favorite.key
        if not (
            isinstance(key, SessionOutputPreferenceKey)
            and key.workspace_id == workspace_id
            and key.session_id == str(session_id)
        ):
            continue
        if _structural_output_exists(graph, key.node_path, key.output_key, store):
            result.add((key.node_path, key.output_key))
    return result


@router.post(
    "/open",
    response_model=NestedWorkflowSnapshotResponse,
    status_code=201,
    responses={423: {"model": NestedWorkflowSnapshotLockedResponse}},
)
async def open_nested_workflow_snapshot(
    body: NestedWorkflowSnapshotOpenRequest,
    service: NestedWorkflowSnapshotService = Depends(get_nested_workflow_snapshot_service),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> NestedWorkflowSnapshotResponse | JSONResponse:
    try:
        async with _idle_mutation_lease(execution_manager):
            return await service.open_snapshot_async(
                body.owner,
                body.parent_node_id,
                body.graph,
            )
    except ExecutionConflictError:
        return _locked_response(execution_manager) or JSONResponse(
            status_code=423,
            content=NestedWorkflowSnapshotLockedResponse(
                detail="Workflow editing is locked while execution is in progress"
            ).model_dump(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{session_id}", response_model=NestedWorkflowSnapshotResponse)
async def get_nested_workflow_snapshot(
    session_id: UUID,
    service: NestedWorkflowSnapshotService = Depends(get_nested_workflow_snapshot_service),
) -> NestedWorkflowSnapshotResponse:
    try:
        return await service.get_snapshot_async(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put(
    "/{session_id}",
    response_model=NestedWorkflowSnapshotResponse,
    responses={
        409: {"model": NestedWorkflowSnapshotConflictResponse},
        423: {"model": NestedWorkflowSnapshotLockedResponse},
    },
)
async def put_nested_workflow_snapshot(
    session_id: UUID,
    body: NestedWorkflowSnapshotPutRequest,
    service: NestedWorkflowSnapshotService = Depends(get_nested_workflow_snapshot_service),
    execution_manager: Any | None = Depends(get_execution_manager),
) -> NestedWorkflowSnapshotResponse | JSONResponse:
    try:
        async with _idle_mutation_lease(execution_manager):
            return await service.put_snapshot_async(
                session_id,
                expected_revision=body.expected_revision,
                graph=body.graph,
            )
    except ExecutionConflictError:
        return _locked_response(execution_manager) or JSONResponse(
            status_code=423,
            content=NestedWorkflowSnapshotLockedResponse(
                detail="Workflow editing is locked while execution is in progress"
            ).model_dump(),
        )
    except NestedSnapshotRevisionConflict as exc:
        return _conflict_response(exc)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/{session_id}/viewer-preferences/finalize-apply",
    response_model=ViewerPreferencesSnapshot,
    responses={409: {"model": NestedWorkflowSnapshotConflictResponse}},
)
def finalize_nested_viewer_preferences(
    session_id: UUID,
    body: NestedViewerPreferencesFinalizeRequest,
    service: NestedWorkflowSnapshotService = Depends(get_nested_workflow_snapshot_service),
    preferences: ViewerPreferenceStore | None = Depends(get_viewer_preference_store),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
    drafts: WorkflowDraftService | None = Depends(get_workflow_draft_service),
) -> ViewerPreferencesSnapshot | JSONResponse:
    """Remap a child overlay only after its stored parent accepted that graph."""

    if preferences is None or workflow_store is None or drafts is None:
        raise HTTPException(status_code=503, detail="viewer preferences are not configured")
    workspace_id = ensure_workspace_identity(workflow_store.workspace_dir)
    with service.snapshot_mutation():
        child = service.get_snapshot(session_id)
        if child.snapshot_revision != body.expected_revision:
            return _conflict_response(
                NestedSnapshotRevisionConflict(
                    expected_revision=body.expected_revision,
                    current=child,
                )
            )
        owner = child.owner
        if owner.kind == "nested":
            assert owner.session_id is not None
            parent = service.get_snapshot(owner.session_id)
            if not _accepted_child_graph(parent.graph, child.parent_node_id, child.graph):
                raise HTTPException(
                    status_code=409,
                    detail="parent snapshot has not accepted the child graph",
                )
            surviving = _surviving_session_outputs(
                preferences, workspace_id, session_id, child.graph, workflow_store
            )
            return preferences.apply_session_to_session(
                workspace_id,
                str(session_id),
                parent_session_id=str(parent.session_id),
                parent_node_path=(child.parent_node_id,),
                surviving_outputs=surviving,
            )
        if owner.workflow_id is None:
            raise HTTPException(
                status_code=409,
                detail="save the root workflow before finalizing viewer preferences",
            )
        with workflow_store.workflow_mutation(owner.workflow_id):
            if owner.identity_generation is None:
                raise HTTPException(status_code=409, detail="workflow identity is incomplete")
            try:
                workflow_store.ensure_workflow_generation(
                    owner.workflow_id, owner.identity_generation
                )
                draft = drafts.get_draft_authority_snapshot(owner.workflow_id)
                generation = workflow_store.workflow_generation(owner.workflow_id)
            except (FileNotFoundError, ValueError) as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            if not _accepted_child_graph(draft.graph, child.parent_node_id, child.graph):
                raise HTTPException(
                    status_code=409,
                    detail="root draft has not accepted the child graph",
                )
            surviving = _surviving_session_outputs(
                preferences, workspace_id, session_id, child.graph, workflow_store
            )
            return preferences.apply_session(
                workspace_id,
                str(session_id),
                workflow_id=owner.workflow_id,
                identity_generation=generation,
                parent_node_path=(child.parent_node_id,),
                surviving_outputs=surviving,
            )


@router.delete(
    "/{session_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
    responses={
        409: {
            "model": (
                NestedWorkflowSnapshotConflictResponse
                | NestedWorkflowSnapshotDependencyConflictResponse
            )
        },
        423: {"model": NestedWorkflowSnapshotLockedResponse},
    },
)
async def delete_nested_workflow_snapshot(
    session_id: UUID,
    expected_revision: int = Query(ge=0),
    service: NestedWorkflowSnapshotService = Depends(get_nested_workflow_snapshot_service),
    execution_manager: Any | None = Depends(get_execution_manager),
    preferences: ViewerPreferenceStore | None = Depends(get_viewer_preference_store),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
) -> Response:
    try:
        async with _idle_mutation_lease(execution_manager):
            await service.delete_snapshot_async(
                session_id,
                expected_revision=expected_revision,
            )
            if preferences is not None and workflow_store is not None:
                preferences.discard_session(
                    ensure_workspace_identity(workflow_store.workspace_dir),
                    str(session_id),
                )
    except ExecutionConflictError:
        return _locked_response(execution_manager) or JSONResponse(
            status_code=423,
            content=NestedWorkflowSnapshotLockedResponse(
                detail="Workflow editing is locked while execution is in progress"
            ).model_dump(),
        )
    except NestedSnapshotRevisionConflict as exc:
        return _conflict_response(exc)
    except NestedSnapshotHasDependents as exc:
        return _dependency_conflict_response(exc)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)
