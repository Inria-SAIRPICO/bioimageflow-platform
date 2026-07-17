"""Tests for live workflow draft endpoints."""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import tomllib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowUpdate
from bioimageflow_server.models.validation import ValidationResult
from bioimageflow_server.routers.execution import (
    get_workflow_draft_service as execution_get_workflow_draft_service,
)
from bioimageflow_server.routers.workflow_drafts import (
    get_workflow_draft_service as drafts_get_workflow_draft_service,
)
from bioimageflow_server.services.execution import ExecutionManager, NullEventBus
from bioimageflow_server.models.workflow_draft import WorkflowDraftResponse
from bioimageflow_server.services import workflow_draft as workflow_draft_service
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService
from bioimageflow_server.ws.handler import ConnectionManager

pytestmark = pytest.mark.anyio


FORBIDDEN_AGENT_CONTEXT_PHRASES = [
    "Operation REST second",
    "Raw full-DAG",
    "REST fallback",
    "MCP is a protocol",
    "curl",
    "human_diagnostic_rest",
    "workflow-draft-operations",
    "workflow-drafts",
    "execution/run",
]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _ExecutionManager:
    def __init__(self, *, is_running: bool = False) -> None:
        self.is_running = is_running


async def _client(
    tmp_path: Path,
    *,
    is_running: bool = False,
    connection_manager: ConnectionManager | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    registry = ToolRegistryService()
    store = WorkflowStoreService(
        root_dir=tmp_path / "workspace" / "workflows",
        tool_registry=registry,
        storage_base_dir=tmp_path / "workspace" / "outputs",
    )
    app = create_app(
        AppConfig(
            tool_registry=registry,
            workflow_store=store,
            execution_manager=_ExecutionManager(is_running=is_running),
            connection_manager=connection_manager,
            storage_path=tmp_path / "bif_data",
            disable_hot_reload=True,
        )
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    async for ac in _client(tmp_path):
        yield ac


@pytest.fixture
async def locked_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    async for ac in _client(tmp_path, is_running=True):
        yield ac


async def _create_workflow(client: httpx.AsyncClient, name: str = "wf") -> None:
    response = await client.post(
        "/api/v1/workflows",
        json={"name": name, "display_name": name.split("/")[-1]},
    )
    assert response.status_code == 201


def _graph_state(node_id: str) -> GraphState:
    return GraphState.model_validate(_graph(node_id))


def _graph(node_id: str = "bad") -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": node_id,
                "name": "Bad",
                "tool_name": "MissingTool",
                "position": [1, 2],
                "parameters": {"value": 1},
            }
        ],
        "edges": [],
    }


async def test_get_synthesizes_draft_from_saved_workflow(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    await _create_workflow(client, "wf")

    response = await client.get("/api/v1/workflow-drafts/wf")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"] == "wf"
    assert body["draft_revision"] == 0
    assert body["dirty_against_saved"] is False
    assert body["updated_by"] == "system"
    assert body["graph"] == {
        "nodes": [],
        "edges": [],
        "published_inputs": [],
        "published_outputs": [],
    }
    assert body["base_saved_revision"].startswith("sha256:")
    assert not (
        tmp_path / "workspace" / "workflows" / "wf" / ".bioimageflow" / "draft.json"
    ).exists()

    agent_state = tmp_path / "workspace" / ".bioimageflow" / "agent-state.json"
    assert agent_state.exists()
    context = json.loads(agent_state.read_text())
    assert context["mcp_contract_version"] == 2
    assert context["active_workflow_id"] == "wf"
    assert context["api_base_url"] == "http://test/api/v1"
    assert context["health_url"] == "http://test/api/v1/health"
    assert all(command.startswith("MCP ") for command in context["recommended_commands"])
    recommended = "\n".join(context["recommended_commands"])
    assert "get_bioimageflow_capabilities" in recommended
    assert "get_workspace_context" in recommended
    assert "list_workflows" in recommended
    assert "create_workflow" in recommended
    assert "set_active_workflow" in recommended
    assert "describe_workflow" in recommended
    assert "describe_bioimageflow_tool" in recommended
    assert "apply_workflow_operations" in recommended
    assert "get_execution_status" in recommended
    assert context["mcp_server_command"] == f"{sys.executable} -m bioimageflow_server.agent_mcp"
    assert context["mcp_client_config"] == {
        "command": sys.executable,
        "args": ["-m", "bioimageflow_server.agent_mcp"],
        "cwd": str(tmp_path / "workspace"),
        "env": {
            "BIOIMAGEFLOW_AGENT_STATE": str(agent_state),
            "PYTHONPATH": str(workflow_draft_service._BACKEND_PACKAGE_PARENT),
        },
    }
    assert "agent_client_config_errors" not in context
    config_files = context["agent_client_config_files"]
    assert set(config_files) == {
        "codex",
        "claude_code",
        "opencode",
        "oh_my_pi",
        "shared_mcp_json",
    }
    assert "human_diagnostic_rest" not in context

    codex_config = tomllib.loads((tmp_path / "workspace" / ".codex" / "config.toml").read_text())
    codex_mcp = codex_config["mcp_servers"]["bioimageflow"]
    assert codex_mcp["command"] == sys.executable
    assert codex_mcp["args"] == ["-m", "bioimageflow_server.agent_mcp"]
    assert codex_mcp["cwd"] == str(tmp_path / "workspace")
    assert codex_mcp["env"]["BIOIMAGEFLOW_AGENT_STATE"] == str(agent_state)
    assert codex_mcp["env"]["PYTHONPATH"] == str(workflow_draft_service._BACKEND_PACKAGE_PARENT)

    claude_config = json.loads((tmp_path / "workspace" / ".mcp.json").read_text())
    assert claude_config["mcpServers"]["bioimageflow"] == context["mcp_client_config"]

    shared_config = json.loads(
        (tmp_path / "workspace" / ".bioimageflow" / "mcp-client-config.json").read_text()
    )
    assert shared_config["mcpServers"]["bioimageflow"] == context["mcp_client_config"]

    omp_config = json.loads((tmp_path / "workspace" / ".omp" / "mcp.json").read_text())
    assert omp_config["mcpServers"]["bioimageflow"] == {
        **context["mcp_client_config"],
        "type": "stdio",
        "enabled": True,
        "timeout": 30000,
    }

    opencode_config = json.loads((tmp_path / "workspace" / "opencode.json").read_text())
    assert opencode_config["$schema"] == "https://opencode.ai/config.json"
    assert opencode_config["mcp"]["bioimageflow"] == {
        "type": "local",
        "command": [sys.executable, "-m", "bioimageflow_server.agent_mcp"],
        "cwd": str(tmp_path / "workspace"),
        "environment": context["mcp_client_config"]["env"],
        "enabled": True,
        "timeout": 30000,
    }

    hidden_agent_doc = tmp_path / "workspace" / ".bioimageflow" / "AGENTS.md"
    assert not hidden_agent_doc.exists()

    agent_doc = tmp_path / "workspace" / "AGENTS.md"
    instructions = agent_doc.read_text()
    normalized_instructions = " ".join(instructions.split())
    assert "Use BioImageFlow MCP tools for workflow inspection" in normalized_instructions
    assert "MCP Tool Reference" in instructions
    assert "MCP client setup" in instructions
    assert "BIOIMAGEFLOW_AGENT_STATE" in instructions
    assert "get_bioimageflow_capabilities" in instructions
    assert "get_workspace_context" in instructions
    assert "list_workflows" in instructions
    assert "create_workflow" in instructions
    assert "delete_workflow" in instructions
    assert "get_workflow_draft" in instructions
    assert "describe_workflow" in instructions
    assert "describe_bioimageflow_tool" in instructions
    assert "apply_workflow_operations" in instructions
    assert "bioimageflow_server.agent_mcp" in instructions
    assert ".bioimageflow/platform-source/" in instructions
    assert "/Users/" not in instructions
    for phrase in FORBIDDEN_AGENT_CONTEXT_PHRASES:
        assert phrase not in instructions


async def test_put_writes_atomic_draft_and_conflicts_on_stale_revision(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    await _create_workflow(client, "wf")

    first = await client.put(
        "/api/v1/workflow-drafts/wf",
        json={
            "graph": _graph("n1"),
            "expected_revision": 0,
            "updated_by": "frontend",
        },
    )
    assert first.status_code == 200
    assert first.json()["draft_revision"] == 1
    assert first.json()["dirty_against_saved"] is True
    assert first.json()["validation"]["valid"] is False

    draft_path = tmp_path / "workspace" / "workflows" / "wf" / ".bioimageflow" / "draft.json"
    assert draft_path.exists()
    assert json.loads(draft_path.read_text())["graph"]["nodes"][0]["id"] == "n1"

    stale = await client.put(
        "/api/v1/workflow-drafts/wf",
        json={
            "graph": _graph("n2"),
            "expected_revision": 0,
            "updated_by": "frontend",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"] == "draft_revision_conflict"
    assert stale.json()["expected_revision"] == 0
    assert stale.json()["current_revision"] == 1


async def test_reset_to_saved_is_revision_checked_and_publishes_only_on_success(
    tmp_path: Path,
) -> None:
    manager = ConnectionManager()
    published: list[dict[str, Any]] = []

    def _publish(**payload: Any) -> None:
        published.append(payload)

    manager.publish_workflow_draft_changed = _publish  # type: ignore[method-assign]

    async for client in _client(tmp_path, connection_manager=manager):
        await _create_workflow(client, "wf")
        saved_graph = _graph("saved")
        saved = await client.put(
            "/api/v1/workflows/wf",
            json={"graph": saved_graph},
        )
        assert saved.status_code == 200

        dirty = await client.put(
            "/api/v1/workflow-drafts/wf",
            json={
                "graph": _graph("discarded"),
                "expected_revision": 0,
                "updated_by": "frontend",
            },
        )
        assert dirty.status_code == 200
        assert dirty.json()["draft_revision"] == 1
        published.clear()

        reset = await client.post(
            "/api/v1/workflow-drafts/wf/reset-to-saved",
            json={"expected_revision": 1, "updated_by": "frontend"},
        )

        assert reset.status_code == 200
        accepted = reset.json()
        assert accepted["draft_revision"] == 2
        assert accepted["dirty_against_saved"] is False
        assert accepted["graph"]["nodes"][0]["id"] == "saved"
        assert published == [
            {
                "workflow_id": "wf",
                "draft_revision": 2,
                "updated_by": "frontend",
                "updated_at": accepted["updated_at"],
                "dirty_against_saved": False,
            }
        ]

        draft_path = tmp_path / "workspace" / "workflows" / "wf" / ".bioimageflow" / "draft.json"
        accepted_bytes = draft_path.read_bytes()
        stale = await client.post(
            "/api/v1/workflow-drafts/wf/reset-to-saved",
            json={"expected_revision": 1, "updated_by": "frontend"},
        )

        assert stale.status_code == 409
        assert stale.json()["error"] == "draft_revision_conflict"
        assert stale.json()["current_revision"] == 2
        assert draft_path.read_bytes() == accepted_bytes
        assert len(published) == 1


async def test_reset_to_saved_rejects_locked_and_missing_workflows(
    tmp_path: Path,
) -> None:
    async for client in _client(tmp_path, is_running=True):
        await _create_workflow(client, "wf")

        locked = await client.post(
            "/api/v1/workflow-drafts/wf/reset-to-saved",
            json={"expected_revision": 0},
        )

        assert locked.status_code == 423
        assert locked.json()["error"] == "workflow_locked"

    async for client in _client(tmp_path):
        missing = await client.post(
            "/api/v1/workflow-drafts/missing/reset-to-saved",
            json={"expected_revision": 0},
        )

        assert missing.status_code == 404


async def test_put_publishes_one_workflow_draft_changed_event_per_success(
    tmp_path: Path,
) -> None:
    manager = ConnectionManager()
    published: list[dict[str, Any]] = []

    def _publish(**payload: Any) -> None:
        published.append(payload)

    manager.publish_workflow_draft_changed = _publish  # type: ignore[method-assign]

    async for client in _client(tmp_path, connection_manager=manager):
        await _create_workflow(client, "wf")

        get_response = await client.get("/api/v1/workflow-drafts/wf")
        assert get_response.status_code == 200
        assert published == []

        first = await client.put(
            "/api/v1/workflow-drafts/wf",
            json={
                "graph": _graph("n1"),
                "expected_revision": 0,
                "updated_by": "frontend",
            },
        )
        assert first.status_code == 200
        first_body = first.json()
        assert published == [
            {
                "workflow_id": "wf",
                "draft_revision": 1,
                "updated_by": "frontend",
                "updated_at": first_body["updated_at"],
                "dirty_against_saved": True,
            }
        ]

        second = await client.put(
            "/api/v1/workflow-drafts/wf",
            json={
                "graph": _graph("n2"),
                "expected_revision": 1,
                "updated_by": "agent",
            },
        )
        assert second.status_code == 200
        second_body = second.json()
        assert published[-1] == {
            "workflow_id": "wf",
            "draft_revision": 2,
            "updated_by": "agent",
            "updated_at": second_body["updated_at"],
            "dirty_against_saved": True,
        }
        assert len(published) == 2


async def test_put_does_not_publish_for_unsuccessful_writes(
    tmp_path: Path,
) -> None:
    manager = ConnectionManager()
    published: list[dict[str, Any]] = []

    def _publish(**payload: Any) -> None:
        published.append(payload)

    manager.publish_workflow_draft_changed = _publish  # type: ignore[method-assign]

    async for client in _client(tmp_path, connection_manager=manager):
        await _create_workflow(client, "wf")

        first = await client.put(
            "/api/v1/workflow-drafts/wf",
            json={
                "graph": _graph("n1"),
                "expected_revision": 0,
                "updated_by": "frontend",
            },
        )
        assert first.status_code == 200
        assert len(published) == 1

        stale = await client.put(
            "/api/v1/workflow-drafts/wf",
            json={
                "graph": _graph("n2"),
                "expected_revision": 0,
                "updated_by": "frontend",
            },
        )
        missing = await client.put(
            "/api/v1/workflow-drafts/missing",
            json={
                "graph": _graph("n3"),
                "expected_revision": 0,
                "updated_by": "agent",
            },
        )
        invalid = await client.put(
            "/api/v1/workflow-drafts/wf",
            json={
                "expected_revision": 1,
                "updated_by": "agent",
            },
        )

        assert stale.status_code == 409
        assert missing.status_code == 404
        assert invalid.status_code == 422
        assert len(published) == 1


async def test_put_does_not_publish_when_locked(
    tmp_path: Path,
) -> None:
    manager = ConnectionManager()
    published: list[dict[str, Any]] = []

    def _publish(**payload: Any) -> None:
        published.append(payload)

    manager.publish_workflow_draft_changed = _publish  # type: ignore[method-assign]

    async for client in _client(tmp_path, is_running=True, connection_manager=manager):
        await _create_workflow(client, "wf")

        response = await client.put(
            "/api/v1/workflow-drafts/wf",
            json={
                "graph": _graph("n1"),
                "expected_revision": 0,
                "updated_by": "frontend",
            },
        )

        assert response.status_code == 423
        assert published == []


async def test_nested_workflow_draft_route_does_not_shadow_workflow_get(
    client: httpx.AsyncClient,
) -> None:
    await _create_workflow(client, "folder/wf")

    draft = await client.get("/api/v1/workflow-drafts/folder/wf")
    workflow = await client.get("/api/v1/workflows/folder/wf")

    assert draft.status_code == 200
    assert draft.json()["workflow_id"] == "folder/wf"
    assert workflow.status_code == 200
    assert workflow.json()["info"]["id"] == "folder/wf"


async def test_get_repairs_legacy_mismatched_draft_identity_without_losing_fields(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    workflow_id = "folder/wf"
    await _create_workflow(client, workflow_id)
    draft_path = (
        tmp_path / "workspace" / "workflows" / "folder" / "wf" / ".bioimageflow" / "draft.json"
    )
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    legacy = {
        "draft_version": 1,
        "workflow_id": "legacy/location",
        "base_saved_revision": "sha256:legacy",
        "draft_revision": 11,
        "updated_at": "2026-07-16T04:45:00Z",
        "updated_by": "agent",
        "dirty_against_saved": True,
        "graph": _graph("legacy-node"),
        "validation": {
            "valid": False,
            "node_statuses": {},
            "errors": [
                {
                    "type": "missing_tool",
                    "detail": "MissingTool is unavailable",
                    "node": "legacy-node",
                }
            ],
        },
        "future_compatible": {"preserve": True},
    }
    draft_path.write_text(json.dumps(legacy, indent=2), encoding="utf-8")

    response = await client.get(f"/api/v1/workflow-drafts/{workflow_id}")

    assert response.status_code == 200
    body = response.json()
    normalized = {**legacy, "workflow_id": workflow_id}
    assert body == WorkflowDraftResponse.model_validate(normalized).model_dump(mode="json")
    repaired = json.loads(draft_path.read_text(encoding="utf-8"))
    assert repaired == normalized
    assert not list(draft_path.parent.glob(".draft.json.*.tmp"))


async def test_get_does_not_repair_mismatched_invalid_draft(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    workflow_id = "folder/wf"
    await _create_workflow(client, workflow_id)
    draft_path = (
        tmp_path / "workspace" / "workflows" / "folder" / "wf" / ".bioimageflow" / "draft.json"
    )
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    invalid = {
        "draft_version": 1,
        "workflow_id": "legacy/location",
        "future_compatible": {"preserve": True},
    }
    draft_path.write_text(json.dumps(invalid, indent=2), encoding="utf-8")

    response = await client.get(f"/api/v1/workflow-drafts/{workflow_id}")

    assert response.status_code == 422
    assert json.loads(draft_path.read_text(encoding="utf-8")) == invalid
    assert not list(draft_path.parent.glob(".draft.json.*.tmp"))


async def test_put_rejects_writes_while_execution_is_running(
    locked_client: httpx.AsyncClient,
) -> None:
    await _create_workflow(locked_client, "wf")

    response = await locked_client.put(
        "/api/v1/workflow-drafts/wf",
        json={
            "graph": {"nodes": [], "edges": []},
            "expected_revision": 0,
            "updated_by": "frontend",
        },
    )

    assert response.status_code == 423
    assert response.json()["error"] == "workflow_locked"


async def test_admitted_draft_validation_blocks_run_until_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = ToolRegistryService()
    store = WorkflowStoreService(
        root_dir=tmp_path / "workspace" / "workflows",
        tool_registry=registry,
        storage_base_dir=tmp_path / "workspace" / "outputs",
    )
    store.create_workflow(WorkflowCreate(name="wf"))
    drafts = workflow_draft_service.WorkflowDraftService(lambda: store)
    graph_a = _graph_state("graph-a")
    graph_b = _graph_state("graph-b")
    accepted = drafts.put_draft(
        "wf",
        graph=graph_a,
        expected_revision=0,
        should_validate=False,
    )
    manager = ExecutionManager(
        NullEventBus(),
        registry,
        Settings(
            deployment_mode="desktop",
            output_data_folder=str(tmp_path / "outputs"),
        ),
    )
    validation_entered = threading.Event()
    release_validation = threading.Event()

    def blocking_validate(
        _store: WorkflowStoreService,
        _workflow_id: str,
        graph: GraphState,
    ) -> ValidationResult:
        if graph == graph_b:
            validation_entered.set()
            assert release_validation.wait(timeout=2)
        return drafts._default_validation(graph)

    monkeypatch.setattr(drafts, "_validate", blocking_validate)
    app = create_app(
        AppConfig(
            tool_registry=registry,
            workflow_store=store,
            execution_manager=manager,
            settings=manager.settings,
            storage_path=tmp_path / "outputs",
            disable_hot_reload=True,
        )
    )
    app.dependency_overrides[drafts_get_workflow_draft_service] = lambda: drafts
    app.dependency_overrides[execution_get_workflow_draft_service] = lambda: drafts
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        draft_write = asyncio.create_task(
            client.put(
                "/api/v1/workflow-drafts/wf",
                json={
                    "graph": graph_b.model_dump(mode="json"),
                    "expected_revision": accepted.draft_revision,
                    "updated_by": "frontend",
                },
            )
        )
        try:
            async with asyncio.timeout(2):
                while not validation_entered.is_set():
                    await asyncio.sleep(0)

            run = await client.post(
                "/api/v1/execution/run",
                json={
                    "graph": graph_a.model_dump(mode="json"),
                    "workflow_name": "wf",
                    "draft_revision": accepted.draft_revision,
                },
            )

            assert run.status_code == 409
            assert draft_write.done() is False
            assert manager._starting is False
            assert manager.context is None
            assert manager.get_status().state == "idle"
        finally:
            release_validation.set()

        committed = await draft_write

    assert committed.status_code == 200
    assert committed.json()["draft_revision"] == accepted.draft_revision + 1
    assert manager.is_running is False


async def test_revision_zero_authority_validation_is_reserved_as_starting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = ToolRegistryService()
    store = WorkflowStoreService(
        root_dir=tmp_path / "workspace" / "workflows",
        tool_registry=registry,
        storage_base_dir=tmp_path / "workspace" / "outputs",
    )
    store.create_workflow(WorkflowCreate(name="wf"))
    drafts = workflow_draft_service.WorkflowDraftService(lambda: store)
    manager = ExecutionManager(
        NullEventBus(),
        registry,
        Settings(
            deployment_mode="desktop",
            output_data_folder=str(tmp_path / "outputs"),
        ),
    )
    validation_entered = threading.Event()
    release_validation = threading.Event()

    def blocking_validate(
        _store: WorkflowStoreService,
        _workflow_id: str,
        graph: GraphState,
    ) -> ValidationResult:
        validation_entered.set()
        assert release_validation.wait(timeout=2)
        return drafts._default_validation(graph)

    monkeypatch.setattr(drafts, "_validate", blocking_validate)
    app = create_app(
        AppConfig(
            tool_registry=registry,
            workflow_store=store,
            execution_manager=manager,
            settings=manager.settings,
            storage_path=tmp_path / "outputs",
            disable_hot_reload=True,
        )
    )
    app.dependency_overrides[drafts_get_workflow_draft_service] = lambda: drafts
    app.dependency_overrides[execution_get_workflow_draft_service] = lambda: drafts
    transport = httpx.ASGITransport(app=app)
    payload = {
        "graph": GraphState(nodes=[], edges=[]).model_dump(mode="json"),
        "workflow_name": "wf",
        "draft_revision": 0,
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first_run = asyncio.create_task(client.post("/api/v1/execution/run", json=payload))
        try:
            async with asyncio.timeout(2):
                while not validation_entered.is_set():
                    await asyncio.sleep(0)

            status = (await client.get("/api/v1/execution/status")).json()
            duplicate = await client.post("/api/v1/execution/run", json=payload)

            assert status["state"] == "starting"
            assert status["workflow_id"] == "wf"
            assert status["draft_revision"] == 0
            assert status["execution_id"]
            assert duplicate.status_code == 409
            assert first_run.done() is False
        finally:
            release_validation.set()

        accepted = await first_run

    assert accepted.status_code == 202, accepted.text


async def test_revisionless_run_rechecks_move_fence_after_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = ToolRegistryService()
    store = WorkflowStoreService(
        root_dir=tmp_path / "workspace" / "workflows",
        tool_registry=registry,
        storage_base_dir=tmp_path / "workspace" / "outputs",
    )
    store.create_workflow(WorkflowCreate(name="run-wf"))
    store.create_workflow(WorkflowCreate(name="move-source"))
    manager = ExecutionManager(
        NullEventBus(),
        registry,
        Settings(
            deployment_mode="desktop",
            output_data_folder=str(tmp_path / "outputs"),
        ),
    )
    original_reserve_start = manager.reserve_start
    prepared_operation_ids: list[Any] = []

    @asynccontextmanager
    async def reserve_start_with_pending_move(
        workflow_id: str,
        draft_revision: int | None,
    ) -> AsyncIterator[Any]:
        async with original_reserve_start(workflow_id, draft_revision) as context:
            operation_id = store.prepare_workflow_patch_move(
                "move-source",
                WorkflowUpdate(action="update", new_id="move-destination"),
            )
            assert operation_id is not None
            prepared_operation_ids.append(operation_id)
            yield context

    monkeypatch.setattr(manager, "reserve_start", reserve_start_with_pending_move)
    app = create_app(
        AppConfig(
            tool_registry=registry,
            workflow_store=store,
            execution_manager=manager,
            settings=manager.settings,
            storage_path=tmp_path / "outputs",
            disable_hot_reload=True,
        )
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        run = await client.post(
            "/api/v1/execution/run",
            json={
                "graph": GraphState(nodes=[], edges=[]).model_dump(mode="json"),
                "workflow_name": "run-wf",
            },
        )

    assert prepared_operation_ids
    assert store.pending_workflow_move() is not None
    assert run.status_code == 503
    assert run.json()["error"] == "workflow_move_recovery_required"
    assert manager.is_running is False
    assert manager.context is None
