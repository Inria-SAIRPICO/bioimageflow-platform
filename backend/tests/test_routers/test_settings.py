"""Tests for the /settings router."""

from __future__ import annotations

import logging
import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.models.workflow import WorkflowCreate
from bioimageflow_server.services.omero_credentials import OmeroCredentialError, OmeroCredentialKey
from bioimageflow_server.services.settings_store import SettingsStore
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def settings_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "settings_version": 2,
                "deployment_mode": "desktop",
                "workspace_path": str(tmp_path / "workspace"),
            }
        ),
        encoding="utf-8",
    )
    store = SettingsStore(path=settings_path)
    config = AppConfig(
        settings_store=store,
        settings=Settings(
            deployment_mode="desktop",
            workspace_path=str(tmp_path / "workspace"),
        ),
        deployment_mode="desktop",
        disable_hot_reload=True,
    )
    app = create_app(config)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client


class FakeOmeroCredentials:
    def __init__(self) -> None:
        self.passwords: dict[str, str] = {}
        self.deleted: list[str] = []
        self.fail_get = False
        self.fail_set = False

    def get_password(self, key: OmeroCredentialKey) -> str | None:
        if self.fail_get:
            raise OmeroCredentialError("keyring read failed")
        return self.passwords.get(key.username)

    def set_password(self, key: OmeroCredentialKey, password: str) -> None:
        if self.fail_set:
            raise OmeroCredentialError("keyring write failed")
        self.passwords[key.username] = password

    def delete_password(self, key: OmeroCredentialKey) -> None:
        self.deleted.append(key.username)
        self.passwords.pop(key.username, None)


@pytest.fixture
async def omero_settings_client(
    tmp_path: Path,
) -> AsyncIterator[tuple[httpx.AsyncClient, SettingsStore, FakeOmeroCredentials, Path]]:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "settings_version": 2,
                "deployment_mode": "desktop",
                "workspace_path": str(tmp_path / "workspace"),
            }
        ),
        encoding="utf-8",
    )
    credentials = FakeOmeroCredentials()
    store = SettingsStore(path=settings_path, omero_credentials=credentials)
    config = AppConfig(
        settings_store=store,
        settings=Settings(
            deployment_mode="desktop",
            workspace_path=str(tmp_path / "workspace"),
        ),
        deployment_mode="desktop",
        disable_hot_reload=True,
    )
    app = create_app(config)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, store, credentials, settings_path


class TestGetSettings:
    async def test_get_returns_full_model(self, settings_client: httpx.AsyncClient) -> None:
        response = await settings_client.get("/api/v1/settings")
        assert response.status_code == 200
        body = response.json()
        # Wrapper contains the Settings fields plus the resolved-path helpers.
        assert body["deployment_mode"] == "desktop"
        assert body["new_workflow_execution"] == "sequential"
        assert "execution_engine" not in body
        assert body["node_data_page_size"] == 250
        assert "cache_max_executions" not in body
        assert "cache_max_age" not in body
        assert body["external_editor"] is None
        assert "resolved_tool_store_path" in body
        # Resolved paths should be absolute.
        assert body["resolved_tool_store_path"].startswith("/")

    async def test_get_omero_instances_include_password_state_not_password(
        self,
        omero_settings_client: tuple[httpx.AsyncClient, SettingsStore, FakeOmeroCredentials, Path],
    ) -> None:
        client, store, credentials, _path = omero_settings_client
        await store.patch({"omero_instances": [{"host": "omero.example.com", "username": "admin"}]})
        credentials.passwords["omero.example.com:4064:admin"] = "secret"

        response = await client.get("/api/v1/settings")

        assert response.status_code == 200
        instance = response.json()["omero_instances"][0]
        assert instance["password_stored"] is True
        assert "password" not in instance

    async def test_get_omero_keyring_failure_returns_structured_error(
        self,
        omero_settings_client: tuple[httpx.AsyncClient, SettingsStore, FakeOmeroCredentials, Path],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        client, store, credentials, _path = omero_settings_client
        await store.patch({"omero_instances": [{"host": "omero.example.com", "username": "admin"}]})
        credentials.fail_get = True

        with caplog.at_level(logging.ERROR, logger="bioimageflow_server.routers.settings"):
            response = await client.get("/api/v1/settings")

        assert response.status_code == 500
        body = response.json()
        assert body["error"] == "settings_keyring_error"
        assert body["detail"] == "keyring read failed"
        assert "Settings keyring operation failed" in caplog.text
        assert "HTTP 500 returned" not in caplog.text


class TestPatchSettings:
    async def test_patch_updates_field(self, settings_client: httpx.AsyncClient) -> None:
        response = await settings_client.patch(
            "/api/v1/settings", json={"external_editor": "code {file_path}"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["external_editor"] == "code {file_path}"
        # GET reflects the change.
        getresp = await settings_client.get("/api/v1/settings")
        assert getresp.json()["external_editor"] == "code {file_path}"

    async def test_patch_validates_and_clears_fiji_installation(
        self, settings_client: httpx.AsyncClient, tmp_path: Path
    ) -> None:
        root = tmp_path / "Fiji.app"
        root.mkdir()
        launcher = root / "fiji"
        launcher.write_text("launcher")
        launcher.chmod(0o755)
        for name in ("fiji-macos-arm64", "fiji-macos-x64"):
            mac_launcher = root / "Contents" / "MacOS" / name
            mac_launcher.parent.mkdir(parents=True, exist_ok=True)
            mac_launcher.write_text("launcher")
            mac_launcher.chmod(0o755)

        response = await settings_client.patch("/api/v1/settings", json={"fiji_path": str(root)})

        assert response.status_code == 200
        assert response.json()["fiji_path"] == str(root)

        cleared = await settings_client.patch("/api/v1/settings", json={"fiji_path": None})
        assert cleared.status_code == 200
        assert cleared.json()["fiji_path"] is None

    async def test_patch_rejects_invalid_fiji_installation(
        self, settings_client: httpx.AsyncClient, tmp_path: Path
    ) -> None:
        root = tmp_path / "Fiji.app"
        root.mkdir()

        response = await settings_client.patch("/api/v1/settings", json={"fiji_path": str(root)})

        assert response.status_code == 422
        assert response.json()["error"] == "invalid_fiji_path"
        assert response.json()["field"] == "fiji_path"

    async def test_patch_invalid_value(self, settings_client: httpx.AsyncClient) -> None:
        response = await settings_client.patch(
            "/api/v1/settings", json={"new_workflow_execution": "dask"}
        )
        assert response.status_code == 422

    async def test_patch_node_data_page_size(self, settings_client: httpx.AsyncClient) -> None:
        response = await settings_client.patch(
            "/api/v1/settings", json={"node_data_page_size": 100}
        )
        assert response.status_code == 200
        assert response.json()["node_data_page_size"] == 100

        invalid = await settings_client.patch("/api/v1/settings", json={"node_data_page_size": 75})
        assert invalid.status_code == 422

    async def test_patch_unknown_key(self, settings_client: httpx.AsyncClient) -> None:
        response = await settings_client.patch("/api/v1/settings", json={"foo": 1})
        assert response.status_code == 422

    @pytest.mark.parametrize("value", [True, False])
    async def test_patch_retired_dev_mode_rejected(
        self, settings_client: httpx.AsyncClient, value: bool
    ) -> None:
        before = await settings_client.get("/api/v1/settings")
        response = await settings_client.patch("/api/v1/settings", json={"dev_mode": value})
        assert response.status_code == 422
        after = await settings_client.get("/api/v1/settings")
        assert after.json() == before.json()
        assert "dev_mode" not in after.json()

    async def test_patch_workspace_path_retargets_workflow_store(
        self,
        settings_client: httpx.AsyncClient,
        tmp_path: Path,
    ) -> None:
        workspace = tmp_path / "new workspace"
        workflows_root = workspace / "workflows"
        store = WorkflowStoreService(
            root_dir=workflows_root,
            tool_registry=ToolRegistryService(),
        )
        store.create_workflow(WorkflowCreate(name="retargeted", display_name="Retargeted"))
        workflow_file = workflows_root / "retargeted" / "workflow.json"

        response = await settings_client.patch(
            "/api/v1/settings",
            json={"workspace_path": str(workspace)},
        )
        assert response.status_code == 200

        workflows = await settings_client.get("/api/v1/workflows")

        assert workflows.status_code == 200
        assert [workflow["id"] for workflow in workflows.json()] == ["retargeted"]
        assert workflow_file.exists()

    async def test_patch_unsafe_webapp_features_rejected(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        response = await settings_client.patch(
            "/api/v1/settings",
            json={"enable_unsafe_webapp_features": True},
        )
        assert response.status_code == 422
        assert "settings file" in response.json()["detail"]

    async def test_webapp_fiji_configuration_is_rejected(self, tmp_path: Path) -> None:
        store = SettingsStore(
            path=tmp_path / "settings.json",
            deployment_mode="webapp",
        )
        app = create_app(
            AppConfig(
                settings_store=store,
                deployment_mode="webapp",
                workspace_path=tmp_path / "workspace",
                workspaces_root=tmp_path / "users",
                user_id="test-user",
                disable_hot_reload=True,
            )
        )
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.patch(
                    "/api/v1/settings",
                    json={"fiji_path": "/server/Fiji.app"},
                )

        assert response.status_code == 403
        assert "desktop mode" in response.json()["detail"]

    @pytest.mark.parametrize(
        "field,preloaded,explicit_root",
        [
            ("deployment_mode", False, False),
            ("workspaces_root", False, False),
            ("workspaces_root", True, True),
        ],
    )
    async def test_webapp_policy_patch_keeps_administrator_root_and_consumers(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        field: str,
        preloaded: bool,
        explicit_root: bool,
    ) -> None:
        from unittest.mock import AsyncMock, MagicMock
        from types import SimpleNamespace
        from bioimageflow_server.routers.datasets import get_datasets_root

        path = tmp_path / "settings.json"
        stored_root = tmp_path / "administrator-users"
        configured_root = tmp_path / "configured-users"
        path.write_text(
            json.dumps({"deployment_mode": "webapp", "workspaces_root": str(stored_root)})
        )
        store = SettingsStore(
            path=path, deployment_mode="webapp", omero_credentials=FakeOmeroCredentials()
        )
        if preloaded:
            await store.load()
        reveal = MagicMock()
        export = MagicMock()
        monkeypatch.setattr("bioimageflow_server.routers.workflows.reveal_in_file_browser", reveal)
        monkeypatch.setattr(
            "bioimageflow_server.routers.workflows.WorkflowExportService.export_latest_results_folder",
            export,
        )
        app = create_app(
            AppConfig(
                deployment_mode="webapp",
                settings_store=store,
                # Initial services precede load; keep their independent fallback disposable.
                settings=Settings(
                    deployment_mode="webapp", workspaces_root=str(tmp_path / "initial-only-users")
                ),
                user_id="fixture-user",
                workspaces_root=configured_root if explicit_root else None,
                tool_registry=ToolRegistryService(),
                disable_hot_reload=True,
                package_catalog=SimpleNamespace(refresh=AsyncMock(), list_packages=lambda: []),
            )
        )
        expected_workspace = (
            (configured_root if explicit_root else stored_root) / "fixture-user" / "workspace"
        )
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                initial = await client.get("/api/v1/workspace")
                assert initial.json()["workspace_path"] == str(expected_workspace)
                before = path.read_bytes()
                current = store.get()
                value = "desktop" if field == "deployment_mode" else str(tmp_path / "client-root")
                refused = await client.patch("/api/v1/settings", json={field: value})
                assert refused.status_code == 403
                assert refused.json()["error"] == "settings_policy_read_only"
                assert refused.json()["field"] == field
                assert path.read_bytes() == before
                assert store.get() is current
                assert (await client.get("/api/v1/settings")).json()["deployment_mode"] == "webapp"
                workspace = (await client.get("/api/v1/workspace")).json()
                assert workspace["workspace_path"] == str(expected_workspace)
                assert workspace["workflows_root"] == str(expected_workspace / "workflows")
                assert (
                    app.dependency_overrides[get_datasets_root]() == expected_workspace / "datasets"
                )
                assert (
                    await client.patch(
                        "/api/v1/workspace",
                        json={"workspace_path": str(tmp_path / "client-workspace")},
                    )
                ).status_code == 403
                assert (
                    await client.patch("/api/v1/settings", json={"node_data_page_size": 50})
                ).status_code == 200
                assert (
                    await client.post("/api/v1/workflows/missing/outputs/latest/reveal")
                ).status_code == 403
                assert (
                    await client.post(
                        "/api/v1/workflows/missing/exports/latest-results-folder",
                        json={"destination_parent": str(tmp_path), "replace": False},
                    )
                ).status_code == 403
                assert (
                    await client.patch("/api/v1/settings", json={"fiji_path": "/server/Fiji.app"})
                ).status_code == 403
        reveal.assert_not_called()
        export.assert_not_called()

    async def test_patch_empty_body(self, settings_client: httpx.AsyncClient) -> None:
        response = await settings_client.patch("/api/v1/settings", json={})
        assert response.status_code == 200

    async def test_patch_clear_with_null(self, settings_client: httpx.AsyncClient) -> None:
        await settings_client.patch("/api/v1/settings", json={"external_editor": "vim"})
        response = await settings_client.patch("/api/v1/settings", json={"external_editor": None})
        assert response.status_code == 200
        assert response.json()["external_editor"] is None

    @pytest.mark.campaign_excluded(reason="parsl")
    async def test_patch_old_execution_engine_is_rejected(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        response = await settings_client.patch(
            "/api/v1/settings", json={"execution_engine": "parsl"}
        )
        assert response.status_code == 422

    async def test_patch_cache_max_executions_is_deprecated(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        response = await settings_client.patch("/api/v1/settings", json={"cache_max_executions": 0})
        assert response.status_code == 422

    async def test_patch_cache_max_age_is_deprecated(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        response = await settings_client.patch("/api/v1/settings", json={"cache_max_age": "30d"})
        assert response.status_code == 422

    async def test_patch_omero_password_persists_metadata_only(
        self,
        omero_settings_client: tuple[httpx.AsyncClient, SettingsStore, FakeOmeroCredentials, Path],
    ) -> None:
        client, _store, credentials, path = omero_settings_client

        response = await client.patch(
            "/api/v1/settings",
            json={
                "omero_instances": [
                    {
                        "host": "omero.example.com",
                        "username": "admin",
                        "password": "secret",
                    }
                ]
            },
        )

        assert response.status_code == 200
        instance = response.json()["omero_instances"][0]
        assert instance["password_stored"] is True
        assert "password" not in instance
        assert credentials.passwords == {"omero.example.com:4064:admin": "secret"}
        persisted = path.read_text()
        assert '"password"' not in persisted
        assert "secret" not in persisted

    async def test_patch_omero_duplicate_names_return_422(
        self,
        omero_settings_client: tuple[httpx.AsyncClient, SettingsStore, FakeOmeroCredentials, Path],
    ) -> None:
        client, _store, credentials, _path = omero_settings_client

        response = await client.patch(
            "/api/v1/settings",
            json={
                "omero_instances": [
                    {"name": "prod", "host": "one.example.com", "username": "a"},
                    {"name": " prod ", "host": "two.example.com", "username": "b"},
                ]
            },
        )

        assert response.status_code == 422
        assert credentials.passwords == {}

    async def test_patch_omero_remove_deletes_key(
        self,
        omero_settings_client: tuple[httpx.AsyncClient, SettingsStore, FakeOmeroCredentials, Path],
    ) -> None:
        client, _store, credentials, _path = omero_settings_client
        await client.patch(
            "/api/v1/settings",
            json={
                "omero_instances": [
                    {
                        "host": "omero.example.com",
                        "username": "admin",
                        "password": "secret",
                    }
                ]
            },
        )

        response = await client.patch("/api/v1/settings", json={"omero_instances": []})

        assert response.status_code == 200
        assert credentials.deleted == ["omero.example.com:4064:admin"]

    @pytest.mark.parametrize("mutate_first", [False, True], ids=["before", "after"])
    async def test_patch_omero_keyring_failure_returns_error_without_persisting(
        self,
        omero_settings_client: tuple[httpx.AsyncClient, SettingsStore, FakeOmeroCredentials, Path],
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
        mutate_first: bool,
    ) -> None:
        client, store, credentials, path = omero_settings_client
        instance = {"name": "Existing", "host": "omero.example.com", "username": "admin"}
        await store.patch({"omero_instances": [instance]})
        credentials.passwords["omero.example.com:4064:admin"] = "prior-password"
        before_disk, before_settings = path.read_bytes(), store.get()
        failure = OmeroCredentialError("keyring write failed")
        original_set = credentials.set_password
        fired = False

        def set_once(key: OmeroCredentialKey, password: str) -> None:
            nonlocal fired
            if not fired:
                fired = True
                if mutate_first:
                    original_set(key, password)
                raise failure
            original_set(key, password)

        monkeypatch.setattr(credentials, "set_password", set_once)
        with caplog.at_level(logging.ERROR, logger="bioimageflow_server.routers.settings"):
            response = await client.patch(
                "/api/v1/settings",
                json={"omero_instances": [{**instance, "password": "replacement-secret"}]},
            )
        assert response.status_code == 500
        assert response.json()["error"] == "settings_keyring_error"
        assert path.read_bytes() == before_disk and store.get() is before_settings
        assert credentials.passwords == {"omero.example.com:4064:admin": "prior-password"}
        assert "Settings keyring operation failed" in caplog.text
        assert "HTTP 500 returned" not in caplog.text
        followup = await client.get("/api/v1/settings")
        assert followup.status_code == 200
        assert followup.json()["omero_instances"] == [
            {**instance, "port": 4064, "password_stored": True}
        ]
        assert "prior-password" not in followup.text and "replacement-secret" not in followup.text
        assert all(
            '"password"' not in text for text in [followup.text, response.text, path.read_text()]
        )
