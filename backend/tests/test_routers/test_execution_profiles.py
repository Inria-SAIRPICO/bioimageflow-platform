"""HTTP contracts for distributed profiles, capabilities, and targets."""

from __future__ import annotations

from collections.abc import AsyncIterator
import io
from pathlib import Path
from types import SimpleNamespace
import zipfile
import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from bioimageflow_server.models.settings import Settings
from bioimageflow_server.routers.execution_profiles import (
    _cluster_failure,
    get_execution_profile_store,
    get_settings,
    router,
)
from bioimageflow_server.services.execution_profiles import ExecutionProfileStore
from tests.test_services.test_execution_profiles import profile_fields, write_config


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def profile_store(tmp_path: Path) -> ExecutionProfileStore:
    store = ExecutionProfileStore(tmp_path / "profiles.json")
    await store.load()
    return store


@pytest.fixture
async def profile_client(
    profile_store: ExecutionProfileStore,
) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(deployment_mode="desktop")
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_execution_profile_store] = lambda: profile_store
    app.dependency_overrides[get_settings] = lambda: settings
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def test_profile_crud_and_targets(
    profile_client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    config = write_config(tmp_path / "cluster.py")
    created_response = await profile_client.post(
        "/api/v1/execution/profiles",
        json=profile_fields(config).model_dump(mode="json"),
    )
    assert created_response.status_code == 201
    created = created_response.json()
    assert created["revision"] == 1
    assert created["config_path"] == str(config)
    assert created["cluster_host"] == "cluster"

    listing = (await profile_client.get("/api/v1/execution/profiles")).json()
    assert listing["editable"] is True
    assert [item["id"] for item in listing["profiles"]] == [created["id"]]

    targets = (await profile_client.get("/api/v1/execution/targets")).json()
    assert targets["targets"][0] == {
        "id": "local",
        "name": "Local",
        "kind": "local",
        "mode": "local",
        "available": True,
        "disabled_reason": None,
        "profile_revision": None,
    }
    assert targets["targets"][1]["id"] == created["id"]

    patch = {
        "expected_revision": 1,
        "profile": profile_fields(config, name="Renamed").model_dump(mode="json"),
    }
    updated = await profile_client.patch(f"/api/v1/execution/profiles/{created['id']}", json=patch)
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    conflict = await profile_client.patch(f"/api/v1/execution/profiles/{created['id']}", json=patch)
    assert conflict.status_code == 409

    deleted = await profile_client.delete(
        f"/api/v1/execution/profiles/{created['id']}?expected_revision=2"
    )
    assert deleted.status_code == 204


async def test_slurm_example_archive_contains_relative_companion_files(
    profile_client: httpx.AsyncClient,
) -> None:
    response = await profile_client.get("/api/v1/execution/profiles/example/slurm")

    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {"cluster.py", "parsl.py", "setup.sh"}
        cluster_source = archive.read("cluster.py").decode("utf-8")
    assert "HERE = Path(__file__).resolve().parent" in cluster_source
    assert 'HERE / "parsl.py"' in cluster_source
    assert 'HERE / "setup.sh"' in cluster_source


async def test_profile_delete_reports_active_execution_conflict(
    profile_client: httpx.AsyncClient,
    profile_store: ExecutionProfileStore,
    tmp_path: Path,
) -> None:
    config = write_config(tmp_path / "cluster.py")
    created = (
        await profile_client.post(
            "/api/v1/execution/profiles",
            json=profile_fields(config).model_dump(mode="json"),
        )
    ).json()
    profile_store.set_reference_checker(lambda profile_id: profile_id == created["id"])

    response = await profile_client.delete(
        f"/api/v1/execution/profiles/{created['id']}?expected_revision=1"
    )

    assert response.status_code == 409
    assert "non-terminal execution" in response.json()["detail"]


async def test_describe_is_the_only_profile_observation_route(
    profile_client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    config = write_config(tmp_path / "cluster.py")
    created = (
        await profile_client.post(
            "/api/v1/execution/profiles",
            json=profile_fields(config).model_dump(mode="json"),
        )
    ).json()

    described = await profile_client.post(f"/api/v1/execution/profiles/{created['id']}/describe")
    deprecated_test = await profile_client.post(f"/api/v1/execution/profiles/{created['id']}/test")
    deprecated_connection = await profile_client.post(
        f"/api/v1/execution/profiles/{created['id']}/test-connection"
    )
    deprecated_cleanup = await profile_client.post(
        f"/api/v1/execution/profiles/{created['id']}/cleanup/plan",
        json={},
    )

    assert described.status_code == 200
    assert described.json()["cluster_host"] == "cluster"
    assert deprecated_test.status_code == 404
    assert deprecated_connection.status_code == 404
    assert deprecated_cleanup.status_code == 404


async def test_target_listing_never_executes_trusted_profile_script(
    profile_client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    config = write_config(tmp_path / "cluster.py")
    created = (
        await profile_client.post(
            "/api/v1/execution/profiles",
            json=profile_fields(config).model_dump(mode="json"),
        )
    ).json()
    config.write_text("raise RuntimeError('must not execute during listing')\n")

    targets = await profile_client.get("/api/v1/execution/targets")
    described = await profile_client.post(f"/api/v1/execution/profiles/{created['id']}/describe")

    assert targets.status_code == 200
    assert targets.json()["targets"][1]["available"] is True
    assert described.status_code == 422


async def test_profile_script_exception_text_is_not_reflected(
    profile_client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    config = tmp_path / "cluster.py"
    config.write_text(
        "raise RuntimeError('credential=must-not-escape')\n",
        encoding="utf-8",
    )

    response = await profile_client.post(
        "/api/v1/execution/profiles",
        json=profile_fields(config).model_dump(mode="json"),
    )

    assert response.status_code == 422
    assert "could not be evaluated" in response.text
    assert "must-not-escape" not in response.text


async def test_describe_rejects_forged_connection_diagnostic_without_reflecting_text(
    profile_client: httpx.AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bioimageflow.cluster import ClusterDiagnostic

    config = write_config(tmp_path / "cluster.py")
    created = (
        await profile_client.post(
            "/api/v1/execution/profiles",
            json=profile_fields(config).model_dump(mode="json"),
        )
    ).json()

    class ForgedDiagnosticError(RuntimeError):
        def __init__(self) -> None:
            super().__init__("credential=must-not-escape")
            self.diagnostic = ClusterDiagnostic(
                phase="connection-check",
                category="protocol-incompatible",
                message="credential=must-not-escape",
                retry_safety="safe",
                next_action="update-gateway",
            )

    class Cluster:
        configured = True

        def to_dict(self) -> dict[str, object]:
            return {
                "schema": "bioimageflow.remote_cluster.v1",
                "host": "cluster",
                "root": "/shared/bioimageflow",
                "results_root": None,
                "environment": None,
                "parsl": None,
                "orchestrator": None,
                "setup": None,
            }

        def check_connection(self) -> None:
            raise ForgedDiagnosticError()

    monkeypatch.setattr(
        "bioimageflow_server.routers.execution_profiles.load_cluster_config",
        lambda *_args, **_kwargs: SimpleNamespace(cluster=Cluster()),
    )

    response = await profile_client.post(
        f"/api/v1/execution/profiles/{created['id']}/describe?check_connection=true"
    )

    assert response.status_code == 500
    assert response.json()["detail"]["error"] == "cluster-connection-check-failed"
    assert "must-not-escape" not in response.text


async def test_describe_sanitizes_unexpected_cluster_description_failure(
    profile_client: httpx.AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = write_config(tmp_path / "cluster.py")
    created = (
        await profile_client.post(
            "/api/v1/execution/profiles",
            json=profile_fields(config).model_dump(mode="json"),
        )
    ).json()

    class Cluster:
        configured = True

        def to_dict(self) -> dict[str, object]:
            raise RuntimeError("credential=must-not-escape")

    monkeypatch.setattr(
        "bioimageflow_server.routers.execution_profiles.load_cluster_config",
        lambda *_args, **_kwargs: SimpleNamespace(cluster=Cluster()),
    )

    response = await profile_client.post(
        f"/api/v1/execution/profiles/{created['id']}/describe"
    )

    assert response.status_code == 500
    assert response.json()["detail"]["error"] == "cluster-description-failed"
    assert "must-not-escape" not in response.text


async def test_describe_preserves_genuine_connection_diagnostic(
    profile_client: httpx.AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bioimageflow.cluster import ClusterDiagnostic, ClusterOperationError

    config = write_config(tmp_path / "cluster.py")
    created = (
        await profile_client.post(
            "/api/v1/execution/profiles",
            json=profile_fields(config).model_dump(mode="json"),
        )
    ).json()

    class Cluster:
        configured = True

        def to_dict(self) -> dict[str, object]:
            return {
                "schema": "bioimageflow.remote_cluster.v1",
                "host": "cluster",
                "root": "/shared/bioimageflow",
                "results_root": None,
                "environment": None,
                "parsl": None,
                "orchestrator": None,
                "setup": None,
            }

        def check_connection(self) -> None:
            raise ClusterOperationError(
                ClusterDiagnostic(
                    phase="connection-check",
                    category="protocol-incompatible",
                    message="The gateway protocol is incompatible.",
                    retry_safety="safe",
                    next_action="update-gateway",
                )
            )

    monkeypatch.setattr(
        "bioimageflow_server.routers.execution_profiles.load_cluster_config",
        lambda *_args, **_kwargs: SimpleNamespace(cluster=Cluster()),
    )

    response = await profile_client.post(
        f"/api/v1/execution/profiles/{created['id']}/describe?check_connection=true"
    )

    assert response.status_code == 200
    assert response.json()["diagnostics"][0]["category"] == "protocol-incompatible"


def test_profile_cluster_failure_preserves_public_diagnostic() -> None:
    from bioimageflow.cluster import ClusterDiagnostic, ClusterOperationError

    error = _cluster_failure(
        ClusterOperationError(
            ClusterDiagnostic(
                phase="connection-check",
                category="protocol-incompatible",
                message="The gateway protocol is incompatible.",
                retry_safety="safe",
                next_action="update-gateway",
                identities={"deployment_id": "deployment-1"},
            )
        )
    )

    assert error.status_code == 503
    assert error.detail["error"] == "protocol-incompatible"
    assert error.detail["detail"] == "The gateway protocol is incompatible."
    assert error.detail["details"]["diagnostic"]["identities"] == {"deployment_id": "deployment-1"}


async def test_webapp_profile_mutations_are_forbidden(tmp_path: Path) -> None:
    store = ExecutionProfileStore(tmp_path / "profiles.json", editable=False)
    await store.load()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_execution_profile_store] = lambda: store
    app.dependency_overrides[get_settings] = lambda: Settings(deployment_mode="webapp")
    config = write_config(tmp_path / "cluster.py")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        listing = await client.get("/api/v1/execution/profiles")
        created = await client.post(
            "/api/v1/execution/profiles",
            json=profile_fields(config).model_dump(mode="json"),
        )

    assert listing.json()["editable"] is False
    assert created.status_code == 403
