from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from bioimageflow_server.models.execution_runtime import (
    ExecutionSnapshot,
    RecomputeSelection,
    RetryPlanPresentation,
)
from bioimageflow_server.routers.executions import (
    _execution_http_error,
    get_download_destination_resolver,
    get_execution_coordinator,
    get_preflight_service,
    get_prepared_run_registrar,
    preflight_router,
    router,
)
from bioimageflow_server.services.execution_registry import ExecutionRegistry
from bioimageflow_server.services.execution_runtime import (
    ExecutionCoordinator,
    ExecutionOperationError,
    SubmittedRunAdapter,
    _operation_error,
)


pytestmark = pytest.mark.campaign_excluded(reason="distributed-engine")


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
                backend="managed_remote",
                target_id="cluster",
                profile_id="profile_" + "1" * 32,
                profile_revision=3,
                target_snapshot={
                    "name": "Managed cluster",
                    "mode": "managed_remote",
                },
                reconnect={
                    "host": "secret-cluster",
                    "root": "/secret/run",
                    "run_id": "private-run",
                },
                backend_metadata={
                    "scheduler_job_id": "scheduler-42",
                    "retry_plan_digest": "sha256:" + "f" * 64,
                },
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
        "cleanup",
    }
    assert listing.json()["items"][0]["target_label"] == "Managed cluster"
    assert listing.json()["items"][0]["target_mode"] == "managed_remote"
    assert listing.json()["items"][0]["scheduler_job_id"] == "scheduler-42"
    assert detail.status_code == 200
    assert detail.json()["revision"] == 0
    forbidden = {
        "reconnect",
        "target_snapshot",
        "backend_metadata",
        "profile_id",
        "profile_revision",
        "graph_fingerprint",
        "result_export",
    }
    assert forbidden.isdisjoint(listing.json()["items"][0])
    assert forbidden.isdisjoint(detail.json())
    assert "secret-cluster" not in listing.text
    assert "/secret/run" not in detail.text
    assert missing.status_code == 404


def test_execution_openapi_uses_public_presentation_without_durable_fields(
    tmp_path: Path,
) -> None:
    coordinator = ExecutionCoordinator(
        ExecutionRegistry(tmp_path),
        reconnector=lambda snapshot: None,  # type: ignore[arg-type,return-value]
    )
    schema = _app(coordinator).openapi()
    properties = schema["components"]["schemas"]["ExecutionPresentation"]["properties"]

    assert {"target_label", "target_mode", "scheduler_job_id"} <= properties.keys()
    assert {
        "reconnect",
        "target_snapshot",
        "backend_metadata",
        "profile_id",
        "profile_revision",
    }.isdisjoint(properties)
    assert "logs" not in properties
    assert not any(path.endswith("/logs") for path in schema["paths"])
    listing_schema = schema["paths"]["/api/v1/executions"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert listing_schema["$ref"].endswith("/ExecutionPresentationPage")


@pytest.mark.anyio
async def test_remote_observation_is_allowlisted_before_registry_and_api(
    tmp_path: Path,
) -> None:
    class _SensitiveObservationHandle:
        status = "running"

        def refresh(self) -> None:
            return None

        def progress(self, *, after_sequence: int = 0) -> list[dict[str, object]]:
            return []

        def snapshot(self) -> dict[str, object]:
            return {
                "state": "running",
                "scheduler_job_id": "scheduler-42",
                "unknown": "must-disappear",
                "secret_token": "sensitive-value",
            }

        def diagnostics(self) -> tuple[object, ...]:
            return ()

    execution_id = "run_0123456789abcdef0123456789abcdef"
    registry = ExecutionRegistry(tmp_path)
    coordinator = ExecutionCoordinator(
        registry,
        reconnector=lambda snapshot: None,  # type: ignore[arg-type,return-value]
        poll_interval=60,
    )
    await coordinator.register(
        ExecutionSnapshot(
            execution_id=execution_id,
            workflow_id="demo",
            backend="managed_remote",
            target_id="cluster",
            state="prepared",
        ),
        SubmittedRunAdapter(_SensitiveObservationHandle()),
    )
    await coordinator._refresh_once(execution_id)

    persisted = registry.get(execution_id)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(coordinator)),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/executions/{execution_id}")
    await coordinator.close()

    assert persisted.backend_metadata == {
        "state": "running",
        "scheduler_job_id": "scheduler-42",
    }
    assert response.status_code == 200
    assert response.json()["scheduler_job_id"] == "scheduler-42"
    assert "sensitive-value" not in response.text
    assert "must-disappear" not in response.text


@pytest.mark.anyio
async def test_retry_plan_and_confirmation_use_locked_request_shapes(tmp_path: Path) -> None:
    parent_id = "run_0123456789abcdef0123456789abcdef"
    digest = "sha256:" + "1" * 64
    calls: list[tuple[str, object]] = []
    parent = ExecutionSnapshot(
        execution_id=parent_id,
        workflow_id="demo",
        backend="managed_remote",
        target_id="profile",
        state="failed",
    )

    class _Coordinator:
        async def plan_retry(self, execution_id: str, *, node_paths=None, cascade=True):
            calls.append(("plan", (execution_id, node_paths, cascade)))
            recompute = (
                None
                if node_paths is None
                else RecomputeSelection(node_paths=list(node_paths), cascade=cascade)
            )
            return RetryPlanPresentation(
                plan_digest=digest,
                parent_execution_id=parent_id,
                child_execution_id="run_abcdef0123456789abcdef0123456789",
                mode="recompute" if recompute is not None else "retry",
                target={"id": "profile", "label": "Cluster", "mode": "managed_remote"},
                recompute=recompute,
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
        recompute_response = await client.post(
            f"/api/v1/executions/{parent_id}/retry/plan",
            json={
                "recompute": {
                    "node_paths": ["preprocessing/masks"],
                    "cascade": False,
                }
            },
        )
        missing_shape_response = await client.post(
            f"/api/v1/executions/{parent_id}/retry/plan",
            json={},
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
    assert recompute_response.status_code == 200
    assert recompute_response.json()["recompute"] == {
        "node_paths": ["preprocessing/masks"],
        "cascade": False,
    }
    assert missing_shape_response.status_code == 422
    assert confirm_response.status_code == 202
    assert legacy_response.status_code == 422
    assert calls == [
        ("plan", (parent_id, None, True)),
        ("plan", (parent_id, ("preprocessing/masks",), False)),
        ("confirm", (parent_id, digest)),
    ]


@pytest.mark.parametrize(
    ("code", "status", "retryable"),
    [
        ("retry-plan-not-found", 404, False),
        ("cleanup-plan-not-found", 404, False),
        ("invalid-recompute-request", 422, False),
        ("invalid-retry", 422, False),
        ("ssh-timeout", 503, True),
        ("protocol-incompatible", 503, False),
        ("gateway-unavailable", 503, False),
        ("retry-conflict", 409, False),
        ("cleanup-conflict", 409, False),
        ("cleanup-plan-integrity-error", 409, False),
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


def test_public_cluster_diagnostic_drives_http_status_and_preserves_identity() -> None:
    from bioimageflow.cluster import ClusterDiagnostic, ClusterOperationError

    operation = _operation_error(
        ClusterOperationError(
            ClusterDiagnostic(
                phase="run-cancel",
                category="ssh-timeout",
                message="The cluster could not be reached.",
                allocation_state="orchestrator-submitted",
                retry_safety="safe",
                next_action="retry-cancel",
                identities={"run_id": "run_" + "6" * 32},
            )
        ),
        fallback="execution-cancel-failed",
    )

    error = _execution_http_error(operation)

    assert error.status_code == 503
    assert error.detail["details"]["identities"] == {"run_id": "run_" + "6" * 32}


def test_public_cluster_diagnostic_uses_global_error_handler_shape() -> None:
    from bioimageflow.cluster import ClusterDiagnostic, ClusterOperationError

    operation = _operation_error(
        ClusterOperationError(
            ClusterDiagnostic(
                phase="retry-start",
                category="retry-conflict",
                message="The retained child conflicts with this retry.",
                allocation_state="orchestrator-submitted",
                retry_safety="same-attempt-only",
                next_action="attach-child",
                identities={"run_id": "run_" + "7" * 32},
            )
        ),
        fallback="workflow-run-retry-error",
    )

    error = _execution_http_error(operation)

    assert error.status_code == 409
    assert error.detail["error"] == "retry-conflict"
    assert error.detail["detail"] == "The retained child conflicts with this retry."
    assert error.detail["details"]["diagnostic"] == {
        "schema": "bioimageflow.cluster_diagnostic.v1",
        "phase": "retry-start",
        "category": "retry-conflict",
        "message": "The retained child conflicts with this retry.",
        "allocation_state": "orchestrator-submitted",
        "retry_safety": "same-attempt-only",
        "next_action": "attach-child",
        "identities": {"run_id": "run_" + "7" * 32},
    }


@pytest.mark.anyio
async def test_direct_submit_failure_preserves_public_diagnostic_shape(
    tmp_path: Path,
) -> None:
    from bioimageflow.cluster import ClusterDiagnostic, ClusterOperationError

    class _Tokens:
        async def consume(self, token: str, *, binding: str) -> object:
            del token, binding
            raise ClusterOperationError(
                ClusterDiagnostic(
                    phase="scheduler-submit",
                    category="scheduler-rejected",
                    message="The scheduler rejected the request.",
                    allocation_state="none",
                    retry_safety="safe",
                    next_action="inspect-scheduler-request",
                    identities={"attempt_id": "attempt-1"},
                )
            )

    class _Preflight:
        tokens = _Tokens()

    coordinator = ExecutionCoordinator(
        ExecutionRegistry(tmp_path),
        reconnector=lambda snapshot: None,  # type: ignore[arg-type,return-value]
    )
    app = _app(coordinator)
    app.dependency_overrides[get_preflight_service] = _Preflight
    app.dependency_overrides[get_prepared_run_registrar] = lambda: object()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/executions",
            json={
                "token": "prepared-token",
                "workflow_id": "demo",
                "draft_revision": 1,
                "target_id": "profile_" + "1" * 32,
                "requested_nodes": None,
            },
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "scheduler-rejected"
    assert detail["detail"] == "The scheduler rejected the request."
    assert detail["details"]["diagnostic"]["identities"] == {"attempt_id": "attempt-1"}


@pytest.mark.anyio
async def test_direct_submit_failure_sanitizes_unexpected_exception(
    tmp_path: Path,
) -> None:
    class _Tokens:
        async def consume(self, token: str, *, binding: str) -> object:
            del token, binding
            raise RuntimeError("credential=must-not-escape")

    class _Preflight:
        tokens = _Tokens()

    coordinator = ExecutionCoordinator(
        ExecutionRegistry(tmp_path),
        reconnector=lambda snapshot: None,  # type: ignore[arg-type,return-value]
    )
    app = _app(coordinator)
    app.dependency_overrides[get_preflight_service] = _Preflight
    app.dependency_overrides[get_prepared_run_registrar] = lambda: object()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/executions",
            json={
                "token": "prepared-token",
                "workflow_id": "demo",
                "draft_revision": 1,
                "target_id": "profile_" + "1" * 32,
                "requested_nodes": None,
            },
        )

    assert response.status_code == 500
    assert response.json()["detail"]["error"] == "workflow-submission-failed"
    assert "must-not-escape" not in response.text


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
