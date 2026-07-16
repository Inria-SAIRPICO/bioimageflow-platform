"""Graph validation router."""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from functools import partial
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from bioimageflow_server.models.graph import (
    GraphState,
    GraphValidationRequest,
    NodeOutputSchemaResponse,
)
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.validation import ValidationResult
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.execution import ExecutionConflictError
from bioimageflow_server.services.graph_validator import GraphValidationService
from bioimageflow_server.services.graph_worker import run_graph_work
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_context import resolve_workflow_storage_path
from bioimageflow_server.services.workflow_store import WorkflowStoreService

router = APIRouter(prefix="/graph", tags=["graph"])


class _WorkflowValidationContextChanged(RuntimeError):
    """Signal that validation must restart in a newer storage context."""


@dataclass(frozen=True)
class _WorkflowValidationContext:
    storage_path: Path | None
    identity_generation: int | None


def get_tool_registry() -> ToolRegistryService:  # pragma: no cover
    raise RuntimeError("tool_registry dependency not configured")


def get_storage_path() -> Path | None:
    return None


def get_execution_manager() -> Any | None:
    return None


def get_dev_mode() -> bool:
    return True


def get_workflow_store() -> WorkflowStoreService | None:
    return None


def get_settings() -> Settings | None:
    """Live Settings or None when the app is configured without one."""
    return None


def _ensure_unlocked(execution_manager: Any | None) -> None:
    if execution_manager is None:
        return
    if getattr(execution_manager, "is_running", False):
        raise HTTPException(
            status_code=423,
            detail="Graph editing is locked while execution is in progress",
        )


@asynccontextmanager
async def _idle_validation_lease(
    execution_manager: Any | None,
) -> AsyncIterator[None]:
    if execution_manager is None:
        yield
        return
    lease = getattr(execution_manager, "exclusive_idle_mutation", None)
    if lease is None:
        _ensure_unlocked(execution_manager)
        yield
        return
    try:
        async with lease():
            yield
    except ExecutionConflictError as exc:
        raise HTTPException(
            status_code=423,
            detail="Graph editing is locked while execution is in progress",
        ) from exc


@router.put("")
async def validate_graph_endpoint(
    body: GraphState | GraphValidationRequest,
    registry: ToolRegistryService = Depends(get_tool_registry),
    storage_path: Path | None = Depends(get_storage_path),
    execution_manager: Any | None = Depends(get_execution_manager),
    dev_mode: bool = Depends(get_dev_mode),
    settings: Settings | None = Depends(get_settings),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
) -> ValidationResult:
    if isinstance(body, GraphValidationRequest):
        graph = body.graph
        workflow_name = body.workflow_name
    else:
        graph = body
        workflow_name = None
    graph = graph.model_copy(deep=True)
    validation_service = GraphValidationService(registry)
    async with _idle_validation_lease(execution_manager):
        while True:
            try:
                context = await run_graph_work(
                    partial(
                        _capture_workflow_validation_context,
                        workflow_name,
                        workflow_store,
                        storage_path,
                    )
                )
                validation = await validation_service.validate_async(
                    graph,
                    storage_path=context.storage_path,
                    dev_mode=dev_mode,
                    settings=settings,
                )
                await run_graph_work(
                    partial(
                        _ensure_workflow_validation_context,
                        workflow_name,
                        workflow_store,
                        storage_path,
                        context,
                    )
                )
                return validation
            except _WorkflowValidationContextChanged:
                continue
            except FileNotFoundError as exc:
                raise HTTPException(
                    status_code=404,
                    detail=f"Workflow '{workflow_name}' not found",
                ) from exc


@router.post("/nodes/{node_id}/output_schema")
async def resolve_node_output_schema(
    node_id: str,
    graph: GraphState,
    registry: ToolRegistryService = Depends(get_tool_registry),
    storage_path: Path | None = Depends(get_storage_path),
) -> NodeOutputSchemaResponse:
    """Return the resolved output column schema for a single node.

    The full ``GraphState`` is required because schema resolution may
    depend on upstream wiring (e.g. merge tools). Build failures return
    ``{resolved: false, columns: {}}`` — input edits frequently produce
    transiently invalid graph states.
    """
    graph = graph.model_copy(deep=True)
    return await run_graph_work(
        partial(
            _resolve_node_output_schema,
            node_id,
            graph,
            registry,
            storage_path,
        )
    )


def _capture_workflow_validation_context(
    workflow_name: str | None,
    workflow_store: WorkflowStoreService | None,
    fallback_storage_path: Path | None,
) -> _WorkflowValidationContext:
    if not workflow_name or workflow_store is None:
        return _WorkflowValidationContext(
            storage_path=resolve_workflow_storage_path(
                workflow_name,
                workflow_store,
                fallback_storage_path,
            ),
            identity_generation=None,
        )
    with workflow_store.workflow_mutation(workflow_name):
        return _WorkflowValidationContext(
            storage_path=resolve_workflow_storage_path(
                workflow_name,
                workflow_store,
                fallback_storage_path,
            ),
            identity_generation=workflow_store.workflow_generation(workflow_name),
        )


def _ensure_workflow_validation_context(
    workflow_name: str | None,
    workflow_store: WorkflowStoreService | None,
    fallback_storage_path: Path | None,
    expected: _WorkflowValidationContext,
) -> None:
    if not workflow_name or workflow_store is None:
        return
    assert expected.identity_generation is not None
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
            raise _WorkflowValidationContextChanged


def _resolve_node_output_schema(
    node_id: str,
    graph: GraphState,
    registry: ToolRegistryService,
    storage_path: Path | None,
) -> NodeOutputSchemaResponse:
    from bioimageflow.validation import serialize_resolved_outputs

    # 404 only when the node_id is not present in the request body at all.
    node_ids_in_graph = {n.id for n in graph.nodes}
    if node_id not in node_ids_in_graph:
        raise HTTPException(
            status_code=404,
            detail=f"Node {node_id!r} not found in graph",
        )

    try:
        result = build_workflow(graph, registry, storage_path=storage_path)
    except Exception:
        # Transient invalid state — cycle, unknown tool, bad constant, etc.
        return NodeOutputSchemaResponse(resolved=False, columns={})

    workflow = result.workflow
    node = workflow._nodes.get(node_id)
    if node is None:
        # Node was in the request but didn't make it into the workflow
        # (e.g. unknown tool, missing package). Return unresolved.
        return NodeOutputSchemaResponse(resolved=False, columns={})

    try:
        wire = serialize_resolved_outputs(node)
    except Exception:
        return NodeOutputSchemaResponse(resolved=False, columns={})

    return NodeOutputSchemaResponse(**wire)
