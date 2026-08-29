"""HTTP contracts for distributed profiles, capabilities, and targets."""

from __future__ import annotations

from collections.abc import AsyncIterator
import io
from pathlib import Path
import zipfile
import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from bioimageflow_server.models.settings import Settings
from bioimageflow_server.routers.execution_profiles import (
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

    described = await profile_client.post(
        f"/api/v1/execution/profiles/{created['id']}/describe"
    )
    deprecated_test = await profile_client.post(
        f"/api/v1/execution/profiles/{created['id']}/test"
    )
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
