"""OpenHands process lifecycle router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from bioimageflow_server.models.openhands import (
    OpenHandsApproval,
    OpenHandsConfig,
    OpenHandsConfigUpdate,
    OpenHandsContext,
    OpenHandsStatus,
    OpenHandsUndoRequest,
)
from bioimageflow_server.services.agent_workspace import (
    AgentPackageRequestNotFoundError,
    AgentWorkspaceService,
)
from bioimageflow_server.services.execution import ExecutionManager
from bioimageflow_server.services.graph_proposal_manager import (
    GraphProposalManager,
    ProposalOperationError,
    ProposalStaleError,
    ProposalValidationError,
)
from bioimageflow_server.services.openhands import (
    OpenHandsLaunchError,
    OpenHandsService,
    OpenHandsUnavailableError,
)
from bioimageflow_server.services.settings_store import SettingsStore
from bioimageflow_server.services.workflow_drafts import WorkflowDraftManager


router = APIRouter(prefix="/openhands", tags=["openhands"])


def get_openhands_service() -> OpenHandsService:  # pragma: no cover
    """Stub overridden by ``create_app`` via ``dependency_overrides``."""
    raise NotImplementedError


def get_settings_store() -> SettingsStore:  # pragma: no cover
    """Stub overridden by ``create_app`` via ``dependency_overrides``."""
    raise NotImplementedError


def get_agent_workspace_service() -> AgentWorkspaceService:  # pragma: no cover
    """Stub overridden by ``create_app`` via ``dependency_overrides``."""
    raise NotImplementedError


def get_graph_proposal_manager() -> GraphProposalManager:  # pragma: no cover
    """Stub overridden by ``create_app`` via ``dependency_overrides``."""
    raise NotImplementedError


def get_workflow_draft_manager() -> WorkflowDraftManager:  # pragma: no cover
    """Stub overridden by ``create_app`` via ``dependency_overrides``."""
    raise NotImplementedError


def get_execution_manager() -> ExecutionManager | None:  # pragma: no cover
    return None


def _ensure_unlocked(execution_manager: ExecutionManager | None) -> None:
    if execution_manager is None:
        return
    if getattr(execution_manager, "is_running", False):
        raise HTTPException(
            status_code=423,
            detail="Graph editing is locked while execution is in progress",
        )


def _ensure_available(service: OpenHandsService) -> None:
    context = service.context()
    if context.available:
        return
    raise _unavailable_error(Exception(context.reason or "OpenHands is unavailable"))


@router.get("/status", response_model=OpenHandsStatus)
async def openhands_status(
    launch: bool = False,
    service: OpenHandsService = Depends(get_openhands_service),
    agent_workspace: AgentWorkspaceService = Depends(get_agent_workspace_service),
) -> OpenHandsStatus:
    if not launch:
        return _with_approvals(service.status(), agent_workspace)
    try:
        return _with_approvals(await service.launch(), agent_workspace)
    except OpenHandsUnavailableError as exc:
        raise _unavailable_error(exc) from exc
    except OpenHandsLaunchError as exc:
        raise _launch_error(service, exc) from exc


@router.post("/launch", response_model=OpenHandsStatus)
async def launch_openhands(
    service: OpenHandsService = Depends(get_openhands_service),
    agent_workspace: AgentWorkspaceService = Depends(get_agent_workspace_service),
) -> OpenHandsStatus:
    try:
        return _with_approvals(await service.launch(), agent_workspace)
    except OpenHandsUnavailableError as exc:
        raise _unavailable_error(exc) from exc
    except OpenHandsLaunchError as exc:
        raise _launch_error(service, exc) from exc


@router.post("/shutdown", response_model=OpenHandsStatus)
async def shutdown_openhands(
    service: OpenHandsService = Depends(get_openhands_service),
    agent_workspace: AgentWorkspaceService = Depends(get_agent_workspace_service),
) -> OpenHandsStatus:
    return _with_approvals(await service.shutdown(), agent_workspace)


@router.get("/config", response_model=OpenHandsConfig)
def get_openhands_config(
    service: OpenHandsService = Depends(get_openhands_service),
    settings_store: SettingsStore = Depends(get_settings_store),
) -> OpenHandsConfig:
    return _config_response(service, settings_store)


@router.post("/config", response_model=OpenHandsConfig)
async def save_openhands_config(
    body: OpenHandsConfigUpdate,
    service: OpenHandsService = Depends(get_openhands_service),
    settings_store: SettingsStore = Depends(get_settings_store),
) -> OpenHandsConfig:
    await settings_store.patch(
        {
            "openhands_command": body.command,
            "openhands_process_acknowledged": True,
        }
    )
    return _config_response(service, settings_store)


@router.post("/install", response_model=OpenHandsConfig)
async def install_openhands(
    service: OpenHandsService = Depends(get_openhands_service),
    settings_store: SettingsStore = Depends(get_settings_store),
) -> OpenHandsConfig:
    try:
        installed = await service.install()
    except OpenHandsLaunchError as exc:
        raise _launch_error(service, exc) from exc
    response = _config_response(service, settings_store)
    if not installed:
        return response.model_copy(update={"message": "OpenHands install command completed, but executable was not found on PATH."})
    return response


@router.get("/context", response_model=OpenHandsContext)
def openhands_context(
    service: OpenHandsService = Depends(get_openhands_service),
) -> OpenHandsContext:
    return service.context()


@router.post("/context")
def receive_openhands_context(
    payload: dict[str, Any],
    service: OpenHandsService = Depends(get_openhands_service),
    agent_workspace: AgentWorkspaceService = Depends(get_agent_workspace_service),
) -> dict[str, Any]:
    context = service.context()
    if not context.available:
        return {
            "accepted": False,
            "context": payload,
            "message": context.reason,
        }
    prepared = agent_workspace.prepare_context(payload)
    return {
        "accepted": context.available,
        "context": payload,
        "message": context.reason,
        "workspace": prepared["workflows_root"],
        "platform_reference": prepared["platform_reference"],
        "context_file": prepared["context_file"],
    }


@router.post("/approvals/{approval_id}/approve")
async def approve_openhands_approval(
    approval_id: str,
    service: OpenHandsService = Depends(get_openhands_service),
    agent_workspace: AgentWorkspaceService = Depends(get_agent_workspace_service),
) -> dict[str, Any]:
    _ensure_available(service)
    try:
        await agent_workspace.approve_package_install(approval_id)
    except AgentPackageRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Package install request not found") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"approved": True, "approval": {"id": approval_id, "status": "approved"}}


@router.post("/approvals/{approval_id}/reject")
async def reject_openhands_approval(
    approval_id: str,
    service: OpenHandsService = Depends(get_openhands_service),
    agent_workspace: AgentWorkspaceService = Depends(get_agent_workspace_service),
) -> dict[str, Any]:
    _ensure_available(service)
    try:
        agent_workspace.reject_package_install(approval_id)
    except AgentPackageRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Package install request not found") from exc
    return {"rejected": True, "approval": {"id": approval_id, "status": "rejected"}}


@router.post("/undo")
async def undo_openhands_change(
    body: OpenHandsUndoRequest,
    service: OpenHandsService = Depends(get_openhands_service),
    manager: GraphProposalManager = Depends(get_graph_proposal_manager),
    execution_manager: ExecutionManager | None = Depends(get_execution_manager),
) -> dict[str, Any]:
    _ensure_available(service)
    _ensure_unlocked(execution_manager)
    try:
        result = manager.undo_last_apply(body.draft_id, base_revision=body.base_revision)
    except ProposalStaleError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "conflict",
                "detail": str(exc),
                "field": "base_revision",
                "current_revision": exc.current_revision,
            },
        ) from exc
    except ProposalOperationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProposalValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "graph_validation_failed",
                "detail": "Undo graph failed validation",
                "validation": exc.validation.model_dump(mode="json"),
            },
        ) from exc
    return {
        "draft_id": result.draft_id,
        "revision": result.revision,
        "graph": result.graph.model_dump(mode="json"),
        "validation": result.validation.model_dump(mode="json"),
    }


def _unavailable_error(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "error": "openhands_unavailable",
            "detail": str(exc),
        },
    )


def _launch_error(service: OpenHandsService, exc: Exception) -> HTTPException:
    try:
        if not service.context().available:
            return _unavailable_error(exc)
    except Exception:  # noqa: BLE001
        pass
    return HTTPException(
        status_code=503,
        detail={
            "error": "openhands_launch_failed",
            "detail": str(exc),
        },
    )


def _config_response(
    service: OpenHandsService,
    settings_store: SettingsStore,
) -> OpenHandsConfig:
    settings = settings_store.get()
    installed = service.status().installed
    configured = (
        settings.openhands_process_acknowledged
        and bool(settings.openhands_command)
    )
    return OpenHandsConfig(
        installed=installed,
        configured=configured,
        command=settings.openhands_command,
    )


def _with_approvals(
    status: OpenHandsStatus,
    agent_workspace: AgentWorkspaceService,
) -> OpenHandsStatus:
    return status.model_copy(update={"approvals": _approval_responses(agent_workspace)})


def _approval_responses(
    agent_workspace: AgentWorkspaceService,
) -> list[OpenHandsApproval]:
    return [
        OpenHandsApproval(
            id=request.id,
            package_name=request.package_name,
            package_version=request.version,
            command=f"Install tool package {request.package_name}"
            + (f"=={request.version}" if request.version else ""),
            status="approved" if request.approved else "pending",
        )
        for request in agent_workspace.list_package_install_requests()
    ]
