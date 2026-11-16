"""Canonical workflow document persistence tests."""

from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.workflow import (
    WorkflowCreate,
    WorkflowSaveBody,
    WorkflowUpdate,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_artifacts import OwnedWorkflowSources
from bioimageflow_server.services.workflow_store import (
    WorkflowArchiveError,
    WorkflowResultsBundleImportError,
    WorkflowStoreService,
)


def _store(tmp_path: Path) -> WorkflowStoreService:
    return WorkflowStoreService(
        tmp_path / "workflows",
        ToolRegistryService(),
    )


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


def _move_workflow(
    store: WorkflowStoreService, source: str, patch: WorkflowUpdate
):
    operation_id = store.prepare_workflow_patch_move(source, patch)
    result = store.patch_workflow(source, patch, move_operation_id=operation_id)
    assert operation_id is not None
    store.mark_workflow_move_phase(operation_id, "snapshots_rewritten")
    store.mark_workflow_move_phase(operation_id, "preferences_rewritten")
    store.complete_workflow_move(operation_id)
    return result


def test_create_persists_one_canonical_document(tmp_path: Path) -> None:
    identities: dict[str, str] = {}
    store = _store(tmp_path)
    info = store.create_workflow(
        WorkflowCreate(name="folder/demo", display_name="Demo", description="A workflow")
    )
    identities["folder/demo"] = info.id

    raw = json.loads(
        (tmp_path / "workflows" / "folder" / "demo" / "workflow.json").read_text()
    )

    assert set(raw) == {
        "platform_document_version",
        "workflow_id",
        "graph",
        "metadata",
        "owned_source_ids",
        "artifact_hash",
    }
    assert raw["graph"]["name"] == "demo"
    assert raw["graph"]["display_name"] == "Demo"
    assert raw["metadata"] == {
        "description": "A workflow",
    }
    assert info.display_name == "Demo"
    assert info.results_path == str(
        tmp_path / "workflows" / "folder" / "demo" / "results"
    )


def test_new_workflow_scheduling_is_captured_once(tmp_path: Path) -> None:
    identities: dict[str, str] = {}
    preference: Literal["sequential", "parallel"] = "sequential"
    store = WorkflowStoreService(
        tmp_path / "workflows",
        ToolRegistryService(),
        new_workflow_execution=lambda: preference,
    )

    identities["first"] = store.create_workflow(WorkflowCreate(name="first")).id
    preference = "parallel"
    identities["second"] = store.create_workflow(WorkflowCreate(name="second")).id

    assert store.get_workflow(identities["first"]).graph.config.execution == "sequential"
    assert store.get_workflow(identities["second"]).graph.config.execution == "parallel"


def test_save_and_get_use_the_graph_as_display_authority(tmp_path: Path) -> None:
    identities: dict[str, str] = {}
    store = _store(tmp_path)
    identities["demo"] = store.create_workflow(WorkflowCreate(name="demo")).id
    graph = _graph("definition", "Editable Label")

    store.save_workflow(identities["demo"], WorkflowSaveBody(graph=graph))
    loaded = store.get_workflow(identities["demo"])

    assert loaded.graph == graph
    assert loaded.info.display_name == "Editable Label"
    assert loaded.artifact_hash.startswith("sha256:")
    assert "display_name" not in store._read_raw("demo")["metadata"]


def test_get_workflow_respects_explicit_tool_binding_without_catalog_entry(
    tmp_path: Path,
) -> None:
    identities: dict[str, str] = {}
    from bioimageflow_server.services.workflow_draft import WorkflowDraftService

    store = _store(tmp_path)
    assert store.tool_registry.get_tool("TemplateTool") is None
    drafts = WorkflowDraftService(lambda: store)

    def save_bound_graph(name: str, module: str) -> GraphState:
        identities[name] = store.create_workflow(WorkflowCreate(name=name)).id
        graph = GraphState.model_validate({
            "schema_version": 2,
            "name": name,
            "display_name": name,
            "nodes": [{
                "type": "tool", "id": "write", "name": "Write report",
                "tool_name": "TemplateTool", "tool_module": module,
                "tool_class": "TemplateTool", "position": [200, 160],
                "parameters": {},
                "output_templates": {"result": "report_{row_index}.txt"},
            }],
            "edges": [],
            "interface": {
                "inputs": [],
                "outputs": [{
                    "id": "published-report", "name": "report",
                    "schema": {"type": "Path"},
                    "source": {"node": "write", "column": "result"},
                }],
            },
            "config": {"engine": "direct", "execution": "sequential"},
        })
        store.save_workflow(identities[name], WorkflowSaveBody(graph=graph))
        return graph

    # An explicit but unavailable source must keep its scoped dependency error.
    save_bound_graph("unavailable", "platform_template_missing_module")
    unavailable = store.get_workflow(identities["unavailable"])
    assert [(item.node_id, item.tool_name) for item in unavailable.missing_tools] == [
        ("write", "TemplateTool"),
    ]

    graph = save_bound_graph("available", "platform_test_tools.graph")
    document = (store.workflow_dir(identities["available"]) / "workflow.json").read_bytes()
    projected = drafts.get_draft(identities["available"])
    assert projected.validation.valid
    assert projected.validation.errors == []
    assert projected.validation.node_tools["write"].model_dump(mode="json")[
        "outputs"
    ]["result"]["type"] == "Path"
    assert store.tool_registry.get_tool("TemplateTool") is None

    loaded = store.get_workflow(identities["available"])
    assert loaded.graph == projected.graph == graph
    assert loaded.missing_packages == []
    assert loaded.missing_tools == []
    assert (store.workflow_dir(identities["available"]) / "workflow.json").read_bytes() == document

    # A same-named catalog entry cannot rescue a refused explicit binding.
    from platform_test_tools.graph import TemplateTool

    store.tool_registry.register_tool(
        "TemplateTool", ToolRegistryService.metadata_for_class(TemplateTool),
    )
    assert store.get_workflow(identities["available"]).missing_tools == []
    assert [item.node_id for item in store.get_workflow(identities["unavailable"]).missing_tools] == [
        "write",
    ]


def test_rebind_versions_preserves_recursive_canvas_presentation(tmp_path: Path) -> None:
    identities: dict[str, str] = {}
    store = _store(tmp_path)
    identities["demo"] = store.create_workflow(WorkflowCreate(name="demo")).id
    from bioimageflow_server.models.tools import PackageInfo
    store.tool_registry.register_package("example-tools", PackageInfo(
        name="example-tools", installed_versions=["1.0.0", "2.0.0"], active_version="2.0.0",
    ))
    child_payload = _graph("child").model_dump(mode="json", by_alias=True)
    child_payload["nodes"] = [
        {
            "type": "tool",
            "id": "inner",
            "name": "Inner label",
            "tool_name": "ExampleTool",
            "position": [37, 91],
            "parameters": {},
            "collapsed": True,
            "tool_module": "example_tools",
            "tool_class": "ExampleTool",
            "tool_package": "example-tools",
            "tool_package_version": "1.0.0",
        }
    ]
    child = GraphState.model_validate(child_payload)
    graph_payload = _graph("root").model_dump(mode="json", by_alias=True)
    graph_payload["nodes"] = [
        {
            "type": "workflow",
            "id": "child",
            "name": "Custom child label",
            "workflow": child,
            "bindings": {},
            "position": [401, 233],
            "collapsed": True,
        }
    ]
    graph = GraphState.model_validate(graph_payload)
    store.save_workflow(identities["demo"], WorkflowSaveBody(graph=graph))

    loaded = store.get_workflow(identities["demo"]).graph
    assert loaded.nodes[0].workflow.nodes[0].tool_package_version == "1.0.0"
    assert loaded == GraphState.model_validate(graph_payload)
    rebound = store.rebind_versions(identities["demo"]).graph

    child_node = rebound.nodes[0]
    assert child_node.position == (401, 233)
    assert child_node.collapsed is True
    assert child_node.name == "Custom child label"
    assert child_node.type == "workflow"
    inner = child_node.workflow.nodes[0]
    assert inner.position == (37, 91)
    assert inner.collapsed is True
    assert inner.name == "Inner label"
    assert inner.tool_package == "example-tools"
    assert inner.tool_package_version == "2.0.0"
    assert store.get_workflow(identities["demo"]).graph == rebound


def test_unknown_persisted_sections_are_rejected_without_fallback(tmp_path: Path) -> None:
    identities: dict[str, str] = {}
    from bioimageflow_server.models.nested_workflow_snapshot import NestedSnapshotOwner
    from bioimageflow_server.services.nested_workflow_snapshot import NestedWorkflowSnapshotService
    from bioimageflow_server.services.workflow_draft import WorkflowDraftService

    store = _store(tmp_path)
    drafts = WorkflowDraftService(lambda: store)
    snapshots = NestedWorkflowSnapshotService(lambda: store)
    private = {}
    for workflow_id in ("demo", "unrelated"):
        identities[workflow_id] = store.create_workflow(WorkflowCreate(name=workflow_id)).id
        graph = _graph(f"{workflow_id}-definition", f"Saved {workflow_id}")
        store.save_workflow(identities[workflow_id], WorkflowSaveBody(graph=graph))
        drafts.put_draft(
            identities[workflow_id],
            graph=graph.model_copy(update={"display_name": f"Pending {workflow_id}"}),
            expected_revision=0,
            should_validate=False,
        )
        private[workflow_id] = snapshots.open_snapshot(
            NestedSnapshotOwner(
                kind="root", canvas_id=f"canvas:{workflow_id}", workflow_id=identities[workflow_id],
            ),
            "child",
            _graph(f"{workflow_id}-private"),
        )
        # Inert file sentinels prove retention, not executable source or results.
        tools = store.workflow_dir(identities[workflow_id]) / "tools"
        tools.mkdir(exist_ok=True)
        (tools / "retained.txt").write_bytes(f"source sentinel: {workflow_id}".encode())
        results = store.get_storage_path(identities[workflow_id])
        results.mkdir(exist_ok=True)
        (results / "retained.bin").write_bytes(f"result sentinel: {workflow_id}".encode())
    foreign = tmp_path / "unmanaged.bin"
    foreign.write_bytes(b"unmanaged sentinel")
    unrelated = store.read_workflow_document(identities["unrelated"])
    path = store.workflow_dir(identities["demo"]) / "workflow.json"
    raw = json.loads(path.read_text())
    raw["derived"] = {"nodes": []}
    path.write_text(json.dumps(raw), encoding="utf-8")

    def authority(current_store, current_drafts, current_snapshots):
        return {
            workflow_id: (
                json.loads((current_store.workflow_dir(identities[workflow_id]) / "workflow.json").read_text()),
                current_drafts.get_draft_authority_snapshot(identities[workflow_id]),
                current_store.workflow_generation(identities[workflow_id]),
                current_snapshots.get_snapshot(private[workflow_id].session_id),
            )
            for workflow_id in ("demo", "unrelated")
        }

    def files():
        return {
            item.relative_to(tmp_path).as_posix(): item.read_bytes()
            for item in tmp_path.rglob("*") if item.is_file()
        }

    retained = authority(store, drafts, snapshots)
    retained_files = files()
    with pytest.raises(ValidationError, match="derived"):
        store.get_workflow(identities["demo"])
    # A valid replacement graph cannot bypass the invalid saved-document fence.
    with pytest.raises(ValidationError, match="derived"):
        store.save_workflow(identities["demo"], WorkflowSaveBody(graph=_graph("replacement")))
    assert authority(store, drafts, snapshots) == retained
    assert files() == retained_files
    assert store.read_workflow_document(identities["unrelated"]) == unrelated

    reopened = _store(tmp_path)
    reopened_drafts = WorkflowDraftService(lambda: reopened)
    reopened_snapshots = NestedWorkflowSnapshotService(lambda: reopened)
    with pytest.raises(ValidationError, match="derived"):
        reopened.get_workflow(identities["demo"])
    assert reopened.read_workflow_document(identities["unrelated"]) == unrelated
    assert authority(reopened, reopened_drafts, reopened_snapshots) == retained
    assert files() == retained_files


def test_duplicate_assigns_new_definition_identity_atomically(tmp_path: Path) -> None:
    identities: dict[str, str] = {}
    store = _store(tmp_path)
    identities["source"] = store.create_workflow(WorkflowCreate(name="source", display_name="Source")).id
    store.save_workflow(identities["source"], WorkflowSaveBody(graph=_graph("source-definition")))
    source_results = store.get_storage_path(identities["source"])
    source_results.mkdir()
    (source_results / "result.txt").write_text("source", encoding="utf-8")

    duplicated = store.patch_workflow(
        identities["source"],
        WorkflowUpdate(
            action="duplicate",
            new_name="copy",
            display_name="Copy",
        ),
    )
    identities["copy"] = duplicated.id

    source = store.get_workflow(identities["source"])
    copy = store.get_workflow(identities["copy"])
    assert source.graph.name == "source-definition"
    assert copy.graph.name == "copy"
    assert copy.graph.display_name == "Copy"
    assert duplicated.id != identities["source"]
    assert duplicated.relative_path == "copy"
    assert not store.get_storage_path(identities["copy"]).exists()
    assert (store.get_storage_path(identities["source"]) / "result.txt").read_text() == "source"


def test_duplicate_copies_destination_owned_runtime_sources(tmp_path: Path) -> None:
    identities: dict[str, str] = {}
    store = _store(tmp_path)
    identities["source"] = store.create_workflow(WorkflowCreate(name="source")).id
    source_record = {"id": "embedded-tool-sha256", "module": "custom_tool", "filename": "custom_tool.py", "source": "class Tool: pass\n", "source_hash": hashlib.sha256(b"class Tool: pass\n").hexdigest()}
    sources = OwnedWorkflowSources(store.workflow_dir(identities["source"]))
    staged = sources.stage([source_record])
    sources.publish(staged)
    graph_payload = _graph("definition").model_dump(mode="json", by_alias=True)
    graph_payload["nodes"] = [
        {
            "type": "tool",
            "id": "tool",
            "name": "tool",
            "tool_name": "Tool",
            "position": (0.0, 0.0),
            "parameters": {},
            "source_module": source_record["id"],
        }
    ]
    graph = GraphState.model_validate(graph_payload)
    store.save_workflow(identities["source"], WorkflowSaveBody(graph=graph))

    identities["copy"] = store.patch_workflow(
        identities["source"],
        WorkflowUpdate(action="duplicate", new_name="copy"),
    ).id

    assert store.get_workflow(identities["copy"]).graph.nodes[0].source_module == source_record["id"]  # type: ignore[union-attr]
    assert OwnedWorkflowSources(store.workflow_dir(identities["copy"])).read(
        source_record["id"]
    ) == source_record


def _agent_owned_source(source_id: str, offset: int) -> dict[str, str]:
    source = f'''from bioimageflow import DataFrameTool
from bioimageflow_core import IOModel
import pandas as pd

class Outputs(IOModel):
    value: int

class AgentOwnedNumbers(DataFrameTool):
    accepts_upstream = False
    Outputs = Outputs

    def transform(self, df, arguments):
        return pd.DataFrame({{"value": [n + {offset} for n in [1, 2, 3]]}})
'''
    return {
        "id": source_id,
        "module": f"agent_owned_{offset}",
        "filename": f"agent_owned_{offset}.py",
        "source": source,
        "source_hash": hashlib.sha256(source.encode()).hexdigest(),
    }


def _agent_recursive_graph() -> GraphState:
    payload = _graph("agent-definition", "Agent recursive definition").model_dump(
        mode="json", by_alias=True
    )
    payload["nodes"] = [
        {
            "type": "tool",
            "id": "root-owned",
            "name": "Root owned source",
            "tool_name": "AgentOwnedNumbers",
            "tool_module": "agent_owned_1",
            "tool_class": "AgentOwnedNumbers",
            "source_module": "root-source",
            "position": (80.0, 140.0),
            "parameters": {},
        },
        {
            "type": "workflow",
            "id": "embedded-child",
            "name": "Embedded child",
            "position": (420.0, 140.0),
            "bindings": {},
            "workflow": {
                "schema_version": 1,
                "name": "embedded-definition",
                "display_name": "Embedded definition",
                "nodes": [
                    {
                        "type": "tool",
                        "id": "child-owned",
                        "name": "Child owned source",
                        "tool_name": "AgentOwnedNumbers",
                        "tool_module": "agent_owned_20",
                        "tool_class": "AgentOwnedNumbers",
                        "source_module": "child-source",
                        "position": (180.0, 120.0),
                        "parameters": {},
                    }
                ],
                "edges": [],
                "interface": {"inputs": [], "outputs": []},
                "config": {"engine": "direct", "execution": "sequential"},
            },
        },
    ]
    return GraphState.model_validate(payload)


@pytest.mark.parametrize("keep_canvas_first", [False, True])
def test_duplicate_agent_snapshot_copies_recursive_unsaved_sources(
    tmp_path: Path, keep_canvas_first: bool
) -> None:
    identities: dict[str, str] = {}
    store = _store(tmp_path)
    identities["source"] = store.create_workflow(WorkflowCreate(name="source")).id
    source_records = [
        _agent_owned_source("root-source", 1),
        _agent_owned_source("child-source", 20),
    ]
    sources = OwnedWorkflowSources(store.workflow_dir(identities["source"]))
    staged = sources.stage(source_records)
    sources.publish(staged)
    graph = _agent_recursive_graph()
    from bioimageflow_server.services.workflow_draft import WorkflowDraftService

    drafts = WorkflowDraftService(lambda: store)
    agent = drafts.put_draft(identities["source"], graph=graph, expected_revision=0, updated_by="agent")
    assert agent.validation.valid
    if keep_canvas_first:
        kept = drafts.put_draft(
            identities["source"],
            graph=_graph("source"),
            expected_revision=agent.draft_revision,
            updated_by="frontend",
        )
        agent = drafts.put_draft(
            identities["source"],
            graph=graph,
            expected_revision=kept.draft_revision,
            updated_by="agent",
        )
        assert agent.validation.valid
    original = store.get_workflow(identities["source"])
    original_document = (store.workflow_dir(identities["source"]) / "workflow.json").read_bytes()
    # This was the old frontend sequence: a graph-only save in an empty workflow.
    identities["broken_copy"] = store.create_workflow(WorkflowCreate(name="broken_copy")).id
    with pytest.raises(FileNotFoundError):
        store.save_workflow(identities["broken_copy"], WorkflowSaveBody(graph=agent.graph))

    identities["copy"] = store.patch_workflow(
        identities["source"],
        WorkflowUpdate(action="duplicate", new_name="copy", graph=agent.graph),
    ).id

    copy = store.get_workflow(identities["copy"])
    assert copy.graph.name == "copy"
    assert copy.graph.display_name == "copy"
    assert copy.graph.nodes[0].source_module == "root-source"  # type: ignore[union-attr]
    child = copy.graph.nodes[1]
    assert child.type == "workflow"
    assert child.workflow.name == "embedded-definition"
    assert child.workflow.nodes[0].source_module == "child-source"  # type: ignore[union-attr]
    copy_sources = OwnedWorkflowSources(store.workflow_dir(identities["copy"]))
    for record in source_records:
        assert copy_sources.read(record["id"]) == record
        assert copy_sources.source_path(record["id"]) != sources.source_path(record["id"])

    copy_child_path = copy_sources.source_path("child-source")
    copy_child_path.write_text(
        copy_child_path.read_text().replace("n + 20", "n + 40"),
        encoding="utf-8",
    )
    assert "n + 40" in copy_child_path.read_text(encoding="utf-8")
    assert sources.read("child-source") == source_records[1]
    assert store.get_workflow(identities["source"]).graph == original.graph
    assert (store.workflow_dir(identities["source"]) / "workflow.json").read_bytes() == original_document
    assert drafts.get_draft_snapshot(identities["source"]).draft_revision == agent.draft_revision
    assert drafts.get_draft_snapshot(identities["source"]).graph == agent.graph
    raw_copy = json.loads((store.workflow_dir(identities["copy"]) / "workflow.json").read_text())
    assert raw_copy["owned_source_ids"] == ["child-source", "root-source"]


def test_move_preserves_workspace_identity_definition_name_and_hash(tmp_path: Path) -> None:
    identities: dict[str, str] = {}
    store = _store(tmp_path)
    identities["source"] = store.create_workflow(WorkflowCreate(name="source")).id
    store.save_workflow(identities["source"], WorkflowSaveBody(graph=_graph("definition")))
    results = store.get_storage_path(identities["source"])
    results.mkdir()
    (results / "result.txt").write_text("result", encoding="utf-8")
    before = store.get_workflow(identities["source"])

    moved = _move_workflow(
        store,
        identities["source"],
        WorkflowUpdate(action="update", new_id="folder/moved"),
    )
    after = store.get_workflow(identities["source"])

    assert moved.id == identities["source"]
    assert moved.relative_path == "folder/moved"
    assert after.graph.name == "definition"
    assert after.artifact_hash == before.artifact_hash
    assert (store.get_storage_path(identities["source"]) / "result.txt").read_text() == "result"


def test_move_preserves_saved_workspace_provenance_and_hash(
    tmp_path: Path,
) -> None:
    identities: dict[str, str] = {}
    store = _store(tmp_path)
    identities["source"] = store.create_workflow(WorkflowCreate(name="source")).id
    source = store.get_workflow(identities["source"])
    identities["parent"] = store.create_workflow(WorkflowCreate(name="parent")).id
    parent = GraphState.model_validate(
        {
            **_graph("parent").model_dump(mode="json", by_alias=True),
            "nodes": [
                {
                    "type": "workflow",
                    "id": "embedded",
                    "name": "Embedded",
                    "workflow": source.graph.model_dump(mode="json", by_alias=True),
                    "bindings": {},
                    "position": [0, 0],
                    "source": {
                        "kind": "workspace",
                        "workflow_id": identities["source"],
                        "artifact_hash": source.artifact_hash,
                    },
                }
            ],
        }
    )
    store.save_workflow(identities["parent"], WorkflowSaveBody(graph=parent))
    before_hash = store.get_workflow(identities["parent"]).artifact_hash

    _move_workflow(
        store, identities["source"], WorkflowUpdate(action="update", new_id="folder/source")
    )

    loaded = store.get_workflow(identities["parent"])
    assert loaded.graph.nodes[0].source.workflow_id == identities["source"]  # type: ignore[union-attr]
    assert loaded.artifact_hash == before_hash


def test_direct_and_transitive_source_containment_cycles_are_rejected(
    tmp_path: Path,
) -> None:
    identities: dict[str, str] = {}
    from bioimageflow_server.services.workflow_draft import WorkflowDraftService

    store = _store(tmp_path)
    for name in ("a", "b"):
        identities[name] = store.create_workflow(WorkflowCreate(name=name)).id
    a = store.get_workflow(identities["a"])
    b_with_a = GraphState.model_validate(
        {
            **_graph("b").model_dump(mode="json", by_alias=True),
            "nodes": [
                {
                    "type": "workflow",
                    "id": "a-instance",
                    "name": "A",
                    "workflow": a.graph.model_dump(mode="json", by_alias=True),
                    "bindings": {},
                    "position": [0, 0],
                    "source": {
                        "kind": "workspace",
                        "workflow_id": identities["a"],
                        "artifact_hash": a.artifact_hash,
                    },
                }
            ],
        }
    )
    store.save_workflow(identities["b"], WorkflowSaveBody(graph=b_with_a))
    b = store.get_workflow(identities["b"])
    a_with_b = GraphState.model_validate(
        {
            **_graph("a").model_dump(mode="json", by_alias=True),
            "nodes": [
                {
                    "type": "workflow",
                    "id": "b-instance",
                    "name": "B",
                    "workflow": b.graph.model_dump(mode="json", by_alias=True),
                    "bindings": {},
                    "position": [0, 0],
                    "source": {
                        "kind": "workspace",
                        "workflow_id": identities["b"],
                        "artifact_hash": b.artifact_hash,
                    },
                }
            ],
        }
    )

    identities["unrelated"] = store.create_workflow(WorkflowCreate(name="unrelated")).id
    drafts = WorkflowDraftService(lambda: store)
    for workflow_id in ("a", "b", "unrelated"):
        saved = store.read_workflow_document(identities[workflow_id])
        # These persisted snapshots establish structural authority only.
        drafts.put_draft(
            identities[workflow_id],
            graph=saved.graph.model_copy(update={"display_name": f"Pending {workflow_id}"}),
            expected_revision=0,
            should_validate=False,
        )
        tools = store.workflow_dir(identities[workflow_id]) / "tools"
        tools.mkdir(exist_ok=True)
        (tools / "retained.py").write_bytes(f"# retained source: {workflow_id}\n".encode())
        results = store.get_storage_path(identities[workflow_id])
        results.mkdir()
        (results / "retained.bin").write_bytes(f"result: {workflow_id}".encode())
    foreign = tmp_path / "foreign-cycle.bin"
    foreign.write_bytes(b"unmanaged cycle sentinel")

    def authority(current_store, current_drafts, workflow_id):
        directory = current_store.workflow_dir(identities[workflow_id])
        return (
            current_store.read_workflow_document(identities[workflow_id]),
            current_drafts.get_draft_authority_snapshot(identities[workflow_id]),
            current_store.workflow_generation(identities[workflow_id]),
            {
                path.relative_to(directory).as_posix(): path.read_bytes()
                for path in directory.rglob("*") if path.is_file()
            },
        )

    retained = {
        workflow_id: authority(store, drafts, workflow_id)
        for workflow_id in ("a", "b", "unrelated")
    }
    foreign_bytes = foreign.read_bytes()

    with pytest.raises(
        ValueError, match=f"{identities['a']} -> b-instance -> a-instance -> source:{identities['a']}"
    ):
        store.save_workflow(identities["a"], WorkflowSaveBody(graph=a_with_b))
    for workflow_id, before in retained.items():
        assert authority(store, drafts, workflow_id) == before
    assert foreign.read_bytes() == foreign_bytes
    reopened = _store(tmp_path)
    reopened_drafts = WorkflowDraftService(lambda: reopened)
    for workflow_id, before in retained.items():
        assert authority(reopened, reopened_drafts, workflow_id) == before
    assert reopened.get_workflow(identities["a"]).graph == a.graph
    assert reopened.get_workflow(identities["b"]).graph == b_with_a
    assert foreign.read_bytes() == foreign_bytes


class _ArchiveAdapter:
    def __init__(self, imported: dict[str, Any] | None = None) -> None:
        self.imported = imported
        self.exported: dict[str, Any] | None = None

    def export_archive(
        self,
        workflow_data: dict[str, Any],
        archive_path: Path,
        *,
        storage_path: Path,
    ) -> None:
        assert storage_path.name == "results"
        self.exported = workflow_data
        archive_path.write_bytes(b"archive")

    def read_archive(
        self,
        archive_path: Path,
        *,
        extract_to: Path | None = None,
        storage_path: Path,
    ) -> dict[str, Any]:
        assert storage_path.name == "results"
        del archive_path, extract_to
        assert self.imported is not None
        return self.imported


def test_portable_export_is_generated_from_the_accepted_graph(tmp_path: Path) -> None:
    identities: dict[str, str] = {}
    adapter = _ArchiveAdapter()
    store = WorkflowStoreService(
        tmp_path / "workflows",
        ToolRegistryService(),
        archive_adapter=adapter,
    )
    identities["demo"] = store.create_workflow(WorkflowCreate(name="demo")).id

    filename, content = store.export_workflow_archive(identities["demo"])

    assert filename == "demo.bioimageflow.zip"
    assert content == b"archive"
    assert adapter.exported is not None
    assert adapter.exported["schema_version"] == 2
    assert "platform_document_version" not in adapter.exported


def test_nested_portable_export_uses_one_safe_archive_filename(tmp_path: Path) -> None:
    identities: dict[str, str] = {}
    adapter = _ArchiveAdapter()
    store = WorkflowStoreService(
        tmp_path / "workflows",
        ToolRegistryService(),
        archive_adapter=adapter,
    )
    identities["folder/demo"] = store.create_workflow(WorkflowCreate(name="folder/demo")).id

    filename, content = store.export_workflow_archive(identities["folder/demo"])

    assert filename.startswith("folder--demo-")
    assert filename.endswith(".bioimageflow.zip")
    assert "/" not in filename
    assert content == b"archive"


def test_results_bundle_is_rejected_before_archive_adapter_read(tmp_path: Path) -> None:
    adapter = _ArchiveAdapter(imported=None)
    store = WorkflowStoreService(
        tmp_path / "workflows",
        ToolRegistryService(),
        archive_adapter=adapter,
    )
    payload = BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("bioimageflow-results-bundle.json", "{}")
        archive.writestr("workflow/demo.bioimageflow.zip", b"nested")

    with pytest.raises(WorkflowResultsBundleImportError, match="export artifacts"):
        store.import_workflow_archive(
            payload.getvalue(),
            filename="renamed.bioimageflow.zip",
        )

    assert not (tmp_path / "workflows" / "renamed").exists()


def test_archive_import_rejects_unknown_graph_fields_without_persisting(tmp_path: Path) -> None:
    library = {
        "schema_version": 1,
        "name": "portable",
        "display_name": "Portable",
        "interface": {"inputs": [], "outputs": []},
        "nodes": [],
        "edges": [],
        "config": {
            "storage_path": "./bif_data",
            "engine": "direct",
            "execution": "parallel",
        },
    }
    adapter = _ArchiveAdapter(imported=library)
    store = WorkflowStoreService(
        tmp_path / "workflows",
        ToolRegistryService(),
        archive_adapter=adapter,
    )

    with pytest.raises(WorkflowArchiveError, match="Unknown workflow config field"):
        store.import_workflow_archive(
            b"archive", filename="portable.bioimageflow.zip"
        )
    assert not (store.root_dir / "portable").exists()


def test_duplicate_failure_does_not_publish_partial_copy(tmp_path: Path, monkeypatch) -> None:
    identities: dict[str, str] = {}
    import shutil

    from bioimageflow_server.services.workflow_artifacts import artifact_hash
    from bioimageflow_server.services.workflow_draft import WorkflowDraftService

    store = _store(tmp_path)
    drafts = WorkflowDraftService(lambda: store)
    for workflow_id in ("source", "occupied", "unrelated"):
        identities[workflow_id] = store.create_workflow(WorkflowCreate(name=workflow_id)).id
    records = [_agent_owned_source("root-source", 1), _agent_owned_source("child-source", 20)]
    sources = OwnedWorkflowSources(store.workflow_dir(identities["source"]))
    sources.publish(sources.stage(records))
    graph = _agent_recursive_graph()
    store.save_workflow(identities["source"], WorkflowSaveBody(graph=graph))
    root_source = sources.source_path("root-source")
    root_source.write_text(root_source.read_text().replace("n + 1", "n + 10"), encoding="utf-8")
    working_records = sources.collect_for_graph(graph)
    for workflow_id in ("source", "occupied", "unrelated"):
        saved = store.read_workflow_document(identities[workflow_id])
        # Structural authority is sufficient here; this test enters no runtime.
        drafts.put_draft(
            identities[workflow_id],
            graph=saved.graph.model_copy(update={"display_name": f"Pending {workflow_id}"}),
            expected_revision=0,
            should_validate=False,
        )
        result_dir = store.get_storage_path(identities[workflow_id])
        result_dir.mkdir()
        (result_dir / "preserved.bin").write_bytes(f"result:{workflow_id}".encode())
    foreign = tmp_path / "foreign.bin"
    foreign.write_bytes(b"unmanaged sentinel")

    def authority(current_store, current_drafts, workflow_id):
        directory = current_store.workflow_dir(identities[workflow_id])
        return (
            current_store.read_workflow_document(identities[workflow_id]),
            current_drafts.get_draft_authority_snapshot(identities[workflow_id]),
            current_store.workflow_generation(identities[workflow_id]),
            {
                path.relative_to(directory).as_posix(): path.read_bytes()
                for path in directory.rglob("*") if path.is_file()
            },
        )

    retained = {
        workflow_id: authority(store, drafts, workflow_id)
        for workflow_id in ("source", "occupied", "unrelated")
    }
    foreign_bytes = foreign.read_bytes()
    with pytest.raises(FileExistsError, match="occupied"):
        identities["occupied"] = store.patch_workflow(identities["source"], WorkflowUpdate(action="duplicate", new_name="occupied")).id
    for workflow_id, before in retained.items():
        assert authority(store, drafts, workflow_id) == before
    assert foreign.read_bytes() == foreign_bytes
    assert not list(store.root_dir.glob(".workflow-copy-*"))

    tools = store.workflow_dir(identities["source"]) / "tools"
    original_copytree = shutil.copytree
    staged_copies: list[Path] = []

    def fail_copy(source, destination, *args, **kwargs):
        # copytree recursively calls the patched symbol: interrupt only the
        # selected root after the genuine tools copy has fully populated it.
        result = original_copytree(source, destination, *args, **kwargs)
        if Path(source) == tools:
            staging = Path(destination).parent
            assert staging.name.startswith(".workflow-copy-")
            staged_sources = OwnedWorkflowSources(staging)
            assert staged_sources.collect_for_graph(graph) == working_records
            for record in working_records:
                assert staged_sources.source_path(record["id"]).read_bytes() == sources.source_path(
                    record["id"]
                ).read_bytes()
            staged_copies.append(staging)
            raise OSError("copy failed")
        return result

    generation_before = store.workflow_generation("copy")
    monkeypatch.setattr("bioimageflow_server.services.workflow_store.shutil.copytree", fail_copy)
    with pytest.raises(OSError, match="copy failed"):
        identities["copy"] = store.patch_workflow(identities["source"], WorkflowUpdate(action="duplicate", new_name="copy")).id
    assert len(staged_copies) == 1
    assert not staged_copies[0].exists()
    assert not (store.root_dir / "copy").exists()
    assert not list(store.root_dir.glob(".workflow-copy-*"))
    generation_after_failure = store.workflow_generation("copy")
    assert generation_after_failure >= generation_before
    for workflow_id, before in retained.items():
        assert authority(store, drafts, workflow_id) == before
    assert foreign.read_bytes() == foreign_bytes

    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_store.shutil.copytree", original_copytree
    )
    duplicated = store.patch_workflow(identities["source"], WorkflowUpdate(action="duplicate", new_name="copy"))
    identities["copy"] = duplicated.id
    assert duplicated.identity_generation > generation_after_failure
    reopened = _store(tmp_path)
    reopened_drafts = WorkflowDraftService(lambda: reopened)
    copy_document = reopened.read_workflow_document(identities["copy"])
    assert copy_document.graph == graph.model_copy(update={"name": "copy", "display_name": "copy"})
    assert copy_document.owned_source_ids == ["child-source", "root-source"]
    copy_sources = OwnedWorkflowSources(reopened.workflow_dir(identities["copy"]))
    assert copy_sources.collect_for_graph(copy_document.graph) == working_records
    for record in working_records:
        copied_path = copy_sources.source_path(record["id"])
        assert copied_path != sources.source_path(record["id"])
        assert copied_path.is_relative_to(reopened.workflow_dir(identities["copy"]))
        assert copied_path.read_bytes() == sources.source_path(record["id"]).read_bytes()
    assert copy_document.artifact_hash == artifact_hash(copy_document.graph, working_records)
    assert reopened.get_workflow(identities["copy"]).artifact_hash == copy_document.artifact_hash
    assert not reopened.get_storage_path(identities["copy"]).exists()
    assert not (reopened.workflow_dir(identities["copy"]) / ".bioimageflow" / "draft.json").exists()
    assert not list(reopened.root_dir.glob(".workflow-copy-*"))
    for workflow_id, before in retained.items():
        assert authority(reopened, reopened_drafts, workflow_id) == before
    assert foreign.read_bytes() == foreign_bytes


def test_duplicate_rejects_recreated_source_identity(tmp_path: Path) -> None:
    identities: dict[str, str] = {}
    from bioimageflow_server.services.workflow_draft import WorkflowDraftService

    store = _store(tmp_path)
    original = store.create_workflow(WorkflowCreate(name="source"))
    identities["source"] = original.id
    store.delete_workflow(identities["source"])
    recreated = store.create_workflow(WorkflowCreate(name="source"))
    identities["source"] = recreated.id
    assert recreated.id != original.id
    assert store.workflow_generation(original.id) > original.identity_generation
    identities["unrelated"] = store.create_workflow(WorkflowCreate(name="unrelated")).id
    drafts = WorkflowDraftService(lambda: store)
    for workflow_id in ("source", "unrelated"):
        graph = _graph(f"{workflow_id}-definition", f"Saved {workflow_id}")
        store.save_workflow(identities[workflow_id], WorkflowSaveBody(graph=graph))
        # The refusal concerns generation and structural persisted authority.
        drafts.put_draft(
            identities[workflow_id],
            graph=graph.model_copy(update={"display_name": f"Pending {workflow_id}"}),
            expected_revision=0,
            should_validate=False,
        )
        tools = store.workflow_dir(identities[workflow_id]) / "tools"
        tools.mkdir(exist_ok=True)
        (tools / "retained.py").write_bytes(f"# retained source: {workflow_id}\n".encode())
        results = store.get_storage_path(identities[workflow_id])
        results.mkdir()
        (results / "retained.bin").write_bytes(f"result: {workflow_id}".encode())
    foreign = tmp_path / "foreign-generation.bin"
    foreign.write_bytes(b"unmanaged generation sentinel")

    def authority(current_store, current_drafts, workflow_id):
        directory = current_store.workflow_dir(identities[workflow_id])
        return (
            current_store.read_workflow_document(identities[workflow_id]),
            current_drafts.get_draft_authority_snapshot(identities[workflow_id]),
            current_store.workflow_generation(identities[workflow_id]),
            {
                path.relative_to(directory).as_posix(): path.read_bytes()
                for path in directory.rglob("*") if path.is_file()
            },
        )

    retained = {
        workflow_id: authority(store, drafts, workflow_id)
        for workflow_id in ("source", "unrelated")
    }
    foreign_bytes = foreign.read_bytes()
    # Address the recreated authority through a fresh public store, while the
    # duplicate request deliberately retains its deleted incarnation's token.
    store = _store(tmp_path)
    reopened_drafts = WorkflowDraftService(lambda: store)
    for workflow_id, before in retained.items():
        assert authority(store, reopened_drafts, workflow_id) == before
    with pytest.raises(FileNotFoundError):
        identities["copy"] = store.patch_workflow(original.id, WorkflowUpdate(
            action="duplicate", new_name="copy", graph=_graph("snapshot"),
            expected_identity_generation=original.identity_generation,
        )).id
    assert not (store.root_dir / "copy").exists()
    assert not list(store.root_dir.glob(".workflow-copy-*"))
    for workflow_id, before in retained.items():
        assert authority(store, reopened_drafts, workflow_id) == before
    assert foreign.read_bytes() == foreign_bytes
    reopened = _store(tmp_path)
    final_drafts = WorkflowDraftService(lambda: reopened)
    for workflow_id, before in retained.items():
        assert authority(reopened, final_drafts, workflow_id) == before
    assert reopened.get_workflow(identities["source"]).info.identity_generation == recreated.identity_generation
    assert not (reopened.root_dir / "copy").exists()
    assert not list(reopened.root_dir.glob(".workflow-copy-*"))
    assert foreign.read_bytes() == foreign_bytes


def test_update_rejects_duplicate_only_graph() -> None:
    with pytest.raises(ValidationError, match="only supported when duplicating"):
        WorkflowUpdate(action="update", graph=_graph("snapshot"))
