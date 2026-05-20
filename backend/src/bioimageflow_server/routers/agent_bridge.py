"""Agent bridge endpoints with backend write-scope enforcement."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from bioimageflow_server.models.agent_bridge import (
    AgentContextResponse,
    AgentPackageInstallApproveResponse,
    AgentPackageInstallRequestCreate,
    AgentPackageInstallRequestResponse,
    AgentToolWriteRequest,
    AgentToolWriteResponse,
)
from bioimageflow_server.services.agent_workspace import (
    AgentBridgePermissionError,
    AgentPackageRequestNotFoundError,
    AgentWorkspaceService,
)
from bioimageflow_server.services.package_installer import (
    PackageNetworkError,
    PackageNotFoundError,
)

router = APIRouter(prefix="/agent-bridge", tags=["agent-bridge"])


def get_agent_workspace_service() -> AgentWorkspaceService:  # pragma: no cover
    raise RuntimeError("agent_workspace_service dependency not configured")


@router.get("/context", response_model=AgentContextResponse)
async def get_agent_context(
    service: AgentWorkspaceService = Depends(get_agent_workspace_service),
) -> AgentContextResponse:
    return AgentContextResponse(**service.prepare_context())


@router.put(
    "/workflows/{workflow_name}/tools",
    response_model=AgentToolWriteResponse,
)
async def write_workflow_tool(
    workflow_name: str,
    body: AgentToolWriteRequest,
    service: AgentWorkspaceService = Depends(get_agent_workspace_service),
) -> AgentToolWriteResponse:
    try:
        path = service.write_workflow_tool_file(workflow_name, body.path, body.content)
    except AgentBridgePermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "agent_write_forbidden",
                "detail": str(exc),
            },
        ) from exc
    return AgentToolWriteResponse(path=str(path))


@router.post(
    "/package-install-requests",
    response_model=AgentPackageInstallRequestResponse,
    status_code=202,
)
async def create_package_install_request(
    body: AgentPackageInstallRequestCreate,
    service: AgentWorkspaceService = Depends(get_agent_workspace_service),
) -> AgentPackageInstallRequestResponse:
    request = service.request_package_install(body.package_name, version=body.version)
    return AgentPackageInstallRequestResponse(
        id=request.id,
        package_name=request.package_name,
        version=request.version,
        approved=request.approved,
    )


@router.post(
    "/package-install-requests/{request_id}/approve",
    response_model=AgentPackageInstallApproveResponse,
)
async def approve_package_install_request(
    request_id: str,
    service: AgentWorkspaceService = Depends(get_agent_workspace_service),
) -> AgentPackageInstallApproveResponse:
    try:
        await service.approve_package_install(request_id)
    except AgentPackageRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Package install request not found") from exc
    except PackageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PackageNetworkError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AgentPackageInstallApproveResponse(status="installed")
