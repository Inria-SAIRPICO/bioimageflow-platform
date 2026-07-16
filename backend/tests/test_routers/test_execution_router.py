"""Tests for the execution router."""
# pyright: reportInvalidTypeForm=false
# Rationale: image file fields use ``Annotated[Path, ImageSpec(...)]`` metadata;
# pyright can't evaluate this runtime metadata statically.

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import IOModel, ProcessingTool
from bioimageflow_core.types import ImageSpec, Semantic

from bioimageflow_server.app import create_app
from bioimageflow_server.models.execution import (
    ExecutionContext,
    ExecutionResult,
    ExecutionStatus,
    ProgressInfo,
)
from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.tools import AppConfig, ToolMetadata
from bioimageflow_server.models.validation import (
    GraphValidationError,
    NodeStatus,
    ValidationResult,
)
from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowUpdate
from bioimageflow_server.models.workflow_draft import DraftWriter, WorkflowDraftResponse
from bioimageflow_server.routers.execution import (
    get_workflow_draft_service as execution_get_workflow_draft_service,
    get_workflow_store as execution_get_workflow_store,
)
from bioimageflow_server.services.execution import (
    ExecutionConflictError,
    WorkflowBuildError,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService


# ---- Mock tool classes (module-level so from_dict can re-import) -----------


class _SrcInputs(IOModel):
    input_image: Annotated[Path, ImageSpec(semantics={Semantic.INTENSITY})]


class _SrcOutputs(IOModel):
    mask: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class SrcTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = _SrcInputs
    Outputs = _SrcOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class _DstInputs(IOModel):
    mask_input: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class _DstOutputs(IOModel):
    result: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class DstTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = _DstInputs
    Outputs = _DstOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


def _make_registry() -> ToolRegistryService:
    reg = ToolRegistryService()
    for name, cls in [("SrcTool", SrcTool), ("DstTool", DstTool)]:
        reg.register_tool(
            name,
            ToolMetadata(
                name=name, display_name=name,
                package="test-pkg", package_version="1.0.0",
                tool_type="ProcessingTool",
            ),
            tool_class=cls,
        )
    return reg

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _clear_active_workflow() -> Any:
    from bioimageflow.node import set_active_workflow

    set_active_workflow(None)
    yield
    set_active_workflow(None)


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


def _accepted_draft(
    graph: dict[str, Any] | None = None,
    *,
    workflow_id: str = "wf",
    revision: int = 7,
    valid: bool = True,
    updated_by: DraftWriter = "frontend",
) -> WorkflowDraftResponse:
    return WorkflowDraftResponse(
        workflow_id=workflow_id,
        base_saved_revision="sha256:test",
        draft_revision=revision,
        updated_at="2026-07-16T00:00:00Z",
        updated_by=updated_by,
        dirty_against_saved=True,
        graph=GraphState.model_validate(graph or _minimal_graph()),
        validation=ValidationResult(valid=valid),
    )


class _FakeExecutionManager:
    def __init__(
        self,
        running: bool = False,
        start_error: Exception | None = None,
        status: ExecutionStatus | None = None,
    ) -> None:
        self.is_running = running
        self.start = AsyncMock(return_value=ExecutionContext(
            execution_id="exec-123",
            workflow_id="wf",
            draft_revision=7,
        ))
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
    tool_registry: ToolRegistryService | None = None,
    workflow_store: Any = None,
    workflow_draft_service: Any = None,
) -> httpx.AsyncClient:
    config = AppConfig(
        storage_path=tmp_path,
        execution_manager=execution_manager,
        tool_registry=tool_registry,
        workflow_store=workflow_store,
    )
    app = create_app(config)
    if workflow_draft_service is not None:
        app.dependency_overrides[execution_get_workflow_draft_service] = (
            lambda: workflow_draft_service
        )
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def idle_client(tmp_path: Path) -> AsyncIterator[tuple[httpx.AsyncClient, _FakeExecutionManager]]:
    em = _FakeExecutionManager(running=False)
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path
    workflow_draft_service = MagicMock()
    workflow_draft_service.get_draft_snapshot.return_value = _accepted_draft()
    c = await _make_client(
        tmp_path,
        execution_manager=em,
        workflow_store=workflow_store,
        workflow_draft_service=workflow_draft_service,
    )
    async with c:
        yield c, em


# ---- POST /execution/run ----------------------------------------------------


async def test_run_returns_202(idle_client) -> None:
    client, em = idle_client
    resp = await client.post(
        "/api/v1/execution/run",
        json={
            "graph": _minimal_graph(),
            "workflow_name": "wf",
            "draft_revision": 7,
        },
    )
    assert resp.status_code == 202, resp.text
    assert resp.json() == {
        "status": "started",
        "execution_id": "exec-123",
        "workflow_id": "wf",
        "draft_revision": 7,
    }
    em.start.assert_awaited_once()
    assert em.start.await_args.kwargs["workflow_id"] == "wf"
    assert em.start.await_args.kwargs["draft_revision"] == 7
    assert em.start.await_args.args[0] == _accepted_draft().graph


async def test_run_selected_uses_accepted_draft_graph(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path
    draft_service = MagicMock()
    accepted = _accepted_draft()
    draft_service.get_draft_snapshot.return_value = accepted
    client = await _make_client(
        tmp_path,
        execution_manager=em,
        workflow_store=workflow_store,
        workflow_draft_service=draft_service,
    )

    async with client:
        response = await client.post(
            "/api/v1/execution/run",
            json={
                "graph": accepted.graph.model_dump(mode="json"),
                "nodes": ["n1"],
                "workflow_name": "wf",
                "draft_revision": 7,
            },
        )

    assert response.status_code == 202, response.text
    assert em.start.await_args.args[0] is accepted.graph
    assert em.start.await_args.kwargs["nodes"] == ["n1"]


async def test_run_rejects_stale_draft_before_execution_side_effects(
    tmp_path: Path,
) -> None:
    prior_context = ExecutionContext(
        execution_id="exec-prior",
        workflow_id="prior",
        draft_revision=3,
    )
    prior_status = ExecutionStatus(
        state="idle",
        execution_id=prior_context.execution_id,
        workflow_id=prior_context.workflow_id,
        draft_revision=prior_context.draft_revision,
    )
    em = _FakeExecutionManager(running=False, status=prior_status)
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path
    draft_service = MagicMock()
    draft_service.get_draft_snapshot.return_value = _accepted_draft(revision=8)
    cache_sentinel = tmp_path / "cache-sentinel"
    cache_sentinel.write_text("retained")
    client = await _make_client(
        tmp_path,
        execution_manager=em,
        workflow_store=workflow_store,
        workflow_draft_service=draft_service,
    )

    async with client:
        response = await client.post(
            "/api/v1/execution/run",
            json={
                "graph": _minimal_graph(),
                "workflow_name": "wf",
                "draft_revision": 7,
            },
        )

    assert response.status_code == 409
    assert response.json() == {
        "error": "draft_revision_conflict",
        "detail": "Draft revision conflict: expected 7, current is 8",
        "expected_revision": 7,
        "current_revision": 8,
        "current_updated_by": "frontend",
        "current_updated_at": "2026-07-16T00:00:00Z",
    }
    em.start.assert_not_awaited()
    workflow_store.get_storage_path.assert_not_called()
    assert em.get_status() is prior_status
    assert cache_sentinel.read_text() == "retained"


async def test_run_rejects_same_revision_graph_mismatch(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path
    accepted_graph = _minimal_graph()
    accepted_graph["nodes"][0]["parameters"] = {"value": 1}
    draft_service = MagicMock()
    draft_service.get_draft_snapshot.return_value = _accepted_draft(accepted_graph)
    client = await _make_client(
        tmp_path,
        execution_manager=em,
        workflow_store=workflow_store,
        workflow_draft_service=draft_service,
    )

    async with client:
        response = await client.post(
            "/api/v1/execution/run",
            json={
                "graph": _minimal_graph(),
                "workflow_name": "wf",
                "draft_revision": 7,
            },
        )

    assert response.status_code == 409
    assert response.json() == {
        "error": "draft_graph_mismatch",
        "detail": (
            "Submitted graph does not match accepted draft revision 7 "
            "for workflow 'wf'"
        ),
        "workflow_id": "wf",
        "draft_revision": 7,
    }
    em.start.assert_not_awaited()
    workflow_store.get_storage_path.assert_not_called()


async def test_run_without_revision_preserves_inline_execution(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    em.start.return_value = ExecutionContext(
        execution_id="exec-inline",
        workflow_id="wf",
        draft_revision=None,
    )
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path
    draft_service = MagicMock()
    client = await _make_client(
        tmp_path,
        execution_manager=em,
        workflow_store=workflow_store,
        workflow_draft_service=draft_service,
    )

    async with client:
        response = await client.post(
            "/api/v1/execution/run",
            json={"graph": _minimal_graph(), "workflow_name": "wf"},
        )

    assert response.status_code == 202, response.text
    draft_service.get_draft_snapshot.assert_not_called()
    assert em.start.await_args.args[0] == GraphState.model_validate(_minimal_graph())
    assert em.start.await_args.kwargs["draft_revision"] is None


async def test_run_accepts_revision_zero_synthesized_baseline(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    em.start.return_value = ExecutionContext(
        execution_id="exec-zero",
        workflow_id="wf",
        draft_revision=0,
    )
    workflow_store = WorkflowStoreService(
        root_dir=tmp_path / "workspace" / "workflows",
        tool_registry=ToolRegistryService(),
        storage_base_dir=tmp_path / "workspace" / "outputs",
    )
    workflow_store.create_workflow(WorkflowCreate(name="wf"))
    draft_path = workflow_store.workflow_dir("wf") / ".bioimageflow" / "draft.json"
    assert not draft_path.exists()
    client = await _make_client(
        tmp_path,
        execution_manager=em,
        workflow_store=workflow_store,
    )

    async with client:
        response = await client.post(
            "/api/v1/execution/run",
            json={
                "graph": {"nodes": [], "edges": []},
                "workflow_name": "wf",
                "draft_revision": 0,
            },
        )

    assert response.status_code == 202, response.text
    assert response.json()["draft_revision"] == 0
    assert em.start.await_args.args[0] == GraphState(nodes=[], edges=[])
    assert em.start.await_args.kwargs["draft_revision"] == 0
    assert not draft_path.exists()


async def test_run_rejects_revision_zero_graph_mismatch_without_materializing_draft(
    tmp_path: Path,
) -> None:
    em = _FakeExecutionManager(running=False)
    workflow_store = WorkflowStoreService(
        root_dir=tmp_path / "workspace" / "workflows",
        tool_registry=ToolRegistryService(),
        storage_base_dir=tmp_path / "workspace" / "outputs",
    )
    workflow_store.create_workflow(WorkflowCreate(name="wf"))
    draft_path = workflow_store.workflow_dir("wf") / ".bioimageflow" / "draft.json"
    client = await _make_client(
        tmp_path,
        execution_manager=em,
        workflow_store=workflow_store,
    )

    async with client:
        response = await client.post(
            "/api/v1/execution/run",
            json={
                "graph": _minimal_graph(),
                "workflow_name": "wf",
                "draft_revision": 0,
            },
        )

    assert response.status_code == 409
    assert response.json()["error"] == "draft_graph_mismatch"
    assert response.json()["draft_revision"] == 0
    em.start.assert_not_awaited()
    assert not draft_path.exists()


@pytest.mark.parametrize("race", ["moved", "deleted"])
async def test_run_returns_not_found_when_workflow_disappears_before_start(
    tmp_path: Path,
    race: str,
) -> None:
    em = _FakeExecutionManager(running=False)
    workflow_store = WorkflowStoreService(
        root_dir=tmp_path / "workspace" / "workflows",
        tool_registry=ToolRegistryService(),
        storage_base_dir=tmp_path / "workspace" / "outputs",
    )
    workflow_store.create_workflow(WorkflowCreate(name="wf"))
    client = await _make_client(
        tmp_path,
        execution_manager=em,
        workflow_store=workflow_store,
    )
    if race == "moved":
        workflow_store.patch_workflow(
            "wf",
            WorkflowUpdate(action="update", new_id="archive/wf"),
        )
    else:
        workflow_store.delete_workflow("wf")

    async with client:
        response = await client.post(
            "/api/v1/execution/run",
            json={
                "graph": _minimal_graph(),
                "workflow_name": "wf",
                "draft_revision": 7,
            },
        )

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"
    em.start.assert_not_awaited()


async def test_run_selected_defers_invalid_full_draft_validation_to_execution_scope(
    tmp_path: Path,
) -> None:
    em = _FakeExecutionManager(running=False)
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path
    invalid_graph = _minimal_graph()
    error = GraphValidationError(
        type="missing_tool",
        detail="Tool 'T' is not installed",
        node="n1",
    )
    draft = _accepted_draft(invalid_graph, valid=False)
    draft.validation.errors = [error]
    draft_service = MagicMock()
    draft_service.get_draft_snapshot.return_value = draft
    client = await _make_client(
        tmp_path,
        execution_manager=em,
        workflow_store=workflow_store,
        workflow_draft_service=draft_service,
    )

    async with client:
        response = await client.post(
            "/api/v1/execution/run",
            json={
                "graph": invalid_graph,
                "nodes": ["n1"],
                "workflow_name": "wf",
                "draft_revision": 7,
            },
        )

    assert response.status_code == 202, response.text
    em.start.assert_awaited_once()
    assert em.start.await_args.args[0] is draft.graph
    assert em.start.await_args.kwargs["nodes"] == ["n1"]


@pytest.mark.parametrize("retained_validation_valid", [False, True])
async def test_run_recompiles_draft_instead_of_trusting_retained_validation(
    tmp_path: Path,
    retained_validation_valid: bool,
) -> None:
    error = GraphValidationError(
        type="missing_tool",
        detail="Tool 'T' is not installed",
        node="n1",
    )
    em = _FakeExecutionManager(
        running=False,
        start_error=WorkflowBuildError([error]),
    )
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path
    draft = _accepted_draft(_minimal_graph(), valid=retained_validation_valid)
    if not retained_validation_valid:
        draft.validation.errors = [error]
    draft_service = MagicMock()
    draft_service.get_draft_snapshot.return_value = draft
    client = await _make_client(
        tmp_path,
        execution_manager=em,
        workflow_store=workflow_store,
        workflow_draft_service=draft_service,
    )

    async with client:
        response = await client.post(
            "/api/v1/execution/run",
            json={
                "graph": _minimal_graph(),
                "workflow_name": "wf",
                "draft_revision": 7,
            },
        )

    assert response.status_code == 422
    assert response.json() == {
        "error": "validation_error",
        "detail": "Failed to build workflow: 1 error(s)",
        "errors": [error.model_dump()],
    }
    em.start.assert_awaited_once()
    assert em.start.await_args.args[0] is draft.graph


async def test_run_conflict_returns_409(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=True)
    em.start.side_effect = ExecutionConflictError("already running")
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path
    c = await _make_client(
        tmp_path,
        execution_manager=em,
        workflow_store=workflow_store,
    )
    async with c:
        resp = await c.post(
            "/api/v1/execution/run",
            json={"graph": _minimal_graph(), "workflow_name": "wf"},
        )
    assert resp.status_code == 409


async def test_run_build_failure_returns_422(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    em.start.side_effect = WorkflowBuildError(
        [GraphValidationError(type="cycle_detected", detail="cycle")]
    )
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path
    c = await _make_client(
        tmp_path,
        execution_manager=em,
        workflow_store=workflow_store,
    )
    async with c:
        resp = await c.post(
            "/api/v1/execution/run",
            json={"graph": _minimal_graph(), "workflow_name": "wf"},
        )
    assert resp.status_code == 422
    body = resp.json()
    assert "cycle" in str(body).lower() or body.get("error") == "validation_error"


async def test_run_passes_nodes_subset(idle_client) -> None:
    client, em = idle_client
    resp = await client.post(
        "/api/v1/execution/run",
        json={
            "graph": _minimal_graph(),
            "nodes": ["n1"],
            "workflow_name": "wf",
        },
    )
    assert resp.status_code == 202
    call_args = em.start.call_args
    # graph as first arg, nodes as second
    assert call_args.args[0].nodes[0].id == "n1"
    assert call_args.kwargs.get("nodes") == ["n1"] or call_args.args[1] == ["n1"]


async def test_run_resolves_workflow_storage_path(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    workflow_store = MagicMock()
    workflow_storage = tmp_path / "workflows" / "wf_a"
    workflow_store.get_storage_path.return_value = workflow_storage
    c = await _make_client(
        tmp_path,
        execution_manager=em,
        workflow_store=workflow_store,
    )
    async with c:
        resp = await c.post(
            "/api/v1/execution/run",
            json={"graph": _minimal_graph(), "workflow_name": "wf_a"},
        )

    assert resp.status_code == 202
    workflow_store.get_storage_path.assert_called_once_with("wf_a")
    assert em.start.call_args.kwargs["storage_path"] == workflow_storage


async def test_run_requires_workflow_identity(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    workflow_store = MagicMock()
    c = await _make_client(
        tmp_path,
        execution_manager=em,
        workflow_store=workflow_store,
    )
    async with c:
        resp = await c.post(
            "/api/v1/execution/run",
            json={"graph": _minimal_graph()},
        )

    assert resp.status_code == 422
    workflow_store.get_storage_path.assert_not_called()
    em.start.assert_not_awaited()


async def test_run_requires_workflow_store(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    app = create_app(
        AppConfig(
            storage_path=tmp_path,
            execution_manager=em,
            workflow_store=MagicMock(),
        )
    )
    app.dependency_overrides[execution_get_workflow_store] = lambda: None
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/v1/execution/run",
            json={
                "graph": _minimal_graph(),
                "workflow_name": "wf",
            },
        )

    assert resp.status_code == 503
    em.start.assert_not_awaited()


@pytest.mark.parametrize("workflow_name", [None, "", " ", "../outside"])
async def test_run_rejects_invalid_workflow_identity(
    tmp_path: Path,
    workflow_name: str | None,
) -> None:
    em = _FakeExecutionManager(running=False)
    workflow_store = MagicMock()
    c = await _make_client(
        tmp_path,
        execution_manager=em,
        workflow_store=workflow_store,
    )
    async with c:
        resp = await c.post(
            "/api/v1/execution/run",
            json={
                "graph": _minimal_graph(),
                "workflow_name": workflow_name,
            },
        )

    assert resp.status_code == 422
    workflow_store.get_storage_path.assert_not_called()
    em.start.assert_not_awaited()


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
    reg = _make_registry()
    graph = {
        "nodes": [
            {"id": "a", "name": "a", "tool_name": "SrcTool", "position": [0, 0],
             "parameters": {"input_image": "/a"}},
        ],
        "edges": [],
    }
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path
    c = await _make_client(
        tmp_path,
        execution_manager=em,
        tool_registry=reg,
        workflow_store=workflow_store,
    )
    async with c:
        resp = await c.post(
            "/api/v1/execution/clear",
            json={"graph": graph, "nodes": ["a"], "workflow_name": "wf"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "node_statuses" in body
    assert body["node_statuses"]["a"]["status"] == "unexecuted"


async def test_clear_without_graph_returns_422(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    c = await _make_client(tmp_path, execution_manager=em)
    async with c:
        resp = await c.post(
            "/api/v1/execution/clear",
            json={"nodes": ["n1"], "workflow_name": "wf"},
        )
    assert resp.status_code == 422


async def test_clear_while_running_returns_423(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=True)
    reg = _make_registry()
    graph = {
        "nodes": [
            {"id": "a", "name": "a", "tool_name": "SrcTool", "position": [0, 0],
             "parameters": {"input_image": "/a"}},
        ],
        "edges": [],
    }
    c = await _make_client(tmp_path, execution_manager=em, tool_registry=reg)
    async with c:
        resp = await c.post(
            "/api/v1/execution/clear",
            json={"graph": graph, "nodes": ["a"], "workflow_name": "wf"},
        )
    assert resp.status_code == 423


async def test_clear_requires_workflow_identity(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    c = await _make_client(
        tmp_path,
        execution_manager=em,
        tool_registry=_make_registry(),
    )
    async with c:
        resp = await c.post(
            "/api/v1/execution/clear",
            json={"graph": _minimal_graph(), "nodes": ["n1"]},
        )

    assert resp.status_code == 422


@pytest.mark.parametrize("workflow_name", [None, "", " ", "../outside"])
async def test_clear_rejects_invalid_workflow_identity(
    tmp_path: Path,
    workflow_name: str | None,
) -> None:
    c = await _make_client(
        tmp_path,
        execution_manager=_FakeExecutionManager(running=False),
        tool_registry=_make_registry(),
    )
    async with c:
        resp = await c.post(
            "/api/v1/execution/clear",
            json={
                "graph": _minimal_graph(),
                "nodes": ["n1"],
                "workflow_name": workflow_name,
            },
        )

    assert resp.status_code == 422


async def test_clear_downstream_out_of_date(tmp_path: Path) -> None:
    em = _FakeExecutionManager(running=False)
    reg = _make_registry()
    graph = {
        "nodes": [
            {"id": "a", "name": "a", "tool_name": "SrcTool", "position": [0, 0],
             "parameters": {"input_image": "/a"}},
            {"id": "b", "name": "b", "tool_name": "DstTool", "position": [0, 0],
             "parameters": {}},
        ],
        "edges": [
            {
                "type": "column_ref",
                "id": "e",
                "source_node": "a",
                "target_node": "b",
                "source_output": "mask",
                "target_input": "mask_input",
            }
        ],
    }
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path
    c = await _make_client(
        tmp_path,
        execution_manager=em,
        tool_registry=reg,
        workflow_store=workflow_store,
    )
    async with c:
        resp = await c.post(
            "/api/v1/execution/clear",
            json={"graph": graph, "nodes": ["a"], "workflow_name": "wf"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["node_statuses"]["a"]["status"] == "unexecuted"
    assert body["node_statuses"]["b"]["status"] == "out_of_date"


async def test_clear_resolves_workflow_storage_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    em = _FakeExecutionManager(running=False)
    workflow_store = MagicMock()
    workflow_storage = tmp_path / "workflows" / "wf_a"
    workflow_store.get_storage_path.return_value = workflow_storage
    seen: dict[str, Path | None] = {}

    def _fake_clear(nodes, graph, registry, storage_path, *, dev_mode, settings):
        seen["storage_path"] = storage_path
        seen["dev_mode"] = dev_mode
        seen["settings"] = settings
        return {
            "a": NodeStatus(node_id="a", status="unexecuted", cached=False),
        }

    monkeypatch.setattr(
        "bioimageflow_server.routers.execution.clear_node_cache",
        _fake_clear,
    )
    c = await _make_client(
        tmp_path,
        execution_manager=em,
        tool_registry=_make_registry(),
        workflow_store=workflow_store,
    )
    async with c:
        resp = await c.post(
            "/api/v1/execution/clear",
            json={
                "graph": _minimal_graph(),
                "nodes": ["a"],
                "workflow_name": "wf_a",
            },
        )

    assert resp.status_code == 200
    workflow_store.get_storage_path.assert_called_once_with("wf_a")
    assert seen["storage_path"] == workflow_storage
    assert seen["dev_mode"] is True
    assert seen["settings"] is not None


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
        execution_id="exec-123",
        workflow_id="wf",
        draft_revision=7,
    )
    object.__setattr__(status, "node_statuses", {})
    em = _FakeExecutionManager(running=True, status=status)
    c = await _make_client(tmp_path, execution_manager=em)
    async with c:
        resp = await c.get("/api/v1/execution/status")
    body = resp.json()
    assert body["state"] == "running"
    assert body["progress"]["row"] == 1
    assert body["execution_id"] == "exec-123"
    assert body["workflow_id"] == "wf"
    assert body["draft_revision"] == 7


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
