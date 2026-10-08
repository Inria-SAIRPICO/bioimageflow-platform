"""One isolated actual manual force lifecycle, fault/retry and owner isolation."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

import pytest

pytestmark = [pytest.mark.external, pytest.mark.integration, pytest.mark.serial, pytest.mark.slow]


def test_manual_force_replacement_failure_retry_preserves_other_owners(tmp_path: Path) -> None:
    runtime = tmp_path / "lifecycle-runtime"
    (runtime / "temp").mkdir(parents=True)
    receipt = runtime / "lifecycle.json"
    environment = os.environ.copy()
    environment.pop("BIOIMAGEFLOW_CORE_SOURCE", None)
    environment.update({
        "TMPDIR": str(runtime / "temp"), "BIOIMAGEFLOW_HOME": str(runtime / "home"),
        "BIOIMAGEFLOW_WETLANDS": str(runtime / "wetlands"),
        "BIOIMAGEFLOW_TOOL_STORE": str(runtime / "tool-store"),
    })
    with (runtime / "driver.stdout.log").open("w") as stdout, (runtime / "driver.stderr.log").open("w") as stderr:
        completed = subprocess.run(
            [sys.executable, "-m", "tests.test_integration.test_tool_environment_lifecycle",
             "--driver", str(runtime), "--receipt", str(receipt)],
            env=environment, stdout=stdout, stderr=stderr, timeout=600, check=False,
        )
    assert completed.returncode == 0, f"Actual lifecycle failed; receipt={receipt}; stderr={runtime / 'driver.stderr.log'}"
    evidence = json.loads(receipt.read_text())
    assert evidence["cleanup_errors"] == [], evidence
    assert evidence["retired_selected_workers_absent"], evidence
    assert evidence["independent_preserved"] and evidence["worker_verified"], evidence
    assert evidence["final_workers_absent"] and evidence["final_context_closed"], evidence


async def _drive(runtime: Path, receipt: Path) -> None:
    assert Path(tempfile.gettempdir()).resolve() == (runtime / "temp").resolve()
    from bioimageflow import Workflow, WorkflowExecutionContext
    from bioimageflow.env_manager import WetlandsEnvManager, configure_wetlands, get_shared_environment_manager
    from wetlands import ProvisioningError

    from bioimageflow_server.services.tool_environments import ToolEnvironmentService
    from bioimageflow_server.services.tool_registry import ToolRegistryService
    from bioimageflow_server.services.result_store import ResultStoreService
    from platform_lifecycle_test_tools import LifecycleOther, LifecycleSelected, LifecycleSibling
    from tests.fixtures.stale_environment import pixi_forwarder

    evidence: dict[str, Any] = {
        "controller_pid": os.getpid(), "cleanup_errors": [], "snapshots": {},
        "versions": {}, "retired_selected_workers_absent": False,
        "independent_preserved": False, "worker_verified": False,
        "final_workers_absent": False, "final_context_closed": False,
    }
    for name in ("bioimageflow", "bioimageflow-core", "wetlands"):
        distribution = importlib.metadata.distribution(name)
        assert distribution.read_text("direct_url.json") is None
        evidence["versions"][name] = distribution.version
    pixi, marker = pixi_forwarder(runtime)
    configure_wetlands(root=runtime / "wetlands", pixi_executable=pixi)
    manager = WetlandsEnvManager(use_local_bioimageflow_core=False)
    public = get_shared_environment_manager()
    registry = ToolRegistryService()
    for tool in (LifecycleSelected, LifecycleSibling, LifecycleOther):
        registry._register_tool_from_class(tool, tool.__name__, "lifecycle-proof", "1.0.0")
    service = ToolEnvironmentService(registry=registry, wetlands_manager=manager)
    name = LifecycleSelected.environment.name
    external = public.environments_root / "t1-external"
    external.mkdir(parents=True)
    sentinel = external / "pixi.toml"
    sentinel.write_bytes(b"T1 independently owned unmanaged fixture\n")
    sentinel_hash = hashlib.sha256(sentinel.read_bytes()).hexdigest()
    worker_pids: set[int] = set()
    engine: Any = None
    context: Any = None
    groups: tuple[Any, ...] = ()

    def inventory() -> dict[str, dict[str, Any]]:
        return {
            item.name: {
                "name": item.name, "generation_id": item.generation_id,
                "recipe_hash": item.recipe_hash, "state": item.state.value, "path": str(item.path),
                "worker_pids": [worker.process_id for worker in public.running_workers(item.name)],
            } for item in public.managed_environments()
        }

    def snapshot(label: str) -> dict[str, Any]:
        value = inventory()
        evidence["snapshots"][label] = value
        for item in value.values():
            worker_pids.update(item["worker_pids"])
        assert value[LifecycleOther.environment.name] == unrelated
        assert hashlib.sha256(sentinel.read_bytes()).hexdigest() == sentinel_hash
        return value

    def absent(pids: list[int]) -> None:
        for pid in pids:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)

    def closed(value: dict[str, Any]) -> bool:
        return value["state"] == "closed" and not any(
            value[key] for key in ("pending_readers", "pending_grants", "pending_files", "pending_leases", "errors")
        )

    try:
        manager.get_or_create(LifecycleOther.environment, max_workers=1)
        unrelated = inventory()[LifecycleOther.environment.name]
        assert len(unrelated["worker_pids"]) == 1
        evidence["unmanaged_sha256"] = sentinel_hash
        assert await service.recreate(name) == "running"
        created = snapshot("created")[name]
        assert created["state"] == "ready" and len(created["worker_pids"]) == 1
        assert await service.start(name) == "running"
        assert snapshot("warm")[name] == created
        assert await service.recreate(name) == "running"
        replaced = snapshot("replaced")[name]
        assert replaced["generation_id"] != created["generation_id"]
        assert replaced["recipe_hash"] == created["recipe_hash"]
        absent(created["worker_pids"])
        marker.write_text("one selected real install fault", encoding="utf-8")
        with pytest.raises(ProvisioningError, match="77") as failure:
            await service.recreate(name)
        assert not marker.exists()
        failed = snapshot("failed")
        assert name not in failed or failed[name]["state"] != "ready"
        absent(replaced["worker_pids"])
        evidence["retired_selected_workers_absent"] = True
        evidence["failure"] = failure.value.failure.to_payload()
        assert await service.recreate(name) == "running"
        recovered = snapshot("recovered")[name]
        assert recovered["generation_id"] != replaced["generation_id"]
        assert recovered["recipe_hash"] == created["recipe_hash"]
        with Workflow(storage_path=runtime / "results", name="force-proof", engine="wetlands", execution="sequential") as workflow:
            node = LifecycleSelected()(name="selected", value=4)
            for column in ("multiplied", "process_id", "report"):
                workflow.output(column, node[column])
        context = WorkflowExecutionContext()
        engine = workflow.create_engine(resource_lifetime="external", env_manager=manager)
        value = workflow.compute(engine=engine, run_context=context)
        groups = tuple(context.result_groups)
        assert value.shape == (1, 3)
        assert int(value.iloc[0]["multiplied"]) == 12
        worker_pid = int(value.iloc[0]["process_id"])
        assert worker_pid != os.getpid() and worker_pid in recovered["worker_pids"]
        record = ResultStoreService(storage_path=runtime / "results", tool_registry=registry).get_latest_record_dir("selected")
        assert record is not None
        report = (record / Path(value.iloc[0]["report"])).resolve()
        assert report.is_relative_to(record.resolve())
        assert report.is_file() and report.read_text() == "4 * 3 = 12\n"
        evidence["worker"] = {"value": 12, "pid": worker_pid, "report": report.read_text()}
        evidence["worker_verified"] = True
        snapshot("after_science")
        evidence["independent_preserved"] = True
    except BaseException as error:
        evidence["primary_error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        if context is not None and not groups:
            groups = tuple(context.result_groups)
        actions: list[Any] = [group.release for group in groups]
        if engine is not None:
            actions.append(engine.close)
        actions.append(manager.shutdown_all)
        if context is not None and context.shared_memory_context is not None:
            actions.append(context.shared_memory_context.close)
        for action in actions:
            try:
                action()
            except BaseException as error:
                evidence["cleanup_errors"].append({"type": type(error).__name__, "message": str(error)})
        try:
            absent(list(worker_pids))
            assert all(public.running_workers(env) == () for env in (name, LifecycleOther.environment.name))
            evidence["final_workers_absent"] = True
            if context is not None and context.shared_memory_context is not None:
                status = asdict(context.shared_memory_context.status())
                evidence["final_context_status"] = status
                evidence["final_context_closed"] = closed(status)
                assert closed(status)
            else:
                evidence["final_context_closed"] = context is not None
            assert all(closed(asdict(group.status())) for group in groups)
        except BaseException as error:
            evidence["cleanup_errors"].append({"type": type(error).__name__, "message": str(error)})
        try:
            public.close()
        except BaseException as error:
            evidence["cleanup_errors"].append({"type": type(error).__name__, "message": str(error)})
        receipt.write_text(json.dumps(evidence, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--driver", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(_drive(args.driver, args.receipt))
