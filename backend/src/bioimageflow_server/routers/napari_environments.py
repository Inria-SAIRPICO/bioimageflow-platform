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
    NapariManagedEnvironmentCopy,
    NapariManagedEnvironmentCreate,
    NapariManagedOperationMutation,
    NapariManagedRetryRequest,
    NapariFilenamePreview,
    NapariFilenamePreviewRequest,
    NapariFilenameRuleCreate,
    NapariFilenameRuleMutation,
    NapariFilenameRulesReplace,
    NapariProbeRequest,
    NapariResolveRequest,
    NapariResolveResponse,
    NapariViewingReadinessResponse,
)
from bioimageflow_server.models.viewer_preferences import (
    PersistentOutputPreferenceKey,
    SessionOutputPreferenceKey,
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
    compatibility_status,
)
from bioimageflow_server.services.viewer_preferences import (
    ViewerPreferenceStore,
    ViewerPreferencesRevisionConflict,
    ViewerPreferenceTargetConflict,
    ensure_workspace_identity,
)
from bioimageflow_server.models.graph import (
    GraphState,
    ToolNodeState,
    ViewerSpec,
    WorkflowNodeState,
)
from bioimageflow_server.models.workflow import ViewingRequirementsManifest
from bioimageflow_server.routers.nested_workflow_snapshots import (
    get_nested_workflow_snapshot_service,
)
from bioimageflow_server.routers.workflow_drafts import get_workflow_draft_service
from bioimageflow_server.routers.workflows import get_workflow_store
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedWorkflowSnapshotService,
)
from bioimageflow_server.services.workflow_store import WorkflowStoreService
from bioimageflow_server.services.workflow_draft import WorkflowDraftService


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
    if exc.code in {"napari_environment_not_found", "napari_operation_not_found"}:
        status_code = 404
    elif exc.code in {
        "napari_environment_duplicate",
        "duplicate_environment_name",
        "duplicate_filename_pattern",
        "napari_registry_revision_conflict",
        "napari_environment_mutation_active",
        "napari_operation_not_live",
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
    "/environments/managed",
    response_model=NapariManagedOperationMutation,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_managed_environment(
    request: NapariManagedEnvironmentCreate,
    service: NapariEnvironmentService = Depends(_service),
) -> NapariManagedOperationMutation:
    try:
        return await service.create_managed(request)
    except NapariEnvironmentError as exc:
        raise _http_error(exc) from exc


@router.delete(
    "/environments/managed/{environment_id}",
    response_model=NapariManagedOperationMutation,
    status_code=status.HTTP_202_ACCEPTED,
)
async def remove_managed_environment(
    environment_id: UUID,
    expected_revision: int = Query(ge=0),
    service: NapariEnvironmentService = Depends(_service),
) -> NapariManagedOperationMutation:
    try:
        return await service.remove_managed(
            environment_id, expected_revision=expected_revision
        )
    except NapariEnvironmentError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/environments/{environment_id}/copy",
    response_model=NapariManagedOperationMutation,
    status_code=status.HTTP_202_ACCEPTED,
)
async def copy_managed_environment(
    environment_id: UUID,
    request: NapariManagedEnvironmentCopy,
    service: NapariEnvironmentService = Depends(_service),
) -> NapariManagedOperationMutation:
    try:
        return await service.copy_managed(environment_id, request)
    except NapariEnvironmentError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/environments/{environment_id}/retry",
    response_model=NapariManagedOperationMutation,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_managed_environment(
    environment_id: UUID,
    request: NapariManagedRetryRequest,
    service: NapariEnvironmentService = Depends(_service),
) -> NapariManagedOperationMutation:
    try:
        return await service.retry_managed(
            environment_id, expected_revision=request.expected_revision
        )
    except NapariEnvironmentError as exc:
        raise _http_error(exc) from exc


@router.get(
    "/environments/{environment_id}/operations/{operation_id}",
    response_model=NapariManagedOperationMutation,
)
def get_managed_operation(
    environment_id: UUID,
    operation_id: UUID,
    service: NapariEnvironmentService = Depends(_service),
) -> NapariManagedOperationMutation:
    try:
        return service.managed_operation(environment_id, operation_id)
    except NapariEnvironmentError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/environments/{environment_id}/operations/{operation_id}/cancel",
    response_model=NapariManagedOperationMutation,
    status_code=status.HTTP_202_ACCEPTED,
)
async def cancel_managed_operation(
    environment_id: UUID,
    operation_id: UUID,
    service: NapariEnvironmentService = Depends(_service),
) -> NapariManagedOperationMutation:
    try:
        return await service.cancel_managed_operation(environment_id, operation_id)
    except NapariEnvironmentError as exc:
        raise _http_error(exc) from exc


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


def _output_viewer_declaration(
    declared: ViewerSpec | None, addition: ViewerSpec | None
) -> ViewerSpec | None:
    """Combine one output's declared and additive viewer metadata.

    The graph is the authority for a structural output's viewer declaration;
    combining through the library's own merge keeps the additive semantics
    identical to the resolver's retained-result viewer.
    """
    if declared is None:
        return addition
    if addition is None:
        return declared
    from bioimageflow_core import ViewerSpec as LibraryViewerSpec
    from bioimageflow_core import merge_viewer_specs

    return ViewerSpec.from_library(
        merge_viewer_specs(
            LibraryViewerSpec.from_dict(declared.model_dump(mode="json", by_alias=True)),
            LibraryViewerSpec.from_dict(addition.model_dump(mode="json", by_alias=True)),
        )
    )


def _validate_structural_output(
    graph: GraphState,
    node_path: tuple[str, ...],
    output_key: str,
    store: WorkflowStoreService,
) -> ViewerSpec | None:
    """Validate the addressed structural output and return its viewer declaration."""
    current = graph
    node = None
    for index, node_id in enumerate(node_path):
        node = next((item for item in current.nodes if item.id == node_id), None)
        if node is None:
            raise HTTPException(status_code=422, detail="favorite node path does not exist")
        if index < len(node_path) - 1:
            if not isinstance(node, WorkflowNodeState):
                raise HTTPException(status_code=422, detail="favorite node path is not structural")
            current = node.workflow
    if isinstance(node, WorkflowNodeState):
        output = next(
            (item for item in node.workflow.interface.outputs if item.id == output_key),
            None,
        )
        if output is None:
            raise HTTPException(status_code=422, detail="favorite output does not exist")
        return _output_viewer_declaration(
            output.viewer_addition, node.viewer_additions.get(output_key)
        )
    if isinstance(node, ToolNodeState):
        metadata = store.tool_registry.get_tool(node.tool_name)
        schema = metadata.outputs if metadata is not None else None
        outputs = set(node.viewer_additions) | set(node.output_templates)
        if isinstance(schema, dict):
            outputs.update(key for key in schema if key != "_passthrough")
        if output_key not in outputs:
            raise HTTPException(status_code=422, detail="favorite output does not exist")
        return node.viewer_additions.get(output_key)
    raise HTTPException(status_code=422, detail="favorite output does not exist")


def _enforce_favorite_compatibility(
    key,
    environment,
    viewer: ViewerSpec | None,
    preferences: ViewerPreferenceStore,
) -> None:
    """Refuse a new incompatible favorite for this structural output identity.

    Spec section 5.3 keeps an incompatible saved favorite for repair but
    disallows setting a new one, so re-affirming the current favorite stays
    allowed while unsetting is always permitted.
    """
    if compatibility_status(environment, viewer) != "incompatible":
        return
    if preferences.favorite_for(key) == environment.id:
        return
    raise HTTPException(
        status_code=409,
        detail={
            "error": "napari_favorite_incompatible",
            "detail": (
                f"Environment {environment.name!r} does not satisfy this output's "
                "required packages"
            ),
        },
    )


def _validate_preference_key(
    key,
    store: WorkflowStoreService,
    snapshots: NestedWorkflowSnapshotService,
    drafts: WorkflowDraftService,
) -> ViewerSpec | None:
    if key.workspace_id != ensure_workspace_identity(store.workspace_dir):
        raise HTTPException(status_code=409, detail="workspace identity changed")
    if isinstance(key, PersistentOutputPreferenceKey):
        try:
            with store.workflow_mutation(key.workflow_id):
                store.ensure_workflow_generation(
                    key.workflow_id, key.identity_generation
                )
                graph = drafts.get_draft_authority_snapshot(key.workflow_id).graph
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="workflow identity not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _validate_structural_output(graph, key.node_path, key.output_key, store)
    if isinstance(key, SessionOutputPreferenceKey):
        try:
            snapshot = snapshots.get_snapshot(UUID(key.session_id))
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="nested editor session not found") from exc
        return _validate_structural_output(snapshot.graph, key.node_path, key.output_key, store)
    return None


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
    snapshots: NestedWorkflowSnapshotService = Depends(
        get_nested_workflow_snapshot_service
    ),
    drafts: WorkflowDraftService = Depends(get_workflow_draft_service),
) -> ViewerPreferencesSnapshot:
    environment = next(
        (
            item
            for item in service.snapshot().environments
            if item.id == request.environment_id
        ),
        None,
    )
    if environment is None:
        raise HTTPException(status_code=404, detail="napari environment not found")
    try:
        with snapshots.snapshot_mutation():
            viewer = _validate_preference_key(request.key, workflow_store, snapshots, drafts)
            _enforce_favorite_compatibility(request.key, environment, viewer, preferences)
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
    snapshots: NestedWorkflowSnapshotService = Depends(
        get_nested_workflow_snapshot_service
    ),
    drafts: WorkflowDraftService = Depends(get_workflow_draft_service),
) -> ViewerPreferencesSnapshot:
    del service
    try:
        with snapshots.snapshot_mutation():
            _validate_preference_key(request.key, workflow_store, snapshots, drafts)
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
    snapshots: NestedWorkflowSnapshotService = Depends(
        get_nested_workflow_snapshot_service
    ),
    drafts: WorkflowDraftService = Depends(get_workflow_draft_service),
) -> ViewerPreferencesSnapshot:
    environment = next(
        (
            item
            for item in service.snapshot().environments
            if item.id == request.environment_id
        ),
        None,
    )
    if environment is None:
        raise HTTPException(status_code=404, detail="napari environment not found")
    try:
        with snapshots.snapshot_mutation():
            viewer = _validate_preference_key(request.key, workflow_store, snapshots, drafts)
            _enforce_favorite_compatibility(request.key, environment, viewer, preferences)
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


@router.post("/viewing-readiness", response_model=NapariViewingReadinessResponse)
def viewing_readiness(
    manifest: ViewingRequirementsManifest,
    environment_service: NapariEnvironmentService = Depends(_service),
    resolver: NapariResolverService = Depends(get_napari_resolver_service),
) -> NapariViewingReadinessResponse:
    """Evaluate portable viewer metadata against the current inventory snapshot."""
    del environment_service
    return resolver.viewing_readiness(manifest)
