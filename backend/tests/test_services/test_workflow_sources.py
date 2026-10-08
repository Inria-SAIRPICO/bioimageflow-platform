"""Explicit saved-source refresh and trusted Python materialization tests."""

from __future__ import annotations

import inspect
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import pytest

from bioimageflow_server.models.graph import GraphState, ToolNodeState
from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowSaveBody
from bioimageflow_server.models.workflow_sources import WorkflowSourceApplyRequest
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_artifacts import OwnedWorkflowSources
from bioimageflow_server.services.workflow_sources import (
    WorkflowSourceConflict,
    WorkflowSourceService,
)
from bioimageflow_server.services.workflow_store import WorkflowStoreService


def _store(tmp_path: Path) -> WorkflowStoreService:
    return WorkflowStoreService(tmp_path / "workflows", ToolRegistryService())


def _graph(name: str, display_name: str | None = None) -> GraphState:
    return GraphState.model_validate(
        {
            "schema_version": 1,
            "name": name,
            "display_name": display_name or name.title(),
            "nodes": [],
            "edges": [],
            "interface": {"inputs": [], "outputs": []},
            "config": {
                "engine": "direct",
                "execution": "parallel",
            },
        }
    )


def _parent_graph(source_graph: GraphState, source_hash: str) -> GraphState:
    return GraphState.model_validate(
        {
            **_graph("parent").model_dump(mode="json", by_alias=True),
            "nodes": [
                {
                    "type": "workflow",
                    "id": "child",
                    "name": "Child instance",
                    "workflow": source_graph.model_dump(mode="json", by_alias=True),
                    "bindings": {},
                    "position": [0, 0],
                    "source": {
                        "kind": "workspace",
                        "workflow_id": "child",
                        "artifact_hash": source_hash,
                    },
                }
            ],
        }
    )


def test_source_refresh_is_previewed_and_applied_explicitly(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="child"))
    child = store.get_workflow("child")
    store.create_workflow(WorkflowCreate(name="parent"))
    store.save_workflow(
        "parent", WorkflowSaveBody(graph=_parent_graph(child.graph, child.artifact_hash))
    )
    store.save_workflow(
        "child", WorkflowSaveBody(graph=_graph("child", "Updated child"))
    )
    parent = store.get_workflow("parent")
    service = WorkflowSourceService(lambda: store)

    preview = service.preview_source_update(
        "parent", ["child"], expected_artifact_hash=parent.artifact_hash
    )

    assert preview.replacement.display_name == "Updated child"
    assert store.get_workflow("parent").graph.nodes[0].workflow.display_name == "child"  # type: ignore[union-attr]

    result = service.apply(
        WorkflowSourceApplyRequest(
            token=preview.token,
            confirm_effects=preview.destructive_effects,
        )
    )

    updated = store.get_workflow("parent")
    assert result.artifact_hash == updated.artifact_hash
    assert updated.graph.nodes[0].workflow.display_name == "Updated child"  # type: ignore[union-attr]
    assert updated.graph.nodes[0].source.artifact_hash == store.get_workflow(  # type: ignore[union-attr]
        "child"
    ).artifact_hash


def test_source_refresh_conflicts_when_parent_changes_after_preview(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="child"))
    child = store.get_workflow("child")
    store.create_workflow(WorkflowCreate(name="parent"))
    parent_graph = _parent_graph(child.graph, child.artifact_hash)
    store.save_workflow("parent", WorkflowSaveBody(graph=parent_graph))
    service = WorkflowSourceService(lambda: store)
    parent = store.get_workflow("parent")
    preview = service.preview_source_update(
        "parent", ["child"], expected_artifact_hash=parent.artifact_hash
    )
    store.save_workflow(
        "parent",
        WorkflowSaveBody(
            graph=parent_graph.model_copy(update={"display_name": "Changed parent"})
        ),
    )

    with pytest.raises(WorkflowSourceConflict, match="Parent workflow artifact changed"):
        service.apply(
            WorkflowSourceApplyRequest(
                token=preview.token,
                confirm_effects=preview.destructive_effects,
            )
        )


def test_source_refresh_conflicts_when_destination_is_recreated_with_same_artifact(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="child"))
    child = store.get_workflow("child")
    store.create_workflow(WorkflowCreate(name="parent"))
    parent_graph = _parent_graph(child.graph, child.artifact_hash)
    store.save_workflow("parent", WorkflowSaveBody(graph=parent_graph))
    service = WorkflowSourceService(lambda: store)
    original = store.get_workflow("parent")
    preview = service.preview_source_update(
        "parent", ["child"], expected_artifact_hash=original.artifact_hash
    )

    store.delete_workflow("parent")
    recreated = store.create_workflow(WorkflowCreate(name="parent"))
    assert recreated.identity_generation == 3
    store.save_workflow("parent", WorkflowSaveBody(graph=parent_graph))
    before = store.get_workflow("parent")
    before_files = {
        path.relative_to(store.workflow_dir("parent")).as_posix(): path.read_bytes()
        for path in store.workflow_dir("parent").rglob("*")
        if path.is_file()
    }
    assert before.artifact_hash == original.artifact_hash

    with pytest.raises(WorkflowSourceConflict, match="Destination workflow identity changed"):
        service.apply(
            WorkflowSourceApplyRequest(
                token=preview.token,
                confirm_effects=preview.destructive_effects,
            )
        )

    after = store.get_workflow("parent")
    after_files = {
        path.relative_to(store.workflow_dir("parent")).as_posix(): path.read_bytes()
        for path in store.workflow_dir("parent").rglob("*")
        if path.is_file()
    }
    assert after.graph == before.graph
    assert after.artifact_hash == before.artifact_hash
    assert store.workflow_generation("parent") == recreated.identity_generation
    assert after_files == before_files


def test_source_refresh_preview_captures_parent_and_generation_under_one_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="child"))
    child = store.get_workflow("child")
    store.create_workflow(WorkflowCreate(name="parent"))
    store.save_workflow(
        "parent", WorkflowSaveBody(graph=_parent_graph(child.graph, child.artifact_hash))
    )
    parent = store.get_workflow("parent")
    service = WorkflowSourceService(lambda: store)
    parent_read = threading.Event()
    allow_preview_to_continue = threading.Event()
    original_get_workflow = store.get_workflow

    def paused_get_workflow(workflow_id: str):
        result = original_get_workflow(workflow_id)
        if workflow_id == "parent" and not parent_read.is_set():
            parent_read.set()
            assert allow_preview_to_continue.wait(timeout=5)
        return result

    monkeypatch.setattr(store, "get_workflow", paused_get_workflow)
    with ThreadPoolExecutor(max_workers=2) as pool:
        preview_future = pool.submit(
            service.preview_source_update,
            "parent",
            ["child"],
            expected_artifact_hash=parent.artifact_hash,
        )
        assert parent_read.wait(timeout=5)
        delete_future = pool.submit(store.delete_workflow, "parent")
        assert not delete_future.done()
        allow_preview_to_continue.set()
        preview = preview_future.result(timeout=5)
        assert delete_future.result(timeout=5) == 2

    store.create_workflow(WorkflowCreate(name="parent"))
    store.save_workflow(
        "parent", WorkflowSaveBody(graph=_parent_graph(child.graph, child.artifact_hash))
    )
    with pytest.raises(WorkflowSourceConflict, match="Destination workflow identity changed"):
        service.apply(
            WorkflowSourceApplyRequest(
                token=preview.token,
                confirm_effects=preview.destructive_effects,
            )
        )


def test_python_materialization_uses_workflow_local_factory_and_fresh_helpers(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="python-authored"))
    workflow_dir = store.workflow_dir("python-authored")
    helper = workflow_dir / "helper.py"
    entry = workflow_dir / "workflow.py"
    # A non-Python log records factory calls without changing the captured
    # authoring manifest. The factory's storage binding owns this exact root.
    call_log = workflow_dir / "factory-calls.txt"
    helper.write_text('LABEL = "First"\n', encoding="utf-8")
    entry.write_text(
        "from bioimageflow import Workflow\n"
        "from pathlib import Path\n"
        "from helper import LABEL\n\n"
        "def build_workflow(*, storage_path):\n"
        "    log = Path(storage_path).parent / 'factory-calls.txt'\n"
        "    with log.open('a', encoding='utf-8') as stream:\n"
        "        stream.write(LABEL + '\\n')\n"
        "    return Workflow(\n"
        "        name='python_definition',\n"
        "        display_name=LABEL,\n"
        "        engine='direct',\n"
        "        execution='sequential',\n"
        "        storage_path=storage_path,\n"
        "    )\n",
        encoding="utf-8",
    )

    def python_bytes() -> dict[str, bytes]:
        return {
            path.relative_to(workflow_dir).as_posix(): path.read_bytes()
            for path in workflow_dir.rglob("*.py")
        }

    service = WorkflowSourceService(lambda: store)
    current = store.get_workflow("python-authored")
    original_document = store.read_workflow_document("python-authored")
    generation = store.workflow_generation("python-authored")
    original_sources = python_bytes()
    assert not call_log.exists()
    first = service.preview_python_rebuild(
        "python-authored", expected_artifact_hash=current.artifact_hash
    )
    assert call_log.read_text(encoding="utf-8").splitlines() == ["First"]
    assert store.read_workflow_document("python-authored") == original_document
    assert store.workflow_generation("python-authored") == generation
    assert python_bytes() == original_sources
    service.apply(
        WorkflowSourceApplyRequest(
            token=first.token,
            confirm_effects=first.destructive_effects,
        )
    )
    saved = store.get_workflow("python-authored")

    assert saved.graph.name == "python_definition"
    assert saved.graph.display_name == "First"
    assert saved.authoring_source is not None
    assert saved.authoring_source.factory == "build_workflow"
    assert saved.authoring_source.source_hash == first.source_artifact_hash
    assert call_log.read_text(encoding="utf-8").splitlines() == ["First"]
    assert python_bytes() == original_sources
    assert store.workflow_generation("python-authored") == generation
    saved_document = store.read_workflow_document("python-authored")

    helper.write_text('LABEL = "Second"\n', encoding="utf-8")
    second = service.preview_python_rebuild(
        "python-authored", expected_artifact_hash=saved.artifact_hash
    )

    assert second.source_artifact_hash != first.source_artifact_hash
    assert second.replacement.display_name == "Second"
    assert call_log.read_text(encoding="utf-8").splitlines() == ["First", "Second"]
    assert store.read_workflow_document("python-authored") == saved_document

    helper.write_text('LABEL = "Third"\n', encoding="utf-8")
    changed_sources = python_bytes()
    with pytest.raises(
        WorkflowSourceConflict, match="Python authoring source changed after preview"
    ):
        service.apply(
            WorkflowSourceApplyRequest(
                token=second.token,
                confirm_effects=second.destructive_effects,
            )
        )
    assert store.read_workflow_document("python-authored") == saved_document
    assert store.get_workflow("python-authored") == saved
    assert store.workflow_generation("python-authored") == generation
    assert python_bytes() == changed_sources
    assert call_log.read_text(encoding="utf-8").splitlines() == ["First", "Second"]

    fresh = service.preview_python_rebuild(
        "python-authored", expected_artifact_hash=saved.artifact_hash
    )
    assert fresh.source_artifact_hash != second.source_artifact_hash
    assert fresh.replacement.display_name == "Third"
    assert store.read_workflow_document("python-authored") == saved_document
    assert python_bytes() == changed_sources
    expected_calls = ["First", "Second", "Third"]
    assert call_log.read_text(encoding="utf-8").splitlines() == expected_calls
    applied = service.apply(
        WorkflowSourceApplyRequest(
            token=fresh.token,
            confirm_effects=fresh.destructive_effects,
        )
    )
    assert applied.graph == fresh.replacement
    assert applied.artifact_hash != saved.artifact_hash
    assert call_log.read_text(encoding="utf-8").splitlines() == expected_calls
    assert python_bytes() == changed_sources
    assert store.workflow_generation("python-authored") == generation
    accepted_document = store.read_workflow_document("python-authored")
    assert accepted_document.graph.display_name == "Third"
    assert accepted_document.authoring_source is not None
    assert accepted_document.authoring_source.source_hash == fresh.source_artifact_hash
    assert accepted_document.owned_source_ids == saved_document.owned_source_ids

    # Ordinary graph loading and empty Direct execution must never import the
    # authoring entry again. This is a control-plane check, without science.
    entry.write_text("raise AssertionError('authoring entry was imported by Run')\n", encoding="utf-8")
    reopened = store.get_workflow("python-authored")
    assert reopened.graph == applied.graph
    assert reopened.artifact_hash == applied.artifact_hash
    assert reopened.authoring_source == accepted_document.authoring_source
    compiled = build_workflow(
        reopened.graph,
        store.tool_registry,
        storage_path=store.get_storage_path("python-authored"),
    )
    assert compiled.errors == []
    assert compiled.workflow is not None
    assert compiled.workflow.engine_type == "direct"
    assert compiled.workflow.execution == "sequential"
    assert compiled.workflow.nodes == {}
    result = compiled.workflow.compute()
    assert isinstance(result, pd.DataFrame)
    assert result.empty
    assert list(result.columns) == []
    assert call_log.read_text(encoding="utf-8").splitlines() == expected_calls
    assert store.read_workflow_document("python-authored") == accepted_document


def test_python_materialization_is_disabled_in_webapp_mode(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="python-authored"))
    service = WorkflowSourceService(
        lambda: store,
        deployment_mode_provider=lambda: "webapp",
        unsafe_webapp_features_provider=lambda: False,
    )

    with pytest.raises(PermissionError):
        service.preview_python_rebuild(
            "python-authored",
            expected_artifact_hash=store.get_workflow("python-authored").artifact_hash,
        )


def test_python_materialization_apply_preserves_captured_tool_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bioimageflow import Workflow
    from bioimageflow_dev_tools.tools import SeedNumbers

    execution_calls: list[str] = []

    def refuse_execution(*args: object, **kwargs: object) -> None:
        execution_calls.append("execution")
        raise AssertionError("Python preview/apply must not execute the tool")

    # Observe public execution entry points without modifying the ordinary
    # scientific declaration or hiding source admission behind a fixture tool.
    monkeypatch.setattr(Workflow, "compute", refuse_execution)
    monkeypatch.setattr(Workflow, "create_engine", refuse_execution)
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="python-tool-sources"))
    workflow_dir = store.workflow_dir("python-tool-sources")
    entry = workflow_dir / "workflow.py"
    entry.write_text(
        "from bioimageflow import Workflow\n"
        "from bioimageflow_dev_tools.tools import SeedNumbers\n\n"
        "def build_workflow(*, storage_path):\n"
        "    with Workflow(name='python_tool_definition', storage_path=storage_path,\n"
        "                  engine='direct', execution='sequential') as workflow:\n"
        "        seed = SeedNumbers()(name='seed')\n"
        "        workflow.output('number', seed['number'])\n"
        "        workflow.output('label', seed['label'])\n"
        "    return workflow\n",
        encoding="utf-8",
    )
    entry_bytes = entry.read_bytes()
    original_document = store.read_workflow_document("python-tool-sources")
    generation = store.workflow_generation("python-tool-sources")
    service = WorkflowSourceService(lambda: store)
    preview = service.preview_python_rebuild(
        "python-tool-sources",
        expected_artifact_hash=store.get_workflow("python-tool-sources").artifact_hash,
    )
    assert store.read_workflow_document("python-tool-sources") == original_document
    assert len(preview.replacement.nodes) == 1
    node = preview.replacement.nodes[0]
    assert isinstance(node, ToolNodeState)
    assert node.id == "seed"
    assert node.source_module is not None
    assert preview.custom_source_ids_added == [node.source_module]
    assert preview.custom_source_ids_removed == []
    assert execution_calls == []

    applied = service.apply(
        WorkflowSourceApplyRequest(
            token=preview.token,
            confirm_effects=preview.destructive_effects,
        )
    )

    assert applied.graph == preview.replacement
    saved = store.get_workflow("python-tool-sources")
    document = store.read_workflow_document("python-tool-sources")
    assert saved.graph == applied.graph
    assert saved.artifact_hash == applied.artifact_hash
    assert document.owned_source_ids == preview.custom_source_ids_added
    assert document.authoring_source is not None
    assert document.authoring_source.source_hash == preview.source_artifact_hash
    assert store.workflow_generation("python-tool-sources") == generation
    owned = OwnedWorkflowSources(workflow_dir)
    records = owned.collect_for_graph(saved.graph)
    assert [record["id"] for record in records] == preview.custom_source_ids_added
    assert (workflow_dir / "tools" / node.source_module / "module.json").is_file()
    staged_source = owned.source_path(node.source_module, node.tool_module)
    original_source = Path(inspect.getfile(SeedNumbers))
    assert staged_source.read_bytes() == original_source.read_bytes()
    assert staged_source.is_relative_to(workflow_dir / "tools" / node.source_module)
    assert entry.read_bytes() == entry_bytes
    assert execution_calls == []


def test_python_materialization_refuses_symlink_helper_before_execution(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="symlink-authored"))
    workflow_dir = store.workflow_dir("symlink-authored")
    foreign_root = tmp_path / "foreign-authoring"
    foreign_root.mkdir()
    foreign_helper = foreign_root / "helper.py"
    helper_marker = foreign_root / "helper-executed.txt"
    factory_marker = workflow_dir / "factory-executed.txt"
    foreign_helper.write_text(
        "from pathlib import Path\n"
        f"Path({str(helper_marker)!r}).write_text('executed', encoding='utf-8')\n"
        "LABEL = 'Foreign helper'\n",
        encoding="utf-8",
    )
    helper = workflow_dir / "helper.py"
    helper.symlink_to(foreign_helper)
    entry = workflow_dir / "workflow.py"
    entry.write_text(
        "from bioimageflow import Workflow\n"
        "from pathlib import Path\n"
        "from helper import LABEL\n\n"
        "def build_workflow(*, storage_path):\n"
        "    marker = Path(storage_path).parent / 'factory-executed.txt'\n"
        "    marker.write_text('executed', encoding='utf-8')\n"
        "    return Workflow(name='symlink_definition', display_name=LABEL,\n"
        "                    storage_path=storage_path, engine='direct',\n"
        "                    execution='sequential')\n",
        encoding="utf-8",
    )
    saved = store.get_workflow("symlink-authored")
    document = store.read_workflow_document("symlink-authored")
    generation = store.workflow_generation("symlink-authored")
    entry_bytes = entry.read_bytes()
    foreign_bytes = foreign_helper.read_bytes()
    assert helper.is_symlink()
    assert helper.readlink() == foreign_helper
    assert not helper_marker.exists()
    assert not factory_marker.exists()

    service = WorkflowSourceService(lambda: store)
    with pytest.raises(ValueError, match="Python authoring source cannot use symlinks"):
        service.preview_python_rebuild(
            "symlink-authored", expected_artifact_hash=saved.artifact_hash
        )

    assert store.get_workflow("symlink-authored") == saved
    assert store.read_workflow_document("symlink-authored") == document
    assert store.workflow_generation("symlink-authored") == generation
    assert entry.read_bytes() == entry_bytes
    assert helper.is_symlink()
    assert helper.readlink() == foreign_helper
    assert foreign_helper.read_bytes() == foreign_bytes
    assert not helper_marker.exists()
    assert not factory_marker.exists()
