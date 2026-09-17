"""Managed napari provisioning, recovery, cancellation, copy, and removal."""

from __future__ import annotations

import asyncio
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from wetlands import ManagedEnvironmentInfo, ManagedEnvironmentState, OperationCanceled

from bioimageflow_server.models.napari_environments import (
    NapariEnvironment,
    NapariEnvironmentOperation,
    NapariLaunchContext,
    NapariManagedEnvironmentCopy,
    NapariManagedEnvironmentCreate,
    NapariManagedMetadata,
    NapariManagedRecipe,
    NapariManagedRecipeSelection,
    NapariFilenameRuleCreate,
)
from bioimageflow_server.services.napari_environments import (
    NapariEnvironmentError,
    NapariEnvironmentService,
)
from bioimageflow_server.services.napari_launcher import NapariLauncher
from bioimageflow_server.services.settings_store import SettingsStore


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeManagedEnvironment:
    def __init__(self, name: str, path: Path, generation_id: UUID) -> None:
        self.name = name
        self.path = path
        self.generation_id = str(generation_id)


class FakeOperation:
    def __init__(self, *, result: Any | None = None) -> None:
        self.id = str(uuid4())
        self._result = result
        self._error: BaseException | None = None
        self._done = threading.Event()
        self.cancel_calls = 0
        self.listeners: list[Any] = []

    def listen(self, callback: Any, *, replay: bool = True) -> "FakeOperation":
        del replay
        self.listeners.append(callback)
        return self

    def wait_for(self, timeout: float | None = None) -> Any:
        if not self._done.wait(timeout):
            raise TimeoutError
        if self._error is not None:
            raise self._error
        return self._result

    def succeed(self, result: Any | None = None) -> None:
        if result is not None:
            self._result = result
        self._done.set()

    def fail(self, error: BaseException) -> None:
        self._error = error
        self._done.set()

    def cancel(self) -> bool:
        if self._done.is_set():
            return False
        self.cancel_calls += 1
        self._error = OperationCanceled(self.id)
        self._done.set()
        return True

    def emit_progress(self, current: int, maximum: int, message: str) -> None:
        event = SimpleNamespace(
            current=current,
            maximum=maximum,
            message=message,
            operation_id=self.id,
        )
        for callback in self.listeners:
            callback(event)


class FakeManager:
    def __init__(self) -> None:
        self.provision_calls: list[tuple[str, Any, bool]] = []
        self.provision_operations: dict[str, FakeOperation] = {}
        self.environments: dict[str, FakeManagedEnvironment] = {}
        self.remove_calls: list[str] = []
        self.remove_operations: dict[str, FakeOperation] = {}

    def provision(
        self, name: str, spec: Any, *, replace_existing: bool = False
    ) -> FakeOperation:
        operation = FakeOperation()
        self.provision_calls.append((name, spec, replace_existing))
        self.provision_operations[name] = operation
        return operation

    def environment(self, name: str) -> FakeManagedEnvironment:
        return self.environments[name]

    def managed_environments(self) -> tuple[ManagedEnvironmentInfo, ...]:
        return tuple(
            ManagedEnvironmentInfo(
                name=name,
                path=environment.path,
                state=ManagedEnvironmentState.READY,
                generation_id=environment.generation_id,
            )
            for name, environment in self.environments.items()
        )

    def remove(self, name: str) -> FakeOperation:
        self.remove_calls.append(name)
        operation = FakeOperation(
            result=next(info for info in self.managed_environments() if info.name == name)
        )
        self.remove_operations[name] = operation
        return operation

    def complete_provision(self, name: str, path: Path) -> FakeManagedEnvironment:
        environment = FakeManagedEnvironment(name, path, uuid4())
        self.environments[name] = environment
        self.provision_operations[name].succeed(environment)
        return environment


class FakeLauncherPool:
    def __init__(self) -> None:
        self.shutdown_calls: list[UUID] = []

    async def shutdown(self, environment_id: UUID | None = None) -> None:
        assert environment_id is not None
        self.shutdown_calls.append(environment_id)


class BlockingLauncherPool(FakeLauncherPool):
    def __init__(self) -> None:
        super().__init__()
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def shutdown(self, environment_id: UUID | None = None) -> None:
        assert environment_id is not None
        self.shutdown_calls.append(environment_id)
        self.entered.set()
        await self.release.wait()


def _managed_project(path: Path) -> Path:
    prefix = path / ".pixi" / "envs" / "default"
    (prefix / "conda-meta").mkdir(parents=True)
    interpreter = prefix / "bin" / "python"
    interpreter.parent.mkdir()
    interpreter.symlink_to(sys.executable)
    return path


def _inventory() -> str:
    return json.dumps(
        {
            "python_version": "3.12.9",
            "napari_version": "0.9.1",
            "qt_distribution": "pyqt6",
            "qt_version": "6.8.0",
            "distributions": [
                {"name": "napari", "version": "0.9.1"},
                {"name": "pyqt6", "version": "6.8.0"},
            ],
            "fingerprint": "probe-fingerprint",
        }
    )


async def _service(
    tmp_path: Path, manager: FakeManager, **kwargs: Any
) -> NapariEnvironmentService:
    store = SettingsStore(tmp_path / "settings.json")
    await store.load()
    return NapariEnvironmentService(
        store,
        environment_manager_provider=lambda: manager,  # type: ignore[arg-type]
        probe_runner=lambda *_args: _inventory(),
        **kwargs,
    )


async def _wait_terminal(
    service: NapariEnvironmentService, environment_id: UUID, operation_id: UUID
) -> Any:
    for _ in range(100):
        mutation = service.managed_operation(environment_id, operation_id)
        if mutation.operation.state in {"completed", "failed", "cancelled"}:
            return mutation
        await asyncio.sleep(0.01)
    raise AssertionError("operation did not become terminal")


@pytest.mark.parametrize(
    ("selection", "pypi"),
    [
        (NapariManagedRecipeSelection(), ("napari==0.9.1", "PyQt6")),
        (
            NapariManagedRecipeSelection(preset="legacy", requested_packages=["legacy-reader<2"]),
            ("napari==0.6.6", "PyQt5", "legacy-reader<2"),
        ),
        (
            NapariManagedRecipeSelection(
                preset="advanced", napari="0.9.2", qt="PyQt6", requested_packages=["reader>=1"]
            ),
            ("napari==0.9.2", "PyQt6", "reader>=1"),
        ),
    ],
)
async def test_create_uses_exact_pypi_only_environment_spec_and_public_managed_path(
    tmp_path: Path, selection: NapariManagedRecipeSelection, pypi: tuple[str, ...]
) -> None:
    manager = FakeManager()
    service = await _service(tmp_path, manager)

    started = await service.create_managed(
        NapariManagedEnvironmentCreate(name="Viewer", recipe=selection, expected_revision=0)
    )

    assert started.environment is not None
    assert started.environment.state == "creating"
    assert started.operation.state == "resolving"
    wetlands_name, spec, replace_existing = manager.provision_calls[0]
    assert wetlands_name == started.environment.managed.wetlands_name
    assert spec.python == "==3.12.*"
    assert spec.conda == ()
    assert spec.pypi == pypi
    assert spec.channels == ("conda-forge",)
    assert replace_existing is False
    reloaded = SettingsStore(service.store.path)
    await reloaded.load()
    persisted = reloaded.get()
    assert persisted.napari_environments[0].state == "creating"
    assert persisted.napari_environment_operations[0].id == started.operation.id
    assert (
        persisted.napari_environment_operations[0].wetlands_operation_id
        == started.operation.wetlands_operation_id
    )
    manager.provision_operations[wetlands_name].emit_progress(1, 2, "Installing packages")
    for _ in range(20):
        progress = service.managed_operation(
            started.environment.id, started.operation.id
        ).operation
        if progress.state == "installing":
            break
        await asyncio.sleep(0.01)
    assert progress.state == "installing"
    assert progress.progress == 45
    assert progress.message == "Installing packages"

    project = _managed_project(tmp_path / "wetlands" / wetlands_name)
    public_environment = manager.complete_provision(wetlands_name, project)
    completed = await _wait_terminal(service, started.environment.id, started.operation.id)

    assert completed.operation.state == "completed"
    assert completed.environment is not None
    assert completed.environment.root == str(project.resolve())
    assert completed.environment.interpreter.endswith("/.pixi/envs/default/bin/python")
    launcher = NapariLauncher(
        environment=completed.environment,
        managed_environment_provider=manager.environment,
    )
    assert launcher._managed_environment_for_launch(completed.environment) is public_environment


async def test_create_failure_cancel_and_independent_completion(tmp_path: Path) -> None:
    manager = FakeManager()
    service = await _service(tmp_path, manager)
    first = await service.create_managed(
        NapariManagedEnvironmentCreate(name="First", expected_revision=0)
    )
    second = await service.create_managed(
        NapariManagedEnvironmentCreate(name="Second", expected_revision=2)
    )
    assert first.environment is not None and second.environment is not None
    second_name = second.environment.managed.wetlands_name

    manager.complete_provision(second_name, _managed_project(tmp_path / "second"))
    second_done = await _wait_terminal(service, second.environment.id, second.operation.id)
    assert second_done.operation.state == "completed"
    assert service.managed_operation(first.environment.id, first.operation.id).operation.state == "resolving"

    cancelled = await service.cancel_managed_operation(first.environment.id, first.operation.id)
    assert "Cancellation requested" in cancelled.operation.message
    first_done = await _wait_terminal(service, first.environment.id, first.operation.id)
    assert first_done.operation.state == "cancelled"
    assert first_done.environment.state == "cancelled"

    third = await service.create_managed(
        NapariManagedEnvironmentCreate(
            name="Third", expected_revision=service.snapshot().revision
        )
    )
    assert third.environment is not None
    third_name = third.environment.managed.wetlands_name
    manager.provision_operations[third_name].fail(RuntimeError("solver exploded"))
    third_done = await _wait_terminal(service, third.environment.id, third.operation.id)
    assert third_done.operation.error.code == "napari_provision_failed"
    assert third_done.environment.state == "failed"


async def test_modified_copy_has_independent_identity_and_recipe(tmp_path: Path) -> None:
    manager = FakeManager()
    service = await _service(tmp_path, manager)
    source = await service.create_managed(
        NapariManagedEnvironmentCreate(
            name="Source",
            recipe=NapariManagedRecipeSelection(requested_packages=["reader==1"]),
            expected_revision=0,
        )
    )
    assert source.environment is not None
    manager.complete_provision(
        source.environment.managed.wetlands_name, _managed_project(tmp_path / "source")
    )
    await _wait_terminal(service, source.environment.id, source.operation.id)

    copied = await service.copy_managed(
        source.environment.id,
        NapariManagedEnvironmentCopy(
            name="Copy",
            requested_packages=["reader==2", "widget>=1"],
            expected_revision=service.snapshot().revision,
        ),
    )
    assert copied.environment is not None
    assert copied.environment.id != source.environment.id
    assert copied.environment.managed.wetlands_name != source.environment.managed.wetlands_name
    assert copied.environment.managed.recipe.requested_packages == ["reader==2", "widget>=1"]
    assert service.snapshot().environments[0].managed.recipe.requested_packages == ["reader==1"]
    await service.cancel_managed_operation(copied.environment.id, copied.operation.id)
    await _wait_terminal(service, copied.environment.id, copied.operation.id)


async def test_retry_reuses_failed_entry_and_recovers_published_generation(
    tmp_path: Path,
) -> None:
    manager = FakeManager()
    service = await _service(tmp_path, manager)
    created = await service.create_managed(
        NapariManagedEnvironmentCreate(name="Retry me", expected_revision=0)
    )
    assert created.environment is not None
    name = created.environment.managed.wetlands_name
    project = _managed_project(tmp_path / "published-before-failure")
    manager.environments[name] = FakeManagedEnvironment(name, project, uuid4())
    manager.provision_operations[name].fail(RuntimeError("response channel lost"))
    failed = await _wait_terminal(service, created.environment.id, created.operation.id)
    assert failed.operation.state == "failed"

    retried = await service.retry_managed(
        created.environment.id, expected_revision=service.snapshot().revision
    )
    completed = await _wait_terminal(service, created.environment.id, retried.operation.id)
    assert completed.operation.state == "completed"
    assert completed.environment.id == created.environment.id
    assert completed.environment.root == str(project.resolve())
    assert len(manager.provision_calls) == 1


async def test_remove_stops_launcher_verifies_generation_then_cleans_references(
    tmp_path: Path,
) -> None:
    manager = FakeManager()
    cleaned: list[UUID] = []
    service = await _service(tmp_path, manager, reference_cleanup=cleaned.append)
    launcher = FakeLauncherPool()
    service.set_launcher_pool(launcher)  # type: ignore[arg-type]
    created = await service.create_managed(
        NapariManagedEnvironmentCreate(name="Owned", expected_revision=0)
    )
    assert created.environment is not None
    wetlands_name = created.environment.managed.wetlands_name
    manager.complete_provision(wetlands_name, _managed_project(tmp_path / "owned"))
    ready = await _wait_terminal(service, created.environment.id, created.operation.id)
    assert ready.environment is not None
    await service.set_default(
        ready.environment.id, expected_revision=service.snapshot().revision
    )
    await service.add_rule(
        NapariFilenameRuleCreate(
            value=".tif",
            environment_id=ready.environment.id,
            expected_revision=service.snapshot().revision,
        )
    )

    removing = await service.remove_managed(
        ready.environment.id, expected_revision=service.snapshot().revision
    )
    for _ in range(100):
        if wetlands_name in manager.remove_operations:
            break
        await asyncio.sleep(0.01)
    manager.environments.pop(wetlands_name)
    manager.remove_operations[wetlands_name].succeed()
    removed = await _wait_terminal(service, ready.environment.id, removing.operation.id)

    assert removed.environment is None
    assert removed.operation.state == "completed"
    assert launcher.shutdown_calls == [ready.environment.id]
    assert manager.remove_calls == [wetlands_name]
    assert cleaned == [ready.environment.id]
    assert service.snapshot().default_environment_id is None
    assert service.snapshot().filename_rules == []


async def test_remove_rejects_adopted_and_mismatched_owned_generation(tmp_path: Path) -> None:
    manager = FakeManager()
    service = await _service(tmp_path, manager)
    launcher = FakeLauncherPool()
    service.set_launcher_pool(launcher)  # type: ignore[arg-type]
    adopted = NapariEnvironment(
        id=uuid4(),
        registration_order=0,
        name="Adopted",
        ownership="managed",
        kind="conda",
        root=str(tmp_path / "adopted"),
        interpreter=str(tmp_path / "python"),
        interpreter_identity=str(tmp_path / "python"),
        interpreter_fingerprint="fingerprint",
        launch=NapariLaunchContext(strategy="wetlands-managed"),
        managed=NapariManagedMetadata(
            wetlands_name="napari",
            installation_generation=uuid4(),
            recipe=NapariManagedRecipe(source="adopted"),
        ),
    )
    await service.store.patch_napari_registry(0, {"napari_environments": [adopted]})
    with pytest.raises(NapariEnvironmentError) as raised:
        await service.remove_managed(adopted.id, expected_revision=1)
    assert raised.value.code == "napari_managed_delete_forbidden"
    forgotten = await service.forget(adopted.id, expected_revision=1)
    assert forgotten.environments == []
    assert manager.remove_calls == []

    created = await service.create_managed(
        NapariManagedEnvironmentCreate(name="Owned", expected_revision=2)
    )
    assert created.environment is not None
    wetlands_name = created.environment.managed.wetlands_name
    manager.complete_provision(wetlands_name, _managed_project(tmp_path / "owned"))
    ready = await _wait_terminal(service, created.environment.id, created.operation.id)
    manager.environments[wetlands_name].path = tmp_path / "different-generation"
    removing = await service.remove_managed(
        created.environment.id, expected_revision=service.snapshot().revision
    )
    failed = await _wait_terminal(service, created.environment.id, removing.operation.id)
    assert failed.operation.error.code == "napari_managed_generation_mismatch"
    assert manager.remove_calls == []
    assert ready.environment is not None


async def test_remove_can_be_cancelled_while_viewer_is_stopping(tmp_path: Path) -> None:
    manager = FakeManager()
    service = await _service(tmp_path, manager)
    launcher = BlockingLauncherPool()
    service.set_launcher_pool(launcher)  # type: ignore[arg-type]
    created = await service.create_managed(
        NapariManagedEnvironmentCreate(name="Owned", expected_revision=0)
    )
    assert created.environment is not None
    name = created.environment.managed.wetlands_name
    manager.complete_provision(name, _managed_project(tmp_path / "owned"))
    await _wait_terminal(service, created.environment.id, created.operation.id)

    removing = await service.remove_managed(
        created.environment.id, expected_revision=service.snapshot().revision
    )
    await launcher.entered.wait()
    cancellation = await service.cancel_managed_operation(
        created.environment.id, removing.operation.id
    )
    assert "Cancellation requested" in cancellation.operation.message
    launcher.release.set()
    cancelled = await _wait_terminal(
        service, created.environment.id, removing.operation.id
    )
    assert cancelled.operation.state == "cancelled"
    assert cancelled.environment.state == "ready"
    assert manager.remove_calls == []


@pytest.mark.parametrize("failure_kind", ["references", "registry"])
async def test_post_remove_finalization_failure_is_recovered_after_restart(
    tmp_path: Path, failure_kind: str
) -> None:
    manager = FakeManager()
    cleanup_calls: list[UUID] = []
    fail_cleanup = failure_kind == "references"

    def cleanup(environment_id: UUID) -> None:
        cleanup_calls.append(environment_id)
        nonlocal fail_cleanup
        if fail_cleanup:
            fail_cleanup = False
            raise RuntimeError("preference journal unavailable")

    service = await _service(tmp_path, manager, reference_cleanup=cleanup)
    service.set_launcher_pool(FakeLauncherPool())  # type: ignore[arg-type]
    created = await service.create_managed(
        NapariManagedEnvironmentCreate(name="Owned", expected_revision=0)
    )
    assert created.environment is not None
    name = created.environment.managed.wetlands_name
    manager.complete_provision(name, _managed_project(tmp_path / "owned"))
    await _wait_terminal(service, created.environment.id, created.operation.id)

    original_mutate = service.store.mutate_napari_registry
    fail_registry = failure_kind == "registry"

    async def injected_mutation(mutation: Any) -> Any:
        nonlocal fail_registry
        preview = mutation(service.store.get())
        if (
            fail_registry
            and "napari_environments" in preview
            and len(preview["napari_environments"]) == 0
        ):
            fail_registry = False
            raise OSError("settings disk unavailable")
        return await original_mutate(mutation)

    if failure_kind == "registry":
        service.store.mutate_napari_registry = injected_mutation  # type: ignore[method-assign]

    removing = await service.remove_managed(
        created.environment.id, expected_revision=service.snapshot().revision
    )
    for _ in range(100):
        if name in manager.remove_operations:
            break
        await asyncio.sleep(0.01)
    manager.environments.pop(name)
    manager.remove_operations[name].succeed()
    for _ in range(100):
        pending = service.managed_operation(
            created.environment.id, removing.operation.id
        )
        if pending.operation.error is not None:
            break
        await asyncio.sleep(0.01)
    assert pending.operation.state == "removing"
    assert pending.operation.error.code == "napari_remove_finalization_pending"

    service.store.mutate_napari_registry = original_mutate  # type: ignore[method-assign]
    restarted = NapariEnvironmentService(
        service.store,
        environment_manager_provider=lambda: manager,  # type: ignore[arg-type]
        probe_runner=lambda *_args: _inventory(),
        reference_cleanup=cleanup,
    )
    await restarted.reconcile_managed_operations()
    recovered = restarted.managed_operation(
        created.environment.id, removing.operation.id
    )
    assert recovered.operation.state == "completed"
    assert recovered.environment is None
    assert cleanup_calls[-1] == created.environment.id


async def test_restart_reconciliation_recovers_ready_or_marks_interrupted(tmp_path: Path) -> None:
    manager = FakeManager()
    service = await _service(tmp_path, manager)
    ready_project = _managed_project(tmp_path / "ready")
    ready_id, interrupted_id = uuid4(), uuid4()
    ready_name, interrupted_name = f"napari-{ready_id.hex}", f"napari-{interrupted_id.hex}"
    manager.environments[ready_name] = FakeManagedEnvironment(ready_name, ready_project, uuid4())

    recipe = NapariManagedRecipeSelection().resolved()
    environments = [
        NapariEnvironment(
            id=environment_id,
            registration_order=index,
            name=name,
            ownership="managed",
            kind="conda",
            root=f"managed-pending:{wetlands_name}",
            interpreter="",
            interpreter_identity="",
            interpreter_fingerprint="",
            launch=NapariLaunchContext(strategy="wetlands-managed"),
            managed=NapariManagedMetadata(
                wetlands_name=wetlands_name,
                installation_generation=None,
                recipe=recipe,
            ),
            state="creating",
        )
        for index, (environment_id, name, wetlands_name) in enumerate(
            [
                (ready_id, "Ready after restart", ready_name),
                (interrupted_id, "Interrupted", interrupted_name),
            ]
        )
    ]
    operations = [
        NapariEnvironmentOperation(
            id=uuid4(),
            environment_id=environment.id,
            kind="create",
            state="installing",
            progress=60,
            message="Old live progress",
        )
        for environment in environments
    ]
    await service.store.patch_napari_registry(
        0,
        {
            "napari_environments": environments,
            "napari_environment_operations": operations,
        },
    )

    await service.reconcile_managed_operations()

    recovered = service.managed_operation(ready_id, operations[0].id)
    interrupted = service.managed_operation(interrupted_id, operations[1].id)
    assert recovered.operation.state == "completed"
    assert recovered.environment.state == "ready"
    assert recovered.environment.root == str(ready_project.resolve())
    assert interrupted.operation.state == "failed"
    assert interrupted.operation.error.code == "napari_operation_interrupted"
    assert "did not survive process restart" in interrupted.operation.message
