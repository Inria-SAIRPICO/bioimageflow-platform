"""Real workflow execution tests for backend services and API routes."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pandas as pd
import pytest
from tests.graph_factory import graph_state
from tests.platform_fixtures import dataframe_chain, local_registry
from bioimageflow.cache import cache_load
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.execution import ExecutionContext
from bioimageflow_server.models.graph import ColumnEdge, GraphState, ToolNodeState
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.models.workflow import WorkflowCreate
from bioimageflow_server.services.execution import (
    ExecutionManager,
    WorkflowBuildError,
    clear_node_cache,
)
from bioimageflow_server.services.graph_compiler import GraphCompiler
from bioimageflow_server.services.graph_validator import validate_graph
from bioimageflow_server.services.workflow_draft import WorkflowDraftService
from bioimageflow_server.services.workflow_store import WorkflowStoreService

pytestmark = pytest.mark.anyio


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


def _failure_graph(message: str = "deterministic failure from test") -> GraphState:
    return graph_state(
        config={"engine": "wetlands", "execution": "sequential"},
        nodes=[
            ToolNodeState(type="tool",
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
    graph = dataframe_chain()
    registry = local_registry()
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


async def test_draft_status_after_clear_survives_backend_restart(tmp_path: Path) -> None:
    registry = local_registry()
    root = tmp_path / "workspace" / "workflows"
    store = WorkflowStoreService(root_dir=root, tool_registry=registry)
    store.create_workflow(WorkflowCreate(name="wf"))
    drafts = WorkflowDraftService(
        lambda: store, dev_mode_provider=lambda: False, settings_provider=_settings
    )
    graph = dataframe_chain()
    accepted = drafts.put_draft("wf", graph=graph, expected_revision=0)
    storage = store.get_storage_path("wf")
    manager = ExecutionManager(RecordingEventBus(), registry, _settings(), storage_path=storage)
    await manager.start(graph, workflow_id="wf", draft_revision=accepted.draft_revision)
    await _drain_manager(manager)
    assert manager.last_result is not None and manager.last_result.success

    # A harmless accepted canvas edit stores post-run executed validation.
    edited = graph.model_copy(deep=True)
    edited.nodes[0].position = (20, 10)
    accepted = drafts.put_draft("wf", graph=edited, expected_revision=accepted.draft_revision)
    assert accepted.validation.node_statuses["source"].status == "executed"
    assert accepted.validation.node_statuses["offset"].status == "executed"
    before = accepted.model_dump(mode="json")

    cleared = clear_node_cache(
        ["source"], edited, registry, storage, dev_mode=False, settings=_settings()
    )
    assert cleared["source"].status == "unexecuted"
    assert cleared["offset"].status == "out_of_date"

    # New backend services have no live execution status, only the same workspace.
    restarted_registry = local_registry()
    restarted_store = WorkflowStoreService(root_dir=root, tool_registry=restarted_registry)
    restarted_drafts = WorkflowDraftService(
        lambda: restarted_store, dev_mode_provider=lambda: False, settings_provider=_settings
    )
    restarted = restarted_drafts.get_draft("wf")
    assert restarted.validation.node_statuses["source"].status == "unexecuted"
    assert restarted.validation.node_statuses["offset"].status == "out_of_date"
    assert restarted.model_dump(mode="json", exclude={"validation"}) == {
        key: value for key, value in before.items() if key != "validation"
    }
    assert restarted_drafts.get_draft_authority("wf").draft.model_dump(mode="json") == before

    # A new backend's HTTP GET projects the same accepted authority.
    app = create_app(
        AppConfig(
            tool_registry=restarted_registry,
            workflow_store=restarted_store,
            settings=_settings(),
            disable_hot_reload=True,
        )
    )
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/workflow-drafts/wf")
    assert response.status_code == 200, response.text
    assert response.json()["validation"]["node_statuses"]["source"]["status"] == "unexecuted"
    assert response.json()["validation"]["node_statuses"]["offset"]["status"] == "out_of_date"

    # Reopen the same workspace in a separate OS process and query its new app.
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import asyncio
import json
import sys
import httpx
from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.workflow_store import WorkflowStoreService
from tests.platform_fixtures import local_registry

async def main():
    registry = local_registry()
    store = WorkflowStoreService(root_dir=sys.argv[1], tool_registry=registry)
    app = create_app(AppConfig(tool_registry=registry, workflow_store=store, disable_hot_reload=True))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/workflow-drafts/wf")
    print(json.dumps({"http": response.status_code, "body": response.json()}))

asyncio.run(main())
""",
            str(root),
        ],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
        check=True,
    )
    process_response = json.loads(child.stdout.splitlines()[-1])
    assert process_response["http"] == 200
    process_statuses = process_response["body"]["validation"]["node_statuses"]
    assert process_statuses["source"]["status"] == "unexecuted"
    assert process_statuses["offset"]["status"] == "out_of_date"

    # Once no downstream latest output remains, pending_upstream means unexecuted.
    clear_node_cache(
        ["offset"], edited, restarted_registry, storage, dev_mode=False, settings=_settings()
    )
    without_output = restarted_drafts.get_draft("wf")
    assert without_output.validation.node_statuses["offset"].status == "unexecuted"

    # Rerunning the unchanged accepted graph restores current cache status.
    new_manager = ExecutionManager(
        RecordingEventBus(), restarted_registry, _settings(), storage_path=storage
    )
    await new_manager.start(edited, workflow_id="wf", draft_revision=accepted.draft_revision)
    await _drain_manager(new_manager)
    assert new_manager.last_result is not None and new_manager.last_result.success
    rerun = restarted_drafts.get_draft("wf")
    assert rerun.validation.node_statuses["source"].status == "executed"
    assert rerun.validation.node_statuses["offset"].status == "executed"


async def test_draft_status_before_any_run_has_no_false_downstream_staleness(
    tmp_path: Path,
) -> None:
    registry = local_registry()
    store = WorkflowStoreService(root_dir=tmp_path / "workflows", tool_registry=registry)
    store.create_workflow(WorkflowCreate(name="wf"))
    drafts = WorkflowDraftService(
        lambda: store, dev_mode_provider=lambda: False, settings_provider=_settings
    )
    graph = dataframe_chain()
    accepted = drafts.put_draft("wf", graph=graph, expected_revision=0)
    assert accepted.validation.node_statuses["offset"].status == "unexecuted"

    clear_node_cache(
        ["source"],
        graph,
        registry,
        store.get_storage_path("wf"),
        dev_mode=False,
        settings=_settings(),
    )
    restarted = WorkflowDraftService(
        lambda: WorkflowStoreService(
            root_dir=tmp_path / "workflows", tool_registry=local_registry()
        ),
        dev_mode_provider=lambda: False,
        settings_provider=_settings,
    ).get_draft("wf")
    assert restarted.validation.node_statuses["source"].status == "unexecuted"
    assert restarted.validation.node_statuses["offset"].status == "unexecuted"


async def test_draft_get_retries_when_accepted_revision_changes_during_compile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = local_registry()
    store = WorkflowStoreService(root_dir=tmp_path / "workflows", tool_registry=registry)
    store.create_workflow(WorkflowCreate(name="wf"))
    drafts = WorkflowDraftService(
        lambda: store, dev_mode_provider=lambda: False, settings_provider=_settings
    )
    graph = dataframe_chain()
    first = drafts.put_draft("wf", graph=graph, expected_revision=0)
    changed = graph.model_copy(deep=True)
    changed.nodes[0].position = (40, 20)
    compile_original = GraphCompiler.compile
    injected = False

    def compile_with_intervening_write(self: GraphCompiler, *args: Any, **kwargs: Any) -> Any:
        nonlocal injected
        if not injected:
            injected = True
            drafts.put_draft("wf", graph=changed, expected_revision=first.draft_revision)
        return compile_original(self, *args, **kwargs)

    monkeypatch.setattr(GraphCompiler, "compile", compile_with_intervening_write)
    response = drafts.get_draft("wf")
    assert injected
    assert response.draft_revision == first.draft_revision + 1
    assert response.graph == changed


async def test_draft_get_retries_same_id_recreation_during_compile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = local_registry()
    store = WorkflowStoreService(root_dir=tmp_path / "workflows", tool_registry=registry)
    store.create_workflow(WorkflowCreate(name="wf"))
    drafts = WorkflowDraftService(lambda: store, dev_mode_provider=lambda: False)
    drafts.put_draft("wf", graph=dataframe_chain(), expected_revision=0)
    original_generation = store.workflow_generation("wf")
    compile_original = GraphCompiler.compile
    replaced = False

    def compile_with_replacement(self: GraphCompiler, *args: Any, **kwargs: Any) -> Any:
        nonlocal replaced
        result = compile_original(self, *args, **kwargs)
        if not replaced:
            replaced = True
            store.delete_workflow("wf")
            store.create_workflow(WorkflowCreate(name="wf"))
        return result

    monkeypatch.setattr(GraphCompiler, "compile", compile_with_replacement)
    response = drafts.get_draft("wf")
    assert replaced
    assert response.draft_revision == 0
    assert response.graph.nodes == []
    assert store.workflow_generation("wf") != original_generation


async def test_draft_get_preserves_disabled_status(tmp_path: Path) -> None:
    registry = local_registry()
    store = WorkflowStoreService(root_dir=tmp_path / "workflows", tool_registry=registry)
    store.create_workflow(WorkflowCreate(name="wf"))
    drafts = WorkflowDraftService(lambda: store, dev_mode_provider=lambda: False)
    graph = dataframe_chain()
    graph.nodes[1].enabled = False
    accepted = drafts.put_draft("wf", graph=graph, expected_revision=0)
    assert accepted.validation.node_statuses["offset"].status == "disabled"

    projected = drafts.get_draft("wf")
    assert projected.validation.node_statuses["offset"].status == "disabled"
    assert projected.validation.node_statuses["offset"].cached is False
    assert projected.draft_revision == accepted.draft_revision


async def test_draft_get_retries_changed_storage_path_during_compile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = local_registry()
    store = WorkflowStoreService(root_dir=tmp_path / "workflows", tool_registry=registry)
    store.create_workflow(WorkflowCreate(name="wf"))
    drafts = WorkflowDraftService(lambda: store, dev_mode_provider=lambda: False)
    graph = dataframe_chain()
    accepted = drafts.put_draft("wf", graph=graph, expected_revision=0)
    old_storage = store.get_storage_path("wf")
    new_storage = tmp_path / "relocated-results"
    new_storage.mkdir()
    current_storage = old_storage
    original_get_storage_path = store.get_storage_path
    compile_original = GraphCompiler.compile
    compiled_storage_paths: list[Path] = []

    def switched_storage_path(workflow_id: str) -> Path:
        if workflow_id == "wf":
            return current_storage
        return original_get_storage_path(workflow_id)

    def compile_with_storage_switch(self: GraphCompiler, *args: Any, **kwargs: Any) -> Any:
        nonlocal current_storage
        compiled_storage_paths.append(kwargs["storage_path"])
        result = compile_original(self, *args, **kwargs)
        if len(compiled_storage_paths) == 1:
            current_storage = new_storage
        return result

    monkeypatch.setattr(store, "get_storage_path", switched_storage_path)
    monkeypatch.setattr(GraphCompiler, "compile", compile_with_storage_switch)
    projected = drafts.get_draft("wf")
    assert compiled_storage_paths == [old_storage, new_storage]
    assert projected.graph == graph
    assert projected.draft_revision == accepted.draft_revision


async def test_execution_manager_run_selected_executes_valid_branch_with_unrelated_missing_tool(
    tmp_path: Path,
) -> None:
    graph = dataframe_chain()
    graph.nodes.append(
        ToolNodeState(
            type="tool",
            id="unrelated_invalid",
            name="unrelated invalid",
            tool_name="MissingCampaignTool",
            position=(100, 200),
            parameters={},
        )
    )
    manager = ExecutionManager(
        RecordingEventBus(),
        local_registry(),
        _settings(),
        storage_path=tmp_path,
    )

    with pytest.raises(WorkflowBuildError) as full_error:
        await manager.start(graph, workflow_id="integration-workflow")
    assert full_error.value.errors
    assert {
        (error.type, error.node) for error in full_error.value.errors
    } == {("missing_tool", "unrelated_invalid")}

    await manager.start(
        graph,
        nodes=["offset"],
        workflow_id="integration-workflow",
        draft_revision=7,
    )
    await _drain_manager(manager)

    assert manager.last_result is not None
    assert manager.last_result.success is True
    assert set(manager.last_result.node_statuses) == {"source", "offset"}
    assert manager.last_result.node_statuses["source"].status == "executed"
    assert manager.last_result.node_statuses["offset"].status == "executed"
    result = _cached_dataframe(tmp_path, "offset")
    assert result["value"].tolist() == [2, 3, 4]
    assert result["shifted"].tolist() == [7, 8, 9]
    assert not (tmp_path / "views" / "latest" / "unrelated_invalid.bioimageflow-link.json").exists()


async def test_execution_manager_run_uses_request_graph_when_session_is_stale(
    tmp_path: Path,
) -> None:
    registry = local_registry()
    bus = RecordingEventBus()
    manager = ExecutionManager(
        bus,
        registry,
        _settings(),
        storage_path=tmp_path,
    )
    original = dataframe_chain()
    modified = graph_state(
        config={"engine": "wetlands", "execution": "sequential"},
        nodes=[
            ToolNodeState(type="tool",
                id="source",
                name="source",
                tool_name="SourceNumbers",
                position=(0, 0),
                parameters={"start": 10, "count": 3},
            ),
            ToolNodeState(type="tool",
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
    registry = local_registry()
    graph = dataframe_chain()
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
    registry = local_registry()
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


async def test_api_rejects_column_binding_to_dataframe_constant(tmp_path: Path) -> None:
    graph = dataframe_chain()
    # Retain the valid whole-DataFrame input, so only the column binding is invalid.
    graph.nodes[1].parameters = {}
    graph.edges.append(ColumnEdge(
        type="column", id="column_into_constant", source_node="source",
        source_output="value", target_node="offset", target_input="offset",
    ))
    app = create_app(AppConfig(
        storage_path=tmp_path,
        tool_registry=local_registry(),
        settings=_settings(),
        disable_hot_reload=True,
    ))
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        response = await client.put("/api/v1/graph", json=graph.model_dump(mode="json"))
        assert response.status_code == 200, response.text
        validation = response.json()
        assert validation["valid"] is False
        assert len(validation["errors"]) == 1
        error = validation["errors"][0]
        assert (error["type"], error["node"], error["field"], error["edge_id"]) == (
            "type_incompatible", "offset", "offset", "column_into_constant",
        )
        assert "requires a constant" in error["detail"]
