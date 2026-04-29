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
from bioimageflow_server.services.settings_store import SettingsStore


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _read_disk(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


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

    async def test_file_without_settings_version_loads_as_v1(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps(
                {"deployment_mode": "desktop", "external_editor": "vim"}
            )
        )
        store = SettingsStore(path=path)
        result = await store.load()
        assert result.external_editor == "vim"

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

    async def test_unknown_keys_are_stripped_before_validation(
        self, tmp_path: Path
    ) -> None:
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
        result = await store.patch({"execution_engine": "parsl"})
        assert result.execution_engine == "parsl"
        on_disk = _read_disk(path)
        assert on_disk["settings_version"] == 1
        assert on_disk["execution_engine"] == "parsl"
        assert store.get().execution_engine == "parsl"

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

    async def test_patch_negative_cache_max_executions(self, tmp_path: Path) -> None:
        store = SettingsStore(path=tmp_path / "s.json")
        await store.load()
        with pytest.raises(ValidationError):
            await store.patch({"cache_max_executions": -1})

    async def test_patch_invalid_cache_max_age(self, tmp_path: Path) -> None:
        store = SettingsStore(path=tmp_path / "s.json")
        await store.load()
        with pytest.raises(ValidationError):
            await store.patch({"cache_max_age": "1 day"})

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


class TestFlush:
    async def test_flush_is_noop(self, tmp_path: Path) -> None:
        store = SettingsStore(path=tmp_path / "s.json")
        await store.load()
        # Should complete without raising; v1 writes synchronously.
        await store.flush()
