"""Error response models."""

from pydantic import BaseModel, ConfigDict


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
