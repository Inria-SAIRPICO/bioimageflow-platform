from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from bioimageflow import EnvironmentRecipeState
from bioimageflow_core.environment import GENERAL_ENV

from bioimageflow_server.services.tool_environments import ToolEnvironmentService

pytestmark = pytest.mark.anyio


class _FakeEnvironment:
    def __init__(self) -> None:
        self.exited = False

    def exit(self) -> None:
        self.exited = True


class _FakeWetlandsManager:
    def __init__(self, env_path: Path) -> None:
        self.info = SimpleNamespace(
            name="cellpose-env",
            path=env_path,
            ready=True,
            recipe_hash="sha256:old",
        )

    @property
    def environments_root(self) -> Path:
        return Path(self.info.path).parent

    def managed_environments(self) -> tuple[object, ...]:
        return (self.info,)


class _FakeWetlandsWrapper:
    def __init__(self, manager: _FakeWetlandsManager) -> None:
        self._manager = manager
        self._env = _FakeEnvironment()
        self._envs: dict[str, _FakeEnvironment] = {}
        self.state = EnvironmentRecipeState.CURRENT
        self.get_calls: list[tuple[str, bool]] = []
        self.provision_callbacks: list[Any] = []

    def inspect_environment(self, env_spec: object) -> EnvironmentRecipeState:
        return self.state

    def get_or_create(
        self,
        env_spec: object,
        *,
        replace_existing: bool = False,
        on_provision_event: Any = None,
    ) -> _FakeEnvironment:
        env_name = str(getattr(env_spec, "name"))
        self.get_calls.append((env_name, replace_existing))
        if on_provision_event is not None:
            self.provision_callbacks.append(on_provision_event)
            on_provision_event(
                SimpleNamespace(
                    kind=SimpleNamespace(value="output"),
                    state=SimpleNamespace(value="running"),
                    timestamp=123.0,
                    environment=env_name,
                    message="pixi output",
                    line="pixi output",
                )
            )
        self._envs[env_name] = self._env
        return self._env

    def stop(self, env_name: str) -> bool:
        env = self._envs.pop(env_name, None)
        if env is None:
            return False
        env.exit()
        return True


def _registry(*, general: bool = False) -> MagicMock:
    tool = SimpleNamespace(
        environment={
            "name": GENERAL_ENV.name if general else "cellpose-env",
            "dependencies": dict(GENERAL_ENV.dependencies) if general else {},
        },
        name="general" if general else "cellpose",
        package="bioimageflow" if general else "cellpose-pkg",
    )
    package = SimpleNamespace(environment_status="stopped")
    registry = MagicMock()
    registry.list_tools.return_value = [tool]
    registry.get_package.return_value = package
    return registry


async def test_start_and_stop_control_the_shared_environment(tmp_path: Path) -> None:
    wetlands = _FakeWetlandsWrapper(_FakeWetlandsManager(tmp_path / "cellpose-env"))
    service = ToolEnvironmentService(registry=_registry(), wetlands_manager=wetlands)

    assert service.manager is wetlands
    assert await service.start("cellpose-env") == "running"
    assert wetlands.get_calls == [("cellpose-env", False)]

    assert await service.stop("cellpose-env") == "stopped"
    assert wetlands._env.exited is True
    assert wetlands._envs == {}


async def test_start_logs_pixi_operation_output(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    wetlands = _FakeWetlandsWrapper(_FakeWetlandsManager(tmp_path / "cellpose-env"))
    service = ToolEnvironmentService(registry=_registry(), wetlands_manager=wetlands)

    with caplog.at_level("INFO", logger="bioimageflow.environment"):
        await service.start("cellpose-env")

    assert "Environment cellpose-env: pixi output" in caplog.messages


async def test_start_replaces_only_a_stale_managed_recipe(tmp_path: Path) -> None:
    wetlands = _FakeWetlandsWrapper(_FakeWetlandsManager(tmp_path / "cellpose-env"))
    wetlands.state = EnvironmentRecipeState.STALE
    registry = _registry()
    service = ToolEnvironmentService(registry=registry, wetlands_manager=wetlands)

    assert await service.start("cellpose-env") == "running"

    assert wetlands.get_calls == [("cellpose-env", True)]
    assert registry.get_package.return_value.environment_status == "running"


async def test_location_reports_existing_and_expected_managed_paths(tmp_path: Path) -> None:
    env_path = tmp_path / "environments" / "cellpose-env"
    managed = _FakeWetlandsManager(env_path)
    wetlands = _FakeWetlandsWrapper(managed)
    service = ToolEnvironmentService(
        registry=_registry(),
        wetlands_manager=wetlands,
        managed_environment_manager=managed,
    )

    assert service.location("cellpose-env") == str(env_path.resolve())
    assert service.location("new-env") == str((env_path.parent / "new-env").resolve())


async def test_recreate_uses_public_managed_replacement_path(tmp_path: Path) -> None:
    wetlands = _FakeWetlandsWrapper(_FakeWetlandsManager(tmp_path / "cellpose-env"))
    wetlands._envs["cellpose-env"] = wetlands._env
    registry = _registry()
    service = ToolEnvironmentService(registry=registry, wetlands_manager=wetlands)

    assert await service.recreate("cellpose-env") == "running"

    assert wetlands._env.exited is True
    assert wetlands.get_calls == [("cellpose-env", True)]
    assert registry.get_package.return_value.environment_status == "running"


async def test_protected_environment_cannot_be_replaced(tmp_path: Path) -> None:
    wetlands = _FakeWetlandsWrapper(_FakeWetlandsManager(tmp_path / "cellpose-env"))
    service = ToolEnvironmentService(
        registry=_registry(),
        wetlands_manager=wetlands,
        protected_environment_names=lambda: {"cellpose-env"},
    )

    with pytest.raises(PermissionError, match="owned by another platform lifecycle"):
        await service.recreate("cellpose-env")

    assert wetlands.get_calls == []


async def test_background_refresh_rebuilds_only_existing_stale_general(
    tmp_path: Path,
) -> None:
    wetlands = _FakeWetlandsWrapper(_FakeWetlandsManager(tmp_path / GENERAL_ENV.name))
    wetlands.state = EnvironmentRecipeState.STALE
    service = ToolEnvironmentService(registry=_registry(general=True), wetlands_manager=wetlands)

    service.start_standard_environment_refresh()
    await asyncio.wait_for(service._standard_refresh_task, timeout=1)

    assert wetlands.get_calls == [(GENERAL_ENV.name, True)]


async def test_background_refresh_does_not_create_missing_general(
    tmp_path: Path,
) -> None:
    wetlands = _FakeWetlandsWrapper(_FakeWetlandsManager(tmp_path / GENERAL_ENV.name))
    wetlands.state = EnvironmentRecipeState.MISSING
    service = ToolEnvironmentService(registry=_registry(general=True), wetlands_manager=wetlands)

    service.start_standard_environment_refresh()
    await asyncio.wait_for(service._standard_refresh_task, timeout=1)

    assert wetlands.get_calls == []
