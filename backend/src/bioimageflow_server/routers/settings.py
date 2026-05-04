"""Settings router — GET + PATCH /settings (platform_specs_v1.md §2.4.6)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ConfigDict, ValidationError

from bioimageflow_server.models.settings import OMEROInstanceResponse, Settings
from bioimageflow_server.services.omero_credentials import OmeroCredentialError
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

    omero_instances: list[OMEROInstanceResponse] = []
    resolved_tool_store_path: str
    resolved_output_data_folder: str


def _wrap(store: SettingsStore) -> SettingsResponse:
    settings = store.get()
    omero_instances = [
        OMEROInstanceResponse(
            **instance.model_dump(),
            password_stored=store.omero_password_stored(instance),
        )
        for instance in settings.omero_instances
    ]
    payload = settings.model_dump()
    payload["omero_instances"] = omero_instances
    return SettingsResponse(
        **payload,
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


def _keyring_http_error(exc: OmeroCredentialError) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail={
            "error": "settings_keyring_error",
            "detail": str(exc),
        },
    )


@router.get("", response_model=SettingsResponse)
async def get_settings(
    store: SettingsStore = Depends(get_settings_store),
) -> SettingsResponse:
    try:
        return _wrap(store)
    except OmeroCredentialError as exc:
        raise _keyring_http_error(exc) from exc


@router.patch("", response_model=SettingsResponse)
async def patch_settings(
    body: dict[str, Any],
    store: SettingsStore = Depends(get_settings_store),
) -> SettingsResponse:
    if "enable_unsafe_webapp_features" in body:
        raise HTTPException(
            status_code=422,
            detail="enable_unsafe_webapp_features can only be changed in the settings file",
        )
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
    except OmeroCredentialError as exc:
        raise _keyring_http_error(exc) from exc
    try:
        return _wrap(store)
    except OmeroCredentialError as exc:
        raise _keyring_http_error(exc) from exc
