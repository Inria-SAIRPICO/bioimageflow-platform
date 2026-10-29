"""Playwright app factory with isolated persistent services."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Annotated, Any, Literal

import pandas as pd
from bioimageflow import DataFrameTool
from bioimageflow.env_manager import configure_wetlands, get_shared_environment_manager
from bioimageflow_core import Connectable, GUIMeta, IOModel
from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import ProcessingTool, RowConsumption
from fastapi import FastAPI
from pydantic import BaseModel

from bioimageflow_server.app import create_app as create_platform_app
from bioimageflow_server.models.execution import ExecutionContext
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.routers.tools import get_tool_environment_service
from bioimageflow_server.services.pypi_versions import PyPIVersionService
from bioimageflow_server.services.settings_store import SettingsStore
from bioimageflow_server.services.omero_credentials import OmeroCredentialKey
from bioimageflow_server.services.tool_registry import ToolRegistryService
from platform_test_tools.collective import CollectiveNumbers
from platform_test_tools.held import HeldWorkerNumbers
from tests.fixtures.package_metadata import write_package_metadata
from tests.fixtures.stale_environment import (
    ObservedProcessingManager,
    pixi_forwarder,
)
from platform_test_tools.stale import IncompatibleWorkerNumbers, StaleWorkerNumbers


class E2eOmeroCredentials:
    """Deterministic Settings boundary, not actual OS-keyring certification."""

    def __init__(self) -> None:
        self._passwords: dict[OmeroCredentialKey, str] = {}

    def get_password(self, key: OmeroCredentialKey) -> str | None:
        return self._passwords.get(key)

    def set_password(self, key: OmeroCredentialKey, password: str) -> None:
        self._passwords[key] = password

    def delete_password(self, key: OmeroCredentialKey) -> None:
        self._passwords.pop(key, None)


class Generate(DataFrameTool):
    """Dynamic source fixture matching the common-tools GUI contract."""

    display_name = "Generate"
    accepts_upstream = False

    class Inputs(IOModel):
        column_name: Annotated[str, GUIMeta(connectable=Connectable.NEVER)]
        values: Annotated[list[Any], GUIMeta(connectable=Connectable.NEVER)]

    @classmethod
    def resolve_outputs(cls, inputs=None):
        name = (inputs or {}).get("column_name")
        if not name:
            return None
        return {name: {"type": "any", "default": None, "image_spec": None}}

    def transform(self, df, arguments):
        return pd.DataFrame({arguments.column_name: arguments.values})


class CrossJoin(DataFrameTool):
    """Dynamic merge fixture matching the common-tools GUI contract."""

    display_name = "Cross Join"

    class Inputs(IOModel):
        pass

    @classmethod
    def resolve_merge_schema(cls, upstream_schemas, inputs=None):
        if not upstream_schemas or any(schema is None for schema in upstream_schemas):
            return None
        return {
            column: entry
            for schema in upstream_schemas
            for column, entry in schema.items()
        }

    def merge_dataframes(self, dfs, arguments):
        if not dfs:
            return pd.DataFrame()
        result = dfs[0]
        for dataframe in dfs[1:]:
            result = result.merge(dataframe, how="cross")
        return result


class ParameterControls(ProcessingTool):
    """Typed parameter fixture for browser coverage of the real node controls."""

    display_name = "Parameter Controls"
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(name="bioimageflow-e2e", dependencies={})

    class Inputs(IOModel):
        mode: Annotated[
            Literal["fast", "precise"],
            GUIMeta(connectable=Connectable.NEVER),
        ] = "fast"
        enabled: Annotated[
            bool,
            GUIMeta(connectable=Connectable.NEVER),
        ] = True
        labels: Annotated[
            list[str],
            GUIMeta(connectable=Connectable.NEVER),
        ] = ["alpha", "beta"]
        connected_number: Annotated[
            int,
            GUIMeta(connectable=Connectable.BY_DEFAULT),
        ] = 3

    class Outputs(IOModel):
        configured_number: int

    def process_row(self, arguments, *, context=None):
        return self.Outputs(configured_number=arguments.connected_number)


class ExecutionFailureEvent(BaseModel):
    """Contextual worker failure emitted by the Playwright WebSocket fixture."""

    execution_id: str
    workflow_id: str
    draft_revision: int
    node_id: str
    error: str
    traceback: str


class _OfflinePyPIVersionService(PyPIVersionService):
    """Keep managed browser tests independent of the package index."""

    def __init__(self) -> None:
        pass

    async def get_versions(self, package_name: str) -> list[str]:
        return []


def create_app() -> FastAPI:
    """Return the real platform app with E2E-safe storage roots."""
    deployment_mode = os.environ.get("BIOIMAGEFLOW_E2E_DEPLOYMENT_MODE", "desktop")
    if deployment_mode not in {"desktop", "webapp"}:
        raise ValueError("BIOIMAGEFLOW_E2E_DEPLOYMENT_MODE must be desktop or webapp")
    root = Path(
        os.environ.get(
            "BIOIMAGEFLOW_E2E_ROOT",
            str(Path(tempfile.gettempdir()) / f"bioimageflow-platform-e2e-{os.getpid()}"),
        )
    )
    root.mkdir(parents=True, exist_ok=True)
    # The general Playwright suite assumes an existing empty workflow library.
    # First-install demo seeding has dedicated service and startup coverage.
    (root / "workflows").mkdir(parents=True, exist_ok=True)
    tool_store = root / "tool_packages"
    os.environ["BIOIMAGEFLOW_HOME"] = str(root)
    os.environ["BIOIMAGEFLOW_TOOL_STORE"] = str(tool_store)
    os.environ["BIOIMAGEFLOW_WETLANDS"] = str(root / "wetlands")
    pixi, failure_marker = pixi_forwarder(root)
    configure_wetlands(root=root / "wetlands", pixi_executable=pixi)
    # Freeze the public manager configuration before the platform configures
    # its default root. Construction does not prepare Pixi or any environment.
    get_shared_environment_manager()

    hot_reload_fixture = os.environ.get("BIOIMAGEFLOW_HOT_RELOAD_FIXTURE")
    if hot_reload_fixture:
        _write_hot_reload_fixture(Path(hot_reload_fixture))

    registry = ToolRegistryService()
    # An injected registry is not scanned by create_platform_app(). Populate
    # the generated tool-store fixture explicitly so browser tests exercise
    # Files-node creation and hot reload against the real package loader.
    registry.scan_tool_store(tool_store)
    for tool_class in (
        Generate, CrossJoin, ParameterControls, CollectiveNumbers, HeldWorkerNumbers,
        StaleWorkerNumbers, IncompatibleWorkerNumbers,
    ):
        registry._register_tool_from_class(
            tool_class, tool_class.__name__, "bioimageflow-e2e-dynamic", "1.0.0",
        )
    from platform_lifecycle_test_tools import LifecycleOther, LifecycleSelected, LifecycleSibling

    for tool_class in (LifecycleSelected, LifecycleSibling, LifecycleOther):
        registry._register_tool_from_class(tool_class, tool_class.__name__, "lifecycle-proof", "1.0.0")
    app = create_platform_app(
        AppConfig(
            deployment_mode=deployment_mode,
            tool_registry=registry,
            settings_store=SettingsStore(
                path=root / "settings.json",
                deployment_mode=deployment_mode,
                omero_credentials=E2eOmeroCredentials(),
            ),
            workspace_path=root / "workspace",
            workspaces_root=root / "webapp-users" if deployment_mode == "webapp" else None,
            pypi_versions=_OfflinePyPIVersionService(),
            storage_path=root / "storage",
            workflow_root=root / "workflows",
            datasets_root=root / "datasets",
            disable_hot_reload=not hot_reload_fixture,
            enable_dev_router=True,
        )
    )

    @app.post("/api/v1/dev/e2e/execution-failure")
    async def broadcast_execution_failure(event: ExecutionFailureEvent) -> dict[str, str]:
        """Broadcast a worker log and completion through the real WS manager."""
        manager = app.state.connection_manager
        context = ExecutionContext(
            execution_id=event.execution_id,
            workflow_id=event.workflow_id,
            draft_revision=event.draft_revision,
        )
        await manager.broadcast_log(
            "ERROR",
            f"{event.error}\n{event.traceback}",
            event.node_id,
            time.time(),
            context=context,
        )
        await manager.broadcast_execution_complete(
            False,
            [],
            {
                event.node_id: {
                    "node_id": event.node_id,
                    "status": "failed",
                    "cached": False,
                    "error": event.error,
                    "traceback": event.traceback,
                }
            },
            context=context,
        )
        return {"execution_id": event.execution_id}

    @app.get("/api/v1/dev/e2e/process-id")
    async def backend_process_id() -> dict[str, int]:
        """Expose the orchestrator PID for real-worker isolation assertions."""
        return {"process_id": os.getpid()}

    observed: ObservedProcessingManager | None = None

    def worker_manager() -> ObservedProcessingManager:
        nonlocal observed
        if observed is None:
            service = app.dependency_overrides[get_tool_environment_service]()
            observed = ObservedProcessingManager(service.manager)
            service._wetlands = observed
        return observed

    @app.post("/api/v1/dev/e2e/stale-worker-environment")
    def stale_worker_environment() -> dict[str, Any]:
        """Create a real older managed generation, then pause its next preparation."""
        return worker_manager().seed_stale()

    @app.get("/api/v1/dev/e2e/worker-environment")
    def worker_environment() -> dict[str, Any]:
        return {**worker_manager().evidence(), "runtime_root": str(root)}

    @app.post("/api/v1/dev/e2e/release-worker-environment")
    def release_worker_environment() -> dict[str, bool]:
        worker_manager().release.set()
        return {"released": True}

    @app.post("/api/v1/dev/e2e/fail-next-worker-install")
    def fail_next_worker_install() -> dict[str, str]:
        """Inject one actual Pixi command failure; the next attempt uses real Pixi."""
        failure_marker.write_text("E1 injected install fault", encoding="utf-8")
        return {"fault": "E1 injected Pixi install failure (exit 77)"}

    _install_lifecycle_fixture(app, root)
    return app


def _write_hot_reload_fixture(fixture_path: Path) -> None:
    """Create a tiny mutable tool-store package for Playwright hot-reload."""
    package_dir = fixture_path.parent
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").write_text(
        "from .files import Files\n",
        encoding="utf-8",
    )
    fixture_path.write_text(
        "from bioimageflow import DataFrameTool\n"
        "from bioimageflow_core import IOModel\n\n"
        "class _Inputs(IOModel):\n"
        "    path: str = ''\n\n"
        "class _Outputs(IOModel):\n"
        "    path: str\n\n"
        "class Files(DataFrameTool):\n"
        "    accepts_upstream = False\n"
        "    Inputs = _Inputs\n"
        "    Outputs = _Outputs\n",
        encoding="utf-8",
    )
    write_package_metadata(package_dir, package_dir.parent.name)


def _install_lifecycle_fixture(app: FastAPI, root: Path) -> None:
    """Observe explicit lifecycle tests without provisioning at server startup."""
    import hashlib
    import importlib.metadata
    import threading

    from platform_lifecycle_test_tools import LifecycleOther, LifecycleSelected

    service = app.dependency_overrides[get_tool_environment_service]()
    delegate = service.manager
    public = get_shared_environment_manager()
    gate = threading.Event()
    gate.set()
    calls: list[str] = []
    retired: list[int] = []
    external = public.environments_root / "t1-external" / "pixi.toml"

    class ObservedManualManager:
        def __getattr__(self, name: str) -> Any:
            return getattr(delegate, name)

        def recreate(self, spec: Any, **kwargs: Any) -> Any:
            calls.append(spec.name)
            if not gate.wait(60):
                raise TimeoutError("The force-click observer was not released")
            return delegate.recreate(spec, **kwargs)

    service._wetlands = ObservedManualManager()

    def evidence() -> dict[str, Any]:
        inventory = [{
            "name": item.name, "generation_id": item.generation_id,
            "recipe_hash": item.recipe_hash, "state": item.state.value,
            "path": str(item.path),
            "worker_pids": [worker.process_id for worker in public.running_workers(item.name)],
        } for item in public.managed_environments()]
        alive = []
        for pid in retired:
            try:
                os.kill(pid, 0)
                alive.append(pid)
            except ProcessLookupError:
                pass
        return {
            "inventory": inventory, "recreate_calls": list(calls),
            "retired_worker_pids": retired, "retired_workers_alive": alive,
            "unmanaged_sha256": hashlib.sha256(external.read_bytes()).hexdigest() if external.exists() else None,
        }

    @app.post("/api/v1/dev/e2e/tool-lifecycle/prepare")
    async def prepare() -> dict[str, Any]:
        # Only the real-environment proof requires published SDK distributions.
        # Declaring the tools and routes must also work for ordinary GUI tests.
        assert not os.environ.get("BIOIMAGEFLOW_CORE_SOURCE")
        assert os.environ.get("BIOIMAGEFLOW_USE_LOCAL_CORE", "").lower() not in {"1", "true", "yes"}
        for name in ("bioimageflow", "bioimageflow-core", "wetlands"):
            assert importlib.metadata.distribution(name).read_text("direct_url.json") is None
        external.parent.mkdir(parents=True, exist_ok=True)
        external.write_bytes(b"T1 independently owned unmanaged browser fixture\n")
        await service.start(LifecycleOther.environment.name)
        await service.start(LifecycleSelected.environment.name)
        return evidence()

    @app.post("/api/v1/dev/e2e/tool-lifecycle/arm")
    def arm() -> dict[str, Any]:
        retired[:] = [worker.process_id for worker in public.running_workers(LifecycleSelected.environment.name)]
        assert len(retired) == 1
        calls.clear()
        gate.clear()
        return evidence()

    @app.get("/api/v1/dev/e2e/tool-lifecycle/evidence")
    def inspect() -> dict[str, Any]:
        return evidence()

    @app.get("/api/v1/dev/e2e/tool-lifecycle/release")
    async def release() -> dict[str, bool]:
        gate.set()
        return {"released": True}

    @app.post("/api/v1/dev/e2e/tool-lifecycle/close")
    async def close() -> dict[str, Any]:
        gate.set()
        # This fixture owns only these pools; other browser journeys can retain
        # distinct processing managers and shared-array owners in this server.
        owned = {LifecycleSelected.environment.name, LifecycleOther.environment.name}
        for name in owned:
            await service.stop(name)
        value = evidence()
        assert all(not item["worker_pids"] for item in value["inventory"] if item["name"] in owned)
        return value
