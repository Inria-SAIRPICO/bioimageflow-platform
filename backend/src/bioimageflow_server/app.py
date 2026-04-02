"""FastAPI application factory."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from bioimageflow_server.models.errors import ErrorResponse
from bioimageflow_server.routers.health import router as health_router

_STATUS_TO_ERROR: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    500: "internal_server_error",
}


def create_app(settings=None) -> FastAPI:
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

    app.include_router(health_router)

    return app
