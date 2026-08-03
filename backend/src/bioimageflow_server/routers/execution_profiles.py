"""Execution capability, target, and distributed-profile APIs."""

from __future__ import annotations

import asyncio
import importlib

from fastapi import APIRouter, Depends, HTTPException, Query, status

from bioimageflow_server.models.execution_profiles import (
    DistributedExecutionProfile,
    ExecutionCapabilitiesValue,
    ExecutionProfileCreate,
    ExecutionProfileList,
    ExecutionProfilePatch,
    ExecutionProfileTestResult,
    ExecutionTargetsValue,
    ExecutionTargetValue,
)
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.services.execution_profiles import (
    ExecutionProfileConflictError,
    ExecutionProfileNotFoundError,
    ExecutionProfileStore,
)


router = APIRouter(prefix="/execution", tags=["execution"])


def get_execution_profile_store() -> ExecutionProfileStore:  # pragma: no cover
    raise RuntimeError("execution profile store not configured")


def get_settings() -> Settings:  # pragma: no cover
    raise RuntimeError("settings not configured")


def _mutable(store: ExecutionProfileStore, settings: Settings) -> None:
    if settings.deployment_mode == "webapp" or not store.editable:
        raise HTTPException(
            status_code=403,
            detail="Execution profiles are administrator-managed in webapp mode",
        )


def _trusted(profile: ExecutionProfileCreate, settings: Settings) -> None:
    if profile.parsl_config.factory not in settings.trusted_parsl_factories:
        raise HTTPException(
            status_code=422,
            detail="The Parsl configuration factory is not in trusted_parsl_factories",
        )


def _profile(store: ExecutionProfileStore, profile_id: str) -> DistributedExecutionProfile:
    try:
        return store.get(profile_id)
    except ExecutionProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution profile not found") from exc


@router.get("/capabilities", response_model=ExecutionCapabilitiesValue)
async def execution_capabilities() -> ExecutionCapabilitiesValue:
    library = importlib.import_module("bioimageflow")
    return ExecutionCapabilitiesValue.model_validate(library.get_execution_capabilities().to_dict())


@router.get("/targets", response_model=ExecutionTargetsValue)
async def execution_targets(
    store: ExecutionProfileStore = Depends(get_execution_profile_store),
    settings: Settings = Depends(get_settings),
) -> ExecutionTargetsValue:
    capabilities = await execution_capabilities()
    targets = [
        ExecutionTargetValue(
            id="local",
            name="Local",
            kind="local",
            mode="local",
            available=True,
        )
    ]
    capability_for_mode = {
        "attached": "attached_parsl",
        "submitted_local": "submitted_local_parsl",
        "submitted_remote": "submitted_remote_parsl",
    }
    for profile in store.list():
        capability = capabilities.capabilities[capability_for_mode[profile.mode]]
        reason = None
        if not profile.enabled:
            reason = "Profile is disabled."
        elif profile.parsl_config.factory not in settings.trusted_parsl_factories:
            reason = "The Parsl configuration factory is not trusted."
        elif not capability.supported:
            reason = capability.reason
        targets.append(
            ExecutionTargetValue(
                id=profile.id,
                name=profile.name,
                kind="profile",
                mode=profile.mode,
                available=reason is None,
                disabled_reason=reason,
                profile_revision=profile.revision,
            )
        )
    return ExecutionTargetsValue(capabilities=capabilities, targets=targets)


@router.get("/profiles", response_model=ExecutionProfileList)
async def list_execution_profiles(
    store: ExecutionProfileStore = Depends(get_execution_profile_store),
    settings: Settings = Depends(get_settings),
) -> ExecutionProfileList:
    editable = store.editable and settings.deployment_mode == "desktop"
    return ExecutionProfileList(
        editable=editable,
        profiles=(
            store.list()
            if editable
            else [profile.model_copy(update={"pre_launch": None}) for profile in store.list()]
        ),
    )


@router.post(
    "/profiles",
    response_model=DistributedExecutionProfile,
    status_code=status.HTTP_201_CREATED,
)
async def create_execution_profile(
    body: ExecutionProfileCreate,
    store: ExecutionProfileStore = Depends(get_execution_profile_store),
    settings: Settings = Depends(get_settings),
) -> DistributedExecutionProfile:
    _mutable(store, settings)
    _trusted(body, settings)
    return await store.create(body)


@router.patch("/profiles/{profile_id}", response_model=DistributedExecutionProfile)
async def update_execution_profile(
    profile_id: str,
    body: ExecutionProfilePatch,
    store: ExecutionProfileStore = Depends(get_execution_profile_store),
    settings: Settings = Depends(get_settings),
) -> DistributedExecutionProfile:
    _mutable(store, settings)
    _trusted(body.profile, settings)
    try:
        return await store.update(profile_id, body.expected_revision, body.profile)
    except ExecutionProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution profile not found") from exc
    except ExecutionProfileConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_execution_profile(
    profile_id: str,
    expected_revision: int = Query(ge=1),
    store: ExecutionProfileStore = Depends(get_execution_profile_store),
    settings: Settings = Depends(get_settings),
) -> None:
    _mutable(store, settings)
    try:
        await store.delete(profile_id, expected_revision)
    except ExecutionProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution profile not found") from exc
    except ExecutionProfileConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/profiles/{profile_id}/test", response_model=ExecutionProfileTestResult)
async def test_execution_profile(
    profile_id: str,
    store: ExecutionProfileStore = Depends(get_execution_profile_store),
    settings: Settings = Depends(get_settings),
) -> ExecutionProfileTestResult:
    profile = _profile(store, profile_id)
    if profile.parsl_config.factory not in settings.trusted_parsl_factories:
        raise HTTPException(status_code=422, detail="The profile factory is not trusted")

    if profile.mode == "submitted_remote":
        assert profile.transport is not None
        assert profile.launch is not None
        assert profile.remote_workflow_root is not None
        report = await asyncio.to_thread(
            importlib.import_module("bioimageflow").validate_remote_execution_profile,
            transport=profile.transport.to_library(),
            parsl_config=profile.parsl_config.to_library(),
            executor_bindings=profile.library_bindings(),
            launch=profile.launch.to_library(),
            storage_path=profile.remote_workflow_root,
        )
    else:
        report = await asyncio.to_thread(
            importlib.import_module("bioimageflow").validate_parsl_config_ref,
            profile.parsl_config.to_library(),
            executor_bindings=profile.library_bindings(),
            trusted_factories=settings.trusted_parsl_factories,
        )
    return ExecutionProfileTestResult(
        profile_id=profile.id,
        profile_revision=profile.revision,
        mode=profile.mode,
        report=report.to_dict(),
    )
