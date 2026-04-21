"""Dataset API models (v1 §2.4.10)."""

from __future__ import annotations

from pydantic import BaseModel


class Dataset(BaseModel):
    """A stored dataset as returned by `GET /datasets`."""

    id: str
    original_filename: str
    path: str
    size: int
    upload_date: str
    content_type: str | None = None


class UploadedFile(BaseModel):
    """A successfully-stored file, inside `UploadResponse.uploaded`."""

    id: str
    original_filename: str
    path: str
    size: int
    upload_date: str
    content_type: str | None = None


class UploadError(BaseModel):
    """A per-file upload failure, inside `UploadResponse.errors`.

    Distinct from the top-level `ErrorResponse` (which is used only for
    request-level failures like 400 / 413 / 404).
    """

    filename: str
    error: str
    detail: str


class UploadResponse(BaseModel):
    """Response body for `POST /datasets/upload`."""

    uploaded: list[UploadedFile] = []
    errors: list[UploadError] = []
