"""Settings router — GET + PATCH /settings (platform_specs_v1.md §2.4.6)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ConfigDict, ValidationError

from bioimageflow_server.models.errors import mark_exception_logged
from bioimageflow_server.models.settings import OMEROInstanceResponse, Settings
from bioimageflow_server.services.omero_credentials import OmeroCredentialError
from bioimageflow_server.services.settings_store import SettingsStore
from bioimageflow_server.services.fiji_launcher import (
    FijiInstallationError,
    resolve_fiji_installation,
)
from bioimageflow_server.services.output_views import (
    probe_latest_output_modes,
    resolve_latest_output_mode,
)


router = APIRouter(prefix="/settings", tags=["settings"])
_logger = logging.getLogger(__name__)


def get_settings_store() -> SettingsStore:  # pragma: no cover
    """Dependency stub overridden via ``app.dependency_overrides``."""
    raise HTTPException(status_code=500, detail="settings store not configured")


def get_output_view_probe_path() -> Path:
    """Return a workspace-local path used to probe output-view capabilities."""
    return Path.cwd()


class SettingsResponse(Settings):
    """``GET``/``PATCH`` /settings response wrapper.

    Adds the resolved tool-store path and effective latest-output view.
    """

    model_config = ConfigDict(extra="allow")

    omero_instances: list[OMEROInstanceResponse] = []  # pyright: ignore[reportIncompatibleVariableOverride]
    resolved_tool_store_path: str
    latest_output_effective_mode: Literal["symlink", "pointer", "unavailable"]
    latest_output_warning: str | None = None


def _wrap(store: SettingsStore, output_view_probe_path: Path) -> SettingsResponse:
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
    capabilities = probe_latest_output_modes(output_view_probe_path)
    try:
        resolved_mode = resolve_latest_output_mode(
            output_view_probe_path,
            capabilities=capabilities,
        )
        effective_mode = resolved_mode.effective
        output_warning = resolved_mode.warning
    except OSError as exc:
        effective_mode = "unavailable"
        output_warning = str(exc)
    return SettingsResponse(
        **payload,
        resolved_tool_store_path=str(_resolved_tool_store_path(store)),
        latest_output_effective_mode=effective_mode,
        latest_output_warning=output_warning,
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
    output_view_probe_path: Path = Depends(get_output_view_probe_path),
) -> SettingsResponse:
    try:
        return _wrap(store, output_view_probe_path)
    except OmeroCredentialError as exc:
        raise _keyring_http_error(exc) from exc


@router.patch("", response_model=SettingsResponse)
async def patch_settings(
    body: dict[str, Any],
    store: SettingsStore = Depends(get_settings_store),
    output_view_probe_path: Path = Depends(get_output_view_probe_path),
) -> SettingsResponse:
    body = dict(body)
    if "fiji_path" in body:
        if store.deployment_mode == "webapp":
            raise HTTPException(
                status_code=403,
                detail="Fiji configuration is available only in desktop mode",
            )
        raw_fiji_path = body["fiji_path"]
        if isinstance(raw_fiji_path, str) and raw_fiji_path.strip():
            try:
                installation = resolve_fiji_installation(raw_fiji_path.strip())
            except FijiInstallationError as exc:
                raise HTTPException(
                    status_code=422,
                    detail={"error": "invalid_fiji_path", "detail": str(exc), "field": "fiji_path"},
                ) from exc
            body["fiji_path"] = str(installation.root)
        elif raw_fiji_path == "":
            body["fiji_path"] = None
    if store.deployment_mode == "webapp" and "trusted_parsl_factories" in body:
        raise HTTPException(
            status_code=403,
            detail="trusted_parsl_factories is administrator-managed in webapp mode",
        )
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
        return _wrap(store, output_view_probe_path)
    except OmeroCredentialError as exc:
        raise _keyring_http_error(exc) from exc
