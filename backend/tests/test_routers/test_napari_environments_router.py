"""Typed desktop-only napari environment registry routes."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.napari_environments import NapariEnvironmentService
from bioimageflow_server.services.settings_store import SettingsStore


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _venv(root: Path) -> Path:
    (root / "bin").mkdir(parents=True)
    (root / "pyvenv.cfg").write_text("home = test\n")
    (root / "bin" / "python").symlink_to(sys.executable)
    return root


async def _client(tmp_path: Path, mode: str) -> tuple[httpx.AsyncClient, SettingsStore]:
    store = SettingsStore(
        tmp_path / f"{mode}-settings.json",
        deployment_mode=mode,  # type: ignore[arg-type]
    )
    await store.load()
    service = NapariEnvironmentService(store)
    app = create_app(
        AppConfig(
            settings_store=store,
            settings=Settings(deployment_mode=mode),  # type: ignore[arg-type]
            deployment_mode=mode,
            napari_environment_service=service,
            storage_path=tmp_path / "runtime",
            workflow_root=tmp_path / "workflows",
            disable_hot_reload=True,
        )
    )
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test"), store


async def test_routes_return_typed_revisioned_mutations(tmp_path: Path) -> None:
    client, _store = await _client(tmp_path, "desktop")
    async with client:
        created = await client.post(
            "/api/v1/napari/environments",
            json={
                "name": "Microscopy",
                "path": str(_venv(tmp_path / "viewer with spaces")),
                "expected_revision": 0,
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert body["revision"] == 1
        environment_id = body["environment"]["id"]

        renamed = await client.patch(
            f"/api/v1/napari/environments/{environment_id}",
            json={"name": "Renamed", "expected_revision": 1},
        )
        assert renamed.status_code == 200
        assert renamed.json()["revision"] == 2
        assert renamed.json()["environment"]["name"] == "Renamed"

        stale = await client.put(
            "/api/v1/napari/environment-settings/default",
            json={"environment_id": environment_id, "expected_revision": 1},
        )
        assert stale.status_code == 409
        assert stale.json()["error"] == "napari_registry_revision_conflict"

        listing = await client.get("/api/v1/napari/environments")
        assert listing.status_code == 200
        assert listing.json()["revision"] == 2


async def test_webapp_rejects_all_local_registry_operations(tmp_path: Path) -> None:
    client, _store = await _client(tmp_path, "webapp")
    environment_id = str(uuid4())
    rule_id = str(uuid4())
    async with client:
        responses = [
            await client.get("/api/v1/napari/environments"),
            await client.post(
                "/api/v1/napari/environments",
                json={"name": "Nope", "path": "/server/python", "expected_revision": 0},
            ),
            await client.patch(
                f"/api/v1/napari/environments/{environment_id}",
                json={"name": "Nope", "expected_revision": 0},
            ),
            await client.delete(
                f"/api/v1/napari/environments/{environment_id}?expected_revision=0"
            ),
            await client.post(
                f"/api/v1/napari/environments/{environment_id}/probe",
                json={"expected_revision": 0},
            ),
            await client.put(
                "/api/v1/napari/environment-settings/default",
                json={"environment_id": environment_id, "expected_revision": 0},
            ),
            await client.post(
                "/api/v1/napari/environment-settings/filename-rules",
                json={
                    "value": ".tif",
                    "environment_id": environment_id,
                    "expected_revision": 0,
                },
            ),
            await client.put(
                "/api/v1/napari/environment-settings/filename-rules",
                json={
                    "rules": [
                        {
                            "id": rule_id,
                            "pattern": "*.tif",
                            "environment_id": environment_id,
                        }
                    ],
                    "expected_revision": 0,
                },
            ),
            await client.post(
                "/api/v1/napari/environment-settings/filename-rules/preview",
                json={"filename": "image.tif"},
            ),
        ]
    assert [response.status_code for response in responses] == [403] * 9
    assert all(response.json()["error"] == "desktop_only" for response in responses)


async def test_generic_settings_patch_cannot_bypass_registry_invariants(
    tmp_path: Path,
) -> None:
    client, _store = await _client(tmp_path, "desktop")
    async with client:
        response = await client.patch("/api/v1/settings", json={"napari_environments": []})
    assert response.status_code == 422
