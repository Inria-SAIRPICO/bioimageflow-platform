"""Tests for the SettingsStore service."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.settings import Settings
from bioimageflow_server.services.omero_credentials import OmeroCredentialError, OmeroCredentialKey
from bioimageflow_server.services.settings_store import SettingsStore


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _read_disk(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


class FakeOmeroCredentials:
    def __init__(self) -> None:
        self.passwords: dict[str, str] = {}
        self.deleted: list[str] = []
        self.fail_set = False
        self.fail_set_after: int | None = None
        self.set_calls = 0
        self.read_keys: list[OmeroCredentialKey] = []
        self.writes: list[tuple[OmeroCredentialKey, str]] = []

    def get_password(self, key: OmeroCredentialKey) -> str | None:
        self.read_keys.append(key)
        return self.passwords.get(key.username)

    def set_password(self, key: OmeroCredentialKey, password: str) -> None:
        self.set_calls += 1
        self.writes.append((key, password))
        if self.fail_set:
            raise OmeroCredentialError("keyring write failed")
        if self.fail_set_after is not None and self.set_calls > self.fail_set_after:
            raise OmeroCredentialError("keyring write failed")
        self.passwords[key.username] = password

    def delete_password(self, key: OmeroCredentialKey) -> None:
        self.deleted.append(key.username)
        self.passwords.pop(key.username, None)


class TestLoad:
    @pytest.mark.parametrize("configured,persisted", [("webapp", "desktop"), ("desktop", "webapp")])
    async def test_persisted_mode_cannot_override_process_policy(
        self, tmp_path: Path, configured: str, persisted: str
    ) -> None:
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"deployment_mode": persisted, "external_editor": "code"}))
        before = path.read_bytes()
        store = SettingsStore(path=path, deployment_mode=configured)  # type: ignore[arg-type]
        current = await store.load()
        assert current.deployment_mode == configured
        assert current.external_editor == "code"
        assert path.read_bytes() == before
        result = await store.patch({"node_data_page_size": 50})
        assert result.deployment_mode == configured
        assert _read_disk(path)["deployment_mode"] == configured

    async def test_default_uses_standard_user_path(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        store = SettingsStore.default()
        await store.load()

        assert store.path == tmp_path / ".bioimageflow" / "settings.json"
        assert store.get().deployment_mode == "desktop"

    async def test_missing_file_seeds_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        store = SettingsStore(path=path)
        result = await store.load()
        assert isinstance(result, Settings)
        assert result.deployment_mode == "desktop"
        # File should now exist with the version envelope.
        assert path.exists()
        on_disk = _read_disk(path)
        assert on_disk["settings_version"] == 3
        assert on_disk["deployment_mode"] == "desktop"
        assert on_disk["fiji_path"] is None

    async def test_missing_parent_directory_is_created(self, tmp_path: Path) -> None:
        # Parent directory does not yet exist.
        path = tmp_path / "nested" / "subdir" / "settings.json"
        store = SettingsStore(path=path)
        result = await store.load()
        assert path.exists()
        assert result.deployment_mode == "desktop"

    async def test_existing_valid_file_loads(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps(
                {
                    "settings_version": 1,
                    "deployment_mode": "desktop",
                    "external_editor": "code {file_path}",
                }
            )
        )
        store = SettingsStore(path=path)
        result = await store.load()
        assert result.external_editor == "code {file_path}"
        assert result.new_workflow_execution == "sequential"

    @pytest.mark.campaign_excluded(reason="parsl")
    async def test_legacy_execution_engine_parsl_loads_as_parallel(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps(
                {
                    "settings_version": 1,
                    "deployment_mode": "desktop",
                    "execution_engine": "parsl",
                }
            )
        )
        store = SettingsStore(path=path)
        result = await store.load()
        assert result.new_workflow_execution == "parallel"

    @pytest.mark.campaign_excluded(reason="parallel-scheduling")
    async def test_v1_execution_engine_migrates_to_v2_new_workflow_default(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps(
                {
                    "settings_version": 1,
                    "deployment_mode": "desktop",
                    "execution_engine": "parallel",
                }
            )
        )
        store = SettingsStore(path=path)

        result = await store.load()

        assert result.new_workflow_execution == "parallel"
        assert result.default_execution_target_id == "local"

    async def test_legacy_cache_pruning_keys_are_ignored_on_load(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps(
                {
                    "settings_version": 1,
                    "deployment_mode": "desktop",
                    "cache_max_executions": 3,
                    "cache_max_age": "30d",
                }
            )
        )
        store = SettingsStore(path=path)
        result = await store.load()
        assert not hasattr(result, "cache_max_executions")
        assert not hasattr(result, "cache_max_age")

    async def test_file_without_settings_version_loads_as_v1(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"deployment_mode": "desktop", "external_editor": "vim"}))
        store = SettingsStore(path=path)
        result = await store.load()
        assert result.external_editor == "vim"

    async def test_file_loads_unsafe_webapp_features_flag(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps(
                {
                    "settings_version": 1,
                    "deployment_mode": "webapp",
                    "enable_unsafe_webapp_features": True,
                }
            )
        )
        store = SettingsStore(path=path, deployment_mode="webapp")
        result = await store.load()
        assert result.enable_unsafe_webapp_features is True

    async def test_file_with_future_version_returns_defaults_without_overwrite(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = tmp_path / "settings.json"
        original = {"settings_version": 4, "external_editor": "x", "future_field": "y"}
        path.write_text(json.dumps(original))
        store = SettingsStore(path=path)
        with caplog.at_level("WARNING"):
            result = await store.load()
        assert result.external_editor is None  # defaults
        # File untouched.
        assert _read_disk(path) == original

    async def test_unknown_keys_are_stripped_before_validation(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps(
                {
                    "settings_version": 1,
                    "deployment_mode": "desktop",
                    "napari_env_path": "/legacy/napari",
                    "thumbnail_env_path": "/legacy/thumbnail",
                    "future_field": "abc",
                    "dev_mode": False,
                }
            )
        )
        store = SettingsStore(path=path)
        result = await store.load()
        assert result.deployment_mode == "desktop"
        assert "dev_mode" not in result.model_dump()
        # Original file is preserved (until next patch overwrites it).
        on_disk = _read_disk(path)
        assert on_disk["napari_env_path"] == "/legacy/napari"
        assert on_disk["thumbnail_env_path"] == "/legacy/thumbnail"
        assert on_disk["future_field"] == "abc"
        assert on_disk["dev_mode"] is False

    async def test_malformed_json_returns_defaults_without_overwrite(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = tmp_path / "settings.json"
        path.write_text("{not json")
        store = SettingsStore(path=path)
        with caplog.at_level("WARNING"):
            result = await store.load()
        assert result.deployment_mode == "desktop"
        # Broken file kept for inspection.
        assert path.read_text() == "{not json"

    async def test_parent_path_is_regular_file(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Make `tmp_path/foo` a regular file, then point settings at
        # `tmp_path/foo/settings.json`.
        regular_file = tmp_path / "foo"
        regular_file.write_text("blocking")
        path = regular_file / "settings.json"
        store = SettingsStore(path=path)
        with caplog.at_level("WARNING"):
            result = await store.load()
        assert result.deployment_mode == "desktop"

    async def test_permission_error_returns_defaults(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        path = tmp_path / "ro" / "settings.json"

        original_mkdir = Path.mkdir

        def deny_mkdir(self: Path, *args: Any, **kwargs: Any) -> None:
            if str(self) == str(path.parent):
                raise PermissionError("denied")
            return original_mkdir(self, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", deny_mkdir)

        store = SettingsStore(path=path)
        with caplog.at_level("WARNING"):
            result = await store.load()
        assert result.deployment_mode == "desktop"


class TestGet:
    async def test_get_returns_current_state(self, tmp_path: Path) -> None:
        store = SettingsStore(path=tmp_path / "s.json")
        await store.load()
        first = store.get()
        # Subsequent calls don't re-read disk.
        second = store.get()
        assert first is second

    def test_get_before_load_raises(self, tmp_path: Path) -> None:
        store = SettingsStore(path=tmp_path / "s.json")
        with pytest.raises(RuntimeError):
            store.get()


class TestPatch:
    @pytest.mark.parametrize(
        "configured,field,value",
        [
            ("webapp", "deployment_mode", "desktop"),
            ("desktop", "deployment_mode", "desktop"),
            ("webapp", "workspaces_root", "/client-root"),
        ],
    )
    async def test_process_policy_refusal_precedes_credentials_and_publication(
        self, tmp_path: Path, configured: str, field: str, value: str
    ) -> None:
        path = tmp_path / "settings.json"
        credentials = FakeOmeroCredentials()
        store = SettingsStore(path=path, deployment_mode=configured, omero_credentials=credentials)  # type: ignore[arg-type]
        current = await store.load()
        before = path.read_bytes()
        with pytest.raises(PermissionError) as refused:
            await store.patch(
                {
                    field: value,
                    "omero_instances": [
                        {
                            "name": "disposable",
                            "host": "fixture.invalid",
                            "username": "fake-user",
                            "password": "fake-password",
                        }
                    ],
                }
            )
        assert refused.value.field == field
        assert "fake-password" not in str(refused.value)
        assert store.get() is current
        assert path.read_bytes() == before
        assert credentials.read_keys == credentials.writes == credentials.deleted == []
        assert credentials.passwords == {}

    async def test_typed_registry_write_keeps_effective_mode_and_live_preferences(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "settings.json"
        store = SettingsStore(path=path, deployment_mode="webapp")
        current = await store.load()
        current.deployment_mode = "desktop"
        current.external_editor = "retained-live-value"
        result = await store.patch_napari_registry(0, {"napari_filename_rules": []})
        assert result.deployment_mode == "webapp"
        assert result.external_editor == "retained-live-value"
        assert store.get() is result
        assert _read_disk(path)["deployment_mode"] == "webapp"
        result.deployment_mode = "desktop"
        assert store.get() is result
        assert result.deployment_mode == "webapp"

    @pytest.mark.campaign_excluded(reason="parallel-scheduling")
    async def test_patch_updates_state_and_disk(self, tmp_path: Path) -> None:
        path = tmp_path / "s.json"
        store = SettingsStore(path=path)
        await store.load()
        result = await store.patch({"new_workflow_execution": "parallel"})
        assert result.new_workflow_execution == "parallel"
        on_disk = _read_disk(path)
        assert on_disk["settings_version"] == 3
        assert "execution_engine" not in on_disk
        assert on_disk["new_workflow_execution"] == "parallel"
        assert store.get().new_workflow_execution == "parallel"

    async def test_patch_old_execution_engine_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "s.json"
        store = SettingsStore(path=path)
        await store.load()
        with pytest.raises(ValidationError):
            await store.patch({"execution_engine": "parsl"})
        assert "execution_engine" not in _read_disk(path)

    async def test_patch_rejects_invalid_value(self, tmp_path: Path) -> None:
        path = tmp_path / "s.json"
        store = SettingsStore(path=path)
        await store.load()
        before = path.read_text()
        with pytest.raises(ValidationError):
            await store.patch({"new_workflow_execution": "dask"})
        # Disk unchanged.
        assert path.read_text() == before
        assert store.get().new_workflow_execution == "sequential"

    async def test_patch_rejects_unknown_keys(self, tmp_path: Path) -> None:
        path = tmp_path / "s.json"
        store = SettingsStore(path=path)
        await store.load()
        before = path.read_text()
        with pytest.raises(ValidationError) as exc_info:
            await store.patch({"foo": 1})
        assert "foo" in str(exc_info.value)
        assert path.read_text() == before

    async def test_patch_cache_max_executions_is_deprecated(self, tmp_path: Path) -> None:
        store = SettingsStore(path=tmp_path / "s.json")
        await store.load()
        with pytest.raises(ValidationError):
            await store.patch({"cache_max_executions": 0})

    async def test_patch_cache_max_age_is_deprecated(self, tmp_path: Path) -> None:
        store = SettingsStore(path=tmp_path / "s.json")
        await store.load()
        with pytest.raises(ValidationError):
            await store.patch({"cache_max_age": "30d"})

    async def test_patch_clears_value_with_none(self, tmp_path: Path) -> None:
        store = SettingsStore(path=tmp_path / "s.json")
        await store.load()
        await store.patch({"external_editor": "code"})
        assert store.get().external_editor == "code"
        await store.patch({"external_editor": None})
        assert store.get().external_editor is None

    async def test_tilde_expansion_for_tool_store_path(self, tmp_path: Path) -> None:
        store = SettingsStore(path=tmp_path / "s.json")
        await store.load()
        await store.patch({"tool_store_path": "~/foo"})
        assert store.get().tool_store_path == "~/foo"
        resolved = store.resolved_tool_store_path()
        assert resolved.is_absolute()
        assert "~" not in str(resolved)

    async def test_atomic_write_rename_failure_keeps_original(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "s.json"
        store = SettingsStore(path=path)
        await store.load()
        original_content = path.read_text()

        def boom(*_: Any, **__: Any) -> None:
            raise OSError("rename failed")

        monkeypatch.setattr(os, "replace", boom)
        with pytest.raises(OSError):
            await store.patch({"external_editor": "vim"})
        # Original file untouched.
        assert path.read_text() == original_content

    async def test_atomic_write_temp_creation_failure_keeps_original(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = tmp_path / "s.json"
        store = SettingsStore(path=path)
        await store.load()
        original_content = path.read_text()

        real_open = open

        def fail_for_tmp(file: Any, *args: Any, **kwargs: Any) -> Any:
            if isinstance(file, (str, Path)) and str(file).endswith(".tmp"):
                raise OSError("disk full")
            return real_open(file, *args, **kwargs)

        # Patch only the open used by SettingsStore (not the global builtin).
        import bioimageflow_server.services.settings_store as ss_mod

        monkeypatch.setattr(ss_mod, "open", fail_for_tmp, raising=False)
        with pytest.raises(OSError):
            await store.patch({"external_editor": "vim"})
        assert path.read_text() == original_content

    async def test_concurrent_patches_serialize(self, tmp_path: Path) -> None:
        store = SettingsStore(path=tmp_path / "s.json")
        await store.load()
        await asyncio.gather(
            store.patch({"external_editor": "vim"}),
            store.patch({"update_mode": "manual"}),
        )
        s = store.get()
        assert s.external_editor == "vim"
        assert s.update_mode == "manual"

    async def test_omero_patch_accepts_transient_password_without_persisting_it(
        self, tmp_path: Path
    ) -> None:
        credentials = FakeOmeroCredentials()
        path = tmp_path / "s.json"
        store = SettingsStore(path=path, omero_credentials=credentials)
        await store.load()

        result = await store.patch(
            {
                "omero_instances": [
                    {
                        "name": " Prod ",
                        "host": " omero.example.com ",
                        "port": 4064,
                        "username": " admin ",
                        "password": "secret",
                    }
                ]
            }
        )

        assert result.omero_instances[0].name == "Prod"
        assert result.omero_instances[0].host == "omero.example.com"
        assert credentials.passwords == {"omero.example.com:4064:admin": "secret"}
        on_disk = _read_disk(path)
        assert on_disk["omero_instances"] == [
            {
                "name": "Prod",
                "host": "omero.example.com",
                "port": 4064,
                "username": "admin",
            }
        ]
        assert "password" not in json.dumps(on_disk)
        assert "password_stored" not in json.dumps(on_disk)

    async def test_omero_remove_deletes_stored_password(self, tmp_path: Path) -> None:
        credentials = FakeOmeroCredentials()
        store = SettingsStore(path=tmp_path / "s.json", omero_credentials=credentials)
        await store.load()
        aliases = [
            {
                "name": "First",
                "host": "omero.example.com",
                "username": "admin",
                "password": "first",
            },
            {
                "name": "Second",
                "host": " omero.example.com ",
                "username": " admin ",
                "password": "last",
            },
        ]
        await store.patch({"omero_instances": aliases})
        assert credentials.passwords == {"omero.example.com:4064:admin": "last"}
        await store.patch(
            {"omero_instances": [{k: v for k, v in aliases[1].items() if k != "password"}]}
        )
        assert credentials.deleted == []
        assert credentials.passwords == {"omero.example.com:4064:admin": "last"}
        await store.patch({"omero_instances": []})
        assert credentials.deleted == ["omero.example.com:4064:admin"]
        assert credentials.passwords == {}

    async def test_omero_rekey_without_password_deletes_old_key(self, tmp_path: Path) -> None:
        credentials = FakeOmeroCredentials()
        store = SettingsStore(path=tmp_path / "s.json", omero_credentials=credentials)
        await store.load()
        await store.patch(
            {
                "omero_instances": [
                    {
                        "host": "old.example.com",
                        "username": "admin",
                        "password": "secret",
                    }
                ]
            }
        )

        await store.patch({"omero_instances": [{"host": "new.example.com", "username": "admin"}]})

        assert credentials.deleted == ["old.example.com:4064:admin"]
        assert credentials.passwords == {}
        assert not store.omero_password_stored(store.get().omero_instances[0])

    async def test_omero_set_failure_leaves_disk_and_memory_unchanged(self, tmp_path: Path) -> None:
        credentials = FakeOmeroCredentials()
        credentials.fail_set = True
        path = tmp_path / "s.json"
        store = SettingsStore(path=path, omero_credentials=credentials)
        await store.load()
        before_disk = path.read_text()
        before_memory = store.get()

        with pytest.raises(OmeroCredentialError):
            await store.patch(
                {
                    "omero_instances": [
                        {
                            "host": "omero.example.com",
                            "username": "admin",
                            "password": "secret",
                        }
                    ]
                }
            )

        assert path.read_text() == before_disk
        assert store.get() is before_memory
        assert credentials.passwords == {}

    @pytest.mark.parametrize(
        "original", [None, "", "prior-password"], ids=["absent", "empty", "populated"]
    )
    async def test_omero_settings_write_failure_rolls_back_written_password(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, original: str | None
    ) -> None:
        credentials = FakeOmeroCredentials()
        path = tmp_path / "s.json"
        store = SettingsStore(path=path, omero_credentials=credentials)
        await store.load()
        instance = {"host": "omero.example.com", "username": "admin"}
        await store.patch({"omero_instances": [instance]})
        key = OmeroCredentialKey("bioimageflow-omero", "omero.example.com:4064:admin")
        if original is not None:
            credentials.passwords[key.username] = original
        before_passwords = dict(credentials.passwords)
        before_disk, before_memory = path.read_bytes(), store.get()
        failure = OSError("rename failed")

        def boom(*_: Any, **__: Any) -> None:
            raise failure

        monkeypatch.setattr(os, "replace", boom)
        with pytest.raises(OSError) as raised:
            await store.patch({"omero_instances": [{**instance, "password": "replacement-secret"}]})
        assert raised.value is failure
        assert path.read_bytes() == before_disk
        assert store.get() is before_memory
        assert credentials.passwords == before_passwords
        assert credentials.deleted == ([key.username] if original is None else [])
        assert "replacement-secret" not in path.read_text()
        assert '"password"' not in path.read_text()

    async def test_omero_partial_keyring_set_failure_rolls_back_written_keys(
        self, tmp_path: Path
    ) -> None:
        credentials = FakeOmeroCredentials()
        credentials.fail_set_after = 1
        path = tmp_path / "s.json"
        store = SettingsStore(path=path, omero_credentials=credentials)
        await store.load()
        before_disk = path.read_text()

        with pytest.raises(OmeroCredentialError):
            await store.patch(
                {
                    "omero_instances": [
                        {
                            "host": "one.example.com",
                            "username": "admin",
                            "password": "one",
                        },
                        {
                            "host": "two.example.com",
                            "username": "admin",
                            "password": "two",
                        },
                    ]
                }
            )

        assert path.read_text() == before_disk
        assert credentials.passwords == {}
        assert credentials.deleted == ["two.example.com:4064:admin", "one.example.com:4064:admin"]

    @pytest.mark.parametrize("fault", ["before", "after", "interruption"])
    async def test_omero_attempted_set_failure_restores_originals(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
    ) -> None:
        credentials = FakeOmeroCredentials()
        path = tmp_path / "s.json"
        store = SettingsStore(path=path, omero_credentials=credentials)
        await store.load()
        records = [
            {"host": f"{name}.example.com", "username": "admin"} for name in ["one", "two", "three"]
        ]
        await store.patch({"omero_instances": records})
        keys = [OmeroCredentialKey.from_instance(x) for x in store.get().omero_instances]
        credentials.passwords = {keys[0].username: "old-one", keys[2].username: "untouched"}
        before = dict(credentials.passwords)
        before_disk, before_memory = path.read_bytes(), store.get()
        failure = (
            asyncio.CancelledError("interrupted")
            if fault == "interruption"
            else OmeroCredentialError("write refused")
        )
        original_set = credentials.set_password
        fired = False

        def set_once(key: OmeroCredentialKey, password: str) -> None:
            nonlocal fired
            if key == keys[1] and not fired:
                fired = True
                if fault != "before":
                    original_set(key, password)
                raise failure
            original_set(key, password)

        monkeypatch.setattr(credentials, "set_password", set_once)
        with pytest.raises(type(failure)) as raised:
            await store.patch({"omero_instances": [{**x, "password": "new"} for x in records]})
        assert raised.value is failure
        assert credentials.passwords == before
        assert path.read_bytes() == before_disk
        assert store.get() is before_memory
        assert credentials.deleted == [keys[1].username]
        assert keys[2] in credentials.read_keys
        assert all(key != keys[2] for key, _ in credentials.writes)

    async def test_omero_preimage_read_failure_precedes_all_mutations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        credentials = FakeOmeroCredentials()
        path = tmp_path / "s.json"
        store = SettingsStore(path=path, omero_credentials=credentials)
        await store.load()
        before_disk, before_memory = path.read_bytes(), store.get()
        credentials.passwords["one.example.com:4064:admin"] = "prior"
        before = dict(credentials.passwords)
        failure = OmeroCredentialError("snapshot refused")
        original_get = credentials.get_password

        def get_once(key: OmeroCredentialKey) -> str | None:
            value = original_get(key)
            if key.username.startswith("two."):
                raise failure
            return value

        def no_write(_settings: Settings) -> None:
            pytest.fail("settings publication attempted before complete preimages")

        monkeypatch.setattr(credentials, "get_password", get_once)
        monkeypatch.setattr(store, "_write_atomic", no_write)
        with pytest.raises(OmeroCredentialError) as raised:
            await store.patch(
                {
                    "omero_instances": [
                        {"host": f"{name}.example.com", "username": "admin", "password": "new"}
                        for name in ["one", "two"]
                    ]
                }
            )
        assert raised.value is failure
        assert credentials.writes == [] and credentials.deleted == []
        assert credentials.passwords == before
        assert path.read_bytes() == before_disk and store.get() is before_memory

    async def test_omero_alias_failure_restores_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        credentials = FakeOmeroCredentials()
        path = tmp_path / "s.json"
        store = SettingsStore(path=path, omero_credentials=credentials)
        await store.load()
        credentials.passwords["omero.example.com:4064:admin"] = "prior"
        before_disk, before_memory = path.read_bytes(), store.get()
        failure = OSError("replace refused")

        def boom(*_: Any, **__: Any) -> None:
            raise failure

        monkeypatch.setattr(os, "replace", boom)
        with pytest.raises(OSError) as raised:
            await store.patch(
                {
                    "omero_instances": [
                        {
                            "name": "First",
                            "host": "omero.example.com",
                            "username": "admin",
                            "password": "first",
                        },
                        {
                            "name": "Second",
                            "host": " omero.example.com ",
                            "username": " admin ",
                            "password": "second",
                        },
                    ]
                }
            )
        assert raised.value is failure
        assert len(credentials.read_keys) == 1
        assert [password for _key, password in credentials.writes] == ["first", "second", "prior"]
        assert credentials.passwords == {"omero.example.com:4064:admin": "prior"}
        assert credentials.deleted == []
        assert path.read_bytes() == before_disk and store.get() is before_memory

    async def test_omero_failed_restoration_continues_without_secret_logs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        credentials = FakeOmeroCredentials()
        path = tmp_path / "s.json"
        store = SettingsStore(path=path, omero_credentials=credentials)
        await store.load()
        records = [
            {"host": f"{name}.example.com", "username": "admin"} for name in ["one", "two", "three"]
        ]
        await store.patch({"omero_instances": records})
        keys = [OmeroCredentialKey.from_instance(x) for x in store.get().omero_instances]
        credentials.passwords = {keys[0].username: "old-one", keys[2].username: "old-three"}
        before_disk, before_memory = path.read_bytes(), store.get()
        failure = OmeroCredentialError("initial write refused")
        sentinel = "RESTORE-SECRET-SENTINEL"
        original_set, original_delete = credentials.set_password, credentials.delete_password
        rollback: list[tuple[str, OmeroCredentialKey]] = []
        failing = False

        def set_fault(key: OmeroCredentialKey, password: str) -> None:
            nonlocal failing
            if failing:
                rollback.append(("set", key))
                if key == keys[2]:
                    raise OmeroCredentialError(sentinel) from RuntimeError(sentinel)
            original_set(key, password)
            if key == keys[2] and not failing:
                failing = True
                raise failure

        def delete_fault(key: OmeroCredentialKey) -> None:
            rollback.append(("delete", key))
            if key == keys[1]:
                raise OmeroCredentialError(sentinel) from RuntimeError(sentinel)
            original_delete(key)

        monkeypatch.setattr(credentials, "set_password", set_fault)
        monkeypatch.setattr(credentials, "delete_password", delete_fault)
        with caplog.at_level(logging.WARNING, logger="bioimageflow_server.services.settings_store"):
            with pytest.raises(OmeroCredentialError) as raised:
                await store.patch({"omero_instances": [{**x, "password": "new"} for x in records]})
        assert raised.value is failure
        assert rollback == [("set", keys[2]), ("delete", keys[1]), ("set", keys[0])]
        assert credentials.passwords == {
            keys[0].username: "old-one",
            keys[1].username: "new",
            keys[2].username: "new",
        }
        assert path.read_bytes() == before_disk and store.get() is before_memory
        records_logged = [
            x for x in caplog.records if x.name == "bioimageflow_server.services.settings_store"
        ]
        assert len(records_logged) == 1
        record = records_logged[0]
        assert record.getMessage() == "OMERO credential rollback could not restore 2 keys"
        assert record.args == (2,) and record.exc_info is None
        assert sentinel not in caplog.text
        assert all(key.username not in caplog.text for key in keys)


class TestFlush:
    async def test_flush_is_noop(self, tmp_path: Path) -> None:
        store = SettingsStore(path=tmp_path / "s.json")
        await store.load()
        # Should complete without raising; v1 writes synchronously.
        await store.flush()
