"""Health check router."""

import importlib.metadata

from fastapi import APIRouter

router = APIRouter()


def _get_version() -> str:
    try:
        return importlib.metadata.version("bioimageflow-server")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0-dev"


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": _get_version()}
