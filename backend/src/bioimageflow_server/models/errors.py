"""Error response models."""

from typing import TypeVar

from pydantic import BaseModel, ConfigDict

HTTP_EXCEPTION_LOGGED_ATTR = "_bioimageflow_logged"
_ExceptionT = TypeVar("_ExceptionT", bound=Exception)


class ErrorResponse(BaseModel):
    """Standardized error response format.

    The ``error`` field is a short snake_case code (e.g. ``graph_locked``,
    ``execution_running``) and ``detail`` is the human-readable message.
    See platform_specs_v1 §2.4.1b.
    """

    model_config = ConfigDict(extra="forbid")

    error: str
    detail: str
    field: str | None = None


def mark_exception_logged(exc: _ExceptionT) -> _ExceptionT:
    """Mark an exception whose operational context has already been logged."""
    setattr(exc, HTTP_EXCEPTION_LOGGED_ATTR, True)
    return exc


def exception_was_logged(exc: Exception) -> bool:
    return bool(getattr(exc, HTTP_EXCEPTION_LOGGED_ATTR, False))
