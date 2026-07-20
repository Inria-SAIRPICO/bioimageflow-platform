"""Bundled demo workflow endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from bioimageflow_server.models.demo_workflows import DemoWorkflowsStatus
from bioimageflow_server.services.demo_workflows import (
    DemoWorkflowConflictError,
    DemoWorkflowService,
)


router = APIRouter(prefix="/demo-workflows", tags=["demo-workflows"])


def get_demo_workflow_service() -> DemoWorkflowService:  # pragma: no cover
    raise RuntimeError("demo_workflow_service dependency not configured")


def get_execution_manager() -> Any | None:
    return None


def get_connection_manager() -> Any | None:
    return None


@router.get("", response_model=DemoWorkflowsStatus)
async def demo_workflow_status(
    service: DemoWorkflowService = Depends(get_demo_workflow_service),
) -> DemoWorkflowsStatus:
    return service.status()


@router.post("/install", response_model=DemoWorkflowsStatus)
async def install_demo_workflows(
    service: DemoWorkflowService = Depends(get_demo_workflow_service),
    execution_manager: Any | None = Depends(get_execution_manager),
    connection_manager: Any | None = Depends(get_connection_manager),
) -> DemoWorkflowsStatus:
    if execution_manager is not None and getattr(execution_manager, "is_running", False):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Workflow editing is locked while execution is in progress",
        )
    try:
        before = service.status()
        result = service.install()
        if before.can_install and connection_manager is not None:
            connection_manager.publish_workflow_tree_changed(action="demos_installed")
        return result
    except DemoWorkflowConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "demo_workflow_conflict",
                "detail": "Canonical demo locations are occupied: "
                + ", ".join(exc.workflow_ids),
            },
        ) from exc
