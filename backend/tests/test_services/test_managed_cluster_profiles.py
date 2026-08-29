"""Adversarial contracts for trusted managed-cluster profile persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bioimageflow.cluster import RemoteCluster
from bioimageflow_server.models.execution_profiles import ExecutionProfileCreate
from bioimageflow_server.services.execution_profiles import (
    ExecutionProfileStore,
    load_cluster_config,
)
from bioimageflow_server.services.settings_store import SettingsStore


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _write_cluster_config(path: Path, *, host: str = "site-hpc") -> None:
    path.write_text(
        "\n".join(
            (
                "from bioimageflow.cluster import RemoteCluster",
                "",
                "cluster = RemoteCluster(",
                f"    host={host!r},",
                "    root='/shared/project/bioimageflow',",
                ")",
                "",
            )
        ),
        encoding="utf-8",
    )


def _profile(path: Path, **changes: object) -> ExecutionProfileCreate:
    payload: dict[str, object] = {
        "name": "Site HPC",
        "enabled": True,
        "config_path": str(path),
    }
    payload.update(changes)
    return ExecutionProfileCreate.model_validate(payload)


def test_trusted_config_requires_top_level_exact_remote_cluster(tmp_path: Path) -> None:
    valid = tmp_path / "cluster.py"
    _write_cluster_config(valid)

    loaded = load_cluster_config(valid)

    assert type(loaded.cluster) is RemoteCluster
    assert loaded.cluster.host == "site-hpc"
    assert loaded.cluster.root.as_posix() == "/shared/project/bioimageflow"
    assert loaded.digest.startswith("sha256:")

    missing = tmp_path / "missing.py"
    missing.write_text("answer = 42\n", encoding="utf-8")
    with pytest.raises(ValueError, match="cluster"):
        load_cluster_config(missing)

    wrong = tmp_path / "wrong.py"
    wrong.write_text("cluster = object()\n", encoding="utf-8")
    with pytest.raises((TypeError, ValueError), match="RemoteCluster"):
        load_cluster_config(wrong)

    subclass = tmp_path / "subclass.py"
    subclass.write_text(
        "\n".join(
            (
                "from bioimageflow.cluster import RemoteCluster",
                "class CustomCluster(RemoteCluster):",
                "    pass",
                "cluster = CustomCluster(host='site-hpc', root='/shared/root')",
                "",
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises((TypeError, ValueError), match="exact RemoteCluster"):
        load_cluster_config(subclass)


def test_config_digest_binds_exact_bytes_and_rejects_symlinks(tmp_path: Path) -> None:
    config = tmp_path / "cluster.py"
    _write_cluster_config(config)
    loaded = load_cluster_config(config)

    _write_cluster_config(config, host="changed-hpc")
    with pytest.raises(ValueError, match="digest"):
        load_cluster_config(config, expected_digest=loaded.digest)

    symlink = tmp_path / "cluster-link.py"
    symlink.symlink_to(config)
    with pytest.raises(ValueError, match="symlink"):
        load_cluster_config(symlink)


async def test_v2_profile_persists_only_non_secret_reconnectable_facts(tmp_path: Path) -> None:
    config = tmp_path / "cluster.py"
    _write_cluster_config(config)
    path = tmp_path / "profiles.json"
    store = ExecutionProfileStore(path)
    await store.load()

    created = await store.create(_profile(config))
    payload = json.loads(path.read_text(encoding="utf-8"))
    persisted = payload["profiles"][0]

    assert payload["profiles_version"] == 2
    assert created.config_digest.startswith("sha256:")
    assert persisted == {
        "schema": "bioimageflow.platform.execution-profile.v2",
        "id": created.id,
        "revision": 1,
        "name": "Site HPC",
        "enabled": True,
        "config_path": str(config),
        "config_digest": created.config_digest,
        "cluster_host": "site-hpc",
        "cluster_root": "/shared/project/bioimageflow",
    }
    serialized = path.read_text(encoding="utf-8")
    assert "secret" not in serialized.casefold()
    assert "RemoteCluster" not in serialized

    reloaded = ExecutionProfileStore(path)
    await reloaded.load()
    assert reloaded.get(created.id) == created


async def test_v1_profile_file_is_dropped_without_archive_or_secret_retention(
    tmp_path: Path,
) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps(
            {
                "profiles_version": 1,
                "profiles": [
                    {
                        "schema": "bioimageflow.platform.execution-profile.v1",
                        "id": "profile_" + "1" * 32,
                        "revision": 7,
                        "name": "Obsolete agent transport",
                        "enabled": True,
                        "mode": "submitted_remote",
                        "transport": {
                            "host": "legacy-hpc",
                            "remote_executable": "/usr/bin/cluster-agent",
                            "staging_root": "/legacy/staging",
                            "literal_secret": "must-disappear",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    store = ExecutionProfileStore(path)

    loaded = await store.load()

    assert loaded == []
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "profiles_version": 2,
        "profiles": [],
    }
    assert not any(item.name.startswith("profiles.json.") for item in tmp_path.iterdir())
    assert "must-disappear" not in path.read_text(encoding="utf-8")


async def test_v1_profile_drop_durably_repairs_removed_default_target(
    tmp_path: Path,
) -> None:
    obsolete_id = "profile_" + "1" * 32
    profiles_path = tmp_path / "profiles.json"
    profiles_path.write_text(
        json.dumps({"profiles_version": 1, "profiles": [{"id": obsolete_id}]}),
        encoding="utf-8",
    )
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "settings_version": 2,
                "deployment_mode": "desktop",
                "default_execution_target_id": obsolete_id,
            }
        ),
        encoding="utf-8",
    )
    profiles = ExecutionProfileStore(profiles_path)
    settings = SettingsStore(settings_path)

    await settings.load()
    loaded = await profiles.load()
    await settings.ensure_default_execution_target(
        {profile.id for profile in loaded if profile.enabled}
    )

    assert settings.get().default_execution_target_id == "local"
    assert json.loads(settings_path.read_text(encoding="utf-8"))[
        "default_execution_target_id"
    ] == "local"


async def test_profile_digest_is_refreshed_only_by_an_explicit_update(tmp_path: Path) -> None:
    config = tmp_path / "cluster.py"
    _write_cluster_config(config)
    store = ExecutionProfileStore(tmp_path / "profiles.json")
    await store.load()
    created = await store.create(_profile(config))

    _write_cluster_config(config, host="changed-hpc")

    retained = store.get(created.id)
    assert retained.config_digest == created.config_digest
    assert retained.cluster_host == "site-hpc"
    with pytest.raises(ValueError, match="digest"):
        load_cluster_config(config, expected_digest=retained.config_digest)

    updated = await store.update(
        created.id,
        expected_revision=created.revision,
        fields=_profile(config),
    )
    assert updated.revision == 2
    assert updated.config_digest != created.config_digest
    assert updated.cluster_host == "changed-hpc"
