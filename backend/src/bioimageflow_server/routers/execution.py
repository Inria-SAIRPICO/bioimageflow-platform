"""Execution router.

Exposes ``/api/v1/execution/{run,stop,clear,status}``.

Run and Clear load the accepted backend draft identified by the request.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from bioimageflow_server.models.execution import (
    ExecutionRequest,
)
from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.validation import NodeStatus
from bioimageflow_server.models.workflow import validate_workflow_id
from bioimageflow_server.models.workflow_draft import (
    WorkflowDraftConflictResponse,
)
from bioimageflow_server.services.execution import (
    ExecutionConflictError,
    ExecutionManager,
    ExecutionRetryError,
    WorkflowBuildError,
    NodeCacheClearPlan,
    commit_node_cache_clear,
    prepare_node_cache_clear,
)
from bioimageflow_server.services.graph_worker import run_graph_work
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_context import resolve_workflow_storage_path
from bioimageflow_server.services.workflow_draft import (
    WorkflowDraftRevisionConflict,
    WorkflowDraftService,
)
from bioimageflow_server.services.workflow_store import (
    WorkflowFormatUpdateRequiredError,
    WorkflowStoreService,
)

router = APIRouter(prefix="/execution", tags=["execution"])


class _RunWorkflowContextChanged(RuntimeError):
    """Signal that Run compilation must restart in a newer context."""


@dataclass(frozen=True)
class _WorkflowRuntimeContext:
    identity_generation: int
    storage_path: Path | None


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


def _draft_revision_conflict_response(
    exc: WorkflowDraftRevisionConflict,
) -> JSONResponse:
    conflict = WorkflowDraftConflictResponse(
        detail=str(exc),
        expected_revision=exc.expected_revision,
        current_revision=exc.current.draft_revision,
        current_updated_by=exc.current.updated_by,
        current_updated_at=exc.current.updated_at,
    )
    return JSONResponse(status_code=409, content=conflict.model_dump())


class ClearRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[str]
    workflow_id: str = Field(min_length=1)
    draft_revision: int = Field(ge=0)

    @field_validator("workflow_id")
    @classmethod
    def validate_workflow_name(cls, value: str) -> str:
        return validate_workflow_id(value)


@router.post(
    "/run",
    status_code=202,
    response_model=None,
    responses={
        409: {
            "model": WorkflowDraftConflictResponse,
        },
    },
)
async def run_execution(
    body: ExecutionRequest,
    execution_manager: ExecutionManager | None = Depends(get_execution_manager),
    storage_path: Path | None = Depends(get_storage_path),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
    workflow_draft_service: WorkflowDraftService | None = Depends(get_workflow_draft_service),
    registry: ToolRegistryService = Depends(get_tool_registry),
    dev_mode: bool = Depends(get_dev_mode),
) -> dict | JSONResponse:
    if execution_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Execution manager is not configured",
        )
    if workflow_store is None:
        raise HTTPException(
            status_code=503,
            detail="Workflow store is required for execution",
        )
    if workflow_draft_service is None:
        raise HTTPException(
            status_code=503,
            detail="Workflow draft service is required for revision-addressed execution",
        )

    try:
        async with execution_manager.reserve_start(
            body.workflow_id,
            body.draft_revision,
            mode=body.mode,
            requested_nodes=body.nodes,
            retry_of_execution_id=body.retry_of_execution_id,
        ) as reserved_context:
            effective_nodes = reserved_context.requested_nodes
            # A Run that bypassed request-wide serialization because another
            # admission was active may acquire the reservation after that
            # state changes. Recheck the durable move fence while this
            # reservation prevents a workflow move from being admitted.
            workflow_store.ensure_workflow_mutations_available()
            authority = await workflow_draft_service.get_draft_authority_async(body.workflow_id)
            draft = authority.draft
            runtime_context = _WorkflowRuntimeContext(
                identity_generation=authority.identity_generation,
                storage_path=authority.storage_path,
            )
            if body.draft_revision != draft.draft_revision:
                raise WorkflowDraftRevisionConflict(
                    expected_revision=body.draft_revision,
                    current=draft,
                )
            graph = draft.graph.model_copy(deep=True)
            invalidate_node_ids: list[str] = []
            if body.mode == "invalidate_failed":
                assert execution_manager.last_result is not None
                invalidate_node_ids = [
                    node_id
                    for node_id, node_status in execution_manager.last_result.node_statuses.items()
                    if node_status.status == "failed"
                ]
                if not invalidate_node_ids:
                    raise ExecutionRetryError(
                        "The failed execution has no failed node cache to invalidate; use Retry instead"
                    )
            elif body.mode == "recompute":
                invalidate_node_ids = [node.id for node in graph.nodes if node.enabled]
            if body.mode in {"retry", "invalidate_failed"} and effective_nodes is not None:
                known_node_ids = {node.id for node in graph.nodes}
                missing_targets = sorted(set(effective_nodes) - known_node_ids)
                if missing_targets:
                    raise ExecutionRetryError(
                        "The original execution targets no longer exist in the current draft: "
                        + ", ".join(missing_targets)
                    )
            while True:
                attempt_context = runtime_context

                async def ensure_context_current() -> None:
                    await run_graph_work(
                        partial(
                            _ensure_run_workflow_context,
                            workflow_store,
                            body.workflow_id,
                            storage_path,
                            attempt_context,
                            workflow_draft_service,
                            body.draft_revision,
                            graph,
                        )
                    )

                try:
                    if invalidate_node_ids:
                        plan = await run_graph_work(
                            partial(
                                prepare_node_cache_clear,
                                invalidate_node_ids,
                                graph,
                                registry,
                                attempt_context.storage_path,
                                dev_mode=dev_mode,
                            )
                        )
                        await ensure_context_current()
                        await run_graph_work(
                            partial(
                                _commit_clear_workflow_context,
                                workflow_store,
                                body.workflow_id,
                                storage_path,
                                attempt_context,
                                plan,
                                workflow_draft_service,
                                body.draft_revision,
                                graph,
                            )
                        )
                    context = await execution_manager.start(
                        graph,
                        nodes=effective_nodes,
                        storage_path=attempt_context.storage_path,
                        workflow_id=body.workflow_id,
                        draft_revision=body.draft_revision,
                        ensure_context_current=ensure_context_current,
                        reserved_context=reserved_context,
                    )
                    return {"status": "started", **context.model_dump()}
                except _RunWorkflowContextChanged:
                    runtime_context = await run_graph_work(
                        partial(
                            _refresh_workflow_runtime_context,
                            workflow_store,
                            body.workflow_id,
                            storage_path,
                            attempt_context.identity_generation,
                        )
                    )
                    continue
    except WorkflowDraftRevisionConflict as exc:
        return _draft_revision_conflict_response(exc)
    except WorkflowFormatUpdateRequiredError as exc:
        return JSONResponse(
            status_code=409,
            content={
                "error": "workflow_format_update_required",
                "detail": str(exc),
                "workflow_id": exc.workflow_id,
            },
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{body.workflow_id}' not found",
        ) from exc
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ExecutionRetryError as exc:
        return JSONResponse(
            status_code=409,
            content={"error": "execution_retry_unavailable", "detail": str(exc)},
        )
    except WorkflowBuildError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "detail": str(exc),
                "errors": [e.model_dump() for e in exc.errors],
            },
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid workflow draft: {exc}",
        ) from exc


@router.post("/stop")
async def stop_execution(
    execution_manager: ExecutionManager | None = Depends(get_execution_manager),
) -> dict:
    if execution_manager is None:
        raise HTTPException(status_code=503, detail="Execution manager is not configured")
    await execution_manager.stop()
    return {"status": "stopping"}


@router.post("/clear", response_model=None)
async def clear_execution(
    body: ClearRequest,
    execution_manager: ExecutionManager | None = Depends(get_execution_manager),
    storage_path: Path | None = Depends(get_storage_path),
    registry: ToolRegistryService = Depends(get_tool_registry),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
    workflow_draft_service: WorkflowDraftService | None = Depends(get_workflow_draft_service),
    dev_mode: bool = Depends(get_dev_mode),
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
    if workflow_draft_service is None:
        raise HTTPException(
            status_code=503, detail="Workflow draft service is required for cache clearing"
        )

    async def clear_in_current_context() -> dict[str, NodeStatus]:
        authority = await workflow_draft_service.get_draft_authority_async(body.workflow_id)
        draft = authority.draft
        if draft.draft_revision != body.draft_revision:
            raise WorkflowDraftRevisionConflict(
                expected_revision=body.draft_revision, current=draft
            )
        graph = draft.graph.model_copy(deep=True)
        context = _WorkflowRuntimeContext(authority.identity_generation, authority.storage_path)
        while True:
            try:
                plan = await run_graph_work(
                    partial(
                        prepare_node_cache_clear,
                        list(body.nodes),
                        graph,
                        registry,
                        context.storage_path,
                        dev_mode=dev_mode,
                    )
                )
            except WorkflowBuildError:
                try:
                    await run_graph_work(
                        partial(
                            _ensure_run_workflow_context,
                            workflow_store,
                            body.workflow_id,
                            storage_path,
                            context,
                            workflow_draft_service,
                            body.draft_revision,
                            graph,
                        )
                    )
                except _RunWorkflowContextChanged:
                    context = await run_graph_work(
                        partial(
                            _refresh_workflow_runtime_context,
                            workflow_store,
                            body.workflow_id,
                            storage_path,
                            context.identity_generation,
                        )
                    )
                    continue
                raise
            try:
                return await run_graph_work(
                    partial(
                        _commit_clear_workflow_context,
                        workflow_store,
                        body.workflow_id,
                        storage_path,
                        context,
                        plan,
                        workflow_draft_service,
                        body.draft_revision,
                        graph,
                    )
                )
            except _RunWorkflowContextChanged:
                context = await run_graph_work(
                    partial(
                        _refresh_workflow_runtime_context,
                        workflow_store,
                        body.workflow_id,
                        storage_path,
                        context.identity_generation,
                    )
                )
                continue

    try:
        if execution_manager is None:
            statuses = await clear_in_current_context()
        else:
            async with execution_manager.exclusive_idle_mutation():
                statuses = await clear_in_current_context()
                execution_manager.apply_cache_clear_statuses(
                    body.workflow_id, statuses, body.draft_revision
                )
    except WorkflowDraftRevisionConflict as exc:
        return _draft_revision_conflict_response(exc)
    except ExecutionConflictError as exc:
        raise HTTPException(
            status_code=423,
            detail="Cannot clear cache while execution is running",
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{body.workflow_id}' not found",
        ) from exc
    except WorkflowBuildError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "detail": str(exc),
                "errors": [error.model_dump() for error in exc.errors],
            },
        )
    return {"node_statuses": {nid: ns.model_dump() for nid, ns in statuses.items()}}


def _refresh_workflow_runtime_context(
    workflow_store: WorkflowStoreService,
    workflow_name: str,
    fallback_storage_path: Path | None,
    expected_identity_generation: int,
) -> _WorkflowRuntimeContext:
    with workflow_store.workflow_mutation(workflow_name):
        workflow_store.ensure_workflow_generation(
            workflow_name,
            expected_identity_generation,
        )
        return _WorkflowRuntimeContext(
            identity_generation=expected_identity_generation,
            storage_path=resolve_workflow_storage_path(
                workflow_name,
                workflow_store,
                fallback_storage_path,
            ),
        )


def _commit_clear_workflow_context(
    workflow_store: WorkflowStoreService,
    workflow_name: str,
    fallback_storage_path: Path | None,
    expected: _WorkflowRuntimeContext,
    plan: NodeCacheClearPlan,
    workflow_draft_service: WorkflowDraftService,
    expected_draft_revision: int,
    expected_graph: GraphState,
) -> dict[str, NodeStatus]:
    with workflow_store.workflow_mutation(workflow_name):
        _ensure_run_workflow_context(
            workflow_store,
            workflow_name,
            fallback_storage_path,
            expected,
            workflow_draft_service,
            expected_draft_revision,
            expected_graph,
        )
        return commit_node_cache_clear(plan)


def _ensure_run_workflow_context(
    workflow_store: WorkflowStoreService,
    workflow_name: str,
    fallback_storage_path: Path | None,
    expected: _WorkflowRuntimeContext,
    workflow_draft_service: WorkflowDraftService,
    expected_draft_revision: int,
    expected_graph: GraphState,
) -> None:
    with workflow_store.workflow_mutation(workflow_name):
        workflow_store.ensure_workflow_generation(
            workflow_name,
            expected.identity_generation,
        )
        current_storage_path = resolve_workflow_storage_path(
            workflow_name,
            workflow_store,
            fallback_storage_path,
        )
        if current_storage_path != expected.storage_path:
            raise _RunWorkflowContextChanged
        current = workflow_draft_service.get_draft_authority_snapshot(workflow_name)
        if current.draft_revision != expected_draft_revision:
            raise WorkflowDraftRevisionConflict(
                expected_revision=expected_draft_revision,
                current=current,
            )
        if current.graph.model_dump(mode="json") != expected_graph.model_dump(mode="json"):
            raise WorkflowDraftRevisionConflict(
                expected_revision=expected_draft_revision,
                current=current,
            )


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
