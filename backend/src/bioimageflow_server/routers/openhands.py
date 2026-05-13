"""OpenHands process lifecycle router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from bioimageflow_server.models.openhands import OpenHandsContext, OpenHandsStatus
from bioimageflow_server.services.openhands import (
    OpenHandsLaunchError,
    OpenHandsService,
    OpenHandsUnavailableError,
)


router = APIRouter(prefix="/openhands", tags=["openhands"])


def get_openhands_service() -> OpenHandsService:  # pragma: no cover
    """Stub overridden by ``create_app`` via ``dependency_overrides``."""
    raise NotImplementedError


@router.get("/status", response_model=OpenHandsStatus)
async def openhands_status(
    launch: bool = False,
    service: OpenHandsService = Depends(get_openhands_service),
) -> OpenHandsStatus:
    if not launch:
        return service.status()
    try:
        return await service.launch()
    except OpenHandsUnavailableError as exc:
        raise _unavailable_error(exc) from exc
    except OpenHandsLaunchError as exc:
        raise _launch_error(service, exc) from exc


@router.post("/launch", response_model=OpenHandsStatus)
async def launch_openhands(
    service: OpenHandsService = Depends(get_openhands_service),
) -> OpenHandsStatus:
    try:
        return await service.launch()
    except OpenHandsUnavailableError as exc:
        raise _unavailable_error(exc) from exc
    except OpenHandsLaunchError as exc:
        raise _launch_error(service, exc) from exc


@router.post("/shutdown", response_model=OpenHandsStatus)
async def shutdown_openhands(
    service: OpenHandsService = Depends(get_openhands_service),
) -> OpenHandsStatus:
    return await service.shutdown()


@router.get("/context", response_model=OpenHandsContext)
def openhands_context(
    service: OpenHandsService = Depends(get_openhands_service),
) -> OpenHandsContext:
    return service.context()


@router.post("/context")
def receive_openhands_context(
    payload: dict[str, Any],
    service: OpenHandsService = Depends(get_openhands_service),
) -> dict[str, Any]:
    context = service.context()
    return {
        "accepted": context.available,
        "context": payload,
        "message": context.reason,
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
