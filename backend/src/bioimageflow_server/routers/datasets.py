"""Datasets router — server-side dataset storage (v1 §2.4.10)."""

from __future__ import annotations

from collections.abc import AsyncIterable
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile

from bioimageflow_server.models.datasets import (
    Dataset,
    UploadedFile,
    UploadError,
    UploadResponse,
)
from bioimageflow_server.services.dataset_store import (
    DatasetNotFoundError,
    DatasetStore,
    FileTooLargeError,
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
            path=d.path,
            size=d.size,
            upload_date=d.upload_date,
            content_type=d.content_type,
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
    store: DatasetStore = Depends(_check_content_length),
) -> UploadResponse:
    uploaded: list[UploadedFile] = []
    errors: list[UploadError] = []

    for upload in files:
        filename = upload.filename or "unnamed"
        try:
            record = await store.store(filename, _chunks(upload))
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
        except (ValueError, OSError) as exc:
            errors.append(
                UploadError(filename=filename, error="invalid_file", detail=str(exc))
            )
        else:
            uploaded.append(
                UploadedFile(
                    id=record.id,
                    original_filename=record.original_filename,
                    path=record.path,
                    size=record.size,
                    upload_date=record.upload_date,
                    content_type=record.content_type,
                )
            )
        finally:
            await upload.close()

    return UploadResponse(uploaded=uploaded, errors=errors)


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
