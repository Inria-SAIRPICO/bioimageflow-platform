from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from bioimageflow import EnvironmentRecipeState
from bioimageflow_core.environment import GENERAL_ENV

from bioimageflow_server.services.tool_environments import ToolEnvironmentService
from bioimageflow_server.models.execution import ExecutionContext
from bioimageflow_server.services.execution import _ExecutionEnvironmentManager

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
        self.admit_calls: list[tuple[str, bool]] = []
        self.recreate_calls: list[str] = []
        self.shutdown_calls = 0

    def inspect_environment(self, env_spec: object) -> EnvironmentRecipeState:
        return self.state

    def get_or_create(
        self,
        env_spec: object,
        *,
        replace_existing: bool = False,
        on_provision_event: Any = None,
        on_removal_event: Any = None,
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

    def admit_runtime(self, env_spec: object, *, provision: bool, replace_stale: bool = False,
                      admissions: Any = None, on_preparation: Any = None,
                      on_provision_event: Any = None, on_removal_event: Any = None) -> Any:
        name = str(getattr(env_spec, "name"))
        self.admit_calls.append((name, replace_stale))
        if self.state is EnvironmentRecipeState.STALE and not replace_stale:
            raise RuntimeError("Stale generation requires replacement")
        if on_preparation is not None:
            on_preparation(SimpleNamespace(action="updating" if self.state is EnvironmentRecipeState.STALE else "reusing"))
        self.state = EnvironmentRecipeState.CURRENT
        receipt = SimpleNamespace(generation_id=getattr(self, "generation", 0))
        if admissions is not None:
            admissions[(name, "recipe")] = receipt
        return receipt

    def validate_runtime_receipt(self, env_spec: object, receipt: Any) -> Any:
        if receipt.generation_id != getattr(self, "generation", 0):
            raise RuntimeError("Generation changed after admission")
        return receipt

    def recreate(self, env_spec: object, **kwargs: Any) -> _FakeEnvironment:
        name = str(getattr(env_spec, "name"))
        self.recreate_calls.append(name)
        self._env.exit()
        return self.get_or_create(env_spec, replace_existing=True, **kwargs)

    def is_running(self, env_name: str) -> bool:
        return env_name in self._envs

    def shutdown_all(self) -> None:
        self.shutdown_calls += 1
        self._envs.clear()

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
    assert wetlands.recreate_calls == ["cellpose-env"]
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

    assert wetlands.admit_calls == [(GENERAL_ENV.name, True)]
    assert wetlands.get_calls == []


@pytest.mark.parametrize("state", [EnvironmentRecipeState.MISSING, EnvironmentRecipeState.CURRENT])
async def test_background_refresh_does_not_create_missing_general(
    tmp_path: Path,
    state: EnvironmentRecipeState,
) -> None:
    wetlands = _FakeWetlandsWrapper(_FakeWetlandsManager(tmp_path / GENERAL_ENV.name))
    wetlands.state = state
    service = ToolEnvironmentService(registry=_registry(general=True), wetlands_manager=wetlands)

    service.start_standard_environment_refresh()
    await asyncio.wait_for(service._standard_refresh_task, timeout=1)

    assert wetlands.get_calls == []


async def test_background_refresh_failure_releases_automatic_preparation_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    manager = _FakeWetlandsWrapper(_FakeWetlandsManager(tmp_path / GENERAL_ENV.name))
    manager.state = EnvironmentRecipeState.STALE
    registry = _registry(general=True)
    service = ToolEnvironmentService(registry=registry, wetlands_manager=manager)

    def fail(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("controlled startup preparation failure")

    monkeypatch.setattr(manager, "admit_runtime", fail)
    service.start_standard_environment_refresh()
    await asyncio.wait_for(service._standard_refresh_task, timeout=2)

    def guard_available() -> bool:
        acquired = service.processing_environment_lock.acquire(timeout=1)
        if acquired:
            service.processing_environment_lock.release()
        return acquired

    assert await asyncio.to_thread(guard_available)
    assert registry.get_package.return_value.environment_status == "failed"
    assert "controlled startup preparation failure" in caplog.text
    await service.close()


@pytest.mark.parametrize("first_owner", ["startup", "run"])
async def test_startup_general_refresh_cannot_retire_processing_handoff(tmp_path: Path, first_owner: str) -> None:
    inspected = threading.Event()
    release_refresh = threading.Event()
    second_attempted = threading.Event()
    handed_off = threading.Event()

    class PreparationGuard:
        def __init__(self) -> None:
            self.lock = threading.RLock()
            self.first_guarded = False

        def __enter__(self) -> None:
            if inspected.is_set():
                second_attempted.set()
            else:
                self.first_guarded = True
            self.lock.acquire()

        def __exit__(self, *_args: Any) -> None:
            self.lock.release()

    class ProcessingManager(_FakeWetlandsWrapper):
        def __init__(self) -> None:
            super().__init__(_FakeWetlandsManager(tmp_path / GENERAL_ENV.name))
            self.state = EnvironmentRecipeState.STALE
            self.generation = 0
            self.inspect_calls = 0
            self.submitted_generations: list[int] = []
            self.retired_generations: list[int] = []
            self.lock = threading.RLock()

        def inspect_environment(self, env_spec: object) -> EnvironmentRecipeState:
            with self.lock:
                self.inspect_calls += 1
                first = self.inspect_calls == 1
                snapshot = self.state
            if first:
                inspected.set()
                assert release_refresh.wait(5)
            else:
                second_attempted.set()
            return snapshot

        def admit_runtime(self, env_spec: object, **kwargs: Any) -> Any:
            # Simulate public admission's current-state decision, worker-free.
            state = self.inspect_environment(env_spec)
            with self.lock:
                if state is EnvironmentRecipeState.STALE:
                    self.retired_generations.extend(self.submitted_generations)
                    self.generation += 1
                return super().admit_runtime(env_spec, **kwargs)

        def submit_processing_task(self, env_spec: object, payload: dict, **kwargs: Any) -> object:
            self.submitted_generations.append(self.generation)
            handed_off.set()
            return SimpleNamespace(payload=payload)

    manager = ProcessingManager()
    service = ToolEnvironmentService(registry=_registry(general=True), wetlands_manager=manager)
    guard = PreparationGuard()
    service._processing_environment_lock = guard
    adapter = _ExecutionEnvironmentManager(
        manager, context=ExecutionContext(execution_id="startup-race", workflow_id="wf", draft_revision=1),
        current_node_id=lambda: "worker", on_preparation=lambda *_args: None,
        on_provision_event=lambda *_args: None, on_ready=lambda *_args: None,
        on_admitted=lambda *_args: None,
        on_failure=lambda *_args: None, on_stopped=lambda *_args: None,
        replacement_authorizer=service.can_replace_processing_environment,
        environment_lock=service.processing_environment_lock,
    )
    def prepare_and_submit() -> Any:
        receipt = adapter.admit_runtime(GENERAL_ENV, provision=True, admissions={})
        return adapter.submit_processing_task(GENERAL_ENV, {"row": 1}, runtime_receipt=receipt)

    submission = None
    if first_owner == "startup":
        service.start_standard_environment_refresh()
    else:
        submission = asyncio.create_task(asyncio.to_thread(prepare_and_submit))
    try:
        assert await asyncio.to_thread(inspected.wait, 5)
        if first_owner == "startup":
            submission = asyncio.create_task(asyncio.to_thread(prepare_and_submit))
        else:
            service.start_standard_environment_refresh()
        assert await asyncio.to_thread(second_attempted.wait, 5)
        # The original unguarded startup must reach handoff before resuming
        # its stale decision. The guarded owner instead blocks the contender.
        if first_owner == "startup" and not guard.first_guarded:
            assert await asyncio.to_thread(handed_off.wait, 5)
    finally:
        release_refresh.set()
        if submission is not None:
            await asyncio.wait_for(submission, timeout=5)
        await asyncio.wait_for(service._standard_refresh_task, timeout=5)
        await service.close()

    assert manager.generation == 1
    assert manager.submitted_generations == [1]
    assert manager.retired_generations == []


def test_concurrent_first_manager_access_constructs_one_pool_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    first_constructing = threading.Event()
    second_attempted = threading.Event()
    release_first = threading.Event()
    factory_lock = threading.Lock()
    constructed: list[object] = []
    returned: list[object] = []
    errors: list[BaseException] = []

    class InitializationGuard:
        def __init__(self) -> None:
            self.lock = threading.RLock()
            self.entries = 0

        def __enter__(self) -> None:
            self.entries += 1
            if threading.current_thread().name == "e1-second-access":
                second_attempted.set()
            self.lock.acquire()

        def __exit__(self, *_args: Any) -> None:
            self.lock.release()

    def factory() -> object:
        value = SimpleNamespace(pools={})
        with factory_lock:
            constructed.append(value)
            first = len(constructed) == 1
        if first:
            first_constructing.set()
            assert release_first.wait(5)
        else:
            second_attempted.set()
        return value

    monkeypatch.setattr("bioimageflow.env_manager.WetlandsEnvManager", factory)
    service = ToolEnvironmentService(registry=_registry())
    guard = InitializationGuard()
    service._processing_environment_lock = guard

    def access() -> None:
        try:
            returned.append(service.manager)
        except BaseException as error:
            errors.append(error)

    first = threading.Thread(target=access, name="e1-first-access")
    second = threading.Thread(target=access, name="e1-second-access")
    first.start()
    try:
        assert first_constructing.wait(5)
        second.start()
        assert second_attempted.wait(5)
    finally:
        release_first.set()
        first.join(5)
        if second.ident is not None:
            second.join(5)

    assert not first.is_alive() and not second.is_alive()
    assert errors == []
    assert len(constructed) == 1
    assert len(returned) == 2
    assert returned[0] is returned[1] is service.manager
    entries = guard.entries
    assert service.manager is returned[0]
    assert guard.entries == entries  # Initialized reads remain lock-free.

async def test_close_never_constructs_unused_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbid_manager() -> None:
        raise AssertionError("Shutdown must not initialize a manager")
    monkeypatch.setattr("bioimageflow.env_manager.WetlandsEnvManager", forbid_manager)
    await ToolEnvironmentService(registry=_registry()).close()


async def test_failed_pool_close_preserves_manager_for_retry(tmp_path: Path) -> None:
    manager = _FakeWetlandsWrapper(_FakeWetlandsManager(tmp_path / "cellpose-env"))
    manager._envs["cellpose-env"] = manager._env
    original = manager.shutdown_all
    manager.shutdown_all = MagicMock(side_effect=RuntimeError("physical close failed"))
    service = ToolEnvironmentService(registry=_registry(), wetlands_manager=manager)
    with pytest.raises(RuntimeError, match="physical close failed"):
        await service.close()
    assert service.manager is manager
    assert manager._envs["cellpose-env"] is manager._env
    manager.shutdown_all = original
    await service.close()
    assert manager._envs == {}


def test_tool_recipe_reconstruction_preserves_flexible_version_policy() -> None:
    registry = _registry()
    tool = registry.list_tools.return_value[0]
    tool.environment["dependencies"] = {"pip": ["demo>=1,<2"]}
    tool.environment["allow_flexible_versions"] = True
    spec = ToolEnvironmentService(registry=registry)._environment_spec(tool)
    assert spec is not None and spec.allow_flexible_versions is True
