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

from fastapi import APIRouter, Depends, HTTPException

from bioimageflow_server.models.napari import NapariOpenRequest, NapariStatus
from bioimageflow_server.services.napari_launcher import (
    NapariLauncher,
    NapariLaunchError,
)


router = APIRouter(prefix="/napari", tags=["napari"])


def get_napari_launcher() -> NapariLauncher:  # pragma: no cover
    """Stub overridden by ``create_app`` via ``dependency_overrides``."""
    raise NotImplementedError


@router.post("/open")
async def open_in_napari(
    request: NapariOpenRequest,
    launcher: NapariLauncher = Depends(get_napari_launcher),
) -> dict[str, str]:
    try:
        await launcher.open(request.paths, request.clear_layers)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "path_not_found", "detail": str(exc)},
        ) from exc
    except NapariLaunchError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "napari_launch_failed", "detail": str(exc)},
        ) from exc
    return {"status": "ok"}


@router.get("/status", response_model=NapariStatus)
def napari_status(
    launcher: NapariLauncher = Depends(get_napari_launcher),
) -> NapariStatus:
    # Lock-free: safe to call concurrently with a long-running launch.
    return launcher.status()


@router.post("/shutdown")
async def shutdown_napari(
    launcher: NapariLauncher = Depends(get_napari_launcher),
) -> dict[str, str]:
    await launcher.shutdown()
    return {"status": "ok"}
