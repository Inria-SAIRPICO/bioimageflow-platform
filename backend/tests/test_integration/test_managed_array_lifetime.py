"""One real managed return, app export ownership, and physical pool drain.

The normal child interpreter isolates the SDK's default hydration directory.
Observers retain exact compute handles and delegate the nonhydrating bundle API.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import importlib.metadata
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
from typing import Any
import zipfile

import pytest

pytestmark = [pytest.mark.external, pytest.mark.integration, pytest.mark.serial, pytest.mark.slow]


def test_real_managed_array_export_disposes_exact_owned_groups(tmp_path: Path) -> None:
    runtime = tmp_path / "array-runtime"
    temporary = runtime / "temp"
    temporary.mkdir(parents=True)
    receipt = runtime / "array-lifetime.json"
    environment = os.environ.copy()
    environment.update({
        "TMPDIR": str(temporary),
        "BIOIMAGEFLOW_HOME": str(runtime / "home"),
        "BIOIMAGEFLOW_WETLANDS": str(runtime / "wetlands"),
        "BIOIMAGEFLOW_TOOL_STORE": str(runtime / "tool-store"),
    })
    with (runtime / "driver.stdout.log").open("w") as stdout, (runtime / "driver.stderr.log").open("w") as stderr:
        completed = subprocess.run(
            [sys.executable, "-m", "tests.test_integration.test_managed_array_lifetime",
             "--driver", str(runtime), "--receipt", str(receipt)],
            env=environment, stdout=stdout, stderr=stderr, timeout=600, check=False,
        )
    assert completed.returncode == 0, (
        f"Actual array driver failed; receipt={receipt}; stderr={runtime / 'driver.stderr.log'}"
    )
    evidence = json.loads(receipt.read_text())
    assert evidence["cleanup_errors"] == [], evidence
    assert evidence["compute_closed_after_pool_retirement"] is True, evidence
    assert evidence["archive_pixels_match_after_pool_retirement"] is True, evidence
    assert evidence["independent_owner_preserved"] is True, evidence
    assert evidence["bundle_export_calls"] == 1, evidence
    assert evidence["materialized_export_calls"] == 0, evidence
    assert evidence["bundle_destination_matches"] is True, evidence


async def _drive(runtime: Path, receipt: Path) -> None:
    # The fresh process received TMPDIR before any SDK imports or temp allocation.
    expected_temp = (runtime / "temp").resolve()
    assert Path(tempfile.gettempdir()).resolve() == expected_temp

    import numpy as np
    import pandas as pd
    from bioimageflow.env_manager import WetlandsEnvManager, get_shared_environment_manager
    from bioimageflow_core import SharedArray, SharedMemoryContext
    from bioimageflow_core.shm import open_shared_array

    from bioimageflow_server.services.execution import ExecutionManager, NullEventBus
    from bioimageflow_server.services.tool_environments import ToolEnvironmentService
    from bioimageflow_server.services.tool_registry import ToolRegistryService
    from platform_array_test_tools import ManagedArray
    from tests.graph_factory import graph_state

    evidence: dict[str, Any] = {
        "controller_pid": os.getpid(), "tempdir": str(expected_temp),
        "versions": {}, "events": [], "cleanup_errors": [],
        "bundle_export_calls": 0, "materialized_export_calls": 0,
    }
    for distribution in ("bioimageflow", "bioimageflow-core", "wetlands"):
        installed = importlib.metadata.distribution(distribution)
        assert installed.read_text("direct_url.json") is None
        evidence["versions"][distribution] = installed.version

    def copied(reference: Any) -> Any:
        with open_shared_array(reference) as view:
            pixels = np.array(view, copy=True)
            del view
        return pixels

    def arrays(value: Any) -> list[Any]:
        frames = [value] if isinstance(value, pd.DataFrame) else list(value.values())
        return [cell for frame in frames for column in frame for cell in frame[column].array
                if isinstance(cell, SharedArray)]

    def return_shape(value: Any) -> dict[str, Any]:
        frames = [value] if isinstance(value, pd.DataFrame) else (
            list(value.values()) if isinstance(value, dict) else []
        )
        return {
            "type": f"{type(value).__module__}.{type(value).__qualname__}",
            "mapping_keys": list(value)[:8] if isinstance(value, dict) else None,
            "frames": [{
                "type": f"{type(frame).__module__}.{type(frame).__qualname__}",
                "shape": list(frame.shape), "columns": [str(column) for column in frame.columns[:8]],
                "first_row_types": {
                    str(column): f"{type(frame[column].iloc[0]).__module__}.{type(frame[column].iloc[0]).__qualname__}"
                    for column in frame.columns[:8]
                } if len(frame) else {},
            } for frame in frames[:8] if isinstance(frame, pd.DataFrame)],
        }

    def status(owner: Any) -> dict[str, Any]:
        return asdict(owner.status())

    def completely_closed(observed: dict[str, Any]) -> bool:
        return observed["state"] == "closed" and not any(
            observed[name] for name in (
                "pending_readers", "pending_grants", "pending_files", "pending_leases", "errors",
            )
        )

    compute_groups: tuple[Any, ...] = ()
    compute_context: Any = None
    returned_pixels: Any = None
    selected_pid: int | None = None

    class ObservedExecutionManager(ExecutionManager):
        def _create_execution_engine(self, workflow: Any, context: Any) -> Any:
            workflow.get_environment(ManagedArray.environment.name).max_workers = 1
            engine = super()._create_execution_engine(workflow, context)
            real_close = engine.close

            def close() -> Any:
                evidence["events"].append("engine_close")
                return real_close()

            engine.close = close
            return engine

        def _materialize_latest_outputs(self, workflow: Any, storage_path: Any, context: Any) -> None:
            super()._materialize_latest_outputs(workflow, storage_path, context)
            assert (storage_path / "views" / "latest" / "array.bioimageflow-link.json").is_file()
            evidence["events"].append("latest_materialized")

        def _export_managed_result(self, context: Any, value: Any) -> None:
            nonlocal compute_context, compute_groups, returned_pixels, selected_pid
            compute_context = self._workflow_run_contexts[context.execution_id]
            evidence["compute_return_shape"] = return_shape(value)
            references = arrays(value)
            assert len(references) == 1, evidence["compute_return_shape"]
            reference = references[0]
            compute_groups = tuple(compute_context.result_groups)
            assert any(group is reference.bound_group for group in compute_groups)
            assert reference.bound_owner is not None
            assert (
                reference.bound_owner.descriptor()["owner_id"]
                == compute_context.shared_memory_context.descriptor()["owner_id"]
            )
            returned_pixels = copied(reference)
            np.testing.assert_array_equal(returned_pixels, np.full((8, 8), 11, dtype=np.uint16))
            assert returned_pixels.dtype == np.dtype("uint16")
            frames = [value] if isinstance(value, pd.DataFrame) else list(value.values())
            selected_pid = int(frames[0].iloc[0]["worker_pid"])
            assert selected_pid != os.getpid()
            evidence["worker_pid"] = selected_pid
            evidence["compute_owner_descriptor"] = compute_context.shared_memory_context.descriptor()
            evidence["compute_ref_owner_descriptor"] = reference.bound_owner.descriptor()
            real_export = compute_context.export_result_bundle
            real_materialized_export = compute_context.export_result

            def export(*args: Any, **kwargs: Any) -> Path:
                evidence["bundle_export_calls"] += 1
                try:
                    installed = real_export(*args, **kwargs)
                except BaseException as error:
                    evidence["sdk_export_exception"] = {
                        "type": f"{type(error).__module__}.{type(error).__qualname__}",
                        "code": getattr(error, "code", None), "message": str(error),
                        "traceback": traceback.format_exc(),
                    }
                    raise
                assert isinstance(installed, Path)
                assert installed == (export_root / context.execution_id).absolute()
                assert installed.is_dir()
                evidence["bundle_destination_matches"] = True
                evidence["bundle_destination"] = str(installed)
                evidence["events"].append("sdk_bundle_export_returned")
                return installed

            def materialized_export(*_args: Any, **_kwargs: Any) -> Any:
                evidence["materialized_export_calls"] += 1
                raise AssertionError("The application must use the bundle-only export API")

            compute_context.export_result_bundle = export
            compute_context.export_result = materialized_export
            try:
                super()._export_managed_result(context, value)
            finally:
                compute_context.export_result_bundle = real_export
                compute_context.export_result = real_materialized_export
            export_snapshot = self.retained_result_export(context)
            evidence["application_export_snapshot_before_completion"] = export_snapshot.model_dump(mode="json")
            assert export_snapshot.state == "available", evidence["application_export_snapshot_before_completion"]
            destination = export_root / context.execution_id
            assert self.export_retained_result(context, destination).is_file()
            evidence["events"].append("archive_available")

        def _settle_run_resources(self, execution_id: str, run_context: Any, engine: Any, **kwargs: Any) -> None:
            nonlocal compute_context, compute_groups
            if compute_context is None:
                compute_context = run_context
                compute_groups = tuple(run_context.result_groups)
            if kwargs.get("primary") is None:
                assert run_context is compute_context
                assert "archive_available" in evidence["events"]
            evidence["events"].append("app_cleanup")
            super()._settle_run_resources(execution_id, run_context, engine, **kwargs)

    export_root = runtime / "exports"
    export_root.mkdir()
    export_root_stat = export_root.stat()
    evidence["managed_result_root_before_run"] = {
        "path": str(export_root), "exists": export_root.is_dir(),
        "is_symlink": export_root.is_symlink(),
        "identity": [export_root_stat.st_dev, export_root_stat.st_ino],
    }
    registry = ToolRegistryService()
    registry._register_tool_from_class(ManagedArray, "ManagedArray", "array-lifetime", "1.0.0")
    wetlands = WetlandsEnvManager(root=runtime / "wetlands", use_local_bioimageflow_core=False)
    environments = ToolEnvironmentService(registry=registry, wetlands_manager=wetlands)
    manager = ObservedExecutionManager(
        NullEventBus(), registry, storage_path=runtime / "results",
        environment_manager_provider=lambda: wetlands,
        environment_replacement_authorizer=environments.can_replace_processing_environment,
        processing_environment_lock=environments.processing_environment_lock,
        managed_result_root=export_root,
    )
    independent = SharedMemoryContext(runtime / "independent")
    sentinel = independent.create(np.array([41, 42], dtype=np.uint16))
    np.testing.assert_array_equal(copied(sentinel), [41, 42])
    independent_before = status(independent)
    try:
        graph = graph_state(
            config={"engine": "wetlands", "execution": "sequential"},
            nodes=[{
                "type": "tool", "id": "array", "name": "array",
                "tool_name": "ManagedArray", "position": [0, 0], "parameters": {"value": 11},
            }],
            interface={
                "inputs": [],
                "outputs": [{
                    "id": column, "name": column,
                    "source": {"node": "array", "column": column},
                } for column in ("image", "value", "worker_pid")],
            },
        )
        context = await manager.start(graph, workflow_id="array-lifetime", draft_revision=1)
        async with asyncio.timeout(540):
            while manager.state != "idle":
                await asyncio.sleep(0.02)
        assert manager.last_result is not None and manager.last_result.success
        assert manager.last_result.errors == []
        assert compute_groups and all(group.released for group in compute_groups)
        assert wetlands.is_running(ManagedArray.environment.name)
        warm_status = status(compute_context.shared_memory_context)
        assert warm_status["pending_grants"] > 0
        assert warm_status["pending_readers"] == warm_status["pending_leases"] == 0
        evidence["compute_after_app_cleanup"] = warm_status
        assert evidence["events"].index("latest_materialized") < evidence["events"].index("sdk_bundle_export_returned")
        assert evidence["events"].index("sdk_bundle_export_returned") < evidence["events"].index("archive_available")
        assert evidence["events"].index("archive_available") < evidence["events"].index("app_cleanup")
        assert evidence["events"].index("app_cleanup") < evidence["events"].index("engine_close")

        await environments.stop(ManagedArray.environment.name)
        assert not wetlands.is_running(ManagedArray.environment.name)
        assert get_shared_environment_manager().running_workers(ManagedArray.environment.name) == ()
        assert selected_pid is not None
        with pytest.raises(ProcessLookupError):
            os.kill(selected_pid, 0)
        manager.retry_resource_cleanup()
        drained = status(compute_context.shared_memory_context)
        assert completely_closed(drained)
        assert all(completely_closed(asdict(group.status())) for group in compute_groups)
        evidence["compute_closed_after_pool_retirement"] = True
        evidence["compute_after_pool_retirement"] = drained

        assert evidence["bundle_export_calls"] == 1
        assert evidence["materialized_export_calls"] == 0
        destination = export_root / context.execution_id
        archive = manager.export_retained_result(context, destination)
        with zipfile.ZipFile(archive) as bundle:
            assets = [member for member in bundle.namelist() if member.endswith(".npy")]
            assert assets
            for member in assets:
                pixels = np.load(io.BytesIO(bundle.read(member)), allow_pickle=False)
                np.testing.assert_array_equal(pixels, returned_pixels)
                assert pixels.dtype == np.dtype("uint16")
        evidence["archive_pixels_match_after_pool_retirement"] = True
        evidence["archive_array_members"] = assets
        np.testing.assert_array_equal(copied(sentinel), [41, 42])
        assert status(independent) == independent_before
        evidence["independent_owner_preserved"] = True
    except BaseException as error:
        evidence["primary_error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        # Continue independent exact cleanup while preserving any primary error.
        try:
            await environments.stop(ManagedArray.environment.name)
        except BaseException as error:
            evidence["cleanup_errors"].append(f"selected pool: {type(error).__name__}: {error}")
        try:
            wetlands.shutdown_all()
        except BaseException as error:
            evidence["cleanup_errors"].append(f"pools: {type(error).__name__}: {error}")
        try:
            await manager.close()
        except BaseException as error:
            evidence["cleanup_errors"].append(f"execution: {type(error).__name__}: {error}")
        try:
            manager.retry_resource_cleanup()
        except BaseException as error:
            evidence["cleanup_errors"].append(f"retry: {type(error).__name__}: {error}")
        for group in compute_groups:
            try:
                group.release()
            except BaseException as error:
                evidence["cleanup_errors"].append(f"group: {type(error).__name__}: {error}")
        owners = [independent]
        if compute_context is not None and compute_context.shared_memory_context is not None:
            owners.append(compute_context.shared_memory_context)
        for owner in owners:
            try:
                owner.close()
                assert completely_closed(status(owner))
            except BaseException as error:
                evidence["cleanup_errors"].append(f"scope: {type(error).__name__}: {error}")
        try:
            get_shared_environment_manager().close()
        except BaseException as error:
            evidence["cleanup_errors"].append(f"provider: {type(error).__name__}: {error}")
        evidence["cleanup_boundary"] = (
            "Exact compute groups and controller scopes are observed through public statuses. "
            "The application delegates bundle-only export and never requests a materialized return; "
            "this does not certify arbitrary or unrelated hidden owners."
        )
        receipt.write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--driver", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    arguments = parser.parse_args()
    asyncio.run(_drive(arguments.driver, arguments.receipt))
