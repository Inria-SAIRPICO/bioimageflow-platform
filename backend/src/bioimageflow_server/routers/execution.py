"""Execution router.

Exposes ``/api/v1/execution/{run,stop,clear,status}``.

The router is stateless — all persistent state lives on the injected
:class:`ExecutionManager`. The router forwards requests, maps
``ExecutionConflictError`` and ``WorkflowBuildError`` to the
appropriate HTTP statuses, and returns ``ExecutionStatus``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from bioimageflow_server.models.execution import (
    ExecutionRequest,
    ExecutionStatus,
)
from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.validation import NodeStatus
from bioimageflow_server.services.execution import (
    ExecutionConflictError,
    ExecutionManager,
    WorkflowBuildError,
    clear_node_cache,
)

router = APIRouter(prefix="/execution", tags=["execution"])


def get_execution_manager() -> ExecutionManager | None:  # pragma: no cover
    raise RuntimeError("execution_manager dependency not configured")


def get_storage_path() -> Path | None:
    return None


class ClearRequest(BaseModel):
    graph: GraphState
    nodes: list[str]


@router.post("/run", status_code=202)
async def run_execution(
    body: ExecutionRequest,
    execution_manager: ExecutionManager | None = Depends(get_execution_manager),
) -> dict:
    if execution_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Execution manager is not configured",
        )
    try:
        graph = GraphState.model_validate(body.graph)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid graph: {exc}") from exc
    try:
        await execution_manager.start(graph, body.nodes)
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
    return {"status": "started"}


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


@router.post("/clear")
async def clear_execution(
    body: ClearRequest,
    execution_manager: ExecutionManager | None = Depends(get_execution_manager),
    storage_path: Path | None = Depends(get_storage_path),
) -> dict:
    if execution_manager is not None and getattr(
        execution_manager, "is_running", False
    ):
        raise HTTPException(
            status_code=423,
            detail="Cannot clear while execution is running",
        )
    statuses = clear_node_cache(body.nodes, body.graph, storage_path)
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
