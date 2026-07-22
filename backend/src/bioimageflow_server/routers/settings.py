"""Settings router — GET + PATCH /settings (platform_specs_v1.md §2.4.6)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ConfigDict, ValidationError
from pydantic import BaseModel

from bioimageflow_server.models.errors import mark_exception_logged
from bioimageflow_server.models.settings import OMEROInstanceResponse, Settings
from bioimageflow_server.services.omero_credentials import OmeroCredentialError
from bioimageflow_server.services.settings_store import SettingsStore
from bioimageflow_server.services.output_views import (
    probe_latest_output_modes,
    resolve_latest_output_mode,
)


router = APIRouter(prefix="/settings", tags=["settings"])
_logger = logging.getLogger(__name__)


def get_settings_store() -> SettingsStore:  # pragma: no cover
    """Dependency stub overridden via ``app.dependency_overrides``."""
    raise HTTPException(status_code=500, detail="settings store not configured")


class OutputViewCapabilityResponse(BaseModel):
    """Filesystem support for one latest-output materialization mode."""

    mode: str
    supported: bool
    code: str
    detail: str | None = None


class SettingsResponse(Settings):
    """``GET``/``PATCH`` /settings response wrapper.

    Adds two **server-resolved** convenience fields so the frontend can show
    where tools and outputs *actually* live (env-var overrides applied,
    ``~`` expanded). The raw ``Settings`` fields remain so PATCH bodies
    stay symmetrical with what GET returns.
    """

    model_config = ConfigDict(extra="allow")

    omero_instances: list[OMEROInstanceResponse] = []  # pyright: ignore[reportIncompatibleVariableOverride]
    resolved_tool_store_path: str
    resolved_output_data_folder: str
    latest_output_effective_mode: str
    latest_output_warning: str | None = None
    latest_output_capabilities: dict[str, OutputViewCapabilityResponse]


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
    output_root = Path(store.resolved_output_data_folder())
    capabilities = probe_latest_output_modes(output_root)
    try:
        resolved_mode = resolve_latest_output_mode(
            output_root,
            settings.latest_output_mode,
            capabilities=capabilities,
        )
        effective_mode = resolved_mode.effective
        output_warning = resolved_mode.warning
    except OSError as exc:
        effective_mode = settings.latest_output_mode
        output_warning = str(exc)
    return SettingsResponse(
        **payload,
        resolved_tool_store_path=str(_resolved_tool_store_path(store)),
        resolved_output_data_folder=str(store.resolved_output_data_folder()),
        latest_output_effective_mode=effective_mode,
        latest_output_warning=output_warning,
        latest_output_capabilities={
            mode: OutputViewCapabilityResponse(**capability.__dict__)
            for mode, capability in capabilities.items()
        },
    )


def _resolved_tool_store_path(store: SettingsStore):
    """Return the effective tool-store path.

    Honors ``BIOIMAGEFLOW_TOOL_STORE`` via ``bioimageflow.paths``, so users
    see where tools actually live regardless of the saved setting.
    """
    from bioimageflow.paths import get_tool_store_path

    return get_tool_store_path()


def _keyring_http_error(exc: OmeroCredentialError) -> HTTPException:
    _logger.error("Settings keyring operation failed: %s", exc, exc_info=exc)
    return mark_exception_logged(HTTPException(
        status_code=500,
        detail={
            "error": "settings_keyring_error",
            "detail": str(exc),
        },
    ))


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
