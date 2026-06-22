"""Tests for the SettingsStore service."""

from __future__ import annotations

import asyncio
import json
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

    def get_password(self, key: OmeroCredentialKey) -> str | None:
        return self.passwords.get(key.username)

    def set_password(self, key: OmeroCredentialKey, password: str) -> None:
        self.set_calls += 1
        if self.fail_set:
            raise OmeroCredentialError("keyring write failed")
        if self.fail_set_after is not None and self.set_calls > self.fail_set_after:
            raise OmeroCredentialError("keyring write failed")
        self.passwords[key.username] = password

    def delete_password(self, key: OmeroCredentialKey) -> None:
        self.deleted.append(key.username)
        self.passwords.pop(key.username, None)


class TestLoad:
    async def test_missing_file_seeds_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        store = SettingsStore(path=path)
        result = await store.load()
        assert isinstance(result, Settings)
        assert result.deployment_mode == "desktop"
        assert result.output_data_folder == "~/bioimageflow_data/"
        # File should now exist with the version envelope.
        assert path.exists()
        on_disk = _read_disk(path)
        assert on_disk["settings_version"] == 1
        assert on_disk["deployment_mode"] == "desktop"

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
        assert result.execution_engine == "sequential"  # default

    async def test_legacy_execution_engine_parsl_loads_as_parallel(
        self, tmp_path: Path
    ) -> None:
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
        assert result.execution_engine == "parallel"

    async def test_legacy_cache_pruning_keys_are_ignored_on_load(
        self, tmp_path: Path
    ) -> None:
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
        original = {"settings_version": 2, "external_editor": "x", "future_field": "y"}
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
                    "future_field": "abc",
                }
            )
        )
        store = SettingsStore(path=path)
        result = await store.load()
        assert result.deployment_mode == "desktop"
        # Original file is preserved (until next patch overwrites it).
        on_disk = _read_disk(path)
        assert on_disk["future_field"] == "abc"

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
    async def test_patch_updates_state_and_disk(self, tmp_path: Path) -> None:
        path = tmp_path / "s.json"
        store = SettingsStore(path=path)
        await store.load()
        result = await store.patch({"execution_engine": "parallel"})
        assert result.execution_engine == "parallel"
        on_disk = _read_disk(path)
        assert on_disk["settings_version"] == 1
        assert on_disk["execution_engine"] == "parallel"
        assert store.get().execution_engine == "parallel"

    async def test_patch_legacy_execution_engine_parsl_migrates_to_parallel(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "s.json"
        store = SettingsStore(path=path)
        await store.load()
        result = await store.patch({"execution_engine": "parsl"})
        assert result.execution_engine == "parallel"
        assert _read_disk(path)["execution_engine"] == "parallel"

    async def test_patch_rejects_invalid_value(self, tmp_path: Path) -> None:
        path = tmp_path / "s.json"
        store = SettingsStore(path=path)
        await store.load()
        before = path.read_text()
        with pytest.raises(ValidationError):
            await store.patch({"execution_engine": "dask"})
        # Disk unchanged.
        assert path.read_text() == before
        assert store.get().execution_engine == "sequential"

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

    async def test_tilde_expansion_for_output_data_folder(self, tmp_path: Path) -> None:
        store = SettingsStore(path=tmp_path / "s.json")
        await store.load()
        await store.patch({"output_data_folder": "~/custom"})
        assert store.get().output_data_folder == "~/custom"
        resolved = store.resolved_output_data_folder()
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
            store.patch({"napari_env_path": "/envs/napari"}),
        )
        s = store.get()
        assert s.external_editor == "vim"
        assert s.napari_env_path == "/envs/napari"

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

    async def test_omero_settings_write_failure_rolls_back_written_password(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        credentials = FakeOmeroCredentials()
        path = tmp_path / "s.json"
        store = SettingsStore(path=path, omero_credentials=credentials)
        await store.load()
        before_disk = path.read_text()
        before_memory = store.get()

        def boom(*_: Any, **__: Any) -> None:
            raise OSError("rename failed")

        monkeypatch.setattr(os, "replace", boom)

        with pytest.raises(OSError):
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
        assert credentials.deleted == ["omero.example.com:4064:admin"]
        assert "password" not in path.read_text()

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
        assert credentials.deleted == ["one.example.com:4064:admin"]


class TestFlush:
    async def test_flush_is_noop(self, tmp_path: Path) -> None:
        store = SettingsStore(path=tmp_path / "s.json")
        await store.load()
        # Should complete without raising; v1 writes synchronously.
        await store.flush()
