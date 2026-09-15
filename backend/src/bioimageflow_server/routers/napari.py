"""Napari viewer router.

Endpoints:
- ``POST /napari/open``: launch (lazy) and open the given paths.
- ``GET /napari/status``: lock-free status snapshot.
- ``POST /napari/shutdown``: terminate the manager process.

All path validation lives in ``NapariLauncher.open()`` — the router
does not re-validate. Errors map:
- ``FileNotFoundError`` -> 400 ``path_not_found``
- ``NapariLaunchError`` -> 503 ``napari_launch_failed``
"""

from __future__ import annotations

import logging
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from bioimageflow_server.models.errors import mark_exception_logged
from bioimageflow_server.models.napari import (
    NapariEnvironmentStatus,
    NapariLaunchRequest,
    NapariOpenRequest,
    NapariStatus,
)
from bioimageflow_server.routers.viewer_paths import resolve_selected_image_path
from bioimageflow_server.services.napari_launcher import (
    NapariLauncher,
    NapariLauncherPool,
    NapariLaunchError,
    NapariOpenError,
    NapariOpenOutcomeUnknown,
)
from bioimageflow_server.services.result_store import ResultStoreService
from bioimageflow_server.services.workflow_store import WorkflowStoreService


router = APIRouter(prefix="/napari", tags=["napari"])
_logger = logging.getLogger(__name__)


def get_napari_launcher() -> NapariLauncher | NapariLauncherPool:  # pragma: no cover
    """Stub overridden by ``create_app`` via ``dependency_overrides``."""
    raise NotImplementedError


def get_result_store() -> ResultStoreService:  # pragma: no cover
    """Stub overridden by ``create_app`` via ``dependency_overrides``."""
    raise RuntimeError("ResultStoreService dependency is not configured")


def get_workflow_store() -> WorkflowStoreService | None:  # pragma: no cover
    return None


def get_deployment_mode() -> str:  # pragma: no cover
    return "desktop"


def _require_desktop(mode: str = Depends(get_deployment_mode)) -> None:
    if mode != "desktop":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "desktop_only",
                "detail": "napari viewer operations are available only in desktop mode",
            },
        )


def _context_fields(request: NapariOpenRequest) -> tuple[object, ...]:
    return (request.node_id, request.row, request.col, request.result_identity)


def _resolve_open_paths(
    request: NapariOpenRequest,
    result_store: ResultStoreService,
    workflow_store: WorkflowStoreService | None,
) -> list[str]:
    context_values = _context_fields(request)
    has_context = any(value is not None for value in context_values)
    if not has_context:
        return request.paths
    if not all(value is not None for value in context_values):
        raise HTTPException(
            status_code=422,
            detail=(
                "node_id, row, col, and result_identity are required together "
                "for path resolution"
            ),
        )
    if len(request.paths) != 1:
        raise HTTPException(
            status_code=422,
            detail="context-based Napari open supports exactly one selected path",
        )

    assert request.node_id is not None
    assert request.row is not None
    assert request.col is not None
    assert request.result_identity is not None
    image_path = resolve_selected_image_path(
        node_id=request.node_id,
        row=request.row,
        col=request.col,
        workflow_name=request.workflow_name,
        result_store=result_store,
        workflow_store=workflow_store,
        result_identity=request.result_identity,
    )
    return [str(image_path)]


@router.post("/launch")
async def launch_napari_environment(
    request: NapariLaunchRequest,
    _desktop: None = Depends(_require_desktop),
    launcher: NapariLauncher | NapariLauncherPool = Depends(get_napari_launcher),
) -> dict[str, str]:
    """Start one registered viewer without dispatching an artifact open."""

    if not isinstance(launcher, NapariLauncherPool):
        raise HTTPException(
            status_code=503,
            detail={
                "error": "napari_environment_registry_unavailable",
                "detail": "registered napari environments are unavailable",
            },
        )
    try:
        await launcher.launch(request.environment_id)
        return {"status": "launched"}
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "napari_environment_not_found",
                "detail": str(exc),
            },
        ) from exc
    except NapariLaunchError as exc:
        mark_exception_logged(exc)
        _logger.error("Failed to launch napari environment", exc_info=exc)
        raise HTTPException(
            status_code=503,
            detail={"error": "napari_launch_failed", "detail": str(exc)},
        ) from exc


@router.post("/open")
async def open_in_napari(
    request: NapariOpenRequest,
    _desktop: None = Depends(_require_desktop),
    launcher: NapariLauncher | NapariLauncherPool = Depends(get_napari_launcher),
    result_store: ResultStoreService = Depends(get_result_store),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
) -> dict[str, str]:
    try:
        paths = _resolve_open_paths(request, result_store, workflow_store)
        if request.environment_id is None:
            if request.reader_id is None:
                await launcher.open(paths, request.clear_layers)
            else:
                await launcher.open(paths, request.clear_layers, reader_id=request.reader_id)
        else:
            pool = cast(NapariLauncherPool, launcher)
            await pool.open(
                paths,
                request.clear_layers,
                environment_id=request.environment_id,
                reader_id=request.reader_id,
            )
    except HTTPException as exc:
        _logger.warning(
            "Napari open request rejected with HTTP %s: %s",
            exc.status_code,
            exc.detail,
        )
        raise
    except FileNotFoundError as exc:
        _logger.warning(
            "Napari open request rejected because paths were not found: %s",
            exc,
        )
        raise HTTPException(
            status_code=400,
            detail={"error": "path_not_found", "detail": str(exc)},
        ) from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=404 if isinstance(exc, KeyError) else 422,
            detail={"error": "napari_environment_invalid", "detail": str(exc)},
        ) from exc
    except NapariOpenError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "napari_open_failed", "detail": str(exc)},
        ) from exc
    except NapariOpenOutcomeUnknown as exc:
        raise HTTPException(
            status_code=504,
            detail={"error": "napari_open_outcome_unknown", "detail": str(exc)},
        ) from exc
    except NapariLaunchError as exc:
        _logger.error(
            "Napari open request failed while launching or contacting Napari: %s",
            exc,
            exc_info=exc,
        )
        raise mark_exception_logged(
            HTTPException(
                status_code=503,
                detail={"error": "napari_launch_failed", "detail": str(exc)},
            )
        ) from exc
    return {"status": "ok"}


@router.get("/status", response_model=NapariStatus | NapariEnvironmentStatus)
def napari_status(
    environment_id: UUID | None = None,
    _desktop: None = Depends(_require_desktop),
    launcher: NapariLauncher | NapariLauncherPool = Depends(get_napari_launcher),
) -> NapariStatus | NapariEnvironmentStatus:
    # Lock-free: safe to call concurrently with a long-running launch.
    try:
        if environment_id is None:
            return launcher.status()
        return cast(NapariLauncherPool, launcher).status(environment_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": "napari_environment_not_found", "detail": str(exc)},
        ) from exc


@router.post("/shutdown")
async def shutdown_napari(
    environment_id: UUID | None = None,
    _desktop: None = Depends(_require_desktop),
    launcher: NapariLauncher | NapariLauncherPool = Depends(get_napari_launcher),
) -> dict[str, str]:
    try:
        if environment_id is None:
            await launcher.shutdown()
        else:
            await cast(NapariLauncherPool, launcher).shutdown(environment_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": "napari_environment_not_found", "detail": str(exc)},
        ) from exc
    return {"status": "ok"}
