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
from bioimageflow_server.services.viewer_preferences import ensure_workspace_identity
from tests.graph_factory import graph_document


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


async def test_openapi_exposes_typed_managed_operation_routes(tmp_path: Path) -> None:
    client, _store = await _client(tmp_path, "desktop")
    async with client:
        schema = (await client.get("/openapi.json")).json()

    paths = schema["paths"]
    assert paths["/api/v1/napari/environments/managed"]["post"]["responses"]["202"]
    assert paths["/api/v1/napari/environments/managed/{environment_id}"]["delete"][
        "responses"
    ]["202"]
    assert paths["/api/v1/napari/environments/{environment_id}/copy"]["post"]["responses"][
        "202"
    ]
    assert paths["/api/v1/napari/environments/{environment_id}/retry"]["post"]["responses"][
        "202"
    ]
    assert "/api/v1/napari/environments/{environment_id}/operations/{operation_id}" in paths
    assert (
        "/api/v1/napari/environments/{environment_id}/operations/{operation_id}/cancel"
        in paths
    )


async def test_managed_routes_return_operations_and_enforce_initiation_cas(
    tmp_path: Path,
) -> None:
    class FailingManager:
        def provision(self, *_args: object, **_kwargs: object) -> object:
            raise RuntimeError("solver unavailable")

        def managed_environments(self) -> tuple[object, ...]:
            return ()

    store = SettingsStore(tmp_path / "settings.json")
    await store.load()
    manager = FailingManager()
    service = NapariEnvironmentService(
        store,
        environment_manager_provider=lambda: manager,  # type: ignore[arg-type]
    )
    app = create_app(
        AppConfig(
            settings_store=store,
            settings=Settings(deployment_mode="desktop"),
            deployment_mode="desktop",
            napari_environment_service=service,
            storage_path=tmp_path / "runtime",
            workflow_root=tmp_path / "workflows",
            disable_hot_reload=True,
        )
    )
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/napari/environments/managed",
            json={"name": "Managed", "expected_revision": 0},
        )
        assert created.status_code == 202
        body = created.json()
        assert body["operation"]["kind"] == "create"
        assert body["operation"]["state"] == "failed"
        assert body["operation"]["error"]["code"] == "napari_provision_failed"

        polled = await client.get(
            "/api/v1/napari/environments/"
            f"{body['environment']['id']}/operations/{body['operation']['id']}"
        )
        assert polled.status_code == 200
        assert polled.json()["operation"] == body["operation"]

        cancelled = await client.post(
            "/api/v1/napari/environments/"
            f"{body['environment']['id']}/operations/{body['operation']['id']}/cancel"
        )
        assert cancelled.status_code == 202
        assert cancelled.json()["operation"]["state"] == "failed"

        stale = await client.post(
            "/api/v1/napari/environments/managed",
            json={"name": "Stale", "expected_revision": 0},
        )
        assert stale.status_code == 409
        assert stale.json()["error"] == "napari_registry_revision_conflict"


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
            await client.post(
                "/api/v1/napari/environments/managed",
                json={"name": "Nope", "expected_revision": 0},
            ),
            await client.delete(
                f"/api/v1/napari/environments/managed/{environment_id}?expected_revision=0"
            ),
            await client.post(
                f"/api/v1/napari/environments/{environment_id}/copy",
                json={"name": "Nope", "expected_revision": 0},
            ),
            await client.post(
                f"/api/v1/napari/environments/{environment_id}/retry",
                json={"expected_revision": 0},
            ),
            await client.get(
                f"/api/v1/napari/environments/{environment_id}/operations/{rule_id}"
            ),
            await client.post(
                f"/api/v1/napari/environments/{environment_id}/operations/{rule_id}/cancel"
            ),
        ]
    assert [response.status_code for response in responses] == [403] * 15
    assert all(response.json()["error"] == "desktop_only" for response in responses)


async def test_generic_settings_patch_cannot_bypass_registry_invariants(
    tmp_path: Path,
) -> None:
    client, _store = await _client(tmp_path, "desktop")
    async with client:
        response = await client.patch("/api/v1/settings", json={"napari_environments": []})
        operations_response = await client.patch(
            "/api/v1/settings", json={"napari_environment_operations": []}
        )
    assert response.status_code == 422
    assert operations_response.status_code == 422


async def test_favorite_structural_identity_uses_current_draft(tmp_path: Path) -> None:
    client, _store = await _client(tmp_path, "desktop")
    async with client:
        environment = await client.post(
            "/api/v1/napari/environments",
            json={
                "name": "Draft viewer",
                "path": str(_venv(tmp_path / "draft-viewer")),
                "expected_revision": 0,
            },
        )
        created = await client.post("/api/v1/workflows", json={"name": "draft-output"})
        current = await client.get("/api/v1/workflow-drafts/draft-output")
        graph = graph_document(
            nodes=[
                {
                    "type": "tool",
                    "id": "new-node",
                    "name": "New node",
                    "tool_name": "MissingTool",
                    "position": [0, 0],
                    "parameters": {},
                    "viewer_additions": {"image": {"napari": None}},
                }
            ]
        )
        updated = await client.put(
            "/api/v1/workflow-drafts/draft-output",
            json={
                "expected_revision": current.json()["draft_revision"],
                "graph": graph,
            },
        )
        favorite = await client.put(
            "/api/v1/napari/viewer-preferences/favorite",
            json={
                "key": {
                    "kind": "persistent",
                    "workspace_id": str(
                        ensure_workspace_identity(tmp_path)
                    ),
                    "workflow_id": "draft-output",
                    "identity_generation": created.json()["identity_generation"],
                    "node_path": ["new-node"],
                    "output_key": "image",
                },
                "environment_id": environment.json()["environment"]["id"],
                "expected_revision": 0,
            },
        )

    assert updated.status_code == 200
    assert favorite.status_code == 200
