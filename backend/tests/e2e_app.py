"""Playwright app factory with isolated persistent services."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from bioimageflow_server.app import create_app as create_platform_app
from bioimageflow_server.models.execution import ExecutionContext
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.settings_store import SettingsStore


class ExecutionFailureEvent(BaseModel):
    """Contextual worker failure emitted by the Playwright WebSocket fixture."""

    execution_id: str
    workflow_id: str
    draft_revision: int
    node_id: str
    error: str
    traceback: str


def create_app() -> FastAPI:
    """Return the real platform app with E2E-safe storage roots."""
    root = Path(
        os.environ.get(
            "BIOIMAGEFLOW_E2E_ROOT",
            str(Path(tempfile.gettempdir()) / f"bioimageflow-platform-e2e-{os.getpid()}"),
        )
    )
    root.mkdir(parents=True, exist_ok=True)
    tool_store = root / "tool_packages"
    os.environ["BIOIMAGEFLOW_TOOL_STORE"] = str(tool_store)
    os.environ["BIOIMAGEFLOW_WETLANDS"] = str(root / "wetlands")

    hot_reload_fixture = os.environ.get("BIOIMAGEFLOW_HOT_RELOAD_FIXTURE")
    if hot_reload_fixture:
        _write_hot_reload_fixture(Path(hot_reload_fixture))

    app = create_platform_app(
        AppConfig(
            settings_store=SettingsStore(path=root / "settings.json"),
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
