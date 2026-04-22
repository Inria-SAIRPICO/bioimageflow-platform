"""Tests for the execution router."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.execution import (
    ExecutionResult,
    ExecutionStatus,
    ProgressInfo,
)
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.models.validation import GraphValidationError, NodeStatus
from bioimageflow_server.services.execution import (
    ExecutionConflictError,
    WorkflowBuildError,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _minimal_graph() -> dict:
    return {
        "nodes": [
            {
                "id": "n1",
                "name": "n1",
                "tool_name": "T",
                "position": [0, 0],
                "parameters": {},
            }
        ],
        "edges": [],
    }


class _FakeExecutionManager:
    def __init__(
        self,
        running: bool = False,
        start_error: Exception | None = None,
        status: ExecutionStatus | None = None,
    ) -> None:
        self.is_running = running
        self.start = AsyncMock()
        self.stop = AsyncMock()
        if start_error is not None:
            self.start.side_effect = start_error
        self._status = status or ExecutionStatus(
            state="running" if running else "idle",
            last_result=None,
            progress=None,
        )
        if not hasattr(self._status, "node_statuses"):
            object.__setattr__(self._status, "node_statuses", {})

    def get_status(self) -> ExecutionStatus:
        return self._status


async def _make_client(
    tmp_path: Path,
    execution_manager: Any = None,
) -> httpx.AsyncClient:
    config = AppConfig(
        storage_path=tmp_path,
        execution_manager=execution_manager,
    )
    app = create_app(config)
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def idle_client(tmp_path: Path) -> AsyncIterator[tuple[httpx.AsyncClient, _FakeExecutionManager]]:
    em = _FakeExecutionManager(running=False)
    c = await _make_client(tmp_path, execution_manager=em)
    async with c:
        yield c, em


# ---- POST /execution/run ----------------------------------------------------


async def test_run_returns_202(idle_client) -> None:
    client, em = idle_client
    resp = await client.post(
        "/api/v1/execution/run", json={"graph": _minimal_graph()}
    )
    assert resp.status_code == 202, resp.text
    assert resp.json() == {"status": "started"}
    em.start.assert_awaited_once()


async def test_run_conflict_returns_409(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=True)
    em.start.side_effect = ExecutionConflictError("already running")
    c = await _make_client(tmp_path, execution_manager=em)
    async with c:
        resp = await c.post(
            "/api/v1/execution/run", json={"graph": _minimal_graph()}
        )
    assert resp.status_code == 409


async def test_run_build_failure_returns_422(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    em.start.side_effect = WorkflowBuildError(
        [GraphValidationError(type="cycle_detected", detail="cycle")]
    )
    c = await _make_client(tmp_path, execution_manager=em)
    async with c:
        resp = await c.post(
            "/api/v1/execution/run", json={"graph": _minimal_graph()}
        )
    assert resp.status_code == 422
    body = resp.json()
    assert "cycle" in str(body).lower() or body.get("error") == "validation_error"


async def test_run_passes_nodes_subset(idle_client) -> None:
    client, em = idle_client
    resp = await client.post(
        "/api/v1/execution/run",
        json={"graph": _minimal_graph(), "nodes": ["n1"]},
    )
    assert resp.status_code == 202
    call_args = em.start.call_args
    # graph as first arg, nodes as second
    assert call_args.args[0].nodes[0].id == "n1"
    assert call_args.kwargs.get("nodes") == ["n1"] or call_args.args[1] == ["n1"]


# ---- POST /execution/stop ---------------------------------------------------


async def test_stop_returns_200(idle_client) -> None:
    client, em = idle_client
    resp = await client.post("/api/v1/execution/stop")
    assert resp.status_code == 200
    assert resp.json() == {"status": "stopping"}
    em.stop.assert_awaited_once()


# ---- POST /execution/clear --------------------------------------------------


async def test_clear_returns_node_statuses(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    c = await _make_client(tmp_path, execution_manager=em)
    async with c:
        resp = await c.post(
            "/api/v1/execution/clear",
            json={"graph": _minimal_graph(), "nodes": ["n1"]},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "node_statuses" in body
    assert body["node_statuses"]["n1"]["status"] == "unexecuted"


async def test_clear_without_graph_returns_422(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    c = await _make_client(tmp_path, execution_manager=em)
    async with c:
        resp = await c.post(
            "/api/v1/execution/clear", json={"nodes": ["n1"]}
        )
    assert resp.status_code == 422


async def test_clear_while_running_returns_423(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=True)
    c = await _make_client(tmp_path, execution_manager=em)
    async with c:
        resp = await c.post(
            "/api/v1/execution/clear",
            json={"graph": _minimal_graph(), "nodes": ["n1"]},
        )
    assert resp.status_code == 423


async def test_clear_downstream_out_of_date(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    c = await _make_client(tmp_path, execution_manager=em)
    graph = {
        "nodes": [
            {"id": "a", "name": "a", "tool_name": "T", "position": [0, 0], "parameters": {}},
            {"id": "b", "name": "b", "tool_name": "T", "position": [0, 0], "parameters": {}},
        ],
        "edges": [
            {
                "type": "column_ref",
                "id": "e",
                "source_node": "a",
                "target_node": "b",
                "source_output": "out",
                "target_input": "in",
            }
        ],
    }
    async with c:
        resp = await c.post(
            "/api/v1/execution/clear", json={"graph": graph, "nodes": ["a"]}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["node_statuses"]["a"]["status"] == "unexecuted"
    assert body["node_statuses"]["b"]["status"] == "out_of_date"


# ---- GET /execution/status --------------------------------------------------


async def test_status_idle(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    c = await _make_client(tmp_path, execution_manager=em)
    async with c:
        resp = await c.get("/api/v1/execution/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "idle"
    assert body["progress"] is None
    assert body["last_result"] is None


async def test_status_running_with_progress(tmp_path: Path) -> None:
    status = ExecutionStatus(
        state="running",
        last_result=None,
        progress=ProgressInfo(node_id="n1", row=1, total_rows=10),
    )
    object.__setattr__(status, "node_statuses", {})
    em = _FakeExecutionManager(running=True, status=status)
    c = await _make_client(tmp_path, execution_manager=em)
    async with c:
        resp = await c.get("/api/v1/execution/status")
    body = resp.json()
    assert body["state"] == "running"
    assert body["progress"]["row"] == 1


async def test_status_includes_node_statuses(tmp_path: Path) -> None:
    status = ExecutionStatus(state="idle", last_result=None, progress=None)
    object.__setattr__(
        status,
        "node_statuses",
        {"n1": NodeStatus(node_id="n1", status="executed", cached=False)},
    )
    em = _FakeExecutionManager(running=False, status=status)
    c = await _make_client(tmp_path, execution_manager=em)
    async with c:
        resp = await c.get("/api/v1/execution/status")
    body = resp.json()
    assert "node_statuses" in body
    assert body["node_statuses"]["n1"]["status"] == "executed"


async def test_status_persists_last_result(tmp_path: Path) -> None:
    last = ExecutionResult(success=True, errors=[], node_statuses={})
    status = ExecutionStatus(state="idle", last_result=last, progress=None)
    object.__setattr__(status, "node_statuses", {})
    em = _FakeExecutionManager(running=False, status=status)
    c = await _make_client(tmp_path, execution_manager=em)
    async with c:
        r1 = await c.get("/api/v1/execution/status")
        r2 = await c.get("/api/v1/execution/status")
    assert r1.json()["last_result"]["success"] is True
    assert r2.json()["last_result"]["success"] is True


# ---- Router registration ----------------------------------------------------


async def test_router_mounted_at_expected_prefix(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    c = await _make_client(tmp_path, execution_manager=em)
    async with c:
        resp = await c.get("/api/v1/execution/status")
    assert resp.status_code == 200
