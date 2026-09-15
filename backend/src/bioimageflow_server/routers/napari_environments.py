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
    NapariResolveRequest,
    NapariResolveResponse,
)
from bioimageflow_server.models.viewer_preferences import (
    ViewerFavoriteSetRequest,
    ViewerFavoriteToggleRequest,
    ViewerFavoriteUnsetRequest,
    ViewerPreferencesSnapshot,
)
from bioimageflow_server.services.napari_environments import (
    NapariEnvironmentError,
    NapariEnvironmentService,
)
from bioimageflow_server.services.napari_resolver import (
    NapariResolverError,
    NapariResolverService,
)
from bioimageflow_server.services.viewer_preferences import (
    ViewerPreferenceStore,
    ViewerPreferencesRevisionConflict,
    ViewerPreferenceTargetConflict,
    ensure_workspace_identity,
)
from bioimageflow_server.models.viewer_preferences import PersistentOutputPreferenceKey
from bioimageflow_server.routers.workflows import get_workflow_store
from bioimageflow_server.services.workflow_store import WorkflowStoreService


router = APIRouter(prefix="/napari", tags=["napari-environments"])


def get_napari_environment_service() -> NapariEnvironmentService:  # pragma: no cover
    raise RuntimeError("napari environment service is not configured")


def get_viewer_preference_store() -> ViewerPreferenceStore:  # pragma: no cover
    raise RuntimeError("viewer preference store is not configured")


def get_napari_resolver_service() -> NapariResolverService:  # pragma: no cover
    raise RuntimeError("napari resolver service is not configured")


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


def _preference_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ViewerPreferencesRevisionConflict):
        return HTTPException(
            status_code=409,
            detail={
                "error": "viewer_preferences_revision_conflict",
                "detail": str(exc),
                "expected_revision": exc.expected,
                "current_revision": exc.current,
            },
        )
    return HTTPException(
        status_code=409,
        detail={"error": "viewer_favorite_target_conflict", "detail": str(exc)},
    )


def _validate_preference_key(key, store: WorkflowStoreService) -> None:
    if key.workspace_id != ensure_workspace_identity(store.workspace_dir):
        raise HTTPException(status_code=409, detail="workspace identity changed")
    if isinstance(key, PersistentOutputPreferenceKey):
        try:
            store.get_workflow(key.workflow_id)
            store.ensure_workflow_generation(
                key.workflow_id, key.identity_generation
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="workflow identity not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/viewer-preferences", response_model=ViewerPreferencesSnapshot)
def viewer_preferences(
    service: NapariEnvironmentService = Depends(_service),
    preferences: ViewerPreferenceStore = Depends(get_viewer_preference_store),
    workflow_store: WorkflowStoreService = Depends(get_workflow_store),
) -> ViewerPreferencesSnapshot:
    del service
    return preferences.snapshot()


@router.put("/viewer-preferences/favorite", response_model=ViewerPreferencesSnapshot)
def set_viewer_favorite(
    request: ViewerFavoriteSetRequest,
    service: NapariEnvironmentService = Depends(_service),
    preferences: ViewerPreferenceStore = Depends(get_viewer_preference_store),
    workflow_store: WorkflowStoreService = Depends(get_workflow_store),
) -> ViewerPreferencesSnapshot:
    if request.environment_id not in {
        environment.id for environment in service.snapshot().environments
    }:
        raise HTTPException(status_code=404, detail="napari environment not found")
    _validate_preference_key(request.key, workflow_store)
    try:
        return preferences.set(
            request.key,
            request.environment_id,
            expected_revision=request.expected_revision,
        )
    except (ViewerPreferencesRevisionConflict, ViewerPreferenceTargetConflict) as exc:
        raise _preference_error(exc) from exc


@router.delete("/viewer-preferences/favorite", response_model=ViewerPreferencesSnapshot)
def unset_viewer_favorite(
    request: ViewerFavoriteUnsetRequest,
    service: NapariEnvironmentService = Depends(_service),
    preferences: ViewerPreferenceStore = Depends(get_viewer_preference_store),
    workflow_store: WorkflowStoreService = Depends(get_workflow_store),
) -> ViewerPreferencesSnapshot:
    del service
    _validate_preference_key(request.key, workflow_store)
    try:
        return preferences.unset(
            request.key,
            expected_environment_id=request.expected_environment_id,
            expected_revision=request.expected_revision,
        )
    except (ViewerPreferencesRevisionConflict, ViewerPreferenceTargetConflict) as exc:
        raise _preference_error(exc) from exc


@router.post("/viewer-preferences/favorite/toggle", response_model=ViewerPreferencesSnapshot)
def toggle_viewer_favorite(
    request: ViewerFavoriteToggleRequest,
    service: NapariEnvironmentService = Depends(_service),
    preferences: ViewerPreferenceStore = Depends(get_viewer_preference_store),
    workflow_store: WorkflowStoreService = Depends(get_workflow_store),
) -> ViewerPreferencesSnapshot:
    if request.environment_id not in {
        environment.id for environment in service.snapshot().environments
    }:
        raise HTTPException(status_code=404, detail="napari environment not found")
    _validate_preference_key(request.key, workflow_store)
    try:
        return preferences.toggle(
            request.key,
            request.environment_id,
            expected_revision=request.expected_revision,
        )
    except (ViewerPreferencesRevisionConflict, ViewerPreferenceTargetConflict) as exc:
        raise _preference_error(exc) from exc


@router.post("/resolve", response_model=NapariResolveResponse)
def resolve_environment(
    request: NapariResolveRequest,
    environment_service: NapariEnvironmentService = Depends(_service),
    resolver: NapariResolverService = Depends(get_napari_resolver_service),
) -> NapariResolveResponse:
    del environment_service
    try:
        return resolver.resolve(request)
    except NapariResolverError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": exc.code, "detail": exc.detail},
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
