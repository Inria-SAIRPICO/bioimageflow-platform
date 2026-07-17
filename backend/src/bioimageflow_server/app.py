"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable, cast

from bioimageflow.env_manager import configure_wetlands
from bioimageflow.paths import get_home, get_wetlands_path
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

from bioimageflow_server.models.errors import ErrorResponse, exception_was_logged
from bioimageflow_server.models.settings import Settings, _DEFAULT_MAX_UPLOAD_SIZE
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.routers.dev import (
    get_result_store as dev_get_result_store,
    get_tool_registry as dev_get_tool_registry,
    router as dev_router,
)
from bioimageflow_server.routers.datasets import (
    get_datasets_root,
    get_max_upload_size,
    router as datasets_router,
)
from bioimageflow_server.routers.filesystem import router as filesystem_router
from bioimageflow_server.routers.editor import (
    get_editor_service,
    router as editor_router,
)
from bioimageflow_server.routers.graph import (
    get_dev_mode as graph_get_dev_mode,
    get_execution_manager as graph_get_execution_manager,
    get_settings as graph_get_settings,
    get_storage_path as graph_get_storage_path,
    get_tool_registry as graph_get_tool_registry,
    get_workflow_store as graph_get_workflow_store,
    router as graph_router,
)
from bioimageflow_server.routers.execution import (
    get_dev_mode as execution_get_dev_mode,
    get_execution_manager as execution_get_manager,
    get_settings as execution_get_settings,
    get_storage_path as execution_get_storage_path,
    get_tool_registry as execution_get_tool_registry,
    get_workflow_draft_service as execution_get_workflow_draft_service,
    get_workflow_store as execution_get_workflow_store,
    router as execution_router,
)
from bioimageflow_server.routers.health import router as health_router
from bioimageflow_server.routers.data_table import router as data_table_router
from bioimageflow_server.routers.napari import (
    get_napari_launcher,
    get_result_store as napari_get_result_store,
    get_workflow_store as napari_get_workflow_store,
    router as napari_router,
)
from bioimageflow_server.routers.nested_workflow_snapshots import (
    get_execution_manager as nested_snapshots_get_execution_manager,
    get_nested_workflow_snapshot_service,
    router as nested_workflow_snapshots_router,
)
from bioimageflow_server.routers.nodes import (
    get_result_store,
    get_thumbnail_manager,
    get_workflow_store as nodes_get_workflow_store,
    router as nodes_router,
)
from bioimageflow_server.routers.settings import (
    get_settings_store as settings_get_store,
    router as settings_router,
)
from bioimageflow_server.routers.tools import (
    get_deployment_mode,
    get_package_catalog,
    get_known_packages,
    get_package_installer,
    get_tool_environment_service,
    get_tool_registry,
    get_unsafe_webapp_features_enabled,
    get_workflow_root,
    get_workflow_store as tools_get_workflow_store,
    router as tools_router,
)
from bioimageflow_server.routers.workflows import (
    get_connection_manager as workflows_get_connection_manager,
    get_execution_manager as workflows_get_execution_manager,
    get_workflow_store as workflows_get_workflow_store,
    get_nested_workflow_snapshot_service as workflows_get_nested_snapshot_service,
    router as workflows_router,
)
from bioimageflow_server.routers.workflow_drafts import (
    get_connection_manager as workflow_drafts_get_connection_manager,
    get_execution_manager as workflow_drafts_get_execution_manager,
    get_workflow_draft_service,
    router as workflow_drafts_router,
)
from bioimageflow_server.routers.workflow_draft_operations import (
    get_connection_manager as workflow_draft_operations_get_connection_manager,
    get_execution_manager as workflow_draft_operations_get_execution_manager,
    get_tool_registry as workflow_draft_operations_get_tool_registry,
    get_workflow_draft_service as get_workflow_draft_operations_service,
    router as workflow_draft_operations_router,
)
from bioimageflow_server.routers.workspace import (
    get_workspace_service,
    router as workspace_router,
)
from bioimageflow_server.services.execution import (
    ExecutionManager,
)
from bioimageflow_server.services.agent_workspace_context import ensure_agent_workspace_context
from bioimageflow_server.services.editor import EditorService
from bioimageflow_server.services.known_packages import KnownPackagesService
from bioimageflow_server.services.napari_launcher import NapariLauncher
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedWorkflowSnapshotService,
)
from bioimageflow_server.services.package_catalog import PackageCatalogService
from bioimageflow_server.services.package_installer import (
    PackageNetworkError,
    PypiPackageInstaller,
)
from bioimageflow_server.services.pypi_versions import PyPIVersionService
from bioimageflow_server.services.result_store import ResultStoreService
from bioimageflow_server.services.thumbnail_manager import ThumbnailManager
from bioimageflow_server.services.tool_environments import ToolEnvironmentService
from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import (
    WorkflowMoveRecoveryError,
    WorkflowStoreService,
)
from bioimageflow_server.services.workflow_move_recovery import WorkflowMoveRecoveryService
from bioimageflow_server.services.workflow_draft import WorkflowDraftService
from bioimageflow_server.services.workflow_context import normalize_workflow_storage_path
from bioimageflow_server.services.workspace import WorkspaceService
from bioimageflow_server.ws import (
    ConnectionManager,
    attach_ws_log_handler,
    register_ws,
)

_STATUS_TO_ERROR: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "file_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    423: "locked",
    500: "internal_server_error",
    502: "bad_gateway",
    503: "service_unavailable",
}

_logger = logging.getLogger(__name__)


def _log_http_exception(request: Request, exc: HTTPException, body: ErrorResponse) -> None:
    """Log HTTP errors that represent operational failures or security-relevant rejects."""
    if exception_was_logged(exc):
        return
    status = exc.status_code
    if status >= 500:
        level = logging.ERROR
    elif status in {400, 403, 413, 415} and body.error in {
        "path_traversal",
        "file_too_large",
        "unsupported_media_type",
    }:
        level = logging.WARNING
    else:
        return

    cause = exc.__cause__
    _logger.log(
        level,
        "HTTP %s returned for %s %s: error=%s detail=%s",
        status,
        request.method,
        request.url.path,
        body.error,
        body.detail,
        exc_info=cause,
    )


def create_app(config: AppConfig | None = None) -> FastAPI:
    if config is None:
        config = AppConfig()

    # Configure the process-wide BioImageFlow/Wetlands manager before any
    # service can initialize it through a direct get_shared_environment_manager()
    # call. Plain Wetlands defaults to cwd-relative ./wetlands; BioImageFlow
    # state must instead follow bioimageflow.paths.
    configure_wetlands(wetlands_instance_path=get_wetlands_path())

    # Build the package services graph up front so the lifespan hook can
    # close owned resources (e.g. the PyPI httpx client).
    registry = config.tool_registry or ToolRegistryService()
    if config.tool_registry is None:
        registry.scan_tool_store()

    # Resolve Settings once: a loaded SettingsStore wins, then caller-supplied
    # settings, then a minimal default. Used for the initial services graph;
    # request-time settings still go through _live_settings().
    _deployment_mode = (
        config.deployment_mode if config.deployment_mode in ("desktop", "webapp") else "desktop"
    )
    settings_store = config.settings_store
    try:
        store_settings = settings_store.get() if settings_store is not None else None
    except RuntimeError:
        store_settings = None
    resolved_settings: Settings = (
        store_settings or config.settings or Settings(deployment_mode=_deployment_mode)
    )

    def _live_settings() -> Settings:
        if config.settings_store is not None:
            return config.settings_store.get()
        return resolved_settings

    # Always provide a ConnectionManager in the default app. Production launch
    # paths use create_app() directly, so leaving this optional silently drops
    # progress / node_state / execution_complete events.
    ws_manager = config.connection_manager or ConnectionManager()
    event_bus: Any = ws_manager
    workspace_service = WorkspaceService(
        settings=resolved_settings,
        deployment_mode=cast(Any, _deployment_mode),
        workspace_path=config.workspace_path,
        workspaces_root=config.workspaces_root,
        user_id=config.user_id,
    )
    workspace_path = workspace_service.workspace_path()
    configured_storage_path = config.storage_path or Path(resolved_settings.output_data_folder)
    resolved_storage_path = normalize_workflow_storage_path(configured_storage_path)
    assert resolved_storage_path is not None

    result_store = config.result_store or ResultStoreService(
        storage_path=resolved_storage_path,
        tool_registry=registry,
    )
    workflow_root = config.workflow_root or workspace_path / "workflows"
    workflow_storage_base = resolved_storage_path / "workflows"
    workflow_store = config.workflow_store or WorkflowStoreService(
        root_dir=workflow_root,
        tool_registry=registry,
        storage_base_dir=workflow_storage_base,
    )
    workflow_store_cache: dict[tuple[str, str], WorkflowStoreService] = {
        (str(workflow_root), str(workflow_storage_base)): workflow_store
    }
    workflow_store_initializer: Callable[[WorkflowStoreService], None] | None = None

    def _register_workflow_custom_tools(store: WorkflowStoreService) -> None:
        for workflow_info in store.list_workflows():
            custom_tools_root = store.workflow_tools_dir(workflow_info.id)
            if custom_tools_root.exists():
                registry.register_custom_tools_directory(custom_tools_root)

    def _current_workspace_service() -> WorkspaceService:
        workspace_service.settings = _live_settings()
        return workspace_service

    def _current_workflow_root() -> Path:
        current_workspace = _current_workspace_service().workspace_path()
        return config.workflow_root or current_workspace / "workflows"

    def _current_workflow_storage_base() -> Path:
        live_storage_path = normalize_workflow_storage_path(
            config.storage_path or Path(_live_settings().output_data_folder)
        )
        assert live_storage_path is not None
        return live_storage_path / "workflows"

    def _current_workflow_store() -> WorkflowStoreService:
        if config.workflow_store is not None:
            return workflow_store
        current_root = _current_workflow_root()
        current_storage_base = _current_workflow_storage_base()
        cache_key = (str(current_root), str(current_storage_base))
        cached = workflow_store_cache.get(cache_key)
        if cached is None:
            cached = WorkflowStoreService(
                root_dir=current_root,
                tool_registry=registry,
                storage_base_dir=current_storage_base,
            )
            workflow_store_cache[cache_key] = cached
            try:
                if workflow_store_initializer is not None:
                    workflow_store_initializer(cached)
            except Exception:
                workflow_store_cache.pop(cache_key, None)
                raise
            if hot_reload is not None:
                hot_reload.add_watch_root(current_root)
        return cached

    def _live_dev_mode() -> bool:
        if config.settings_store is not None:
            return config.settings_store.get().dev_mode
        return resolved_settings.dev_mode

    workflow_draft_service = WorkflowDraftService(
        _current_workflow_store,
        dev_mode_provider=_live_dev_mode,
        settings_provider=_live_settings,
    )
    nested_workflow_snapshot_service = NestedWorkflowSnapshotService(
        _current_workflow_store,
        fallback_storage_path_provider=lambda: resolved_storage_path,
        dev_mode_provider=_live_dev_mode,
        settings_provider=_live_settings,
    )
    workflow_move_recovery_service = WorkflowMoveRecoveryService(
        _current_workflow_store,
        nested_workflow_snapshot_service,
    )
    initialized_workflow_stores: set[tuple[str, str]] = set()

    def _initialize_workflow_store(store: WorkflowStoreService) -> None:
        key = (str(store.root_dir), str(store.storage_base_dir))
        if key in initialized_workflow_stores:
            return
        workflow_move_recovery_service.recover_pending_move()
        try:
            nested_workflow_snapshot_service.cleanup_orphaned_snapshots()
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                "Retained nested snapshot orphan cleanup failed at startup: %r",
                exc,
                exc_info=exc,
            )
        _register_workflow_custom_tools(store)
        initialized_workflow_stores.add(key)

    workflow_store_initializer = _initialize_workflow_store

    # Keep factory-only consumers compatible without exposing tools from an
    # identity whose durable move still needs startup recovery. The lifespan
    # path always performs the full recovery/cleanup/registration sequence.
    if workflow_store.pending_workflow_move() is None:
        _register_workflow_custom_tools(workflow_store)

    thumbnail_manager = config.thumbnail_manager or ThumbnailManager(
        cache_dir=resolved_storage_path / ".thumbnails",
        env_path=resolved_settings.thumbnail_env_path,
        connection_manager=ws_manager,
    )

    known = config.known_packages or KnownPackagesService.default()
    pypi = config.pypi_versions or PyPIVersionService()
    _owns_pypi = config.pypi_versions is None

    from bioimageflow.paths import get_tool_store_path

    tool_store_path = get_tool_store_path()

    if config.disable_hot_reload:
        hot_reload: ToolHotReloadService | None = None
    else:
        hot_reload = ToolHotReloadService(
            registry=registry,
            connection_manager=ws_manager,
        )

    if config.package_installer is not None:
        installer = config.package_installer
    else:
        installer = PypiPackageInstaller(
            tool_store=tool_store_path,
            registry=registry,
            pypi=pypi,
            hot_reload=hot_reload,
        )

    catalog = config.package_catalog or PackageCatalogService(
        registry=registry, known=known, pypi=pypi
    )
    tool_environment_service = config.tool_environment_service or ToolEnvironmentService(
        registry=registry,
        catalog=catalog,
        connection_manager=ws_manager,
    )

    if config.execution_manager is not None:
        execution_manager: Any = config.execution_manager
    else:
        settings_provider = (lambda: settings_store.get()) if settings_store is not None else None

        def _tool_environment_manager() -> Any | None:
            return getattr(tool_environment_service, "manager", None)

        execution_manager = ExecutionManager(
            event_bus=event_bus,
            tool_registry=registry,
            settings=resolved_settings,
            storage_path=resolved_storage_path,
            settings_provider=settings_provider,
            environment_manager_provider=_tool_environment_manager,
        )

    # Always instantiate a launcher (cheap config + state). The expensive
    # Conda solve is deferred to the first /napari/open call.
    napari_launcher = config.napari_launcher or NapariLauncher(
        napari_env_path=resolved_settings.napari_env_path,
        connection_manager=ws_manager,
    )

    editor_service = config.editor_service or EditorService(
        settings_provider=_live_settings,
    )

    ws_log_handler = None

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        # Settings must load before catalog.refresh() so any settings the
        # catalog might consult (tool_store_path, etc.) are in place.
        if config.settings_store is not None:
            await config.settings_store.load()
        current_workflow_store = _current_workflow_store()
        await asyncio.to_thread(_initialize_workflow_store, current_workflow_store)
        try:
            await asyncio.to_thread(ensure_agent_workspace_context, workspace_path)
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning(
                "Agent workspace context setup failed: %r",
                exc,
                exc_info=exc,
            )

        try:
            await catalog.refresh()
        except PackageNetworkError as exc:
            logging.getLogger(__name__).warning(
                "Initial PyPI refresh failed (%s); package list falls back to installed-only",
                exc,
            )
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning("Initial PyPI refresh crashed: %r", exc)

        nonlocal ws_log_handler
        if ws_manager is not None:
            loop = asyncio.get_running_loop()
            ws_manager._loop = loop
            ws_log_handler = attach_ws_log_handler(ws_manager, loop)

        # Hot-reload watcher starts AFTER the registry has been populated
        # by scan_tool_store() (which runs synchronously above) so the
        # observer never races the initial load.
        hot_reload_started = False
        if hot_reload is not None:
            try:
                await hot_reload.start(tool_store_path)
                hot_reload.add_watch_root(workflow_root)
                hot_reload_started = True
            except Exception as exc:  # noqa: BLE001
                logging.getLogger(__name__).warning(
                    "Tool hot-reload failed to start: %r",
                    exc,
                    exc_info=exc,
                )

        try:
            yield
        finally:
            # Napari shutdown FIRST: it may take up to 5s (kill timeout)
            # and must run before the WS log handler is detached so the
            # final environment_status: stopped event reaches clients.
            try:
                await napari_launcher.shutdown()
            except Exception as exc:  # noqa: BLE001
                logging.getLogger(__name__).exception(
                    "napari_launcher.shutdown() raised during lifespan: %r",
                    exc,
                )
            try:
                await thumbnail_manager.shutdown()
            except Exception as exc:  # noqa: BLE001
                logging.getLogger(__name__).exception(
                    "thumbnail_manager.shutdown() raised during lifespan: %r",
                    exc,
                )
            if hot_reload is not None and hot_reload_started:
                try:
                    await hot_reload.stop()
                except Exception:  # noqa: BLE001
                    logging.getLogger(__name__).warning(
                        "Tool hot-reload failed to stop cleanly",
                        exc_info=True,
                    )
            if ws_manager is not None:
                if ws_log_handler is not None:
                    logging.getLogger("bioimageflow").removeHandler(ws_log_handler)
                    logging.getLogger("wetlands").removeHandler(ws_log_handler)
                ws_manager._loop = None
            if config.settings_store is not None:
                await config.settings_store.flush()
            if _owns_pypi:
                await pypi.aclose()

    app = FastAPI(title="BioImageFlow Server", version="0.1.0", lifespan=_lifespan)

    workspace_mutation_request_lock = asyncio.Lock()

    @app.middleware("http")
    async def pending_workflow_move_fence(request: Request, call_next: Any) -> Any:
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"} or not (
            request.url.path.startswith("/api/v1/")
        ):
            return await call_next(request)
        async with workspace_mutation_request_lock:
            try:
                _current_workflow_store().ensure_workflow_mutations_available()
            except WorkflowMoveRecoveryError as exc:
                body = ErrorResponse(
                    error="workflow_move_recovery_required",
                    detail=str(exc),
                )
                return JSONResponse(status_code=503, content=body.model_dump())
            return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_private_network=True,
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        # Routers may pass `detail` as a dict {"error": "<code>", "detail": "..."}
        # to override the default code mapping (e.g., "path_traversal" on 400).
        detail_obj: object = exc.detail
        if isinstance(detail_obj, dict):
            detail_dict = cast(dict[str, Any], detail_obj)
            if "error" in detail_dict:
                body = ErrorResponse(
                    error=detail_dict["error"],
                    detail=str(detail_dict.get("detail", "")),
                    field=detail_dict.get("field"),
                )
            else:
                error_code = _STATUS_TO_ERROR.get(exc.status_code, "error")
                body = ErrorResponse(
                    error=error_code,
                    detail=str(exc.detail),
                )
        else:
            error_code = _STATUS_TO_ERROR.get(exc.status_code, "error")
            body = ErrorResponse(
                error=error_code,
                detail=str(exc.detail),
            )
        _log_http_exception(request, exc, body)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(WorkflowMoveRecoveryError)
    async def workflow_move_recovery_exception_handler(
        request: Request,
        exc: WorkflowMoveRecoveryError,
    ) -> JSONResponse:
        return await http_exception_handler(
            request,
            HTTPException(
                status_code=503,
                detail=cast(
                    Any,
                    {
                        "error": "workflow_move_recovery_required",
                        "detail": str(exc),
                    },
                ),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        # Use the first error's location as the field hint
        first = errors[0] if errors else {}
        loc = first.get("loc", ())
        field_name = ".".join(str(part) for part in loc) if loc else None
        detail = first.get("msg", "Validation error")
        body = ErrorResponse(
            error="validation_error",
            detail=detail,
            field=field_name,
        )
        return JSONResponse(status_code=422, content=body.model_dump())

    # ---- WebSocket layer ------------------------------------------------
    if ws_manager is not None:
        register_ws(
            app,
            ws_manager,
            status_provider=execution_manager.get_status
            if hasattr(execution_manager, "get_status")
            else None,
        )
        app.state.connection_manager = ws_manager

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(tools_router, prefix="/api/v1")
    if config.enable_dev_router:
        app.include_router(dev_router, prefix="/api/v1")
    app.include_router(filesystem_router, prefix="/api/v1")
    app.include_router(editor_router, prefix="/api/v1")
    app.include_router(graph_router, prefix="/api/v1")
    app.include_router(datasets_router, prefix="/api/v1")
    app.include_router(execution_router, prefix="/api/v1")
    app.include_router(nested_workflow_snapshots_router, prefix="/api/v1")
    app.include_router(workspace_router, prefix="/api/v1")
    app.include_router(workflow_draft_operations_router, prefix="/api/v1")
    app.include_router(workflow_drafts_router, prefix="/api/v1")
    app.include_router(workflows_router, prefix="/api/v1")
    app.include_router(napari_router, prefix="/api/v1")
    app.include_router(nodes_router, prefix="/api/v1")
    app.include_router(data_table_router, prefix="/api/v1")
    app.state.napari_launcher = napari_launcher
    app.dependency_overrides[get_napari_launcher] = lambda: napari_launcher
    if config.settings_store is not None:
        app.include_router(settings_router, prefix="/api/v1")
        app.dependency_overrides[settings_get_store] = lambda: config.settings_store

    # ---- Wire dependency overrides from config ----
    app.dependency_overrides[get_tool_registry] = lambda: registry
    app.dependency_overrides[dev_get_tool_registry] = lambda: registry
    app.dependency_overrides[dev_get_result_store] = lambda: result_store
    app.dependency_overrides[graph_get_tool_registry] = lambda: registry
    app.dependency_overrides[graph_get_storage_path] = lambda: resolved_storage_path
    app.dependency_overrides[graph_get_execution_manager] = lambda: execution_manager
    app.dependency_overrides[graph_get_workflow_store] = _current_workflow_store
    app.dependency_overrides[execution_get_manager] = lambda: execution_manager
    app.dependency_overrides[execution_get_storage_path] = lambda: resolved_storage_path
    app.dependency_overrides[execution_get_tool_registry] = lambda: registry
    app.dependency_overrides[execution_get_workflow_store] = _current_workflow_store
    app.dependency_overrides[execution_get_workflow_draft_service] = lambda: workflow_draft_service
    app.dependency_overrides[execution_get_dev_mode] = _live_dev_mode
    app.dependency_overrides[execution_get_settings] = _live_settings
    app.dependency_overrides[workflows_get_workflow_store] = _current_workflow_store
    app.dependency_overrides[workflows_get_nested_snapshot_service] = lambda: (
        nested_workflow_snapshot_service
    )
    app.dependency_overrides[get_workspace_service] = _current_workspace_service
    app.dependency_overrides[tools_get_workflow_store] = _current_workflow_store
    app.dependency_overrides[workflows_get_execution_manager] = lambda: execution_manager
    app.dependency_overrides[workflows_get_connection_manager] = lambda: ws_manager
    app.dependency_overrides[get_workflow_draft_service] = lambda: workflow_draft_service
    app.dependency_overrides[get_nested_workflow_snapshot_service] = lambda: (
        nested_workflow_snapshot_service
    )
    app.dependency_overrides[nested_snapshots_get_execution_manager] = lambda: execution_manager
    app.dependency_overrides[workflow_drafts_get_execution_manager] = lambda: execution_manager
    app.dependency_overrides[workflow_drafts_get_connection_manager] = lambda: ws_manager
    app.dependency_overrides[get_workflow_draft_operations_service] = lambda: workflow_draft_service
    app.dependency_overrides[workflow_draft_operations_get_tool_registry] = lambda: registry
    app.dependency_overrides[workflow_draft_operations_get_execution_manager] = lambda: (
        execution_manager
    )
    app.dependency_overrides[workflow_draft_operations_get_connection_manager] = lambda: ws_manager

    app.dependency_overrides[graph_get_dev_mode] = _live_dev_mode
    app.dependency_overrides[graph_get_settings] = _live_settings
    app.dependency_overrides[get_editor_service] = lambda: editor_service
    app.dependency_overrides[get_result_store] = lambda: result_store
    app.dependency_overrides[napari_get_result_store] = lambda: result_store
    app.dependency_overrides[napari_get_workflow_store] = _current_workflow_store
    app.dependency_overrides[get_thumbnail_manager] = lambda: thumbnail_manager
    app.dependency_overrides[nodes_get_workflow_store] = _current_workflow_store

    app.dependency_overrides[get_workflow_root] = _current_workflow_root

    app.dependency_overrides[get_deployment_mode] = lambda: config.deployment_mode
    app.dependency_overrides[get_unsafe_webapp_features_enabled] = lambda: (
        _live_settings().enable_unsafe_webapp_features
    )
    app.dependency_overrides[get_package_installer] = lambda: installer
    app.dependency_overrides[get_known_packages] = lambda: known
    app.dependency_overrides[get_package_catalog] = lambda: catalog
    app.dependency_overrides[get_tool_environment_service] = lambda: tool_environment_service

    # Datasets router needs both values present; fall back to Settings-derived
    # defaults when AppConfig leaves them unset so bare `create_app()` (e.g.
    # `uvicorn ... --factory`) produces a working server.
    datasets_root = (
        config.datasets_root if config.datasets_root is not None else get_home() / "datasets"
    )
    max_upload_size = (
        config.max_upload_size if config.max_upload_size is not None else _DEFAULT_MAX_UPLOAD_SIZE
    )
    app.dependency_overrides[get_datasets_root] = lambda: datasets_root
    app.dependency_overrides[get_max_upload_size] = lambda: max_upload_size

    # ---- Static file serving (production desktop mode) ----
    if config.static_dir is not None:
        static_dir = config.static_dir
        assets_dir = static_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static-assets")

        index_html = static_dir / "index.html"
        if index_html.is_file():

            @app.get("/{full_path:path}")
            async def spa_fallback(full_path: str) -> FileResponse:
                return FileResponse(str(index_html))
        else:
            logging.getLogger(__name__).warning(
                "index.html not found at %s; SPA fallback disabled", index_html
            )

    return app
