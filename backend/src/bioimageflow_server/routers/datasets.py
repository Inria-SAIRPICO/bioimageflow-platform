"""Datasets router — server-side dataset storage (v1 §2.4.10)."""

from __future__ import annotations

from collections.abc import AsyncIterable
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, UploadFile

from bioimageflow_server.models.datasets import (
    Dataset,
    DatasetFolder,
    DatasetSelection,
    DatasetUpdate,
    DeletePreviewResponse,
    DeleteSelectionRequest,
    DeleteSelectionResponse,
    FolderCreate,
    FolderUpdate,
    UploadedFile,
    UploadError,
    UploadResponse,
)
from bioimageflow_server.services.dataset_store import (
    CatalogConflictError,
    DatasetNotFoundError,
    DatasetStore,
    FileTooLargeError,
    FolderNotFoundError,
    InvalidMoveError,
    NameConflictError,
    PathTraversalError,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])


# Defence-in-depth: reject multipart bodies whose declared size is clearly
# implausible (any pathological client trying to DoS the server). The
# authoritative per-file enforcement is inside `DatasetStore.store()`.
MAX_FILES_PER_REQUEST = 32


# ---------------------------------------------------------------------------
# Dependency stubs – overridden via app.dependency_overrides in create_app()
# ---------------------------------------------------------------------------


def get_datasets_root() -> Path | None:  # pragma: no cover
    return None


def get_max_upload_size() -> int | None:  # pragma: no cover
    return None


def get_dataset_store(
    datasets_root: Path | None = Depends(get_datasets_root),
    max_upload_size: int | None = Depends(get_max_upload_size),
) -> DatasetStore:
    if datasets_root is None or max_upload_size is None:
        raise HTTPException(
            status_code=500, detail="datasets service not configured"
        )
    return DatasetStore(datasets_root=datasets_root, max_upload_size=max_upload_size)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_datasets(
    store: DatasetStore = Depends(get_dataset_store),
) -> list[Dataset]:
    return [
        Dataset(
            id=d.id,
            original_filename=d.original_filename,
            display_name=d.display_name,
            path=d.path,
            size=d.size,
            upload_date=d.upload_date,
            content_type=d.content_type,
            folder_id=d.folder_id,
        )
        for d in store.list()
    ]


def _check_content_length(
    request: Request,
    store: DatasetStore = Depends(get_dataset_store),
) -> DatasetStore:
    """Defence-in-depth DoS guard. Runs before FastAPI parses the body."""
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            length = int(declared)
        except ValueError:
            length = 0
        cap = store.max_upload_size * MAX_FILES_PER_REQUEST
        if length > cap:
            raise HTTPException(
                status_code=413,
                detail=f"request body exceeds {cap} bytes",
            )
    return store


@router.post("/upload")
async def upload_datasets(
    files: list[UploadFile],
    folder_id: str | None = Form(default=None),
    store: DatasetStore = Depends(_check_content_length),
) -> UploadResponse:
    uploaded: list[UploadedFile] = []
    errors: list[UploadError] = []

    for upload in files:
        filename = upload.filename or "unnamed"
        try:
            record = await store.store(filename, _chunks(upload), folder_id=folder_id)
        except FileTooLargeError as exc:
            errors.append(
                UploadError(
                    filename=filename, error="file_too_large", detail=str(exc)
                )
            )
        except PathTraversalError as exc:
            errors.append(
                UploadError(
                    filename=filename, error="path_traversal", detail=str(exc)
                )
            )
        except FolderNotFoundError as exc:
            errors.append(
                UploadError(
                    filename=filename, error="folder_not_found", detail=str(exc)
                )
            )
        except (ValueError, OSError) as exc:
            errors.append(
                UploadError(filename=filename, error="invalid_file", detail=str(exc))
            )
        else:
            uploaded.append(
                UploadedFile(
                    id=record.id,
                    original_filename=record.original_filename,
                    display_name=record.display_name,
                    path=record.path,
                    size=record.size,
                    upload_date=record.upload_date,
                    content_type=record.content_type,
                    folder_id=record.folder_id,
                )
            )
        finally:
            await upload.close()

    return UploadResponse(uploaded=uploaded, errors=errors)


def _dataset_model(record: object) -> Dataset:
    return Dataset.model_validate(record, from_attributes=True)


def _folder_model(record: object) -> DatasetFolder:
    return DatasetFolder.model_validate(record, from_attributes=True)


def _catalog_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (DatasetNotFoundError, FolderNotFoundError)):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, NameConflictError):
        return HTTPException(
            status_code=409,
            detail={"error": "name_conflict", "detail": str(exc)},
        )
    if isinstance(exc, InvalidMoveError):
        return HTTPException(
            status_code=409,
            detail={"error": "invalid_move", "detail": str(exc)},
        )
    if isinstance(exc, CatalogConflictError):
        return HTTPException(
            status_code=409,
            detail={"error": "catalog_conflict", "detail": str(exc)},
        )
    return HTTPException(status_code=422, detail=str(exc))


@router.get("/folders")
async def list_folders(
    store: DatasetStore = Depends(get_dataset_store),
) -> list[DatasetFolder]:
    return [_folder_model(folder) for folder in store.list_folders()]


@router.post("/folders", status_code=201)
async def create_folder(
    body: FolderCreate,
    store: DatasetStore = Depends(get_dataset_store),
) -> DatasetFolder:
    try:
        return _folder_model(store.create_folder(body.name, body.parent_id))
    except (ValueError, FolderNotFoundError, NameConflictError) as exc:
        raise _catalog_error(exc) from exc


@router.patch("/folders/{folder_id}")
async def update_folder(
    folder_id: str,
    body: FolderUpdate,
    store: DatasetStore = Depends(get_dataset_store),
) -> DatasetFolder:
    kwargs: dict[str, object] = {}
    if "name" in body.model_fields_set:
        kwargs["name"] = body.name
    if "parent_id" in body.model_fields_set:
        kwargs["parent_id"] = body.parent_id
    try:
        return _folder_model(store.update_folder(folder_id, **kwargs))
    except (ValueError, FolderNotFoundError, NameConflictError, InvalidMoveError) as exc:
        raise _catalog_error(exc) from exc


@router.patch("/{dataset_id}")
async def update_dataset(
    dataset_id: str,
    body: DatasetUpdate,
    store: DatasetStore = Depends(get_dataset_store),
) -> Dataset:
    kwargs: dict[str, object] = {}
    if "display_name" in body.model_fields_set:
        kwargs["display_name"] = body.display_name
    if "folder_id" in body.model_fields_set:
        kwargs["folder_id"] = body.folder_id
    try:
        return _dataset_model(store.update_dataset(dataset_id, **kwargs))
    except (ValueError, DatasetNotFoundError, FolderNotFoundError, NameConflictError) as exc:
        raise _catalog_error(exc) from exc


@router.post("/actions/resolve")
async def resolve_selection(
    body: DatasetSelection,
    store: DatasetStore = Depends(get_dataset_store),
) -> list[Dataset]:
    try:
        return [
            _dataset_model(dataset)
            for dataset in store.resolve_selection(body.dataset_ids, body.folder_ids)
        ]
    except (DatasetNotFoundError, FolderNotFoundError) as exc:
        raise _catalog_error(exc) from exc


@router.post("/actions/delete-preview")
async def preview_delete(
    body: DatasetSelection,
    store: DatasetStore = Depends(get_dataset_store),
) -> DeletePreviewResponse:
    try:
        return DeletePreviewResponse.model_validate(
            store.preview_delete(body.dataset_ids, body.folder_ids),
            from_attributes=True,
        )
    except (DatasetNotFoundError, FolderNotFoundError) as exc:
        raise _catalog_error(exc) from exc


@router.post("/actions/delete")
async def delete_selection(
    body: DeleteSelectionRequest,
    store: DatasetStore = Depends(get_dataset_store),
) -> DeleteSelectionResponse:
    try:
        return DeleteSelectionResponse.model_validate(
            store.delete_selection(
                body.dataset_ids,
                body.folder_ids,
                expected_revision=body.expected_revision,
            ),
            from_attributes=True,
        )
    except (DatasetNotFoundError, FolderNotFoundError, CatalogConflictError) as exc:
        raise _catalog_error(exc) from exc


@router.delete(
    "/{dataset_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
)
async def delete_dataset(
    dataset_id: str,
    store: DatasetStore = Depends(get_dataset_store),
) -> Response:
    try:
        store.delete(dataset_id)
    except PathTraversalError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "path_traversal", "detail": str(exc)},
        ) from exc
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _chunks(upload: UploadFile, chunk_size: int = 1024 * 1024) -> AsyncIterable[bytes]:
    """Yield chunks from an UploadFile in a streaming fashion."""
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            return
        yield chunk
