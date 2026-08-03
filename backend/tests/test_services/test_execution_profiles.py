"""Tests for versioned distributed execution profile persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from bioimageflow_server.models.execution_profiles import ExecutionProfileCreate
from bioimageflow_server.services.execution_profiles import (
    ExecutionProfileConflictError,
    ExecutionProfileStore,
)


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def profile_fields(**changes: object) -> ExecutionProfileCreate:
    payload: dict[str, object] = {
        "name": "Local Parsl",
        "mode": "attached",
        "parsl_config": {
            "factory": "site.parsl:make_config",
            "kwargs": {"queue": "debug"},
            "secret_refs": {"token": "PARSL_TOKEN"},
        },
        "executor_bindings": {
            "cpu": {
                "schema": "bioimageflow.parsl.executor_binding.v1",
                "label": "cpu",
                "environments": [
                    {
                        "schema": "bioimageflow.parsl.worker_environment_attestation.v1",
                        "name": "default",
                        "dependency_hash": "0" * 64,
                        "allow_flexible_versions": False,
                        "core_requirement": "bioimageflow-core>=0.2",
                    }
                ],
                "capabilities": {
                    "schema": "bioimageflow.parsl.executor_capabilities.v1",
                    "storage_modes": ["shared_fs"],
                    "tool_origin_modes": ["installed_module"],
                    "slot": {
                        "schema": "bioimageflow.parsl.worker_slot_capacity.v1",
                        "cpu": 8,
                        "gpu": 0,
                        "memory_bytes": None,
                        "gpu_memory_bytes": None,
                    },
                },
            }
        },
    }
    payload.update(changes)
    return ExecutionProfileCreate.model_validate(payload)


async def test_create_update_reload_and_compare_and_swap(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    store = ExecutionProfileStore(path)
    await store.load()

    created = await store.create(profile_fields())
    assert created.revision == 1
    assert created.parsl_config.secret_refs == {"token": "PARSL_TOKEN"}
    assert "secret-value" not in path.read_text()

    updated = await store.update(
        created.id,
        expected_revision=1,
        fields=profile_fields(name="Renamed"),
    )
    assert updated.revision == 2
    with pytest.raises(ExecutionProfileConflictError):
        await store.update(created.id, 1, profile_fields())

    reloaded = ExecutionProfileStore(path)
    await reloaded.load()
    assert reloaded.get(created.id) == updated
    assert json.loads(path.read_text())["profiles_version"] == 1


async def test_failed_atomic_replace_rolls_back_in_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "profiles.json"
    store = ExecutionProfileStore(path)
    await store.load()
    created = await store.create(profile_fields())

    def fail_replace(*_args: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        await store.update(created.id, 1, profile_fields(name="Not persisted"))

    assert store.get(created.id) == created


def test_all_pre_launch_sources_validate_through_public_constructors(tmp_path: Path) -> None:
    common = {
        "mode": "submitted_remote",
        "launch": {
            "backend": "psij",
            "executor": "slurm",
            "walltime_seconds": 3600,
            "queue": None,
            "project": None,
            "cpu_cores": 1,
            "work_dir": "/shared/work",
            "hard_cancel_after": None,
        },
        "transport": {
            "host": "cluster",
            "staging_root": "/shared/staging",
            "remote_executable": "/usr/bin/bioimageflow-cluster-agent",
            "connect_timeout": 15,
        },
        "remote_workflow_root": "/shared/workflows",
    }
    script = tmp_path / "setup.sh"
    for pre_launch in (
        {"kind": "inline", "text": "module load cuda\n"},
        {"kind": "local_file", "path": str(script)},
        {
            "kind": "cluster_file",
            "path": "/shared/site/setup.sh",
            "expected_digest": "sha256:" + "a" * 64,
        },
    ):
        profile = profile_fields(**common, pre_launch=pre_launch)
        assert profile.pre_launch is not None
        assert profile.pre_launch.to_library().source_kind in {
            "text",
            "local_file",
            "cluster_file",
        }


def test_inline_pre_launch_rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        profile_fields(
            mode="submitted_remote",
            launch={
                "backend": "psij",
                "executor": "slurm",
                "walltime_seconds": 60,
                "queue": None,
                "project": None,
                "cpu_cores": 1,
                "work_dir": None,
                "hard_cancel_after": None,
            },
            transport={
                "host": "cluster",
                "staging_root": "/tmp/staging",
                "remote_executable": "/usr/bin/agent",
                "connect_timeout": 15,
            },
            remote_workflow_root="/tmp/workflows",
            pre_launch={"kind": "inline", "text": ""},
        )


def test_profile_values_reject_json_type_coercion() -> None:
    with pytest.raises(ValueError):
        profile_fields(
            task_policy={
                "schema": "bioimageflow.parsl.task_policy.v1",
                "row_chunk_size": "1",
                "max_in_flight": 32,
            }
        )
