"""Graph validation router."""

from __future__ import annotations

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
from bioimageflow_server.services.graph_validator import validate_graph as _validate_graph
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_context import resolve_workflow_storage_path
from bioimageflow_server.services.workflow_store import WorkflowStoreService

router = APIRouter(prefix="/graph", tags=["graph"])


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
    _ensure_unlocked(execution_manager)
    if isinstance(body, GraphValidationRequest):
        graph = body.graph
        workflow_name = body.workflow_name
    else:
        graph = body
        workflow_name = None
    try:
        validation_storage_path = resolve_workflow_storage_path(
            workflow_name,
            workflow_store,
            storage_path,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{workflow_name}' not found",
        ) from exc
    return _validate_graph(
        graph,
        registry,
        storage_path=validation_storage_path, dev_mode=dev_mode, settings=settings,
    )


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
