"""Graph validation router."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from bioimageflow_server.models.graph import GraphState, NodeOutputSchemaResponse
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.validation import (
    ParameterPatchRequest,
    ValidationResult,
)
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.graph_validator import (
    patch_session_constants as _patch_session_constants,
    validate_graph as _validate_graph,
    validate_parameters as _validate_parameters,
)
from bioimageflow_server.services.session_manager import SessionManager
from bioimageflow_server.services.tool_registry import ToolRegistryService

router = APIRouter(prefix="/graph", tags=["graph"])


def get_tool_registry() -> ToolRegistryService:  # pragma: no cover
    raise RuntimeError("tool_registry dependency not configured")


def get_storage_path() -> Path | None:
    return None


def get_execution_manager() -> Any | None:
    return None


def get_dev_mode() -> bool:
    return True


def get_session_manager() -> SessionManager:  # pragma: no cover
    raise RuntimeError("session_manager dependency not configured")


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


def _contains_binding(value: Any) -> bool:
    """Detect dicts that look like ``ColumnRef`` bindings (constants-only check)."""
    if isinstance(value, dict):
        if "node_id" in value and "output" in value:
            return True
        return any(_contains_binding(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_binding(v) for v in value)
    return False


@router.put("")
async def validate_graph_endpoint(
    graph: GraphState,
    registry: ToolRegistryService = Depends(get_tool_registry),
    storage_path: Path | None = Depends(get_storage_path),
    execution_manager: Any | None = Depends(get_execution_manager),
    dev_mode: bool = Depends(get_dev_mode),
    session_manager: SessionManager = Depends(get_session_manager),
    settings: Settings | None = Depends(get_settings),
) -> ValidationResult:
    _ensure_unlocked(execution_manager)
    return _validate_graph(
        graph, registry, session_manager,
        storage_path=storage_path, dev_mode=dev_mode, settings=settings,
    )


@router.patch("/nodes/{node_id}/parameters")
async def patch_node_parameters(
    node_id: str,
    body: ParameterPatchRequest,
    tool_name: str | None = None,
    registry: ToolRegistryService = Depends(get_tool_registry),
    storage_path: Path | None = Depends(get_storage_path),
    execution_manager: Any | None = Depends(get_execution_manager),
    dev_mode: bool = Depends(get_dev_mode),
    session_manager: SessionManager = Depends(get_session_manager),
) -> ValidationResult:
    _ensure_unlocked(execution_manager)
    if tool_name is None:
        raise HTTPException(
            status_code=400,
            detail="Missing required query parameter: tool_name",
        )
    for _, value in body.parameters.items():
        if _contains_binding(value):
            raise HTTPException(
                status_code=400,
                detail=(
                    "PATCH accepts constant parameters only; "
                    "use PUT /graph to modify connections"
                ),
            )

    # Prefer the session path when the node is in the active session —
    # set_constant is a non-structural edit that does not re-resolve tools.
    session = session_manager.session
    if session is not None and node_id in session.nodes:
        return _patch_session_constants(
            node_id, body.parameters, session_manager,
            dev_mode=dev_mode,
        )

    # Fallback: isolated parameter validation (no session context).
    return _validate_parameters(
        node_id,
        tool_name,
        body.parameters,
        registry,
        storage_path=storage_path,
        dev_mode=dev_mode,
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
