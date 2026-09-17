"""Desktop Fiji image-viewer endpoint."""

from __future__ import annotations

import logging

from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException

from bioimageflow_server.models.errors import mark_exception_logged
from bioimageflow_server.models.fiji import FijiOpenRequest
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.routers.viewer_paths import resolve_selected_image_path
from bioimageflow_server.services.fiji_launcher import (
    FijiInstallationError,
    FijiLaunchError,
    FijiLauncher,
    FijiNotConfiguredError,
)
from bioimageflow_server.services.result_store import ResultStoreService
from bioimageflow_server.services.workflow_store import WorkflowStoreService


router = APIRouter(prefix="/fiji", tags=["fiji"])
logger = logging.getLogger(__name__)


def get_fiji_launcher() -> FijiLauncher:  # pragma: no cover
    raise RuntimeError("Fiji launcher dependency is not configured")


def get_settings() -> Settings:  # pragma: no cover
    raise RuntimeError("Settings dependency is not configured")


def get_result_store() -> ResultStoreService:  # pragma: no cover
    raise RuntimeError("Result store dependency is not configured")


def get_workflow_store() -> WorkflowStoreService | None:  # pragma: no cover
    return None


@router.post("/open")
async def open_in_fiji(
    request: FijiOpenRequest,
    launcher: FijiLauncher = Depends(get_fiji_launcher),
    settings: Settings = Depends(get_settings),
    result_store: ResultStoreService = Depends(get_result_store),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
) -> dict[str, str]:
    if settings.deployment_mode != "desktop":
        raise HTTPException(
            status_code=403,
            detail={"error": "fiji_unavailable", "detail": "Fiji is available only in the desktop application."},
        )
    if request.result_identity is None:
        raise HTTPException(
            status_code=422,
            detail="result_identity is required for immutable result selection",
        )
    try:
        image_path = resolve_selected_image_path(
            node_id=request.node_id,
            row=request.row,
            col=request.col,
            workflow_name=request.workflow_name,
            result_store=result_store,
            workflow_store=workflow_store,
            result_identity=request.result_identity,
        )
        await to_thread.run_sync(launcher.open, image_path)
    except HTTPException:
        raise
    except FijiNotConfiguredError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "fiji_not_configured", "detail": str(exc)},
        ) from exc
    except FijiInstallationError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "fiji_configuration_invalid", "detail": str(exc)},
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "path_not_found", "detail": str(exc)},
        ) from exc
    except FijiLaunchError as exc:
        logger.error("Fiji launch failed: %s", exc, exc_info=exc)
        raise mark_exception_logged(
            HTTPException(
                status_code=503,
                detail={"error": "fiji_launch_failed", "detail": str(exc)},
            )
        ) from exc
    return {"status": "ok"}
