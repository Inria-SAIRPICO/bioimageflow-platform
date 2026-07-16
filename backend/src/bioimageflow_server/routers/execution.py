"""Execution router.

Exposes ``/api/v1/execution/{run,stop,clear,status}``.

Runs without a draft revision remain request-local compatibility calls.
Revision-addressed runs verify and load the accepted backend draft before
delegating to :class:`ExecutionManager`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from bioimageflow_server.models.execution import (
    DraftGraphMismatchResponse,
    ExecutionRequest,
)
from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.validation import NodeStatus
from bioimageflow_server.models.workflow import validate_workflow_id
from bioimageflow_server.models.workflow_draft import WorkflowDraftConflictResponse
from bioimageflow_server.services.execution import (
    ExecutionConflictError,
    ExecutionManager,
    WorkflowBuildError,
    clear_node_cache,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_context import resolve_workflow_storage_path
from bioimageflow_server.services.workflow_draft import WorkflowDraftService
from bioimageflow_server.services.workflow_store import WorkflowStoreService

router = APIRouter(prefix="/execution", tags=["execution"])


def get_execution_manager() -> ExecutionManager | None:  # pragma: no cover
    raise RuntimeError("execution_manager dependency not configured")


def get_storage_path() -> Path | None:
    return None


def get_tool_registry() -> ToolRegistryService:  # pragma: no cover
    raise RuntimeError("tool_registry dependency not configured")


def get_workflow_store() -> WorkflowStoreService | None:
    return None


def get_workflow_draft_service() -> WorkflowDraftService | None:
    return None


def get_dev_mode() -> bool:
    return True


def get_settings() -> Settings | None:
    return None


class ClearRequest(BaseModel):
    graph: GraphState
    nodes: list[str]
    workflow_name: str = Field(min_length=1)

    @field_validator("workflow_name")
    @classmethod
    def validate_workflow_name(cls, value: str) -> str:
        return validate_workflow_id(value)


@router.post(
    "/run",
    status_code=202,
    response_model=None,
    responses={
        409: {
            "model": WorkflowDraftConflictResponse | DraftGraphMismatchResponse,
        },
    },
)
async def run_execution(
    body: ExecutionRequest,
    execution_manager: ExecutionManager | None = Depends(get_execution_manager),
    storage_path: Path | None = Depends(get_storage_path),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
    workflow_draft_service: WorkflowDraftService | None = Depends(
        get_workflow_draft_service
    ),
) -> dict | JSONResponse:
    if execution_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Execution manager is not configured",
        )
    try:
        graph = GraphState.model_validate(body.graph)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid graph: {exc}") from exc

    if body.draft_revision is not None:
        if workflow_draft_service is None:
            raise HTTPException(
                status_code=503,
                detail="Workflow draft service is required for revision-addressed execution",
            )
        try:
            draft = workflow_draft_service.get_draft_snapshot(body.workflow_name)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow '{body.workflow_name}' not found",
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid workflow draft: {exc}",
            ) from exc

        if body.draft_revision != draft.draft_revision:
            conflict = WorkflowDraftConflictResponse(
                detail=(
                    "Draft revision conflict: expected "
                    f"{body.draft_revision}, current is {draft.draft_revision}"
                ),
                expected_revision=body.draft_revision,
                current_revision=draft.draft_revision,
                current_updated_by=draft.updated_by,
                current_updated_at=draft.updated_at,
            )
            return JSONResponse(status_code=409, content=conflict.model_dump())

        submitted_graph = graph.model_dump(mode="json")
        accepted_graph = draft.graph.model_dump(mode="json")
        if submitted_graph != accepted_graph:
            mismatch = DraftGraphMismatchResponse(
                detail=(
                    "Submitted graph does not match accepted draft revision "
                    f"{draft.draft_revision} for workflow '{body.workflow_name}'"
                ),
                workflow_id=body.workflow_name,
                draft_revision=draft.draft_revision,
            )
            return JSONResponse(status_code=409, content=mismatch.model_dump())

        # Compile the backend-loaded value, never the client object whose equality
        # merely proved that the caller addressed this accepted revision. Do not
        # trust the draft's retained validation result here: it can be stale,
        # deliberately skipped, or invalid only outside a selected execution
        # subgraph. ExecutionManager validates the exact full/selected build scope.
        graph = draft.graph

    if workflow_store is None:
        raise HTTPException(
            status_code=503,
            detail="Workflow store is required for execution",
        )
    try:
        run_storage_path = resolve_workflow_storage_path(
            body.workflow_name,
            workflow_store,
            storage_path,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{body.workflow_name}' not found",
        ) from exc
    try:
        context = await execution_manager.start(
            graph,
            nodes=body.nodes,
            storage_path=run_storage_path,
            workflow_id=body.workflow_name,
            draft_revision=body.draft_revision,
        )
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except WorkflowBuildError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "detail": str(exc),
                "errors": [e.model_dump() for e in exc.errors],
            },
        )
    return {"status": "started", **context.model_dump()}


@router.post("/stop")
async def stop_execution(
    execution_manager: ExecutionManager | None = Depends(get_execution_manager),
) -> dict:
    if execution_manager is None:
        raise HTTPException(
            status_code=503, detail="Execution manager is not configured"
        )
    await execution_manager.stop()
    return {"status": "stopping"}


@router.post("/clear", response_model=None)
async def clear_execution(
    body: ClearRequest,
    execution_manager: ExecutionManager | None = Depends(get_execution_manager),
    storage_path: Path | None = Depends(get_storage_path),
    registry: ToolRegistryService = Depends(get_tool_registry),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
    dev_mode: bool = Depends(get_dev_mode),
    settings: Settings | None = Depends(get_settings),
) -> dict | JSONResponse:
    if execution_manager is not None and execution_manager.is_running:
        raise HTTPException(
            status_code=423,
            detail="Cannot clear cache while execution is running",
        )
    if workflow_store is None:
        raise HTTPException(
            status_code=503,
            detail="Workflow store is required for cache clearing",
        )
    try:
        clear_storage_path = resolve_workflow_storage_path(
            body.workflow_name,
            workflow_store,
            storage_path,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{body.workflow_name}' not found",
        ) from exc
    try:
        statuses = clear_node_cache(
            body.nodes,
            body.graph,
            registry,
            clear_storage_path,
            dev_mode=dev_mode,
            settings=settings,
        )
    except WorkflowBuildError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "detail": str(exc),
                "errors": [error.model_dump() for error in exc.errors],
            },
        )
    return {
        "node_statuses": {nid: ns.model_dump() for nid, ns in statuses.items()}
    }


@router.get("/status")
async def get_status(
    execution_manager: ExecutionManager | None = Depends(get_execution_manager),
) -> dict:
    if execution_manager is None:
        return {
            "state": "idle",
            "last_result": None,
            "progress": None,
            "node_statuses": {},
        }
    status = execution_manager.get_status()
    payload = status.model_dump()
    node_statuses: dict[str, Any] = getattr(status, "node_statuses", {}) or {}
    payload["node_statuses"] = {
        nid: ns.model_dump() if isinstance(ns, NodeStatus) else ns
        for nid, ns in node_statuses.items()
    }
    return payload
