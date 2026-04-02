"""Error response models."""

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standardized error response format."""

    error: str
    detail: str
    field: str | None = None
