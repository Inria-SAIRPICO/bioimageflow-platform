from __future__ import annotations

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
        self.info = SimpleNamespace(
            name="cellpose-env",
            path=env_path,
            ready=True,
            recipe_hash="sha256:old",
        )
        self.removed: list[str] = []

    def managed_environments(self) -> tuple[object, ...]:
        return (self.info,)

    def remove(self, name: str) -> object:
        self.removed.append(name)
        env = self.env

        class _Removal:
            def wait_for(self) -> object:
                env.delete()
                return SimpleNamespace(name=name)

        return _Removal()


class _FakeWetlandsWrapper:
    def __init__(self, manager: _FakeWetlandsManager) -> None:
        self._manager = manager
        self._envs: dict[str, _FakeEnvironment] = {}

    def get_or_create(self, env_spec: object) -> _FakeEnvironment:
        env_name = str(getattr(env_spec, "name"))
        self._envs[env_name] = self._manager.env
        return self._manager.env

    def stop(self, env_name: str) -> bool:
        env = self._envs.pop(env_name, None)
        if env is None:
            return False
        env.exit()
        return True


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


async def test_start_and_stop_control_the_shared_environment(tmp_path: Path) -> None:
    env = _FakeEnvironment()
    env_path = tmp_path / "workspaces" / "cellpose-env" / "pixi.toml"
    manager = _FakeWetlandsManager(env, env_path)
    wetlands = _FakeWetlandsWrapper(manager)
    service = ToolEnvironmentService(
        registry=_registry(),
        wetlands_manager=wetlands,
    )

    assert service.manager is wetlands
    assert await service.start("cellpose-env") == "running"
    assert wetlands._envs == {"cellpose-env": env}

    assert await service.stop("cellpose-env") == "stopped"
    assert env.exited is True
    assert wetlands._envs == {}


async def test_delete_environment_deletes_cached_environment(tmp_path: Path) -> None:
    env = _FakeEnvironment()
    env_path = tmp_path / "workspaces" / "cellpose-env" / "pixi.toml"
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
    assert manager.removed == ["cellpose-env"]
    assert wetlands._envs == {}


async def test_delete_environment_removes_managed_environment_when_not_cached(
    tmp_path: Path,
) -> None:
    env = _FakeEnvironment()
    env_path = tmp_path / "workspaces" / "cellpose-env" / "pixi.toml"
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
    assert manager.removed == ["cellpose-env"]
    assert env.deleted is True


async def test_delete_environment_refuses_stale_recovery_hash(tmp_path: Path) -> None:
    env = _FakeEnvironment()
    env_path = tmp_path / "workspaces" / "cellpose-env" / "pixi.toml"
    manager = _FakeWetlandsManager(env, env_path)
    manager.info.recipe_hash = "sha256:newer"
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


async def test_delete_environment_stays_stopped_when_remove_fails(
    tmp_path: Path,
) -> None:
    env = _FakeEnvironment()
    env.raise_on_delete = RuntimeError("trash unavailable")
    env_path = tmp_path / "workspaces" / "cellpose-env" / "pixi.toml"
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

    assert wetlands._envs == {}
    assert env.exited is True
    assert manager.removed == ["cellpose-env"]
