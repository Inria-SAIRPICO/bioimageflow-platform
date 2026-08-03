from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from bioimageflow_server.models.execution_runtime import ExecutionSnapshot
from bioimageflow_server.routers.executions import (
    get_execution_coordinator,
    preflight_router,
    router,
)
from bioimageflow_server.services.execution_registry import ExecutionRegistry
from bioimageflow_server.services.execution_runtime import ExecutionCoordinator


def _app(coordinator: ExecutionCoordinator) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.include_router(preflight_router, prefix="/api/v1")
    app.dependency_overrides[get_execution_coordinator] = lambda: coordinator
    return app


@pytest.mark.anyio
async def test_plural_execution_listing_and_id_specific_inspection(tmp_path: Path) -> None:
    registry = ExecutionRegistry(tmp_path)
    saved = registry.save(
        ExecutionSnapshot(
            execution_id="run_0123456789abcdef0123456789abcdef",
            workflow_id="demo",
            backend="submitted_local",
            target_id="local-parsl",
            state="succeeded",
        )
    )
    coordinator = ExecutionCoordinator(registry, reconnector=lambda snapshot: None)  # type: ignore[arg-type,return-value]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(coordinator)),
        base_url="http://test",
    ) as client:
        listing = await client.get("/api/v1/executions", params={"workflow_id": "demo"})
        detail = await client.get(f"/api/v1/executions/{saved.execution_id}")
        missing = await client.get("/api/v1/executions/run_missing")

    assert listing.status_code == 200
    assert listing.json()["items"][0]["execution_id"] == saved.execution_id
    assert detail.status_code == 200
    assert detail.json()["revision"] == 0
    assert missing.status_code == 404
