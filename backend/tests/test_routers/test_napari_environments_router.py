"""Typed desktop-only napari environment registry routes."""

from __future__ import annotations

import json
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


async def _client(
    tmp_path: Path, mode: str, probe_runner=None, manager=None, initialize: bool = False,
) -> tuple[httpx.AsyncClient, SettingsStore]:
    store = SettingsStore(
        tmp_path / f"{mode}-settings.json",
        deployment_mode=mode,  # type: ignore[arg-type]
    )
    await store.load()
    service = NapariEnvironmentService(
        store,
        **({"probe_runner": probe_runner} if probe_runner else {}),
        **({"environment_manager_provider": lambda: manager} if manager else {}),
    )
    if initialize:
        await service.initialize_registry()
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


async def test_default_setup_required_probe_is_typed_409_without_probe_or_mutation(tmp_path: Path) -> None:
    def forbidden(*_args: object) -> str:
        raise AssertionError("a declaration cannot be probed before explicit setup")

    client, store = await _client(tmp_path, "desktop", probe_runner=forbidden, initialize=True)
    environment = store.get().napari_environments[0]
    before = store.path.read_bytes()
    async with client:
        response = await client.post(
            f"/api/v1/napari/environments/{environment.id}/probe", json={"expected_revision": 1},
        )
    assert response.status_code == 409
    assert response.json()["error"] == "napari_environment_setup_required"
    assert store.path.read_bytes() == before


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


async def test_settings_journey_persists_rules_and_recovers_failed_managed_setup(
    tmp_path: Path,
) -> None:
    class FailingManager:
        def provision(self, *_args: object, **_kwargs: object) -> object:
            raise RuntimeError("solver unavailable")

        def managed_environments(self) -> tuple[object, ...]:
            return ()

    manager = FailingManager()
    external_path = _venv(tmp_path / "external viewer")
    labels_path = _venv(tmp_path / "labels viewer")
    client, _store = await _client(tmp_path, "desktop", manager=manager)
    async with client:
        first = await client.post(
            "/api/v1/napari/environments",
            json={"name": "Microscopy", "path": str(external_path), "expected_revision": 0},
        )
        assert first.status_code == 201
        first_id = first.json()["environment"]["id"]
        first_identity = first.json()["environment"]["interpreter_identity"]
        second = await client.post(
            "/api/v1/napari/environments",
            json={"name": "Labels", "path": str(labels_path), "expected_revision": 1},
        )
        assert second.status_code == 201
        second_id = second.json()["environment"]["id"]

        default = await client.put(
            "/api/v1/napari/environment-settings/default",
            json={"environment_id": first_id, "expected_revision": 2},
        )
        assert default.status_code == 200
        broad = await client.post(
            "/api/v1/napari/environment-settings/filename-rules",
            json={"value": ".tif", "environment_id": first_id, "expected_revision": 3},
        )
        assert broad.status_code == 201
        specific = await client.post(
            "/api/v1/napari/environment-settings/filename-rules",
            json={
                "value": "*_labels.tif",
                "mode": "pattern",
                "environment_id": second_id,
                "reader_id": "labels-reader",
                "expected_revision": 4,
            },
        )
        assert specific.status_code == 201
        broad_rule = broad.json()["rule"]
        specific_rule = specific.json()["rule"]
        ordered = await client.put(
            "/api/v1/napari/environment-settings/filename-rules",
            json={"rules": [specific_rule, broad_rule], "expected_revision": 5},
        )
        assert ordered.status_code == 200
        assert [rule["id"] for rule in ordered.json()["filename_rules"]] == [
            specific_rule["id"],
            broad_rule["id"],
        ]
        preview = await client.post(
            "/api/v1/napari/environment-settings/filename-rules/preview",
            json={"filename": "SAMPLE_LABELS.TIF"},
        )
        assert preview.status_code == 200
        assert preview.json()["winner_rule_id"] == specific_rule["id"]

        duplicate = await client.post(
            "/api/v1/napari/environment-settings/filename-rules",
            json={"value": ".TIF", "environment_id": second_id, "expected_revision": 6},
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["error"] == "duplicate_filename_pattern"
        assert (await client.get("/api/v1/napari/environments")).json()["revision"] == 6

        failed = await client.post(
            "/api/v1/napari/environments/managed",
            json={"name": "Managed retry", "expected_revision": 6},
        )
        assert failed.status_code == 202
        failed_body = failed.json()
        managed_id = failed_body["environment"]["id"]
        assert failed_body["environment"]["state"] == "failed"
        assert failed_body["operation"]["error"]["code"] == "napari_provision_failed"
        assert failed_body["environment"]["managed"]["installation_generation"] is None

        external_delete = await client.delete(
            f"/api/v1/napari/environments/managed/{first_id}"
            f"?expected_revision={failed_body['revision']}"
        )
        assert external_delete.status_code == 422
        assert external_delete.json()["error"] == "napari_managed_delete_forbidden"
        managed_forget = await client.delete(
            f"/api/v1/napari/environments/{managed_id}?expected_revision={failed_body['revision']}"
        )
        assert managed_forget.status_code == 422
        assert managed_forget.json()["error"] == "napari_managed_forget_forbidden"

    reopened, _store = await _client(tmp_path, "desktop", manager=manager)
    async with reopened:
        listing = (await reopened.get("/api/v1/napari/environments")).json()
        assert listing["default_environment_id"] == first_id
        assert [rule["id"] for rule in listing["filename_rules"]] == [
            specific_rule["id"],
            broad_rule["id"],
        ]
        assert [(item["id"], item["ownership"]) for item in listing["environments"]] == [
            (first_id, "external"),
            (second_id, "external"),
            (managed_id, "managed"),
        ]
        assert listing["environments"][0]["interpreter_identity"] == first_identity
        assert listing["environments"][2]["state"] == "failed"

        retried = await reopened.post(
            f"/api/v1/napari/environments/{managed_id}/retry",
            json={"expected_revision": listing["revision"]},
        )
        assert retried.status_code == 202
        assert retried.json()["environment"]["id"] == managed_id
        assert retried.json()["operation"]["kind"] == "retry"
        assert retried.json()["operation"]["state"] == "failed"
        after_retry = (await reopened.get("/api/v1/napari/environments")).json()
        assert after_retry["default_environment_id"] == first_id
        assert [rule["id"] for rule in after_retry["filename_rules"]] == [
            specific_rule["id"],
            broad_rule["id"],
        ]
        assert len(after_retry["environments"]) == 3

        forgotten = await reopened.delete(
            f"/api/v1/napari/environments/{second_id}?expected_revision={after_retry['revision']}"
        )
        assert forgotten.status_code == 200
        assert [rule["id"] for rule in forgotten.json()["filename_rules"]] == [broad_rule["id"]]
        assert forgotten.json()["default_environment_id"] == first_id
        assert labels_path.exists()


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
    readiness = paths["/api/v1/napari/viewing-readiness"]["post"]
    assert readiness["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ViewingRequirementsManifest-Input"
    }
    assert readiness["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/NapariViewingReadinessResponse"
    }


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
                "/api/v1/napari/viewing-readiness",
                json={
                    "schema": "bioimageflow.viewing_requirements.v1",
                    "complete": True,
                    "outputs": {},
                },
            ),
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
    assert [response.status_code for response in responses] == [403] * 16
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


_REQUIRED_READER_VIEWER = {
    "napari": {
        "required_packages": [
            {"distribution": "reader", "normalized_name": "reader", "version": None}
        ],
        "recommended_packages": [],
        "napari_version": None,
        "reader_id": None,
    }
}


def _inventory(*distributions: tuple[str, str]) -> str:
    return json.dumps(
        {
            "python_version": "3.13.1",
            "napari_version": "0.7.1",
            "distributions": [
                {"name": name, "version": version} for name, version in distributions
            ],
            "fingerprint": "a" * 64,
        }
    )


async def _favorite_key(client: httpx.AsyncClient, tmp_path: Path, viewer: dict) -> dict:
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
                "viewer_additions": {"image": viewer},
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
    assert updated.status_code == 200
    return {
        "kind": "persistent",
        "workspace_id": str(ensure_workspace_identity(tmp_path)),
        "workflow_id": "draft-output",
        "identity_generation": created.json()["identity_generation"],
        "node_path": ["new-node"],
        "output_key": "image",
    }


async def test_toggle_rejects_favorite_incompatible_with_the_output(tmp_path: Path) -> None:
    client, _store = await _client(
        tmp_path, "desktop", probe_runner=lambda *_args: _inventory(("napari", "0.7.1"))
    )
    async with client:
        environment = await client.post(
            "/api/v1/napari/environments",
            json={
                "name": "Old viewer",
                "path": str(_venv(tmp_path / "old-viewer")),
                "expected_revision": 0,
            },
        )
        environment_id = environment.json()["environment"]["id"]
        probed = await client.post(
            f"/api/v1/napari/environments/{environment_id}/probe",
            json={"expected_revision": 1},
        )
        key = await _favorite_key(client, tmp_path, _REQUIRED_READER_VIEWER)
        rejected = await client.post(
            "/api/v1/napari/viewer-preferences/favorite/toggle",
            json={"key": key, "environment_id": environment_id, "expected_revision": 0},
        )
        preferences = await client.get("/api/v1/napari/viewer-preferences")

    assert probed.status_code == 200
    assert probed.json()["environment"]["state"] == "ready"
    assert rejected.status_code == 409
    assert rejected.json()["error"] == "napari_favorite_incompatible"
    assert preferences.json()["favorites"] == []


async def test_toggle_permits_unverified_requirements_for_the_output(tmp_path: Path) -> None:
    client, _store = await _client(tmp_path, "desktop")
    async with client:
        environment = await client.post(
            "/api/v1/napari/environments",
            json={
                "name": "Unprobed viewer",
                "path": str(_venv(tmp_path / "unprobed-viewer")),
                "expected_revision": 0,
            },
        )
        environment_id = environment.json()["environment"]["id"]
        key = await _favorite_key(client, tmp_path, _REQUIRED_READER_VIEWER)
        accepted = await client.post(
            "/api/v1/napari/viewer-preferences/favorite/toggle",
            json={"key": key, "environment_id": environment_id, "expected_revision": 0},
        )

    assert accepted.status_code == 200
    assert [favorite["environment_id"] for favorite in accepted.json()["favorites"]] == [
        environment_id
    ]
