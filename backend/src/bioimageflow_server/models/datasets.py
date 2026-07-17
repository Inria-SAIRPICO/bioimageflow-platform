"""Dataset API models (v1 §2.4.10)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Dataset(BaseModel):
    """A stored dataset as returned by `GET /datasets`."""

    id: str
    original_filename: str
    display_name: str
    path: str
    size: int
    upload_date: str
    content_type: str | None = None
    folder_id: str | None = None


class UploadedFile(BaseModel):
    """A successfully-stored file, inside `UploadResponse.uploaded`."""

    id: str
    original_filename: str
    display_name: str
    path: str
    size: int
    upload_date: str
    content_type: str | None = None
    folder_id: str | None = None


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

    uploaded: list[UploadedFile] = Field(default_factory=list)
    errors: list[UploadError] = Field(default_factory=list)


class DatasetFolder(BaseModel):
    id: str
    name: str
    parent_id: str | None = None
    created_at: str


class FolderCreate(BaseModel):
    name: str
    parent_id: str | None = None


class FolderUpdate(BaseModel):
    name: str | None = None
    parent_id: str | None = None


class DatasetUpdate(BaseModel):
    display_name: str | None = None
    folder_id: str | None = None


class DatasetSelection(BaseModel):
    dataset_ids: list[str] = Field(default_factory=list)
    folder_ids: list[str] = Field(default_factory=list)


class DeleteSelectionRequest(DatasetSelection):
    expected_revision: int


class DeletePreviewResponse(BaseModel):
    revision: int
    dataset_count: int
    folder_count: int


class DeleteSelectionResponse(BaseModel):
    deleted_dataset_ids: list[str] = Field(default_factory=list)
    deleted_folder_ids: list[str] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)
