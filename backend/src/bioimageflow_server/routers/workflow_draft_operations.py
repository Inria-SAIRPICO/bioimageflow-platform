"""Workflow draft semantic operation router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from bioimageflow_server.models.workflow_draft import (
    WorkflowDraftConflictResponse,
    WorkflowDraftLockedResponse,
    WorkflowDraftResponse,
)
from bioimageflow_server.models.workflow_draft_operations import (
    WorkflowDraftOperationValidationResponse,
    WorkflowDraftOperationsRequest,
)
from bioimageflow_server.routers.workflow_drafts import (
    _api_base_url,
    _conflict_response,
    _idle_mutation_lease,
    _publish_workflow_draft_changed,
)
from bioimageflow_server.services.execution import ExecutionConflictError
from bioimageflow_server.services.workflow_draft import (
    WorkflowDraftRevisionConflict,
    WorkflowDraftService,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_draft_operations import (
    WorkflowDraftOperationError,
    apply_and_validate_workflow_draft_operations,
)

router = APIRouter(
    prefix="/workflow-draft-operations",
    tags=["workflow-draft-operations"],
)


def get_workflow_draft_service() -> WorkflowDraftService:  # pragma: no cover
    raise RuntimeError("workflow_draft_service dependency not configured")


def get_tool_registry() -> ToolRegistryService:  # pragma: no cover
    raise RuntimeError("tool_registry dependency not configured")


def get_execution_manager() -> Any | None:
    return None


def get_connection_manager() -> Any | None:
    return None


@router.post(
    "/{workflow_id:path}",
    response_model=WorkflowDraftResponse,
    responses={
        409: {"model": WorkflowDraftConflictResponse},
        422: {"model": WorkflowDraftOperationValidationResponse},
        423: {"model": WorkflowDraftLockedResponse},
    },
)
async def apply_workflow_draft_operations_endpoint(
    workflow_id: str,
    body: WorkflowDraftOperationsRequest,
    request: Request,
    service: WorkflowDraftService = Depends(get_workflow_draft_service),
    registry: ToolRegistryService = Depends(get_tool_registry),
    execution_manager: Any | None = Depends(get_execution_manager),
    connection_manager: Any | None = Depends(get_connection_manager),
) -> WorkflowDraftResponse | JSONResponse:
    try:
        async with _idle_mutation_lease(execution_manager):
            current = await service.get_draft_snapshot_async(workflow_id)
            graph = apply_and_validate_workflow_draft_operations(
                current.graph,
                body.operations,
                get_tool_metadata=registry.get_tool,
            )
            draft = await service.put_draft_async(
                workflow_id,
                graph=graph,
                expected_revision=body.expected_revision,
                updated_by=body.updated_by,
                should_validate=body.validate_,
                api_base_url=_api_base_url(request),
            )
            _publish_workflow_draft_changed(connection_manager, draft)
            return draft
    except ExecutionConflictError:
        error_body = WorkflowDraftLockedResponse(
            detail="Workflow editing is locked while execution is in progress",
        )
        return JSONResponse(status_code=423, content=error_body.model_dump())
    except WorkflowDraftOperationError as exc:
        error_body = WorkflowDraftOperationValidationResponse(
            operation_index=exc.operation_index,
            code=exc.code,
            detail=exc.detail,
        )
        return JSONResponse(status_code=422, content=error_body.model_dump())
    except WorkflowDraftRevisionConflict as exc:
        return _conflict_response(exc)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
