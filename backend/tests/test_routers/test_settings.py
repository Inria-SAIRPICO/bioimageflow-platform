"""Tests for the /settings router."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.omero_credentials import OmeroCredentialError, OmeroCredentialKey
from bioimageflow_server.services.settings_store import SettingsStore


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def settings_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    settings_path = tmp_path / "settings.json"
    store = SettingsStore(path=settings_path)
    config = AppConfig(settings_store=store, deployment_mode="desktop")
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
    credentials = FakeOmeroCredentials()
    store = SettingsStore(path=settings_path, omero_credentials=credentials)
    config = AppConfig(settings_store=store, deployment_mode="desktop")
    app = create_app(config)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, store, credentials, settings_path


class TestGetSettings:
    async def test_default_app_exposes_settings_endpoint(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("bioimageflow_server.app.get_home", lambda: tmp_path)
        app = create_app(AppConfig(disable_hot_reload=True))

        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/settings")

        assert response.status_code == 200
        body = response.json()
        assert body["deployment_mode"] == "desktop"
        assert "resolved_tool_store_path" in body

    async def test_get_returns_full_model(self, settings_client: httpx.AsyncClient) -> None:
        response = await settings_client.get("/api/v1/settings")
        assert response.status_code == 200
        body = response.json()
        # Wrapper contains the Settings fields plus the resolved-path helpers.
        assert body["deployment_mode"] == "desktop"
        assert body["execution_engine"] == "sequential"
        assert body["external_editor"] is None
        assert "resolved_tool_store_path" in body
        assert "resolved_output_data_folder" in body
        # Resolved paths should be absolute.
        assert body["resolved_tool_store_path"].startswith("/")
        assert body["resolved_output_data_folder"].startswith("/")

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
    ) -> None:
        client, store, credentials, _path = omero_settings_client
        await store.patch({"omero_instances": [{"host": "omero.example.com", "username": "admin"}]})
        credentials.fail_get = True

        response = await client.get("/api/v1/settings")

        assert response.status_code == 500
        body = response.json()
        assert body["error"] == "settings_keyring_error"
        assert body["detail"] == "keyring read failed"


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

    async def test_patch_invalid_value(self, settings_client: httpx.AsyncClient) -> None:
        response = await settings_client.patch(
            "/api/v1/settings", json={"execution_engine": "dask"}
        )
        assert response.status_code == 422

    async def test_patch_unknown_key(self, settings_client: httpx.AsyncClient) -> None:
        response = await settings_client.patch("/api/v1/settings", json={"foo": 1})
        assert response.status_code == 422

    async def test_patch_dev_mode_false_rejected(self, settings_client: httpx.AsyncClient) -> None:
        response = await settings_client.patch("/api/v1/settings", json={"dev_mode": False})
        assert response.status_code == 422
        body = response.json()
        # ErrorResponse shape from app.py.
        assert "dev_mode cannot be disabled" in body["detail"]

    async def test_patch_dev_mode_true_accepted(self, settings_client: httpx.AsyncClient) -> None:
        response = await settings_client.patch("/api/v1/settings", json={"dev_mode": True})
        assert response.status_code == 200

    async def test_patch_unsafe_webapp_features_rejected(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        response = await settings_client.patch(
            "/api/v1/settings",
            json={"enable_unsafe_webapp_features": True},
        )
        assert response.status_code == 422
        assert "settings file" in response.json()["detail"]

    async def test_patch_empty_body(self, settings_client: httpx.AsyncClient) -> None:
        response = await settings_client.patch("/api/v1/settings", json={})
        assert response.status_code == 200

    async def test_patch_clear_with_null(self, settings_client: httpx.AsyncClient) -> None:
        await settings_client.patch("/api/v1/settings", json={"external_editor": "vim"})
        response = await settings_client.patch("/api/v1/settings", json={"external_editor": None})
        assert response.status_code == 200
        assert response.json()["external_editor"] is None

    async def test_patch_negative_cache_max_executions(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        response = await settings_client.patch(
            "/api/v1/settings", json={"cache_max_executions": -1}
        )
        assert response.status_code == 422

    async def test_patch_zero_cache_max_executions_accepted(
        self, settings_client: httpx.AsyncClient
    ) -> None:
        response = await settings_client.patch("/api/v1/settings", json={"cache_max_executions": 0})
        assert response.status_code == 200
        assert response.json()["cache_max_executions"] == 0

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
        assert "password" not in path.read_text()

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

    async def test_patch_omero_keyring_failure_returns_error_without_persisting(
        self,
        omero_settings_client: tuple[httpx.AsyncClient, SettingsStore, FakeOmeroCredentials, Path],
    ) -> None:
        client, store, credentials, path = omero_settings_client
        before_disk = path.read_text()
        before_settings = store.get()
        credentials.fail_set = True

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

        assert response.status_code == 500
        assert response.json()["error"] == "settings_keyring_error"
        assert path.read_text() == before_disk
        assert store.get() is before_settings


class TestDevModeAtModelLayer:
    """The model itself stays permissive — only the router rejects dev_mode=False."""

    def test_settings_dev_mode_false_constructible(self) -> None:
        from bioimageflow_server.models.settings import Settings

        s = Settings(deployment_mode="desktop", dev_mode=False)
        assert s.dev_mode is False
