"""Playwright app factory with isolated persistent services."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from bioimageflow import DataFrameTool
from bioimageflow_core import Connectable, GUIMeta, IOModel
from fastapi import FastAPI
from pydantic import BaseModel

from bioimageflow_server.app import create_app as create_platform_app
from bioimageflow_server.models.execution import ExecutionContext
from bioimageflow_server.models.tools import AppConfig, InputFieldSchema, ToolMetadata
from bioimageflow_server.services.pypi_versions import PyPIVersionService
from bioimageflow_server.services.settings_store import SettingsStore
from bioimageflow_server.services.tool_registry import ToolRegistryService


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

    hot_reload_fixture = os.environ.get("BIOIMAGEFLOW_HOT_RELOAD_FIXTURE")
    if hot_reload_fixture:
        _write_hot_reload_fixture(Path(hot_reload_fixture))

    registry = ToolRegistryService()
    # An injected registry is not scanned by create_platform_app(). Populate
    # the generated tool-store fixture explicitly so browser tests exercise
    # Files-node creation and hot reload against the real package loader.
    registry.scan_tool_store(tool_store)
    registry.register_tool(
        "Generate",
        ToolMetadata(
            name="Generate",
            display_name="Generate",
            package="bioimageflow-e2e-dynamic",
            package_version="1.0.0",
            tool_type="DataFrameTool",
            accepts_upstream=False,
            dynamic_outputs=True,
            inputs={
                "column_name": InputFieldSchema(
                    type="str", required=True, connectable="never"
                ),
                "values": InputFieldSchema(
                    type="list", required=True, connectable="never"
                ),
            },
        ),
        tool_class=Generate,
    )
    registry.register_tool(
        "CrossJoin",
        ToolMetadata(
            name="CrossJoin",
            display_name="Cross Join",
            package="bioimageflow-e2e-dynamic",
            package_version="1.0.0",
            tool_type="DataFrameTool",
            accepts_upstream=True,
            dynamic_outputs=True,
        ),
        tool_class=CrossJoin,
    )
    app = create_platform_app(
        AppConfig(
            tool_registry=registry,
            settings_store=SettingsStore(path=root / "settings.json"),
            workspace_path=root / "workspace",
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
