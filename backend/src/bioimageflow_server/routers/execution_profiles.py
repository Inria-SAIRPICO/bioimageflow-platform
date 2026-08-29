"""Managed-cluster capability, profile, describe, and cleanup APIs."""

from __future__ import annotations

import asyncio
import importlib
import io
import zipfile
from importlib.resources import files

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from bioimageflow_server.models.execution_profiles import (
    ClusterDiagnosticValue,
    DistributedExecutionProfile,
    ExecutionCapabilitiesValue,
    ExecutionProfileCreate,
    ExecutionProfileDescription,
    ExecutionProfileList,
    ExecutionProfilePatch,
    ExecutionTargetsValue,
    ExecutionTargetValue,
)
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.routers.executions import _execution_http_error
from bioimageflow_server.services.execution_profiles import (
    ExecutionProfileConflictError,
    ExecutionProfileInUseError,
    ExecutionProfileNotFoundError,
    ExecutionProfileStore,
    load_cluster_config,
)
from bioimageflow_server.services.execution_runtime import (
    ExecutionOperationError,
    _cluster_diagnostic_value,
    _operation_error,
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


def _profile(store: ExecutionProfileStore, profile_id: str) -> DistributedExecutionProfile:
    try:
        return store.get(profile_id)
    except ExecutionProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution profile not found") from exc


def _cluster_failure(exc: Exception) -> HTTPException:
    if isinstance(exc, ExecutionOperationError):
        return _execution_http_error(exc)
    if _cluster_diagnostic_value(exc) is None:
        return HTTPException(status_code=422, detail=str(exc))
    return _execution_http_error(_operation_error(exc, fallback="cluster-profile-operation-failed"))


def _sanitized_cluster_description(cluster: object) -> dict[str, object]:
    raw = cluster.to_dict()  # type: ignore[attr-defined]
    environment = raw.get("environment")
    parsl = raw.get("parsl")
    orchestrator = raw.get("orchestrator")
    setup = raw.get("setup")
    return {
        "schema": raw["schema"],
        "host": raw["host"],
        "root": raw["root"],
        "results_root": raw["results_root"],
        "configured": cluster.configured,  # type: ignore[attr-defined]
        "environment": (
            None if not isinstance(environment, dict) else {"kind": environment.get("kind")}
        ),
        "parsl": (
            None
            if not isinstance(parsl, dict)
            else {
                "source_kind": parsl.get("source_kind"),
                "factory": parsl.get("factory"),
            }
        ),
        "orchestrator": (
            None
            if not isinstance(orchestrator, dict)
            else {
                key: orchestrator.get(key)
                for key in (
                    "scheduler",
                    "queue",
                    "project",
                    "walltime_seconds",
                    "cpu",
                )
            }
        ),
        "setup": (
            None
            if not isinstance(setup, dict)
            else {key: setup.get(key) for key in ("source_kind", "digest", "cluster_path")}
        ),
    }


@router.get("/capabilities", response_model=ExecutionCapabilitiesValue)
async def execution_capabilities() -> ExecutionCapabilitiesValue:
    library = importlib.import_module("bioimageflow")
    return ExecutionCapabilitiesValue.model_validate(library.get_execution_capabilities().to_dict())


@router.get("/targets", response_model=ExecutionTargetsValue)
async def execution_targets(
    store: ExecutionProfileStore = Depends(get_execution_profile_store),
) -> ExecutionTargetsValue:
    capabilities = await execution_capabilities()
    required_capabilities = (
        "remote_cluster_bootstrap",
        "remote_cluster_validation",
        "remote_cluster_planning",
        "idempotent_planned_submission",
        "durable_remote_diagnostics",
    )
    targets = [
        ExecutionTargetValue(
            id="local",
            name="Local",
            kind="local",
            mode="local",
            available=True,
        )
    ]
    for profile in store.list():
        reason = None
        if not profile.enabled:
            reason = "Profile is disabled."
        elif missing := [
            (name, capabilities.capabilities.get(name))
            for name in required_capabilities
            if capabilities.capabilities.get(name) is None
            or not capabilities.capabilities[name].supported
        ]:
            name, capability = missing[0]
            reason = (
                capability.reason
                if capability is not None and capability.reason
                else f"BioImageFlow does not support {name}."
            )
        targets.append(
            ExecutionTargetValue(
                id=profile.id,
                name=profile.name,
                kind="profile",
                mode="managed_remote",
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
    return ExecutionProfileList(
        editable=store.editable and settings.deployment_mode == "desktop",
        profiles=store.list(),
    )


@router.get("/profiles/example/slurm")
async def download_slurm_profile_example() -> StreamingResponse:
    """Download the maintained cluster.py/parsl.py/setup.sh site template."""

    root = files("bioimageflow_server").joinpath("data/cluster_examples/slurm")
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ("cluster.py", "parsl.py", "setup.sh"):
            archive.writestr(name, root.joinpath(name).read_bytes())
    content.seek(0)
    return StreamingResponse(
        content,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="bioimageflow-slurm-profile.zip"'},
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
    try:
        return await store.create(body)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/profiles/{profile_id}", response_model=DistributedExecutionProfile)
async def update_execution_profile(
    profile_id: str,
    body: ExecutionProfilePatch,
    store: ExecutionProfileStore = Depends(get_execution_profile_store),
    settings: Settings = Depends(get_settings),
) -> DistributedExecutionProfile:
    _mutable(store, settings)
    try:
        return await store.update(profile_id, body.expected_revision, body.profile)
    except ExecutionProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution profile not found") from exc
    except ExecutionProfileConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
    except ExecutionProfileInUseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _describe(
    profile: DistributedExecutionProfile,
    *,
    check_connection: bool,
) -> ExecutionProfileDescription:
    loaded = await asyncio.to_thread(
        load_cluster_config,
        profile.config_path,
        expected_digest=profile.config_digest,
    )
    try:
        cluster_description = _sanitized_cluster_description(loaded.cluster)
    except Exception as exc:
        raise _operation_error(
            exc,
            fallback="cluster-description-failed",
        ) from exc
    capabilities = await execution_capabilities()
    connection = None
    diagnostics: list[ClusterDiagnosticValue] = []
    if check_connection:
        try:
            report = await asyncio.to_thread(loaded.cluster.check_connection)
        except Exception as exc:
            diagnostic = _cluster_diagnostic_value(exc)
            if diagnostic is None:
                raise _operation_error(
                    exc,
                    fallback="cluster-connection-check-failed",
                ) from exc
            diagnostics.append(
                ClusterDiagnosticValue.model_validate(
                    diagnostic.model_dump(mode="json", by_alias=True)
                )
            )
        else:
            connection = report.to_dict()
            diagnostics.extend(
                ClusterDiagnosticValue.model_validate(item.to_dict()) for item in report.diagnostics
            )
    return ExecutionProfileDescription(
        profile_id=profile.id,
        profile_revision=profile.revision,
        config_digest=profile.config_digest,
        cluster_host=profile.cluster_host,
        cluster_root=profile.cluster_root,
        configured=loaded.cluster.configured,
        cluster=cluster_description,
        capabilities=capabilities,
        connection=connection,
        diagnostics=diagnostics,
    )


@router.post("/profiles/{profile_id}/describe", response_model=ExecutionProfileDescription)
async def describe_execution_profile(
    profile_id: str,
    check_connection: bool = Query(default=False),
    store: ExecutionProfileStore = Depends(get_execution_profile_store),
) -> ExecutionProfileDescription:
    try:
        return await _describe(_profile(store, profile_id), check_connection=check_connection)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise _cluster_failure(exc) from exc
