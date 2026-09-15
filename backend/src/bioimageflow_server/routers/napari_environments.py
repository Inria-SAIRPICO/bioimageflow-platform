"""Desktop-only registry and inventory routes for named napari environments."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from bioimageflow_server.models.napari_environments import (
    NapariDefaultEnvironmentUpdate,
    NapariEnvironmentCreate,
    NapariEnvironmentList,
    NapariEnvironmentMutation,
    NapariEnvironmentUpdate,
    NapariFilenamePreview,
    NapariFilenamePreviewRequest,
    NapariFilenameRuleCreate,
    NapariFilenameRuleMutation,
    NapariFilenameRulesReplace,
    NapariProbeRequest,
)
from bioimageflow_server.services.napari_environments import (
    NapariEnvironmentError,
    NapariEnvironmentService,
)


router = APIRouter(prefix="/napari", tags=["napari-environments"])


def get_napari_environment_service() -> NapariEnvironmentService:  # pragma: no cover
    raise RuntimeError("napari environment service is not configured")


def _service(
    service: NapariEnvironmentService = Depends(get_napari_environment_service),
) -> NapariEnvironmentService:
    if service.store.deployment_mode != "desktop":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "desktop_only",
                "detail": "napari environment operations are available only in desktop mode",
            },
        )
    return service


def _http_error(exc: NapariEnvironmentError) -> HTTPException:
    if exc.code == "napari_environment_not_found":
        status_code = 404
    elif exc.code in {
        "napari_environment_duplicate",
        "duplicate_environment_name",
        "duplicate_filename_pattern",
        "napari_registry_revision_conflict",
    }:
        status_code = 409
    else:
        status_code = 422
    return HTTPException(status_code=status_code, detail={"error": exc.code, "detail": exc.detail})


@router.get("/environments", response_model=NapariEnvironmentList)
def list_environments(
    service: NapariEnvironmentService = Depends(_service),
) -> NapariEnvironmentList:
    return service.snapshot()


@router.post(
    "/environments",
    response_model=NapariEnvironmentMutation,
    status_code=status.HTTP_201_CREATED,
)
async def register_environment(
    request: NapariEnvironmentCreate,
    service: NapariEnvironmentService = Depends(_service),
) -> NapariEnvironmentMutation:
    try:
        environment = await service.register(
            request.name, request.path, expected_revision=request.expected_revision
        )
        return NapariEnvironmentMutation(
            revision=service.snapshot().revision, environment=environment
        )
    except NapariEnvironmentError as exc:
        raise _http_error(exc) from exc


@router.patch("/environments/{environment_id}", response_model=NapariEnvironmentMutation)
async def update_environment(
    environment_id: UUID,
    request: NapariEnvironmentUpdate,
    service: NapariEnvironmentService = Depends(_service),
) -> NapariEnvironmentMutation:
    if request.name is None and request.path is None:
        raise HTTPException(status_code=422, detail="name or path is required")
    try:
        environment = await service.update(
            environment_id,
            name=request.name,
            path=request.path,
            expected_revision=request.expected_revision,
        )
        return NapariEnvironmentMutation(
            revision=service.snapshot().revision, environment=environment
        )
    except NapariEnvironmentError as exc:
        raise _http_error(exc) from exc


@router.delete("/environments/{environment_id}", response_model=NapariEnvironmentList)
async def forget_environment(
    environment_id: UUID,
    expected_revision: int = Query(ge=0),
    service: NapariEnvironmentService = Depends(_service),
) -> NapariEnvironmentList:
    try:
        return await service.forget(environment_id, expected_revision=expected_revision)
    except NapariEnvironmentError as exc:
        raise _http_error(exc) from exc


@router.post("/environments/{environment_id}/probe", response_model=NapariEnvironmentMutation)
async def probe_environment(
    environment_id: UUID,
    request: NapariProbeRequest,
    service: NapariEnvironmentService = Depends(_service),
) -> NapariEnvironmentMutation:
    try:
        environment = await service.probe(
            environment_id, expected_revision=request.expected_revision
        )
        return NapariEnvironmentMutation(
            revision=service.snapshot().revision, environment=environment
        )
    except NapariEnvironmentError as exc:
        raise _http_error(exc) from exc


@router.put("/environment-settings/default", response_model=NapariEnvironmentList)
async def set_default_environment(
    request: NapariDefaultEnvironmentUpdate,
    service: NapariEnvironmentService = Depends(_service),
) -> NapariEnvironmentList:
    try:
        return await service.set_default(
            request.environment_id, expected_revision=request.expected_revision
        )
    except NapariEnvironmentError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/environment-settings/filename-rules",
    response_model=NapariFilenameRuleMutation,
    status_code=status.HTTP_201_CREATED,
)
async def add_filename_rule(
    request: NapariFilenameRuleCreate,
    service: NapariEnvironmentService = Depends(_service),
) -> NapariFilenameRuleMutation:
    try:
        rule = await service.add_rule(request)
        return NapariFilenameRuleMutation(revision=service.snapshot().revision, rule=rule)
    except NapariEnvironmentError as exc:
        raise _http_error(exc) from exc


@router.put("/environment-settings/filename-rules", response_model=NapariEnvironmentList)
async def replace_filename_rules(
    request: NapariFilenameRulesReplace,
    service: NapariEnvironmentService = Depends(_service),
) -> NapariEnvironmentList:
    try:
        return await service.replace_rules(
            request.rules, expected_revision=request.expected_revision
        )
    except NapariEnvironmentError as exc:
        raise _http_error(exc) from exc


@router.post("/environment-settings/filename-rules/preview", response_model=NapariFilenamePreview)
def preview_filename_rules(
    request: NapariFilenamePreviewRequest,
    service: NapariEnvironmentService = Depends(_service),
) -> NapariFilenamePreview:
    return service.preview(request.filename)
