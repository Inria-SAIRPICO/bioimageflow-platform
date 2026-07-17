"""Real workflow execution tests for backend services and API routes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pandas as pd
import pytest
from bioimageflow import DataFrameTool
from bioimageflow.cache import cache_load
from bioimageflow_core.tool import IOModel
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.execution import ExecutionContext
from bioimageflow_server.models.graph import GraphState, NodeState, PositionalEdge
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.execution import ExecutionManager
from bioimageflow_server.services.graph_validator import validate_graph
from bioimageflow_server.services.tool_registry import ToolRegistryService

pytestmark = pytest.mark.anyio


class _NoInputs(IOModel):
    pass


class _SourceInputs(IOModel):
    start: int = 1
    count: int = 3


class _OffsetInputs(IOModel):
    offset: int = 10


class _FailureInputs(IOModel):
    message: str = "deterministic failure"


class _NumberOutputs(IOModel):
    value: int


class _ShiftedOutputs(IOModel):
    value: int
    shifted: int


class SourceNumbers(DataFrameTool):
    """Deterministic source DataFrameTool that needs no external services."""

    accepts_upstream = False
    Inputs = _SourceInputs
    Outputs = _NumberOutputs

    def transform(self, df: Any, arguments: Any) -> pd.DataFrame:
        values = list(range(arguments.start, arguments.start + arguments.count))
        return pd.DataFrame(
            {"value": values},
            index=[f"row{i}" for i in range(arguments.count)],
        )


class AddOffset(DataFrameTool):
    """Deterministic transform DataFrameTool using one positional upstream."""

    Inputs = _OffsetInputs
    Outputs = _ShiftedOutputs

    def transform(self, df: pd.DataFrame, arguments: Any) -> pd.DataFrame:
        out = df[["value"]].copy()
        out["shifted"] = out["value"] + arguments.offset
        return out


class EmptySource(DataFrameTool):
    accepts_upstream = False
    Inputs = _NoInputs
    Outputs = _NumberOutputs

    def transform(self, df: Any, arguments: Any) -> pd.DataFrame:
        return pd.DataFrame({"value": [1]}, index=["row0"])


class ExplodingNumbers(DataFrameTool):
    accepts_upstream = False
    Inputs = _FailureInputs
    Outputs = _NumberOutputs

    def transform(self, df: Any, arguments: Any) -> pd.DataFrame:
        raise RuntimeError(arguments.message)


class RecordingEventBus:
    def __init__(self) -> None:
        self.progress_events: list[tuple[str, str, int, int, float]] = []
        self.node_state_events: list[tuple[str, str, bool, str | None, str | None]] = []
        self.complete_events: list[tuple[bool, list, dict]] = []
        self.progress_contexts: list[ExecutionContext] = []
        self.node_state_contexts: list[ExecutionContext] = []
        self.complete_contexts: list[ExecutionContext] = []
        self.log_events: list[tuple[str, str, str | None, float]] = []
        self.environment_events: list[tuple[str, str]] = []

    def publish_progress(
        self,
        node_id: str,
        status: str,
        row: int,
        total_rows: int,
        timestamp: float,
        result_key: str | None = None,
        record_id: str | None = None,
        *,
        context: ExecutionContext,
    ) -> None:
        self.progress_events.append((node_id, status, row, total_rows, timestamp))
        self.progress_contexts.append(context)

    def publish_node_state(
        self,
        node_id: str,
        status: str,
        cached: bool,
        error: str | None = None,
        traceback: str | None = None,
        result_key: str | None = None,
        record_id: str | None = None,
        *,
        context: ExecutionContext,
    ) -> None:
        self.node_state_events.append((node_id, status, cached, error, traceback))
        self.node_state_contexts.append(context)

    def publish_execution_complete(
        self,
        success: bool,
        errors: list,
        node_statuses: dict,
        *,
        context: ExecutionContext,
    ) -> None:
        self.complete_events.append((success, errors, node_statuses))
        self.complete_contexts.append(context)

    def publish_log(
        self,
        level: str,
        message: str,
        node_id: str | None,
        timestamp: float,
        *,
        context: ExecutionContext | None = None,
    ) -> None:
        self.log_events.append((level, message, node_id, timestamp))

    def publish_environment_status(self, env_name: str, status: str) -> None:
        self.environment_events.append((env_name, status))


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _clear_active_workflow() -> AsyncIterator[None]:
    from bioimageflow.node import set_active_workflow

    set_active_workflow(None)
    yield
    set_active_workflow(None)


def _settings() -> Settings:
    return Settings(
        deployment_mode="desktop",
        dev_mode=False,
    )


def _registry() -> ToolRegistryService:
    registry = ToolRegistryService()
    for cls in (SourceNumbers, AddOffset, EmptySource, ExplodingNumbers):
        registry._register_tool_from_class(cls, cls.__name__, "test-tools", "1.0.0")
    return registry


def _real_graph() -> GraphState:
    return GraphState(
        nodes=[
            NodeState(
                id="source",
                name="source",
                tool_name="SourceNumbers",
                position=(0, 0),
                parameters={"start": 2, "count": 3},
            ),
            NodeState(
                id="offset",
                name="offset",
                tool_name="AddOffset",
                position=(200, 0),
                parameters={"offset": 5},
            ),
        ],
        edges=[
            PositionalEdge(
                id="source_to_offset",
                source_node="source",
                target_node="offset",
                positional_index=0,
            ),
        ],
    )


def _failure_graph(message: str = "deterministic failure from test") -> GraphState:
    return GraphState(
        nodes=[
            NodeState(
                id="boom",
                name="boom",
                tool_name="ExplodingNumbers",
                position=(0, 0),
                parameters={"message": message},
            ),
        ],
        edges=[],
    )


async def _drain_manager(manager: ExecutionManager, timeout: float = 5.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while manager.state != "idle" and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.01)
    if manager.state != "idle":
        pytest.fail("ExecutionManager did not become idle")
    for _ in range(3):
        await asyncio.sleep(0)


async def _poll_idle(client: httpx.AsyncClient, timeout: float = 5.0) -> dict[str, Any]:
    deadline = asyncio.get_event_loop().time() + timeout
    last_status: dict[str, Any] | None = None
    while asyncio.get_event_loop().time() < deadline:
        response = await client.get("/api/v1/execution/status")
        assert response.status_code == 200, response.text
        last_status = response.json()
        if last_status["state"] == "idle" and last_status["last_result"] is not None:
            return last_status
        await asyncio.sleep(0.01)
    pytest.fail(f"Execution did not finish in time; last status={last_status}")


def _cached_dataframe(storage_path: Path, node_id: str) -> pd.DataFrame:
    latest_link = storage_path / "views" / "latest" / f"{node_id}.bioimageflow-link.json"
    assert latest_link.exists(), f"no latest cache link for {node_id}"
    latest_payload = json.loads(latest_link.read_text())
    run_node_dir = (latest_link.parent / latest_payload["target"]).resolve()
    record_link = run_node_dir / "record.bioimageflow-link.json"
    assert record_link.exists(), f"no record link for {node_id}"
    record_payload = json.loads(record_link.read_text())
    record_dir = (record_link.parent / record_payload["target"]).resolve()
    cache_path = record_dir / "dataframe.parquet"
    assert cache_path.exists()
    return cache_load(cache_path)


def _assert_shifted_cache(storage_path: Path) -> None:
    source_df = _cached_dataframe(storage_path, "source")
    offset_df = _cached_dataframe(storage_path, "offset")

    assert source_df["value"].tolist() == [2, 3, 4]
    assert list(source_df.index) == ["row0", "row1", "row2"]
    assert offset_df[["value", "shifted"]].to_dict(orient="list") == {
        "value": [2, 3, 4],
        "shifted": [7, 8, 9],
    }


async def test_execution_manager_runs_real_dataframe_workflow_and_updates_cache(
    tmp_path: Path,
) -> None:
    graph = _real_graph()
    registry = _registry()
    bus = RecordingEventBus()
    manager = ExecutionManager(
        bus,
        registry,
        _settings(),
        storage_path=tmp_path,
    )

    context = await manager.start(
        graph,
        workflow_id="integration-workflow",
        draft_revision=3,
    )
    await _drain_manager(manager)

    assert manager.last_result is not None
    assert manager.last_result.success is True
    assert manager.last_result.errors == []
    assert manager.last_result.node_statuses["source"].status == "executed"
    assert manager.last_result.node_statuses["source"].cached is False
    assert manager.last_result.node_statuses["offset"].status == "executed"
    assert manager.last_result.node_statuses["offset"].cached is False
    assert bus.complete_events[-1][0] is True
    assert ("source", "executed", False, None, None) in bus.node_state_events
    assert ("offset", "executed", False, None, None) in bus.node_state_events
    assert bus.node_state_contexts
    assert all(event_context == context for event_context in bus.node_state_contexts)
    assert all(event_context == context for event_context in bus.progress_contexts)
    assert bus.complete_contexts == [context]
    assert any("Workflow execution completed successfully" in event[1] for event in bus.log_events)

    _assert_shifted_cache(tmp_path)

    validation = validate_graph(
        graph,
        registry,
        storage_path=tmp_path,
        dev_mode=False,
        settings=_settings(),
    )
    assert validation.valid is True
    assert validation.errors == []
    assert validation.node_statuses["source"].status == "executed"
    assert validation.node_statuses["source"].cached is True
    assert validation.node_statuses["offset"].status == "executed"
    assert validation.node_statuses["offset"].cached is True


async def test_execution_manager_run_uses_request_graph_when_session_is_stale(
    tmp_path: Path,
) -> None:
    registry = _registry()
    bus = RecordingEventBus()
    manager = ExecutionManager(
        bus,
        registry,
        _settings(),
        storage_path=tmp_path,
    )
    original = _real_graph()
    modified = GraphState(
        nodes=[
            NodeState(
                id="source",
                name="source",
                tool_name="SourceNumbers",
                position=(0, 0),
                parameters={"start": 10, "count": 3},
            ),
            NodeState(
                id="offset",
                name="offset",
                tool_name="AddOffset",
                position=(200, 0),
                parameters={"offset": 5},
            ),
        ],
        edges=original.edges,
    )

    validation = validate_graph(
        original,
        registry,
        storage_path=tmp_path,
        dev_mode=False,
        settings=_settings(),
    )
    assert validation.valid is True

    await manager.start(original, workflow_id="integration-workflow")
    await _drain_manager(manager)
    assert manager.last_result is not None
    assert manager.last_result.node_statuses["source"].cached is False
    assert _cached_dataframe(tmp_path, "source")["value"].tolist() == [2, 3, 4]

    await manager.start(modified, workflow_id="integration-workflow")
    await _drain_manager(manager)

    assert manager.last_result is not None
    assert manager.last_result.success is True
    assert manager.last_result.node_statuses["source"].cached is False
    assert manager.last_result.node_statuses["offset"].cached is False
    assert _cached_dataframe(tmp_path, "source")["value"].tolist() == [10, 11, 12]
    assert _cached_dataframe(tmp_path, "offset")[["value", "shifted"]].to_dict(orient="list") == {
        "value": [10, 11, 12],
        "shifted": [15, 16, 17],
    }


async def test_api_runs_real_dataframe_workflow_and_reuses_cache(tmp_path: Path) -> None:
    registry = _registry()
    graph = _real_graph()
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path
    app = create_app(
        AppConfig(
            storage_path=tmp_path,
            tool_registry=registry,
            settings=_settings(),
            disable_hot_reload=True,
            workflow_store=workflow_store,
        )
    )
    client = httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    )

    async with client:
        validation_response = await client.put(
            "/api/v1/graph",
            json=graph.model_dump(mode="json"),
        )
        assert validation_response.status_code == 200, validation_response.text
        validation = validation_response.json()
        assert validation["valid"] is True
        assert validation["node_statuses"]["source"]["status"] == "unexecuted"
        assert validation["node_statuses"]["offset"]["status"] == "unexecuted"

        run_response = await client.post(
            "/api/v1/execution/run",
            json={
                "graph": graph.model_dump(mode="json"),
                "workflow_name": "test-workflow",
            },
        )
        assert run_response.status_code == 202, run_response.text

        status = await _poll_idle(client)
        assert status["last_result"]["success"] is True
        assert status["last_result"]["errors"] == []
        assert status["last_result"]["node_statuses"]["source"]["status"] == "executed"
        assert status["last_result"]["node_statuses"]["source"]["cached"] is False
        assert status["last_result"]["node_statuses"]["offset"]["status"] == "executed"
        assert status["last_result"]["node_statuses"]["offset"]["cached"] is False

        _assert_shifted_cache(tmp_path)

        cached_response = await client.post(
            "/api/v1/execution/run",
            json={
                "graph": graph.model_dump(mode="json"),
                "workflow_name": "test-workflow",
            },
        )
        assert cached_response.status_code == 202, cached_response.text

        cached_status = await _poll_idle(client)
        assert cached_status["last_result"]["success"] is True
        assert cached_status["last_result"]["node_statuses"]["source"]["status"] == "executed"
        assert cached_status["last_result"]["node_statuses"]["source"]["cached"] is True
        assert cached_status["last_result"]["node_statuses"]["offset"]["status"] == "executed"
        assert cached_status["last_result"]["node_statuses"]["offset"]["cached"] is True


async def test_api_real_dataframe_tool_failure_propagates_node_error(
    tmp_path: Path,
) -> None:
    registry = _registry()
    graph = _failure_graph()
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path
    app = create_app(
        AppConfig(
            storage_path=tmp_path,
            tool_registry=registry,
            settings=_settings(),
            disable_hot_reload=True,
            workflow_store=workflow_store,
        )
    )
    client = httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    )

    async with client:
        run_response = await client.post(
            "/api/v1/execution/run",
            json={
                "graph": graph.model_dump(mode="json"),
                "workflow_name": "test-workflow",
            },
        )
        assert run_response.status_code == 202, run_response.text

        status = await _poll_idle(client)
        result = status["last_result"]
        assert result["success"] is False
        assert result["errors"]
        assert "deterministic failure from test" in str(result["errors"])
        node_status = result["node_statuses"]["boom"]
        assert node_status["status"] == "failed"
        assert node_status["cached"] is False
        assert "deterministic failure from test" in node_status["error"]
        assert "transform" in node_status["traceback"]
