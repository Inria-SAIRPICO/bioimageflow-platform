"""Health check router."""

from fastapi import APIRouter

from bioimageflow_server.version import get_application_version

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": get_application_version()}
