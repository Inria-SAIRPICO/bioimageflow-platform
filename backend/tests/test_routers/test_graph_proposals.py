"""Router tests for graph proposal application."""

from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.graph_proposal_manager import DraftSnapshot

pytestmark = pytest.mark.anyio


class RouterDraftStore:
    def __init__(self) -> None:
        self.graph = GraphState(nodes=[], edges=[])
        self.revision = 1

    def get_snapshot(self, draft_id: str) -> DraftSnapshot:
        return DraftSnapshot(
            draft_id=draft_id,
            revision=self.revision,
            graph=self.graph.model_copy(deep=True),
        )

    def save_graph(self, draft_id: str, graph: GraphState, base_revision: int) -> DraftSnapshot:
        if base_revision != self.revision:
            raise AssertionError("manager should reject stale proposals before save")
        self.revision += 1
        self.graph = graph.model_copy(deep=True)
        return DraftSnapshot(draft_id=draft_id, revision=self.revision, graph=self.graph)


class _LockedExecutionManager:
    is_running = True


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _client(
    store: Any,
    tmp_path: Path,
    *,
    execution_manager: Any | None = None,
) -> httpx.AsyncClient:
    app = create_app(
        AppConfig(
            proposal_draft_store=store,
            storage_path=tmp_path,
            execution_manager=execution_manager,
        )
    )
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_apply_stale_proposal_returns_409(tmp_path: Path) -> None:
    store = RouterDraftStore()
    async with await _client(store, tmp_path) as client:
        create = await client.post(
            "/api/v1/graph/proposals",
            json={
                "draft_id": "draft-1",
                "base_revision": 1,
                "operations": [
                    {
                        "type": "add_node",
                        "node": {
                            "id": "n1",
                            "name": "n1",
                            "tool_name": "NoSuchTool",
                            "position": [0, 0],
                            "parameters": {},
                        },
                    }
                ],
            },
        )
        assert create.status_code == 200
        store.revision = 2

        apply = await client.post(
            f"/api/v1/graph/proposals/{create.json()['id']}/apply"
        )

    assert apply.status_code == 409
    assert apply.json()["error"] == "conflict"


async def test_create_and_apply_proposal_returns_updated_graph(tmp_path: Path) -> None:
    store = RouterDraftStore()
    store.graph = GraphState(nodes=[], edges=[])
    async with await _client(store, tmp_path) as client:
        create = await client.post(
            "/api/v1/graph/proposals",
            json={
                "draft_id": "draft-1",
                "base_revision": 1,
                "operations": [
                    {
                        "type": "replace_graph",
                        "graph": {"nodes": [], "edges": []},
                    }
                ],
            },
        )
        apply = await client.post(
            f"/api/v1/graph/proposals/{create.json()['id']}/apply"
        )

    assert create.status_code == 200
    assert apply.status_code == 200
    assert apply.json()["revision"] == 2
    assert apply.json()["graph"] == {
        "nodes": [],
        "edges": [],
        "published_inputs": [],
        "published_outputs": [],
    }


async def test_draft_scoped_proposal_routes_apply_to_requested_draft(tmp_path: Path) -> None:
    store = RouterDraftStore()
    async with await _client(store, tmp_path) as client:
        create = await client.post(
            "/api/v1/workflow-drafts/draft-1/agent-proposals",
            json={
                "base_revision": 1,
                "operations": [{"type": "replace_graph", "graph": {"nodes": [], "edges": []}}],
            },
        )
        apply = await client.post(
            f"/api/v1/workflow-drafts/draft-1/agent-proposals/{create.json()['id']}/apply"
        )

    assert create.status_code == 200
    assert create.json()["draft_id"] == "draft-1"
    assert apply.status_code == 200
    assert apply.json()["draft_id"] == "draft-1"


async def test_proposal_apply_locked_during_execution(tmp_path: Path) -> None:
    store = RouterDraftStore()
    async with await _client(
        store,
        tmp_path,
        execution_manager=_LockedExecutionManager(),
    ) as client:
        create = await client.post(
            "/api/v1/workflow-drafts/draft-1/agent-proposals",
            json={
                "base_revision": 1,
                "operations": [{"type": "replace_graph", "graph": {"nodes": [], "edges": []}}],
            },
        )
        apply = await client.post(
            f"/api/v1/workflow-drafts/draft-1/agent-proposals/{create.json()['id']}/apply"
        )

    assert apply.status_code == 423
