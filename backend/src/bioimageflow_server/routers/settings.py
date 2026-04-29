"""Settings router — GET + PATCH /settings (platform_specs_v1.md §2.4.6)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, ValidationError

from bioimageflow_server.models.settings import Settings
from bioimageflow_server.services.settings_store import SettingsStore


router = APIRouter(prefix="/settings", tags=["settings"])


def get_settings_store() -> SettingsStore:  # pragma: no cover
    """Dependency stub overridden via ``app.dependency_overrides``."""
    raise HTTPException(status_code=500, detail="settings store not configured")


class SettingsResponse(Settings):
    """``GET``/``PATCH`` /settings response wrapper.

    Adds two **server-resolved** convenience fields so the frontend can show
    where tools and outputs *actually* live (env-var overrides applied,
    ``~`` expanded). The raw ``Settings`` fields remain so PATCH bodies
    stay symmetrical with what GET returns.
    """

    model_config = ConfigDict(extra="allow")

    resolved_tool_store_path: str
    resolved_output_data_folder: str


def _wrap(store: SettingsStore) -> SettingsResponse:
    settings = store.get()
    return SettingsResponse(
        **settings.model_dump(),
        resolved_tool_store_path=str(_resolved_tool_store_path(store)),
        resolved_output_data_folder=str(store.resolved_output_data_folder()),
    )


def _resolved_tool_store_path(store: SettingsStore):
    """Return the effective tool-store path.

    Honors ``BIOIMAGEFLOW_TOOL_STORE`` via ``bioimageflow.paths``, so users
    see where tools actually live regardless of the saved setting.
    """
    from bioimageflow.paths import get_tool_store_path

    return get_tool_store_path()


@router.get("", response_model=SettingsResponse)
async def get_settings(
    store: SettingsStore = Depends(get_settings_store),
) -> SettingsResponse:
    return _wrap(store)


@router.patch("", response_model=SettingsResponse)
async def patch_settings(
    body: dict[str, Any],
    store: SettingsStore = Depends(get_settings_store),
) -> SettingsResponse:
    if "dev_mode" in body and body["dev_mode"] is False:
        raise HTTPException(
            status_code=422,
            detail="dev_mode cannot be disabled in GUI mode",
        )
    try:
        await store.patch(body)
    except ValidationError as exc:
        # Re-raise as RequestValidationError so the existing handler in
        # app.py produces the standard ErrorResponse shape.
        raise RequestValidationError(exc.errors()) from exc
    return _wrap(store)
