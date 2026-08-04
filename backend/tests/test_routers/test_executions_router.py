from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from bioimageflow_server.models.execution_runtime import (
    ExecutionSnapshot,
    RetryPlanPresentation,
)
from bioimageflow_server.routers.executions import (
    _execution_http_error,
    get_download_destination_resolver,
    get_execution_coordinator,
    preflight_router,
    router,
)
from bioimageflow_server.services.execution_registry import ExecutionRegistry
from bioimageflow_server.services.execution_runtime import ExecutionCoordinator
from bioimageflow_server.services.execution_runtime import ExecutionOperationError


def _app(coordinator: ExecutionCoordinator) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.include_router(preflight_router, prefix="/api/v1")
    app.dependency_overrides[get_execution_coordinator] = lambda: coordinator
    return app


@pytest.mark.anyio
async def test_plural_execution_listing_and_id_specific_inspection(tmp_path: Path) -> None:
    registry = ExecutionRegistry(tmp_path)
    saved = None
    for index in range(3):
        saved = registry.save(
            ExecutionSnapshot(
                execution_id=f"run_{index:032x}",
                workflow_id="demo",
                backend="submitted_local",
                target_id="local-parsl",
                state="succeeded",
            )
        )
    assert saved is not None
    coordinator = ExecutionCoordinator(registry, reconnector=lambda snapshot: None)  # type: ignore[arg-type,return-value]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(coordinator)),
        base_url="http://test",
    ) as client:
        listing = await client.get(
            "/api/v1/executions",
            params={"workflow_id": "demo", "offset": 1, "limit": 1},
        )
        detail = await client.get(f"/api/v1/executions/{saved.execution_id}")
        missing = await client.get("/api/v1/executions/run_missing")

    assert listing.status_code == 200
    assert listing.json()["total"] == 3
    assert listing.json()["offset"] == 1
    assert listing.json()["limit"] == 1
    assert len(listing.json()["items"]) == 1
    assert set(listing.json()["items"][0]["actions"]) == {
        "cancel",
        "retry",
        "recompute",
        "download_results",
    }
    assert detail.status_code == 200
    assert detail.json()["revision"] == 0
    assert missing.status_code == 404


@pytest.mark.anyio
async def test_retry_plan_and_confirmation_use_locked_request_shapes(tmp_path: Path) -> None:
    parent_id = "run_0123456789abcdef0123456789abcdef"
    digest = "sha256:" + "1" * 64
    calls: list[tuple[str, object]] = []
    parent = ExecutionSnapshot(
        execution_id=parent_id,
        workflow_id="demo",
        backend="submitted_local",
        target_id="profile",
        state="failed",
    )

    class _Coordinator:
        async def plan_retry(self, execution_id: str, *, node_paths=None, cascade=True):
            calls.append(("plan", (execution_id, node_paths, cascade)))
            return RetryPlanPresentation(
                plan_digest=digest,
                parent_execution_id=parent_id,
                child_execution_id="run_abcdef0123456789abcdef0123456789",
                mode="retry",
                target={"id": "profile", "label": "Cluster", "mode": "submitted_local"},
                recompute=None,
                invalidations=[],
                conflicting_run_ids=[],
                confirmable=True,
            )

        async def confirm_retry(self, execution_id: str, *, plan_digest: str):
            calls.append(("confirm", (execution_id, plan_digest)))
            return parent

    app = _app(_Coordinator())  # type: ignore[arg-type]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        plan_response = await client.post(
            f"/api/v1/executions/{parent_id}/retry/plan",
            json={"recompute": None},
        )
        confirm_response = await client.post(
            f"/api/v1/executions/{parent_id}/retry",
            json={"plan_digest": digest},
        )
        legacy_response = await client.post(
            f"/api/v1/executions/{parent_id}/retry",
            json={"plan_digest": digest, "target_id": "other"},
        )

    assert plan_response.status_code == 200
    assert set(plan_response.json()["target"]) == {"id", "label", "mode"}
    assert confirm_response.status_code == 202
    assert legacy_response.status_code == 422
    assert calls == [
        ("plan", (parent_id, None, True)),
        ("confirm", (parent_id, digest)),
    ]


@pytest.mark.parametrize(
    ("code", "status", "retryable"),
    [
        ("retry-plan-not-found", 404, False),
        ("invalid-recompute-request", 422, False),
        ("ssh-timeout", 503, True),
        ("workflow-run-retry-error", 409, False),
        ("workflow-result-export-error", 500, False),
    ],
)
def test_execution_errors_have_structured_status_and_retryability(
    code: str,
    status: int,
    retryable: bool,
) -> None:
    error = _execution_http_error(
        ExecutionOperationError(code, "failed", details={"run_id": "run-id"})
    )

    assert error.status_code == status
    assert error.detail == {
        "error": code,
        "detail": "failed",
        "details": {"run_id": "run-id", "retryable": retryable},
    }


@pytest.mark.anyio
async def test_result_download_has_no_client_destination_body(tmp_path: Path) -> None:
    execution_id = "run_0123456789abcdef0123456789abcdef"
    calls: list[tuple[str, Path]] = []
    archive = tmp_path / "result.zip"
    archive.write_bytes(b"zip")

    class _Coordinator:
        async def download_result(self, run_id: str, destination: Path) -> Path:
            calls.append((run_id, destination))
            return archive

    class _Destinations:
        def resolve(self, run_id: str) -> Path:
            return tmp_path / "managed" / run_id

    app = _app(_Coordinator())  # type: ignore[arg-type]
    app.dependency_overrides[get_download_destination_resolver] = _Destinations
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(f"/api/v1/executions/{execution_id}/result")

    assert response.status_code == 200
    assert response.content == b"zip"
    assert calls == [(execution_id, tmp_path / "managed" / execution_id)]
