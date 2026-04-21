"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

from bioimageflow_server.models.errors import ErrorResponse
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
    get_tool_registry as graph_get_tool_registry,
    router as graph_router,
)
from bioimageflow_server.routers.health import router as health_router
from bioimageflow_server.routers.tools import (
    get_deployment_mode,
    get_package_installer,
    get_tool_registry,
    get_workflow_root,
    router as tools_router,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService

_STATUS_TO_ERROR: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    423: "locked",
    500: "internal_server_error",
}


def create_app(config: AppConfig | None = None) -> FastAPI:
    if config is None:
        config = AppConfig()
    app = FastAPI(title="BioImageFlow Server", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
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

    # ---- Wire dependency overrides from config ----
    registry = config.tool_registry or ToolRegistryService()
    if config.tool_registry is None:
        registry.scan_tool_store()
    app.dependency_overrides[get_tool_registry] = lambda: registry
    app.dependency_overrides[dev_get_tool_registry] = lambda: registry
    app.dependency_overrides[graph_get_tool_registry] = lambda: registry

    if config.workflow_root is not None:
        app.dependency_overrides[get_workflow_root] = lambda: config.workflow_root

    app.dependency_overrides[get_deployment_mode] = lambda: config.deployment_mode

    if config.package_installer is not None:
        app.dependency_overrides[get_package_installer] = lambda: config.package_installer

    if config.datasets_root is not None:
        app.dependency_overrides[get_datasets_root] = lambda: config.datasets_root
    if config.max_upload_size is not None:
        app.dependency_overrides[get_max_upload_size] = lambda: config.max_upload_size

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
            import logging

            logging.getLogger(__name__).warning(
                "index.html not found at %s; SPA fallback disabled", index_html
            )

    return app
