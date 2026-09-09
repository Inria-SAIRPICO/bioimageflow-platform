from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from bioimageflow_server.models.execution_profiles import ExecutionProfileCreate
from bioimageflow_server.services.execution_profiles import (
    ExecutionProfileConflictError,
    ExecutionProfileInUseError,
    ExecutionProfileStore,
    load_cluster_config,
)


pytestmark = [
    pytest.mark.anyio,
    pytest.mark.campaign_excluded(reason="managed-remote"),
]


def write_config(path: Path, *, host: str = "cluster") -> Path:
    path.write_text(
        "from bioimageflow.cluster import RemoteCluster\n"
        f"cluster = RemoteCluster(host={host!r}, root='/shared/bioimageflow')\n",
        encoding="utf-8",
    )
    return path


def profile_fields(path: Path, **changes: object) -> ExecutionProfileCreate:
    payload: dict[str, object] = {
        "name": "Site cluster",
        "enabled": True,
        "config_path": str(path),
    }
    payload.update(changes)
    return ExecutionProfileCreate.model_validate(payload)


async def test_create_update_reload_and_compare_and_swap(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    config = write_config(tmp_path / "cluster.py")
    store = ExecutionProfileStore(path)
    await store.load()

    created = await store.create(profile_fields(config))
    assert created.schema_ == "bioimageflow.platform.execution-profile.v2"
    assert created.cluster_host == "cluster"
    assert created.cluster_root == "/shared/bioimageflow"
    assert created.config_digest.startswith("sha256:")

    updated = await store.update(
        created.id,
        created.revision,
        profile_fields(config, name="Renamed"),
    )
    assert updated.revision == 2
    with pytest.raises(ExecutionProfileConflictError):
        await store.update(created.id, 1, profile_fields(config))

    reloaded = ExecutionProfileStore(path)
    await reloaded.load()
    assert reloaded.get(created.id) == updated


async def test_failed_atomic_replace_rolls_back_in_memory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ExecutionProfileStore(tmp_path / "profiles.json")
    config = write_config(tmp_path / "cluster.py")
    await store.load()
    created = await store.create(profile_fields(config))

    monkeypatch.setattr("bioimageflow_server.services.execution_profiles.os.replace", lambda *_: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(OSError, match="boom"):
        await store.update(created.id, 1, profile_fields(config, name="Changed"))
    assert store.get(created.id) == created


async def test_delete_refuses_profile_referenced_by_non_terminal_run(tmp_path: Path) -> None:
    store = ExecutionProfileStore(tmp_path / "profiles.json")
    config = write_config(tmp_path / "cluster.py")
    await store.load()
    created = await store.create(profile_fields(config))
    store.set_reference_checker(lambda profile_id: profile_id == created.id)
    with pytest.raises(ExecutionProfileInUseError):
        await store.delete(created.id, created.revision)


async def test_v1_profiles_are_dropped_without_archive(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps({"profiles_version": 1, "profiles": [{"secret": "legacy"}]}),
        encoding="utf-8",
    )
    store = ExecutionProfileStore(path)
    assert await store.load() == []
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "profiles_version": 2,
        "profiles": [],
    }
    assert not any(item.name.startswith("profiles.json.") for item in tmp_path.iterdir())


async def test_loader_rejects_symlink_and_changed_digest(tmp_path: Path) -> None:
    config = write_config(tmp_path / "cluster.py")
    loaded = load_cluster_config(config)
    config.write_text(config.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        load_cluster_config(config, expected_digest=loaded.digest)
    link = tmp_path / "link.py"
    link.symlink_to(config)
    with pytest.raises(ValueError, match="symbolic link"):
        load_cluster_config(link)


async def test_loader_requires_exact_top_level_remote_cluster(tmp_path: Path) -> None:
    config = tmp_path / "cluster.py"
    config.write_text("cluster = object()\n", encoding="utf-8")
    with pytest.raises(ValueError, match="top-level cluster"):
        load_cluster_config(config)


async def test_loader_rejects_file_mutation_during_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = write_config(tmp_path / "cluster.py")
    original_read = os.read
    changed = False

    def mutating_read(descriptor: int, size: int) -> bytes:
        nonlocal changed
        chunk = original_read(descriptor, size)
        if chunk and not changed:
            changed = True
            config.write_text(config.read_text(encoding="utf-8") + "# raced\n", encoding="utf-8")
        return chunk

    monkeypatch.setattr("bioimageflow_server.services.execution_profiles.os.read", mutating_read)
    with pytest.raises(ValueError, match="changed while"):
        load_cluster_config(config)
