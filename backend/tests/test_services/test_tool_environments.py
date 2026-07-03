from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from bioimageflow_server.services.tool_environments import ToolEnvironmentService

pytestmark = pytest.mark.anyio


class _FakeEnvironment:
    def __init__(self) -> None:
        self.deleted = False
        self.exited = False
        self.raise_on_delete: Exception | None = None

    def delete(self) -> None:
        if self.raise_on_delete is not None:
            raise self.raise_on_delete
        self.deleted = True

    def exit(self) -> None:
        self.exited = True


class _FakeWetlandsManager:
    def __init__(self, env: _FakeEnvironment, env_path: Path) -> None:
        self.env = env
        self.settings_manager = SimpleNamespace(
            use_pixi=True,
            get_environment_path_from_name=lambda _name: env_path,
        )
        self.loaded: list[tuple[str, object | None]] = []

    def load(self, name: str, environment_path: object | None = None) -> _FakeEnvironment:
        self.loaded.append((name, environment_path))
        return self.env


class _FakeWetlandsWrapper:
    def __init__(self, manager: _FakeWetlandsManager) -> None:
        self._manager = manager
        self._envs: dict[str, _FakeEnvironment] = {}
        self._env_hashes = {"cellpose-env": "old"}
        self._launch_configs = {"cellpose-env": (1, None, None)}


def _registry() -> MagicMock:
    tool = SimpleNamespace(
        environment={"name": "cellpose-env", "dependencies": {}},
        name="cellpose",
        package="cellpose-pkg",
    )
    package = SimpleNamespace(environment_status="running")
    registry = MagicMock()
    registry.list_tools.return_value = [tool]
    registry.get_package.return_value = package
    return registry


def _write_metadata(env_path: Path, recipe_hash: str = "sha256:old") -> None:
    metadata_path = env_path.parent / ".wetlands" / "environment.json"
    metadata_path.parent.mkdir(parents=True)
    metadata_path.write_text(
        json.dumps({
            "schema_version": 1,
            "status": "managed",
            "name": "cellpose-env",
            "manager": "pixi",
            "recipe_hash": recipe_hash,
            "recipe": {},
        }),
        encoding="utf-8",
    )
    env_path.parent.mkdir(exist_ok=True)
    env_path.write_text("[workspace]\n", encoding="utf-8")


async def test_delete_environment_deletes_cached_environment(tmp_path: Path) -> None:
    env = _FakeEnvironment()
    env_path = tmp_path / "workspaces" / "cellpose-env" / "pixi.toml"
    _write_metadata(env_path)
    manager = _FakeWetlandsManager(env, env_path)
    wetlands = _FakeWetlandsWrapper(manager)
    wetlands._envs["cellpose-env"] = env
    service = ToolEnvironmentService(
        registry=_registry(),
        wetlands_manager=wetlands,
    )

    status = await service.delete(
        "cellpose-env",
        expected_path=str(env_path),
        expected_existing_hash="sha256:old",
    )

    assert status == "deleted"
    assert env.deleted is True
    assert manager.loaded == []
    assert wetlands._envs == {}
    assert wetlands._env_hashes == {}
    assert wetlands._launch_configs == {}


async def test_delete_environment_loads_default_environment_when_not_cached(
    tmp_path: Path,
) -> None:
    env = _FakeEnvironment()
    env_path = tmp_path / "workspaces" / "cellpose-env" / "pixi.toml"
    _write_metadata(env_path)
    manager = _FakeWetlandsManager(env, env_path)
    wetlands = _FakeWetlandsWrapper(manager)
    service = ToolEnvironmentService(
        registry=_registry(),
        wetlands_manager=wetlands,
    )

    status = await service.delete(
        "cellpose-env",
        expected_path=str(env_path),
        expected_existing_hash="sha256:old",
    )

    assert status == "deleted"
    assert manager.loaded == [("cellpose-env", None)]
    assert env.deleted is True


async def test_delete_environment_refuses_stale_recovery_hash(tmp_path: Path) -> None:
    env = _FakeEnvironment()
    env_path = tmp_path / "workspaces" / "cellpose-env" / "pixi.toml"
    _write_metadata(env_path, recipe_hash="sha256:newer")
    manager = _FakeWetlandsManager(env, env_path)
    wetlands = _FakeWetlandsWrapper(manager)
    service = ToolEnvironmentService(
        registry=_registry(),
        wetlands_manager=wetlands,
    )

    with pytest.raises(PermissionError, match="recipe changed"):
        await service.delete(
            "cellpose-env",
            expected_path=str(env_path),
            expected_existing_hash="sha256:old",
        )

    assert env.deleted is False


async def test_delete_environment_preserves_cache_when_delete_fails(
    tmp_path: Path,
) -> None:
    env = _FakeEnvironment()
    env.raise_on_delete = RuntimeError("trash unavailable")
    env_path = tmp_path / "workspaces" / "cellpose-env" / "pixi.toml"
    _write_metadata(env_path)
    manager = _FakeWetlandsManager(env, env_path)
    wetlands = _FakeWetlandsWrapper(manager)
    wetlands._envs["cellpose-env"] = env
    service = ToolEnvironmentService(
        registry=_registry(),
        wetlands_manager=wetlands,
    )

    with pytest.raises(RuntimeError, match="trash unavailable"):
        await service.delete(
            "cellpose-env",
            expected_path=str(env_path),
            expected_existing_hash="sha256:old",
        )

    assert wetlands._envs == {"cellpose-env": env}
    assert wetlands._env_hashes == {"cellpose-env": "old"}
    assert wetlands._launch_configs == {"cellpose-env": (1, None, None)}
