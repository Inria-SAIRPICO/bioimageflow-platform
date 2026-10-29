"""Registry, filename-rule, migration, and package-only probe contracts."""

from __future__ import annotations

import json
import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4
import pytest

from bioimageflow_server.models.napari_environments import (
    NapariFilenameRuleCreate,
    NapariEnvironmentOperation,
    NapariManagedRecipeSelection,
)
from bioimageflow_server.services.napari_environments import (
    PROBE_OUTPUT_LIMIT,
    PROBE_TIMEOUT_SECONDS,
    NapariEnvironmentError,
    NapariEnvironmentService,
    _bounded_run,
    canonicalize_rule_value,
)
from bioimageflow_server.services.settings_store import SettingsStore


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _python_link(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(sys.executable)


def _venv(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "pyvenv.cfg").write_text("home = test\n")
    _python_link(root / "bin" / "python")
    return root


def _conda(root: Path) -> Path:
    (root / "conda-meta").mkdir(parents=True)
    _python_link(root / "bin" / "python")
    return root


async def _service(tmp_path: Path, **kwargs: object) -> NapariEnvironmentService:
    store = SettingsStore(tmp_path / "settings.json")
    await store.load()
    return NapariEnvironmentService(store, **kwargs)  # type: ignore[arg-type]


async def test_registers_spaced_venv_with_uuid_and_stable_order(tmp_path: Path) -> None:
    service = await _service(tmp_path)
    first_root = _venv(tmp_path / "viewer one")
    second_root = _venv(tmp_path / "viewer two")

    first = await service.register("Microscopy", str(first_root), expected_revision=0)
    second = await service.register(
        "Tracking", str(second_root / "bin" / "python"), expected_revision=1
    )

    assert first.id != second.id
    assert [first.registration_order, second.registration_order] == [0, 1]
    assert first.kind == "venv"
    assert first.launch.strategy == "interpreter"
    assert first.launch.argv_prefix == [first.interpreter]
    assert first.interpreter_identity == str(Path(sys.executable).resolve())
    assert service.snapshot().revision == 2

    reloaded = SettingsStore(service.store.path)
    await reloaded.load()
    assert reloaded.get().napari_environments[0].launch == first.launch


async def test_conda_registration_retains_conda_run_prefix(tmp_path: Path) -> None:
    conda = tmp_path / "tools" / "conda"
    _python_link(conda)
    service = await _service(tmp_path, conda_executable=str(conda))
    root = _conda(tmp_path / "conda env")

    environment = await service.register("Conda", str(root), expected_revision=0)

    assert environment.kind == "conda"
    assert environment.launch.strategy == "conda-run"
    assert environment.launch.conda_executable == str(Path(sys.executable).resolve())
    assert environment.launch.argv_prefix[1:5] == [
        "run",
        "--no-capture-output",
        "-p",
        os.path.abspath(root),
    ]


async def test_duplicate_interpreter_and_casefolded_name_are_rejected(tmp_path: Path) -> None:
    service = await _service(tmp_path)
    root = _venv(tmp_path / "viewer")
    await service.register("Microscopy", str(root), expected_revision=0)

    with pytest.raises(NapariEnvironmentError, match="already registered"):
        await service.register("Other", str(root / "bin" / "python"), expected_revision=1)
    (root / "bin" / "python3").symlink_to(root / "bin" / "python")
    with pytest.raises(NapariEnvironmentError, match="already registered"):
        await service.register("Alias", str(root / "bin" / "python3"), expected_revision=1)
    other = _venv(tmp_path / "other")
    with pytest.raises(NapariEnvironmentError, match="unique ignoring case"):
        await service.register(" microscopy ", str(other), expected_revision=1)


async def test_stale_registry_mutation_is_rejected(tmp_path: Path) -> None:
    service = await _service(tmp_path)
    environment = await service.register(
        "Viewer", str(_venv(tmp_path / "viewer")), expected_revision=0
    )

    with pytest.raises(NapariEnvironmentError) as raised:
        await service.update(environment.id, name="Stale", expected_revision=0)
    assert raised.value.code == "napari_registry_revision_conflict"


async def test_missing_and_located_external_interpreter(tmp_path: Path) -> None:
    service = await _service(tmp_path)
    original_root = _venv(tmp_path / "original")
    environment = await service.register("Viewer", str(original_root), expected_revision=0)
    (original_root / "bin" / "python").unlink()
    assert service.snapshot().environments[0].state == "missing"

    replacement_root = _venv(tmp_path / "replacement")
    located = await service.update(environment.id, path=str(replacement_root), expected_revision=1)
    assert located.root == os.path.abspath(replacement_root)
    assert located.state == "ready"
    assert located.inventory is None


async def test_legacy_wetlands_workspace_is_adopted_without_probe(tmp_path: Path) -> None:
    workspace = tmp_path / "wetlands" / "pixi" / "workspaces" / "napari"
    prefix = workspace / ".pixi" / "envs" / "default"
    _conda(prefix)
    (workspace / ".wetlands").mkdir()
    (workspace / ".wetlands" / "environment.json").write_text("{}")
    called = False

    def runner(*_args: object) -> str:
        nonlocal called
        called = True
        return "{}"

    service = await _service(tmp_path, managed_singleton_roots=[workspace], probe_runner=runner)

    await service.initialize_registry()

    snapshot = service.snapshot()
    assert snapshot.revision == 1
    assert len(snapshot.environments) == 1
    adopted = snapshot.environments[0]
    assert adopted.name == "Default napari"
    assert adopted.ownership == "managed"
    assert adopted.managed is not None
    assert adopted.managed.wetlands_name == "napari"
    assert adopted.managed.recipe.source == "adopted"
    assert adopted.launch.strategy == "wetlands-managed"
    assert snapshot.default_environment_id == adopted.id
    assert called is False

    reloaded_store = SettingsStore(service.store.path)
    await reloaded_store.load()
    persisted = reloaded_store.get().napari_environments[0]
    assert persisted.id == adopted.id
    assert persisted.managed is not None
    assert persisted.managed.installation_generation == adopted.managed.installation_generation
    assert persisted.managed.recipe == adopted.managed.recipe
    assert persisted.launch == adopted.launch


async def test_forgotten_legacy_installation_stays_forgotten_after_restart(tmp_path: Path) -> None:
    workspace = tmp_path / "wetlands" / "pixi" / "workspaces" / "napari"
    _conda(workspace / ".pixi" / "envs" / "default")
    service = await _service(tmp_path, managed_singleton_roots=[workspace])
    await service.initialize_registry()
    adopted = service.snapshot().environments[0]

    forgotten = await service.forget(adopted.id, expected_revision=1)
    assert forgotten.environments == []
    assert service.store.get().napari_suppressed_legacy_roots == [adopted.root]

    reloaded = await _service(tmp_path, managed_singleton_roots=[workspace])
    await reloaded.initialize_registry()
    assert reloaded.snapshot().environments == []


async def test_initialize_registry_declares_one_persistent_default_without_runtime_access(tmp_path: Path) -> None:
    def forbidden(*_args: object) -> object:
        raise AssertionError("initial registry setup must not access a runtime or probe")

    service = await _service(
        tmp_path, managed_singleton_roots=[tmp_path / "absent-legacy"],
        probe_runner=forbidden, environment_manager_provider=forbidden,
    )
    await service.store.patch({"fiji_path": "/unchanged/manual/fiji"})
    await asyncio.gather(service.initialize_registry(), service.initialize_registry())
    snapshot = service.snapshot()
    assert snapshot.revision == 1
    assert len(snapshot.environments) == 1
    environment = snapshot.environments[0]
    assert environment.state == "setup_needed"
    assert environment.name == "Default napari"
    assert environment.managed is not None
    assert environment.managed.recipe == NapariManagedRecipeSelection().resolved()
    assert environment.managed.installation_generation is None
    assert environment.interpreter == ""
    assert snapshot.default_environment_id == environment.id
    assert snapshot.operations == []
    assert not (tmp_path / "absent-legacy").exists()
    before = service.store.path.read_bytes()
    with pytest.raises(NapariEnvironmentError) as refusal:
        await service.probe(environment.id, expected_revision=1)
    assert refusal.value.code == "napari_environment_setup_required"
    reloaded = await _service(tmp_path, probe_runner=forbidden, environment_manager_provider=forbidden)
    await reloaded.initialize_registry()
    assert reloaded.snapshot() == snapshot
    assert reloaded.store.path.read_bytes() == before
    assert reloaded.store.get().fiji_path == "/unchanged/manual/fiji"


async def test_initialize_registry_preserves_manual_entries_and_default_choice(tmp_path: Path) -> None:
    service = await _service(tmp_path)
    await service.register("My viewer", str(_venv(tmp_path / "manual")), expected_revision=0)
    await service.set_default(None, expected_revision=1)
    before = service.store.path.read_bytes()
    await service.initialize_registry()
    assert service.store.path.read_bytes() == before
    assert service.snapshot().default_environment_id is None
    assert [entry.name for entry in service.snapshot().environments] == ["My viewer"]


async def test_forget_uninstalled_default_clears_references_without_recreation(tmp_path: Path) -> None:
    def forbidden(*_args: object) -> object:
        raise AssertionError("forgetting a declaration must not touch runtime or probe")

    service = await _service(tmp_path, probe_runner=forbidden, environment_manager_provider=forbidden)
    await service.initialize_registry()
    environment = service.snapshot().environments[0]
    await service.add_rule(NapariFilenameRuleCreate(
        value="tif", mode="extension", environment_id=environment.id, expected_revision=1,
    ))
    await service.forget(environment.id, expected_revision=2)
    assert service.snapshot().environments == []
    assert service.snapshot().filename_rules == []
    assert service.snapshot().default_environment_id is None
    before = service.store.path.read_bytes()
    reloaded = await _service(tmp_path, probe_runner=forbidden, environment_manager_provider=forbidden)
    await reloaded.initialize_registry()
    assert reloaded.snapshot().environments == []
    assert reloaded.store.path.read_bytes() == before


async def test_forget_uninstalled_declaration_refuses_an_active_operation(tmp_path: Path) -> None:
    service = await _service(tmp_path)
    await service.initialize_registry()
    environment = service.snapshot().environments[0]
    operation = NapariEnvironmentOperation(
        id=uuid4(), environment_id=environment.id, kind="retry", state="pending", progress=0, message="Setup queued",
    )
    await service.store.patch_napari_registry(1, {"napari_environment_operations": [operation]})
    before = service.store.path.read_bytes()
    with pytest.raises(NapariEnvironmentError) as refusal:
        await service.forget(environment.id, expected_revision=2)
    assert refusal.value.code == "napari_environment_mutation_active"
    assert service.store.path.read_bytes() == before


async def test_initialize_registry_is_inert_in_webapp_mode(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "webapp.json", deployment_mode="webapp")
    await store.load()

    def forbidden(*_args: object) -> object:
        raise AssertionError("webapp must not inspect a local installation")

    service = NapariEnvironmentService(store, managed_singleton_roots=[tmp_path / "legacy"],
                                      probe_runner=forbidden, environment_manager_provider=forbidden)
    service._resolve_installation = forbidden  # type: ignore[method-assign, assignment]
    await service.initialize_registry()
    assert service.snapshot().revision == 0
    assert service.snapshot().environments == []


async def test_probe_is_package_metadata_only_and_detects_drift(tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, str], float, int]] = []
    fingerprints = iter(["a" * 64, "b" * 64])

    def runner(argv: object, env: dict[str, str], timeout: float, limit: int) -> str:
        calls.append((list(argv), env, timeout, limit))  # type: ignore[arg-type]
        return json.dumps(
            {
                "python_version": "3.12.13",
                "napari_version": "0.7.1",
                "qt_distribution": "pyqt5",
                "qt_version": "5.15.11",
                "bridge_distribution": "bioimageflow-server",
                "bridge_version": "1.0",
                "distributions": [
                    {"name": "example-reader", "version": "2.0"},
                    {"name": "napari", "version": "0.7.1"},
                ],
                "fingerprint": next(fingerprints),
            }
        )

    service = await _service(tmp_path, probe_runner=runner)
    environment = await service.register(
        "Viewer", str(_venv(tmp_path / "viewer")), expected_revision=0
    )
    first = await service.probe(environment.id, expected_revision=1)
    second = await service.probe(environment.id, expected_revision=2)

    assert first.state == "ready"
    assert second.state == "drifted"
    assert [item.name for item in second.inventory.distributions] == [  # type: ignore[union-attr]
        "example-reader",
        "napari",
    ]
    argv, env, timeout, limit = calls[0]
    script = argv[-1]
    assert "importlib.metadata" in script
    assert "import napari" not in script
    assert "entry_points" not in script
    assert "PYTHONPATH" not in env
    assert env["PYTHONNOUSERSITE"] == "1"
    assert (timeout, limit) == (PROBE_TIMEOUT_SECONDS, PROBE_OUTPUT_LIMIT)


async def test_probe_failure_retains_last_good_inventory(tmp_path: Path) -> None:
    attempts = 0

    def runner(*_args: object) -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise NapariEnvironmentError("napari_probe_failed", "broken probe")
        return json.dumps(
            {
                "python_version": "3.12.13",
                "napari_version": "0.9.1",
                "distributions": [{"name": "napari", "version": "0.9.1"}],
                "fingerprint": "a" * 64,
            }
        )

    service = await _service(tmp_path, probe_runner=runner)
    environment = await service.register(
        "Viewer", str(_venv(tmp_path / "viewer")), expected_revision=0
    )
    good = await service.probe(environment.id, expected_revision=1)

    with pytest.raises(NapariEnvironmentError, match="broken probe"):
        await service.probe(environment.id, expected_revision=2)

    failed = service.snapshot().environments[0]
    assert failed.state == "probe_failed"
    assert failed.last_error == "broken probe"
    assert failed.inventory == good.inventory


def test_probe_runner_enforces_time_and_output_bounds() -> None:
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONNOUSERSITE": "1"}
    with pytest.raises(NapariEnvironmentError) as timed_out:
        _bounded_run(
            [sys.executable, "-I", "-c", "import time; time.sleep(0.1)"],
            env,
            0.01,
            100,
        )
    assert timed_out.value.code == "napari_probe_timeout"

    with pytest.raises(NapariEnvironmentError) as too_large:
        _bounded_run([sys.executable, "-I", "-c", "print('x' * 200)"], env, 5.0, 100)
    assert too_large.value.code == "napari_probe_output_limit"


@pytest.mark.parametrize(
    "value,mode",
    [
        ("", "extension"),
        ("a/b", "pattern"),
        ("a\\b", "pattern"),
        ("**.tif", "pattern"),
        ("[abc", "pattern"),
        ("abc]", "pattern"),
    ],
)
def test_rule_validation_rejects_malformed_patterns(value: str, mode: str) -> None:
    with pytest.raises(NapariEnvironmentError):
        canonicalize_rule_value(value, mode)


async def test_rules_normalize_preserve_order_preview_and_cleanup(tmp_path: Path) -> None:
    service = await _service(tmp_path)
    environment = await service.register(
        "Viewer", str(_venv(tmp_path / "viewer")), expected_revision=0
    )
    broad = await service.add_rule(
        NapariFilenameRuleCreate(value="tif", environment_id=environment.id, expected_revision=1)
    )
    specific = await service.add_rule(
        NapariFilenameRuleCreate(
            value="*_labels.tif",
            mode="pattern",
            environment_id=environment.id,
            expected_revision=2,
        )
    )
    assert broad.pattern == "*.tif"
    preview = service.preview("folder/SAMPLE_LABELS.TIF")
    assert preview.matching_rule_ids == [broad.id, specific.id]
    assert preview.winner_rule_id == broad.id

    reordered = await service.replace_rules([specific, broad], expected_revision=3)
    assert reordered.filename_rules == [specific, broad]
    assert service.preview("sample_labels.tif").winner_rule_id == specific.id

    with pytest.raises(NapariEnvironmentError) as duplicate:
        await service.add_rule(
            NapariFilenameRuleCreate(
                value=".TIF", environment_id=environment.id, expected_revision=4
            )
        )
    assert duplicate.value.code == "duplicate_filename_pattern"

    await service.forget(environment.id, expected_revision=4)
    final = service.snapshot()
    assert final.default_environment_id is None
    assert final.filename_rules == []
    assert final.environments == []
