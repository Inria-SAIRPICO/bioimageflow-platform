"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

from bioimageflow.paths import get_home
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

from bioimageflow_server.models.errors import ErrorResponse
from bioimageflow_server.models.settings import _DEFAULT_MAX_UPLOAD_SIZE
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.routers.dev import (
    get_tool_registry as dev_get_tool_registry,
    router as dev_router,
)
from bioimageflow_server.routers.datasets import (
    get_datasets_root,
    get_max_upload_size,
    router as datasets_router,
)
from bioimageflow_server.routers.filesystem import router as filesystem_router
from bioimageflow_server.routers.graph import (
    get_dev_mode as graph_get_dev_mode,
    get_execution_manager as graph_get_execution_manager,
    get_session_manager as graph_get_session_manager,
    get_storage_path as graph_get_storage_path,
    get_tool_registry as graph_get_tool_registry,
    router as graph_router,
)
from bioimageflow_server.routers.execution import (
    get_execution_manager as execution_get_manager,
    get_storage_path as execution_get_storage_path,
    get_tool_registry as execution_get_tool_registry,
    router as execution_router,
)
from bioimageflow_server.routers.health import router as health_router
from bioimageflow_server.routers.tools import (
    get_deployment_mode,
    get_package_catalog,
    get_package_installer,
    get_tool_registry,
    get_workflow_root,
    router as tools_router,
)
from bioimageflow_server.services.known_packages import KnownPackagesService
from bioimageflow_server.services.session_manager import SessionManager
from bioimageflow_server.services.package_catalog import PackageCatalogService
from bioimageflow_server.services.package_installer import (
    PackageNetworkError,
    PypiPackageInstaller,
)
from bioimageflow_server.services.pypi_versions import PyPIVersionService
from bioimageflow_server.services.tool_registry import ToolRegistryService

_STATUS_TO_ERROR: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "file_too_large",
    422: "validation_error",
    423: "locked",
    500: "internal_server_error",
}


def create_app(config: AppConfig | None = None) -> FastAPI:
    if config is None:
        config = AppConfig()

    # Build the package services graph up front so the lifespan hook can
    # close owned resources (e.g. the PyPI httpx client).
    registry = config.tool_registry or ToolRegistryService()
    if config.tool_registry is None:
        registry.scan_tool_store()

    session_manager = SessionManager()

    known = config.known_packages or KnownPackagesService.default()
    pypi = config.pypi_versions or PyPIVersionService()
    _owns_pypi = config.pypi_versions is None

    if config.package_installer is not None:
        installer = config.package_installer
    else:
        from bioimageflow.paths import get_tool_store_path

        installer = PypiPackageInstaller(
            tool_store=get_tool_store_path(),
            registry=registry,
            pypi=pypi,
        )

    catalog = config.package_catalog or PackageCatalogService(
        registry=registry, known=known, pypi=pypi
    )

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        try:
            await catalog.refresh()
        except PackageNetworkError as exc:
            logging.getLogger(__name__).warning(
                "Initial PyPI refresh failed (%s); package list falls back to installed-only",
                exc,
            )
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning(
                "Initial PyPI refresh crashed: %r", exc
            )
        try:
            yield
        finally:
            if _owns_pypi:
                await pypi.aclose()

    app = FastAPI(title="BioImageFlow Server", version="0.1.0", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

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

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(tools_router, prefix="/api/v1")
    app.include_router(dev_router, prefix="/api/v1")
    app.include_router(filesystem_router, prefix="/api/v1")
    app.include_router(graph_router, prefix="/api/v1")
    app.include_router(datasets_router, prefix="/api/v1")
    app.include_router(execution_router, prefix="/api/v1")

    # ---- Wire dependency overrides from config ----
    app.dependency_overrides[get_tool_registry] = lambda: registry
    app.dependency_overrides[dev_get_tool_registry] = lambda: registry
    app.dependency_overrides[graph_get_tool_registry] = lambda: registry
    app.dependency_overrides[graph_get_session_manager] = lambda: session_manager
    app.dependency_overrides[graph_get_storage_path] = lambda: config.storage_path
    app.dependency_overrides[graph_get_execution_manager] = (
        lambda: config.execution_manager
    )
    app.dependency_overrides[execution_get_manager] = (
        lambda: config.execution_manager
    )
    app.dependency_overrides[execution_get_storage_path] = lambda: config.storage_path
    app.dependency_overrides[execution_get_tool_registry] = lambda: registry
    _dev_mode = (
        config.settings.dev_mode if config.settings is not None else True
    )
    app.dependency_overrides[graph_get_dev_mode] = lambda: _dev_mode

    if config.workflow_root is not None:
        app.dependency_overrides[get_workflow_root] = lambda: config.workflow_root

    app.dependency_overrides[get_deployment_mode] = lambda: config.deployment_mode
    app.dependency_overrides[get_package_installer] = lambda: installer
    app.dependency_overrides[get_package_catalog] = lambda: catalog

    # Datasets router needs both values present; fall back to Settings-derived
    # defaults when AppConfig leaves them unset so bare `create_app()` (e.g.
    # `uvicorn ... --factory`) produces a working server.
    datasets_root = config.datasets_root if config.datasets_root is not None else get_home() / "datasets"
    max_upload_size = config.max_upload_size if config.max_upload_size is not None else _DEFAULT_MAX_UPLOAD_SIZE
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
