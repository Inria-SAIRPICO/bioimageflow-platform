"""Retained execution and distributed-preflight API."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from bioimageflow_server.models.execution_preflight import (
    ApplyPreparedExecutionRequest,
    ExecutionPreflightRequest,
    ExecutionPreflightResponse,
)
from bioimageflow_server.models.execution_runtime import (
    ConfirmExecutionCleanupRequest,
    ConfirmRetryRequest,
    ExecutionActionResponse,
    ExecutionPage,
    ExecutionPresentation,
    ExecutionPresentationPage,
    ExecutionSnapshot,
    ExecutionCleanupPlanRequest,
    ExecutionCleanupPresentation,
    ExecutionCleanupReport,
    RetryPlanPresentation,
    RetryPlanRequest,
    present_execution,
)
from bioimageflow_server.services.execution_preflight import (
    DistributedPreflightService,
    PreparedTokenConflict,
    PreparedTokenError,
    PreparedTokenExpired,
    invocation_binding,
)
from bioimageflow_server.services.execution_registry import ExecutionNotFoundError
from bioimageflow_server.services.execution_runtime import (
    ExecutionCoordinator,
    ExecutionOperationError,
    _operation_error,
)

router = APIRouter(prefix="/executions", tags=["executions"])
preflight_router = APIRouter(prefix="/execution", tags=["execution"])


class PreparedRunRegistrar(Protocol):
    async def register_prepared_run(
        self,
        request: ApplyPreparedExecutionRequest,
        run_handle: object,
    ) -> ExecutionSnapshot: ...


class DownloadDestinationResolver(Protocol):
    def resolve(self, execution_id: str) -> Path: ...


def get_execution_coordinator() -> ExecutionCoordinator:  # pragma: no cover
    raise RuntimeError("execution coordinator dependency is not configured")


def get_preflight_service() -> DistributedPreflightService:  # pragma: no cover
    raise RuntimeError("distributed preflight dependency is not configured")


def get_prepared_run_registrar() -> PreparedRunRegistrar:  # pragma: no cover
    raise RuntimeError("prepared-run registrar dependency is not configured")


def get_download_destination_resolver() -> DownloadDestinationResolver:  # pragma: no cover
    raise RuntimeError("download destination resolver dependency is not configured")


@preflight_router.post("/preflight", response_model=ExecutionPreflightResponse)
async def preflight_execution(
    request: ExecutionPreflightRequest,
    service: DistributedPreflightService = Depends(get_preflight_service),
) -> ExecutionPreflightResponse:
    try:
        return await service.preflight(request)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("", response_model=ExecutionPresentation, status_code=202)
async def apply_prepared_execution(
    request: ApplyPreparedExecutionRequest,
    service: DistributedPreflightService = Depends(get_preflight_service),
    registrar: PreparedRunRegistrar = Depends(get_prepared_run_registrar),
) -> ExecutionPresentation:
    binding = invocation_binding(
        workflow_id=request.workflow_id,
        draft_revision=request.draft_revision,
        target_id=request.target_id,
        requested_nodes=request.requested_nodes,
    )
    try:
        handle = await service.tokens.consume(request.token, binding=binding)
    except PreparedTokenExpired as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except PreparedTokenConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PreparedTokenError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        diagnostic = getattr(exc, "diagnostic", None)
        if diagnostic is None:
            raise
        raise _execution_http_error(
            _operation_error(exc, fallback="workflow-submission-failed")
        ) from exc
    return present_execution(await registrar.register_prepared_run(request, handle))


@router.get("", response_model=ExecutionPresentationPage)
async def list_executions(
    workflow_id: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    coordinator: ExecutionCoordinator = Depends(get_execution_coordinator),
) -> ExecutionPresentationPage:
    page: ExecutionPage = await coordinator.list(
        workflow_id=workflow_id,
        offset=offset,
        limit=limit,
    )
    return ExecutionPresentationPage(
        items=[present_execution(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{execution_id}", response_model=ExecutionPresentation)
async def get_execution(
    execution_id: str,
    coordinator: ExecutionCoordinator = Depends(get_execution_coordinator),
) -> ExecutionPresentation:
    try:
        return present_execution(await coordinator.get(execution_id))
    except (ExecutionNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc


@router.post("/{execution_id}/cancel", response_model=ExecutionActionResponse, status_code=202)
async def cancel_execution(
    execution_id: str,
    coordinator: ExecutionCoordinator = Depends(get_execution_coordinator),
) -> ExecutionActionResponse:
    try:
        snapshot = await coordinator.cancel(execution_id)
    except (ExecutionNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc
    except ExecutionOperationError as exc:
        raise _execution_http_error(exc) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ExecutionActionResponse(execution_id=execution_id, state=snapshot.state)


@router.post("/{execution_id}/retry/plan", response_model=RetryPlanPresentation)
async def plan_retry_execution(
    execution_id: str,
    request: RetryPlanRequest,
    coordinator: ExecutionCoordinator = Depends(get_execution_coordinator),
) -> RetryPlanPresentation:
    try:
        recompute = request.recompute
        return await coordinator.plan_retry(
            execution_id,
            node_paths=None if recompute is None else tuple(recompute.node_paths),
            cascade=True if recompute is None else recompute.cascade,
        )
    except ExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc
    except ExecutionOperationError as exc:
        raise _execution_http_error(exc) from exc


@router.post("/{execution_id}/retry", response_model=ExecutionPresentation, status_code=202)
async def confirm_retry_execution(
    execution_id: str,
    request: ConfirmRetryRequest,
    coordinator: ExecutionCoordinator = Depends(get_execution_coordinator),
) -> ExecutionPresentation:
    try:
        return present_execution(
            await coordinator.confirm_retry(
                execution_id,
                plan_digest=request.plan_digest,
            )
        )
    except ExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc
    except ExecutionOperationError as exc:
        raise _execution_http_error(exc) from exc


@router.post("/{execution_id}/result", response_class=FileResponse)
async def download_execution_result(
    execution_id: str,
    coordinator: ExecutionCoordinator = Depends(get_execution_coordinator),
    destinations: DownloadDestinationResolver = Depends(get_download_destination_resolver),
) -> FileResponse:
    try:
        destination = destinations.resolve(execution_id)
        path = await coordinator.download_result(execution_id, destination)
    except ExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc
    except ExecutionOperationError as exc:
        raise _execution_http_error(exc) from exc
    return FileResponse(path)


@router.post(
    "/{execution_id}/cleanup/plan",
    response_model=ExecutionCleanupPresentation,
)
async def plan_execution_cleanup(
    execution_id: str,
    request: ExecutionCleanupPlanRequest,
    coordinator: ExecutionCoordinator = Depends(get_execution_coordinator),
) -> ExecutionCleanupPresentation:
    try:
        digest, plan = await coordinator.plan_cleanup(
            execution_id,
            older_than_seconds=request.older_than_seconds,
        )
    except ExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc
    except ExecutionOperationError as exc:
        raise _execution_http_error(exc) from exc
    return ExecutionCleanupPresentation(
        execution_id=execution_id,
        plan_digest=digest,
        plan=plan,
    )


@router.post("/{execution_id}/cleanup", response_model=ExecutionCleanupReport)
async def apply_execution_cleanup(
    execution_id: str,
    request: ConfirmExecutionCleanupRequest,
    coordinator: ExecutionCoordinator = Depends(get_execution_coordinator),
) -> ExecutionCleanupReport:
    try:
        report = await coordinator.apply_cleanup(
            execution_id,
            plan_digest=request.plan_digest,
        )
    except ExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc
    except ExecutionOperationError as exc:
        raise _execution_http_error(exc) from exc
    return ExecutionCleanupReport(execution_id=execution_id, report=report)


def _execution_http_error(exc: ExecutionOperationError) -> HTTPException:
    if exc.code in {"retry-plan-not-found", "cleanup-plan-not-found", "run-not-found"}:
        status = 404
    elif exc.code in {
        "invalid-recompute-request",
        "remote-invalid-retry",
        "invalid-retry",
    }:
        status = 422
    elif (
        exc.code.startswith("ssh-")
        or exc.code.startswith("sftp-")
        or exc.code
        in {
            "remote-protocol",
            "protocol-incompatible",
            "gateway-unavailable",
        }
    ):
        status = 503
    elif exc.code in {
        "workflow-run-retry-error",
        "remote-retry-conflict",
        "psij-submission-uncertain",
        "remote-retry-submission-uncertain",
        "submission-uncertain",
        "scheduler-rejected",
        "attempt-still-uncertain",
        "operation-conflict",
        "retry-conflict",
        "cleanup-conflict",
        "retry-plan-integrity-error",
        "retry-child-conflict",
        "workflow-run-result-unavailable",
        "workflow-result-destination-conflict",
        "workflow-result-integrity-error",
    }:
        status = 409
    else:
        status = 500
    details = dict(exc.details)
    details.setdefault(
        "retryable",
        exc.code in {"ssh-connection", "ssh-timeout", "ssh-command-failed"}
        or exc.code.startswith("sftp-"),
    )
    return HTTPException(
        status_code=status,
        detail={
            "error": exc.code,
            "detail": str(exc),
            "details": details,
        },
    )
