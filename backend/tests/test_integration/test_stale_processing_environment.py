"""Real owned-generation replacement, failed install recovery, and restart reuse."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from bioimageflow.env_manager import (
    WetlandsEnvManager,
    _reset_shared_manager,
    configure_wetlands,
    get_shared_environment_manager,
)
from bioimageflow_core import EnvironmentSpec
from wetlands import ProvisioningError, UnmanagedTargetError

from tests.fixtures.restarted_processing import run_worker
from tests.fixtures.stale_environment import (
    ObservedProcessingManager,
    inventory,
    pixi_forwarder,
)
from platform_test_tools.stale import StaleWorkerNumbers

pytestmark = [pytest.mark.external, pytest.mark.integration, pytest.mark.serial, pytest.mark.slow]


def _generation(evidence: dict, name: str) -> dict:
    return next(item for item in evidence["inventory"] if item["name"] == name)


def _assert_worker(evidence: dict) -> None:
    assert evidence["values"] == [6, 9, 12]
    assert evidence["reports"] == ["2 * 3 = 6\n", "3 * 3 = 9\n", "4 * 3 = 12\n"]
    assert len(set(evidence["worker_pids"])) == 1
    assert evidence["worker_pids"][0] != evidence["orchestrator_pid"]
    assert evidence["failures"] == []


def test_real_stale_generation_failure_retry_and_fresh_process_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIOIMAGEFLOW_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("BIOIMAGEFLOW_WETLANDS", str(tmp_path / "wetlands"))
    monkeypatch.setenv("BIOIMAGEFLOW_TOOL_STORE", str(tmp_path / "tool_packages"))
    _reset_shared_manager()
    pixi, failure_marker = pixi_forwarder(tmp_path)
    configure_wetlands(root=tmp_path / "wetlands", pixi_executable=pixi)
    observed = manager = ObservedProcessingManager(WetlandsEnvManager())
    name = StaleWorkerNumbers.environment.name
    try:
        fresh = run_worker(observed, tmp_path / "fresh-results")
        _assert_worker(fresh)
        assert observed.preparations[0] == {
            "name": name, "action": "creating",
            "requested_recipe_hash": _generation(fresh, name)["recipe_hash"],
            "existing_recipe_hash": None,
        }
        assert [item["action"] for item in observed.preparations] == ["creating"]
        # Another lifecycle's owned environment and a user-managed directory
        # remain exactly as supplied while the selected processing one changes.
        unrelated_spec = EnvironmentSpec(name="codeserver", dependencies={"python": "3.12"})
        manager.get_or_create(unrelated_spec)
        manager.stop(unrelated_spec.name)
        unrelated = next(item for item in inventory() if item["name"] == "codeserver")
        external = get_shared_environment_manager().environments_root / "e1-external"
        external.mkdir()
        external_manifest = external / "pixi.toml"
        external_manifest.write_bytes(b"user-managed fixture bytes\n")

        old = observed.seed_stale()
        observed.release.set()
        failure_marker.write_text("fail one actual install", encoding="utf-8")
        with pytest.raises(ProvisioningError, match="77") as failed_install:
            run_worker(observed, tmp_path / "failed-results")
        assert not failure_marker.exists()
        assert observed.preparations[0]["action"] == "updating"
        assert any("E1 injected Pixi install failure" in str(event) for event in observed.events)
        assert observed.evidence()["retired_workers_alive"] == []

        retry = run_worker(observed, tmp_path / "retry-results")
        _assert_worker(retry)
        replacement = _generation(retry, name)
        assert replacement["state"] == "ready"
        assert replacement["generation_id"] != old["generation_id"]
        assert replacement["recipe_hash"] != old["recipe_hash"]
        assert _generation(retry, "codeserver") == unrelated
        assert external_manifest.read_bytes() == b"user-managed fixture bytes\n"
        with pytest.raises((ProvisioningError, UnmanagedTargetError)):
            manager.get_or_create(EnvironmentSpec(name="e1-external", dependencies={"python": "3.12"}))
        assert external_manifest.read_bytes() == b"user-managed fixture bytes\n"

        reused = run_worker(observed, tmp_path / "reuse-results")
        _assert_worker(reused)
        assert reused["preparations"][0]["action"] == "reusing"
        assert _generation(reused, name) == replacement
        before_restart = observed.evidence()
        prior_pid = reused["worker_pids"][0]
        manager.shutdown_all()
        assert observed.pending_run_contexts == []
        assert get_shared_environment_manager().running_workers(name) == ()
        with pytest.raises(ProcessLookupError):
            os.kill(prior_pid, 0)
        get_shared_environment_manager().close()
        restarted = subprocess.run(
            [sys.executable, "-m", "tests.fixtures.restarted_processing",
             str(tmp_path / "wetlands"), str(pixi), str(tmp_path / "restart-results")],
            cwd=Path(__file__).parents[2], capture_output=True, text=True, timeout=180,
            check=True,
        )
        evidence = json.loads(restarted.stdout.splitlines()[-1])
        _assert_worker(evidence)
        assert evidence["cleanup_pending"] is False
        assert evidence["orchestrator_pid"] != os.getpid()
        assert evidence["worker_pids"][0] != prior_pid
        assert evidence["preparations"][0]["action"] == "reusing"
        # Discovery in a new manager must preserve the exact ready identity;
        # the worker process itself is deliberately new.
        assert {key: _generation(evidence, name)[key] for key in ("generation_id", "recipe_hash")} == {
            key: replacement[key] for key in ("generation_id", "recipe_hash")
        }
        assert _generation(evidence, "codeserver") == unrelated
        assert external_manifest.read_bytes() == b"user-managed fixture bytes\n"
        (tmp_path / "e1-runtime-evidence.json").write_text(json.dumps({
            "fresh": fresh, "old": old,
            "injected_failure": failed_install.value.failure.to_payload(),
            "retry": retry, "reuse": reused,
            "before_restart": before_restart, "restart": evidence,
            "retired_worker_pid": prior_pid, "retired_worker_alive": False,
        }, indent=2))
    finally:
        manager.shutdown_all()
        _reset_shared_manager()
