"""Tests for live workflow draft endpoints."""

from __future__ import annotations

import json
import sys
import tomllib
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
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
    assert body["graph"] == {"nodes": [], "edges": [], "published_inputs": [], "published_outputs": []}
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

    async for client in _client(
        tmp_path, is_running=True, connection_manager=manager
    ):
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
