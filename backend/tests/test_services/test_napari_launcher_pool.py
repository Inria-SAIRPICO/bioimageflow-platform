from __future__ import annotations

import asyncio
import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from wetlands import EnvironmentNotReadyError, OutputEvent, OutputStream

from bioimageflow_server.models.napari import NapariEnvironmentStatus, NapariStatus
from bioimageflow_server.models.napari_environments import (
    NapariEnvironment,
    NapariEnvironmentInventory,
    NapariEnvironmentList,
    NapariLaunchContext,
    NapariManagedMetadata,
    NapariManagedRecipe,
)
from bioimageflow_server.services.napari_launcher import (
    NapariLauncher,
    NapariLauncherPool,
)


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _environment(name: str, *, fingerprint: str = "inventory-a") -> NapariEnvironment:
    environment_id = uuid4()
    root = f"/tmp/{name} env"
    interpreter = f"{root}/bin/python"
    return NapariEnvironment(
        id=environment_id,
        registration_order=0,
        name=name,
        ownership="external",
        kind="venv",
        root=root,
        interpreter=interpreter,
        interpreter_identity=interpreter,
        interpreter_fingerprint=f"python-{name}",
        launch=NapariLaunchContext(strategy="interpreter", argv_prefix=[interpreter]),
        inventory=NapariEnvironmentInventory(
            python_version="3.12.8",
            napari_version="0.9.1",
            distributions=[],
            fingerprint=fingerprint,
            probed_at=datetime.now(UTC),
        ),
    )


def _snapshot(environments: list[NapariEnvironment]) -> NapariEnvironmentList:
    return NapariEnvironmentList(
        revision=0,
        environments=environments,
        default_environment_id=environments[0].id if environments else None,
        filename_rules=[],
    )


def _managed_environment(name: str, *, source: str) -> NapariEnvironment:
    external = _environment(name)
    recipe = (
        NapariManagedRecipe(source="adopted")
        if source == "adopted"
        else NapariManagedRecipe(
            source="managed",
            preset="default",
            python="==3.12.*",
            napari="0.9.1",
            qt="PyQt6",
            channels=["conda-forge"],
        )
    )
    return external.model_copy(
        update={
            "ownership": "managed",
            "launch": NapariLaunchContext(
                strategy="wetlands-managed", argv_prefix=[external.interpreter]
            ),
            "managed": NapariManagedMetadata(
                wetlands_name=f"napari-{name}",
                installation_generation=uuid4(),
                recipe=recipe,
            ),
        }
    )


class _PoolLauncher:
    def __init__(self, environment: NapariEnvironment, entered: asyncio.Event) -> None:
        self.environment = environment
        self.entered = entered
        self.release = asyncio.Event()
        self.shutdown = AsyncMock()
        self.calls: list[tuple[list[str], bool, str | None]] = []

    async def open(
        self, paths: list[str], clear_layers: bool, *, reader_id: str | None = None
    ) -> None:
        self.calls.append((paths, clear_layers, reader_id))
        self.entered.set()
        await self.release.wait()

    def environment_status(self) -> NapariEnvironmentStatus:
        return NapariEnvironmentStatus(
            running=True,
            env_path=self.environment.root,
            pid=123,
            environment_id=self.environment.id,
            environment_name=self.environment.name,
            installation_identity="test",
            status="running",
        )


async def test_different_environments_open_concurrently(tmp_path: Path) -> None:
    first, second = _environment("first"), _environment("second")
    artifacts = [tmp_path / "first.tif", tmp_path / "second.tif"]
    for artifact in artifacts:
        artifact.write_bytes(b"tif")
    entered = {first.id: asyncio.Event(), second.id: asyncio.Event()}
    launchers: dict[UUID, _PoolLauncher] = {}

    def factory(**kwargs: Any) -> _PoolLauncher:
        environment = kwargs["environment"]
        launcher = _PoolLauncher(environment, entered[environment.id])
        launchers[environment.id] = launcher
        return launcher

    legacy = MagicMock(spec=NapariLauncher)
    pool = NapariLauncherPool(
        lambda: _snapshot([first, second]),
        legacy_launcher=legacy,
        config_root=tmp_path / "config",
        launcher_factory=factory,  # type: ignore[arg-type]
    )
    tasks = [
        asyncio.create_task(pool.open([str(artifacts[index])], environment_id=environment.id))
        for index, environment in enumerate((first, second))
    ]
    await asyncio.wait_for(asyncio.gather(*(event.wait() for event in entered.values())), timeout=1)
    for launcher in launchers.values():
        launcher.release.set()
    await asyncio.gather(*tasks)


async def test_shutdown_is_scoped_to_one_environment(tmp_path: Path) -> None:
    first, second = _environment("first"), _environment("second")
    launchers: dict[UUID, _PoolLauncher] = {}

    def factory(**kwargs: Any) -> _PoolLauncher:
        environment = kwargs["environment"]
        launcher = _PoolLauncher(environment, asyncio.Event())
        launchers[environment.id] = launcher
        return launcher

    pool = NapariLauncherPool(
        lambda: _snapshot([first, second]),
        legacy_launcher=MagicMock(spec=NapariLauncher),
        config_root=tmp_path,
        launcher_factory=factory,  # type: ignore[arg-type]
    )
    await pool._launcher(first.id)
    await pool._launcher(second.id)
    await pool.shutdown(first.id)
    launchers[first.id].shutdown.assert_awaited_once()
    launchers[second.id].shutdown.assert_not_awaited()


async def test_inventory_change_marks_running_process_stale(tmp_path: Path) -> None:
    current = _environment("viewer")
    holder = {"environment": current}

    def factory(**kwargs: Any) -> _PoolLauncher:
        return _PoolLauncher(kwargs["environment"], asyncio.Event())

    pool = NapariLauncherPool(
        lambda: _snapshot([holder["environment"]]),
        legacy_launcher=MagicMock(spec=NapariLauncher),
        config_root=tmp_path,
        launcher_factory=factory,  # type: ignore[arg-type]
    )
    await pool._launcher(current.id)
    holder["environment"] = current.model_copy(
        update={"inventory": current.inventory.model_copy(update={"fingerprint": "inventory-b"})}
    )
    status = pool.status(current.id)
    assert isinstance(status, NapariEnvironmentStatus)
    assert status.running is True
    assert status.pid == 123
    assert status.status == "restart_required"
    assert "must restart" in (status.detail or "")


async def test_legacy_calls_remain_no_id_compatibility_path(tmp_path: Path) -> None:
    legacy = MagicMock(spec=NapariLauncher)
    legacy.open = AsyncMock()
    legacy.shutdown = AsyncMock()
    legacy.status.return_value = NapariStatus(running=False)
    pool = NapariLauncherPool(lambda: _snapshot([]), legacy_launcher=legacy, config_root=tmp_path)
    await pool.open([], True)
    assert pool.status() == NapariStatus(running=False)
    await pool.shutdown()
    legacy.open.assert_awaited_once_with([], True)
    legacy.shutdown.assert_awaited_once()


class _FakePopen:
    def __init__(self) -> None:
        self.stdout = io.StringIO("Listening port 54321\n")
        self.pid = 9876
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        self.returncode = 0
        return 0

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9


class _FakeManagedProcess:
    pid = 7654
    running = True

    def wait_for_line(self, predicate, timeout=None):
        del timeout
        event = OutputEvent(0, 0.0, OutputStream.STDOUT, "Listening port 54321")
        assert predicate(event)
        return event

    def close(self) -> None:
        self.running = False


def test_managed_recipe_launch_uses_public_wetlands_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment = _managed_environment("managed", source="managed")
    process = _FakeManagedProcess()
    managed = MagicMock()
    managed.path = Path(environment.root)
    managed.spawn.return_value = process
    provider = MagicMock(return_value=managed)
    monkeypatch.setattr(
        "bioimageflow_server.services.napari_launcher.Client",
        lambda address, *, authkey: MagicMock(),
    )
    process_factory = MagicMock(side_effect=AssertionError("must use Wetlands spawn"))
    launcher = NapariLauncher(
        environment=environment,
        config_root=tmp_path,
        process_factory=process_factory,
        managed_environment_provider=provider,
    )
    launcher._launch()
    provider.assert_called_once_with(environment.managed.wetlands_name)
    spawn_argv = managed.spawn.call_args.args[0]
    assert spawn_argv[:1] == environment.launch.argv_prefix
    assert spawn_argv[-2] == "-u"
    assert managed.spawn.call_args.kwargs["env"]["PYTHONPATH"] is None
    process_factory.assert_not_called()


def test_adopted_legacy_install_falls_back_to_persisted_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment = _managed_environment("adopted", source="adopted")
    provider = MagicMock(side_effect=EnvironmentNotReadyError("legacy Wetlands 1 install"))
    monkeypatch.setattr(
        "bioimageflow_server.services.napari_launcher.Client",
        lambda address, *, authkey: MagicMock(),
    )
    process = _FakePopen()
    process_factory = MagicMock(return_value=process)
    launcher = NapariLauncher(
        environment=environment,
        config_root=tmp_path,
        process_factory=process_factory,
        managed_environment_provider=provider,
    )
    launcher._launch()
    argv = process_factory.call_args.args[0]
    assert argv[:1] == environment.launch.argv_prefix


def test_registered_launch_uses_frozen_argv_and_per_uuid_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment = _environment("path with spaces")
    frozen_prefix = [
        "/opt/Conda With Spaces/bin/conda",
        "run",
        "--no-capture-output",
        "-p",
        environment.root,
        "python",
    ]
    environment = environment.model_copy(
        update={
            "kind": "conda",
            "launch": NapariLaunchContext(
                strategy="conda-run",
                argv_prefix=frozen_prefix,
                conda_executable=frozen_prefix[0],
            ),
        }
    )
    process = _FakePopen()
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def process_factory(argv: list[str], **kwargs: Any) -> _FakePopen:
        calls.append((argv, kwargs))
        return process

    connection = MagicMock()
    monkeypatch.setattr(
        "bioimageflow_server.services.napari_launcher.Client",
        lambda address, *, authkey: connection,
    )
    monkeypatch.setattr(
        "bioimageflow_server.services.napari_launcher.get_shared_environment_manager",
        lambda: (_ for _ in ()).throw(AssertionError("must not provision registered env")),
    )
    launcher = NapariLauncher(
        environment=environment,
        config_root=tmp_path / "user config",
        process_factory=process_factory,  # type: ignore[arg-type]
    )
    launcher._launch()
    argv, kwargs = calls[0]
    assert argv[: len(frozen_prefix)] == frozen_prefix
    assert argv[len(frozen_prefix)] == "-u"
    assert argv[len(frozen_prefix) + 1].endswith("napari_manager.py")
    assert kwargs["shell"] is False
    assert kwargs["env"]["NAPARI_CONFIG"] == str(
        (tmp_path / "user config" / str(environment.id) / "settings.yaml").resolve()
    )
    assert "PYTHONPATH" not in kwargs["env"]


async def test_missing_explicit_artifact_fails_before_launcher_creation(
    tmp_path: Path,
) -> None:
    environment = _environment("viewer")
    factory = MagicMock()
    pool = NapariLauncherPool(
        lambda: _snapshot([environment]),
        legacy_launcher=MagicMock(spec=NapariLauncher),
        config_root=tmp_path,
        launcher_factory=factory,
    )
    with pytest.raises(FileNotFoundError):
        await pool.open([str(tmp_path / "missing.tif")], environment_id=environment.id)
    factory.assert_not_called()
