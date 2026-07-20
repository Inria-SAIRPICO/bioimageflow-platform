"""Concurrency contracts for graph compilation and validation boundaries."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest
from tests.graph_factory import graph_state

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.nested_workflow_snapshot import NestedSnapshotOwner
from bioimageflow_server.models.validation import NodeStatus, ValidationResult
from bioimageflow_server.models.workflow import (
    WorkflowCreate,
    WorkflowSaveBody,
    WorkflowUpdate,
)
from bioimageflow_server.services.graph_validator import GraphValidationService
from bioimageflow_server.services.nested_workflow_snapshot import (
    NestedSnapshotRevisionConflict,
    NestedWorkflowSnapshotService,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_draft import (
    WorkflowDraftRevisionConflict,
    WorkflowDraftService,
)
from bioimageflow_server.services.workflow_store import (
    WorkflowGenerationChangedError,
    WorkflowStoreService,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def store(tmp_path: Path) -> WorkflowStoreService:
    return WorkflowStoreService(
        root_dir=tmp_path / "workspace" / "workflows",
        tool_registry=ToolRegistryService(),
        storage_base_dir=tmp_path / "workspace" / "outputs",
    )


def _graph(node_id: str | None = None) -> GraphState:
    if node_id is None:
        return graph_state(name="wf", display_name="wf", nodes=[], edges=[])
    return graph_state(
        name="wf",
        display_name="wf",
        nodes=[
            {
                "type": "tool",
                "id": node_id,
                "name": node_id,
                "tool_name": "MissingTool",
                "position": [0, 0],
                "parameters": {},
            }
        ]
    )


def _default_validation(graph: GraphState) -> ValidationResult:
    return ValidationResult(
        valid=True,
        node_statuses={
            node.id: NodeStatus(
                node_id=node.id,
                status="unexecuted",
                cached=False,
            )
            for node in graph.nodes
        },
        errors=[],
    )


async def _wait_for_thread_event(event: threading.Event) -> None:
    async with asyncio.timeout(2):
        while not event.is_set():
            await asyncio.sleep(0)


async def test_graph_validation_worker_keeps_the_event_loop_responsive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GraphValidationService(ToolRegistryService())
    entered = threading.Event()
    release = threading.Event()
    event_loop_thread = threading.get_ident()

    def blocking_validate(
        graph: GraphState,
        **_kwargs: object,
    ) -> ValidationResult:
        assert threading.get_ident() != event_loop_thread
        entered.set()
        assert release.wait(timeout=2)
        return _default_validation(graph)

    monkeypatch.setattr(service, "validate", blocking_validate)

    validation = asyncio.create_task(service.validate_async(_graph()))
    try:
        await _wait_for_thread_event(entered)
        await asyncio.wait_for(asyncio.sleep(0), timeout=0.1)
    finally:
        release.set()

    assert (await validation).valid is True


async def test_stale_draft_validation_cannot_commit_over_newer_revision(
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store.create_workflow(WorkflowCreate(name="wf"))
    drafts = WorkflowDraftService(lambda: store)
    slow_validation_entered = threading.Event()
    release_slow_validation = threading.Event()
    graph_a = _graph("graph-a")
    graph_b = _graph("graph-b")

    def controlled_validate(
        _store: WorkflowStoreService,
        _workflow_id: str,
        graph: GraphState,
    ) -> ValidationResult:
        if graph == graph_a:
            slow_validation_entered.set()
            assert release_slow_validation.wait(timeout=2)
        return _default_validation(graph)

    monkeypatch.setattr(drafts, "_validate", controlled_validate)

    stale_write = asyncio.create_task(
        drafts.put_draft_async(
            "wf",
            graph=graph_a,
            expected_revision=0,
        )
    )
    try:
        await _wait_for_thread_event(slow_validation_entered)
        winner = await drafts.put_draft_async(
            "wf",
            graph=graph_b,
            expected_revision=0,
        )
    finally:
        release_slow_validation.set()

    assert winner.draft_revision == 1
    with pytest.raises(WorkflowDraftRevisionConflict):
        await stale_write

    current = await drafts.get_draft_snapshot_async("wf")
    assert current.draft_revision == 1
    assert current.graph == graph_b


async def test_validation_from_deleted_generation_cannot_mutate_same_id_replacement(
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store.create_workflow(WorkflowCreate(name="wf", display_name="Original"))
    drafts = WorkflowDraftService(lambda: store)
    validation_entered = threading.Event()
    release_validation = threading.Event()
    stale_graph = _graph("stale")

    def blocking_validate(
        _store: WorkflowStoreService,
        _workflow_id: str,
        graph: GraphState,
    ) -> ValidationResult:
        validation_entered.set()
        assert release_validation.wait(timeout=2)
        return _default_validation(graph)

    monkeypatch.setattr(drafts, "_validate", blocking_validate)

    stale_write = asyncio.create_task(
        drafts.put_draft_async(
            "wf",
            graph=stale_graph,
            expected_revision=0,
        )
    )
    try:
        await _wait_for_thread_event(validation_entered)
        await asyncio.to_thread(store.delete_workflow, "wf")
        await asyncio.to_thread(
            store.create_workflow,
            WorkflowCreate(name="wf", display_name="Replacement"),
        )
    finally:
        release_validation.set()

    with pytest.raises(WorkflowGenerationChangedError):
        await stale_write

    fresh = store.get_workflow("wf")
    assert fresh.info.display_name == "Replacement"
    assert fresh.graph.nodes == []
    assert fresh.graph.name == "wf"
    assert not (store.workflow_dir("wf") / ".bioimageflow" / "draft.json").exists()


async def test_reset_revalidates_when_saved_workflow_changes_during_validation(
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store.create_workflow(WorkflowCreate(name="wf"))
    drafts = WorkflowDraftService(lambda: store)
    first_validation_entered = threading.Event()
    release_first_validation = threading.Event()
    validated_graphs: list[GraphState] = []
    replacement_saved_graph = _graph("new-saved")

    def controlled_validate(
        _store: WorkflowStoreService,
        _workflow_id: str,
        graph: GraphState,
    ) -> ValidationResult:
        validated_graphs.append(graph)
        if len(validated_graphs) == 1:
            first_validation_entered.set()
            assert release_first_validation.wait(timeout=2)
        return _default_validation(graph)

    monkeypatch.setattr(drafts, "_validate", controlled_validate)

    reset = asyncio.create_task(
        drafts.reset_draft_to_saved_async(
            "wf",
            expected_revision=0,
        )
    )
    try:
        await _wait_for_thread_event(first_validation_entered)
        await asyncio.to_thread(
            store.save_workflow,
            "wf",
            WorkflowSaveBody(graph=replacement_saved_graph),
        )
    finally:
        release_first_validation.set()

    accepted = await reset
    assert accepted.graph == replacement_saved_graph
    assert accepted.dirty_against_saved is False
    assert validated_graphs == [_graph(), replacement_saved_graph]


async def test_stale_nested_validation_cannot_commit_over_newer_revision(
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store.create_workflow(WorkflowCreate(name="wf"))
    snapshots = NestedWorkflowSnapshotService(lambda: store)
    opened = snapshots.open_snapshot(
        NestedSnapshotOwner(
            kind="root",
            canvas_id="workflow:wf",
            workflow_id="wf",
        ),
        "nested-node",
        _graph(),
    )
    slow_validation_entered = threading.Event()
    release_slow_validation = threading.Event()
    graph_a = _graph("graph-a")
    graph_b = _graph("graph-b")

    def controlled_validate(
        _store: WorkflowStoreService,
        _workflow_id: str | None,
        graph: GraphState,
    ) -> ValidationResult:
        if graph == graph_a:
            slow_validation_entered.set()
            assert release_slow_validation.wait(timeout=2)
        return _default_validation(graph)

    monkeypatch.setattr(snapshots, "_validate", controlled_validate)

    stale_write = asyncio.create_task(
        snapshots.put_snapshot_async(
            opened.session_id,
            expected_revision=0,
            graph=graph_a,
        )
    )
    try:
        await _wait_for_thread_event(slow_validation_entered)
        winner = await snapshots.put_snapshot_async(
            opened.session_id,
            expected_revision=0,
            graph=graph_b,
        )
    finally:
        release_slow_validation.set()

    assert winner.snapshot_revision == 1
    with pytest.raises(NestedSnapshotRevisionConflict):
        await stale_write

    current = await snapshots.get_snapshot_async(opened.session_id)
    assert current.snapshot_revision == 1
    assert current.graph == graph_b


async def test_nested_validation_cannot_commit_into_replaced_root_identity(
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store.create_workflow(WorkflowCreate(name="wf", display_name="Original"))
    snapshots = NestedWorkflowSnapshotService(lambda: store)
    monkeypatch.setattr(
        snapshots,
        "_validate",
        lambda _store, _workflow_id, graph: _default_validation(graph),
    )
    opened = snapshots.open_snapshot(
        NestedSnapshotOwner(
            kind="root",
            canvas_id="workflow:wf",
            workflow_id="wf",
        ),
        "nested-node",
        _graph(),
    )
    validation_entered = threading.Event()
    release_validation = threading.Event()
    stale_graph = _graph("stale")

    def blocking_validate(
        _store: WorkflowStoreService,
        _workflow_id: str | None,
        graph: GraphState,
    ) -> ValidationResult:
        validation_entered.set()
        assert release_validation.wait(timeout=2)
        return _default_validation(graph)

    monkeypatch.setattr(snapshots, "_validate", blocking_validate)
    stale_write = asyncio.create_task(
        snapshots.put_snapshot_async(
            opened.session_id,
            expected_revision=0,
            graph=stale_graph,
        )
    )
    try:
        await _wait_for_thread_event(validation_entered)
        await asyncio.to_thread(store.delete_workflow, "wf")
        await asyncio.to_thread(
            store.create_workflow,
            WorkflowCreate(name="wf", display_name="Replacement"),
        )
    finally:
        release_validation.set()

    with pytest.raises(WorkflowGenerationChangedError):
        await stale_write

    current = snapshots.get_snapshot(opened.session_id)
    assert current.snapshot_revision == 0
    assert current.graph == _graph()
    assert store.get_workflow("wf").info.display_name == "Replacement"


async def test_nested_validation_retries_after_root_storage_change(
    store: WorkflowStoreService,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store.create_workflow(WorkflowCreate(name="wf"))
    snapshots = NestedWorkflowSnapshotService(lambda: store)
    monkeypatch.setattr(
        snapshots,
        "_validate",
        lambda _store, _workflow_id, graph: _default_validation(graph),
    )
    opened = snapshots.open_snapshot(
        NestedSnapshotOwner(
            kind="root",
            canvas_id="workflow:wf",
            workflow_id="wf",
        ),
        "nested-node",
        _graph(),
    )
    first_validation_entered = threading.Event()
    release_first_validation = threading.Event()
    validation_storage_paths: list[Path] = []
    replacement_storage = tmp_path / "replacement-storage"

    def controlled_validate(
        current_store: WorkflowStoreService,
        workflow_id: str | None,
        graph: GraphState,
    ) -> ValidationResult:
        assert workflow_id is not None
        validation_storage_paths.append(current_store.get_storage_path(workflow_id))
        if len(validation_storage_paths) == 1:
            first_validation_entered.set()
            assert release_first_validation.wait(timeout=2)
        return _default_validation(graph)

    monkeypatch.setattr(snapshots, "_validate", controlled_validate)
    put = asyncio.create_task(
        snapshots.put_snapshot_async(
            opened.session_id,
            expected_revision=0,
            graph=_graph("updated"),
        )
    )
    try:
        await _wait_for_thread_event(first_validation_entered)
        await asyncio.to_thread(
            store.patch_workflow,
            "wf",
            WorkflowUpdate(action="update", storage_path=str(replacement_storage)),
        )
    finally:
        release_first_validation.set()

    accepted = await put
    assert accepted.snapshot_revision == 1
    assert validation_storage_paths == [
        store.storage_base_dir / "wf",
        replacement_storage,
    ]
