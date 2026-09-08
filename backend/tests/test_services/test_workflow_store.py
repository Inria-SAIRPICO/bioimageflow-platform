"""Canonical workflow document persistence tests."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

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
    store.complete_workflow_move(operation_id)
    return result


def test_create_persists_one_canonical_document(tmp_path: Path) -> None:
    store = _store(tmp_path)
    info = store.create_workflow(
        WorkflowCreate(name="folder/demo", display_name="Demo", description="A workflow")
    )

    raw = json.loads(
        (tmp_path / "workflows" / "folder" / "demo" / "workflow.json").read_text()
    )

    assert set(raw) == {
        "platform_document_version",
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


def test_save_and_get_use_the_graph_as_display_authority(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="demo"))
    graph = _graph("definition", "Editable Label")

    store.save_workflow("demo", WorkflowSaveBody(graph=graph))
    loaded = store.get_workflow("demo")

    assert loaded.graph == graph
    assert loaded.info.display_name == "Editable Label"
    assert loaded.artifact_hash.startswith("sha256:")
    assert "display_name" not in store._read_raw("demo")["metadata"]


def test_unknown_persisted_sections_are_rejected_without_fallback(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="demo"))
    path = store.workflow_dir("demo") / "workflow.json"
    raw = json.loads(path.read_text())
    raw["derived"] = {"nodes": []}
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValidationError):
        store.get_workflow("demo")


def test_duplicate_assigns_new_definition_identity_atomically(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="source", display_name="Source"))
    store.save_workflow("source", WorkflowSaveBody(graph=_graph("source-definition")))
    source_results = store.get_storage_path("source")
    source_results.mkdir()
    (source_results / "result.txt").write_text("source", encoding="utf-8")

    duplicated = store.patch_workflow(
        "source",
        WorkflowUpdate(
            action="duplicate",
            new_name="copy",
            display_name="Copy",
        ),
    )

    source = store.get_workflow("source")
    copy = store.get_workflow("copy")
    assert source.graph.name == "source-definition"
    assert copy.graph.name == "copy"
    assert copy.graph.display_name == "Copy"
    assert duplicated.id == "copy"
    assert not store.get_storage_path("copy").exists()
    assert (store.get_storage_path("source") / "result.txt").read_text() == "source"


def test_duplicate_copies_destination_owned_runtime_sources(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="source"))
    source_record = {"id": "embedded-tool-sha256", "source": "class Tool: pass\n"}
    sources = OwnedWorkflowSources(store.workflow_dir("source"))
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
    store.save_workflow("source", WorkflowSaveBody(graph=graph))

    store.patch_workflow(
        "source",
        WorkflowUpdate(action="duplicate", new_name="copy"),
    )

    assert store.get_workflow("copy").graph.nodes[0].source_module == source_record["id"]  # type: ignore[union-attr]
    assert OwnedWorkflowSources(store.workflow_dir("copy")).read(
        source_record["id"]
    ) == source_record


@pytest.mark.parametrize("keep_canvas_first", [False, True])
def test_duplicate_agent_snapshot_copies_unsaved_sources(tmp_path: Path, keep_canvas_first: bool) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="source"))
    source_record = {"id": "embedded-tool-sha256", "source": "class Tool: pass\n"}
    sources = OwnedWorkflowSources(store.workflow_dir("source"))
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
    from bioimageflow_server.services.workflow_draft import WorkflowDraftService

    drafts = WorkflowDraftService(lambda: store)
    agent = drafts.put_draft("source", graph=graph, expected_revision=0, updated_by="agent")
    if keep_canvas_first:
        kept = drafts.put_draft(
            "source", graph=_graph("source"), expected_revision=agent.draft_revision,
            updated_by="frontend",
        )
        agent = drafts.put_draft(
            "source", graph=graph, expected_revision=kept.draft_revision, updated_by="agent",
        )
    original = store.get_workflow("source")
    # This was the old frontend sequence: a graph-only save in an empty workflow.
    store.create_workflow(WorkflowCreate(name="broken_copy"))
    with pytest.raises(FileNotFoundError):
        store.save_workflow("broken_copy", WorkflowSaveBody(graph=agent.graph))

    store.patch_workflow(
        "source",
        WorkflowUpdate(action="duplicate", new_name="copy", graph=agent.graph),
    )

    assert store.get_workflow("copy").graph.nodes[0].source_module == source_record["id"]  # type: ignore[union-attr]
    assert OwnedWorkflowSources(store.workflow_dir("copy")).read(
        source_record["id"]
    ) == source_record


    assert store.get_workflow("source").graph == original.graph
    assert drafts.get_draft_snapshot("source").draft_revision == agent.draft_revision
    raw_copy = json.loads((store.workflow_dir("copy") / "workflow.json").read_text())
    assert raw_copy["owned_source_ids"] == [source_record["id"]]


def test_move_changes_workspace_identity_not_definition_name_or_hash(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="source"))
    store.save_workflow("source", WorkflowSaveBody(graph=_graph("definition")))
    results = store.get_storage_path("source")
    results.mkdir()
    (results / "result.txt").write_text("result", encoding="utf-8")
    before = store.get_workflow("source")

    moved = _move_workflow(
        store,
        "source",
        WorkflowUpdate(action="update", new_id="folder/moved"),
    )
    after = store.get_workflow("folder/moved")

    assert moved.id == "folder/moved"
    assert after.graph.name == "definition"
    assert after.artifact_hash == before.artifact_hash
    assert (store.get_storage_path("folder/moved") / "result.txt").read_text() == "result"


def test_move_rewrites_saved_workspace_provenance_without_changing_hash(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="source"))
    source = store.get_workflow("source")
    store.create_workflow(WorkflowCreate(name="parent"))
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
                        "workflow_id": "source",
                        "artifact_hash": source.artifact_hash,
                    },
                }
            ],
        }
    )
    store.save_workflow("parent", WorkflowSaveBody(graph=parent))
    before_hash = store.get_workflow("parent").artifact_hash

    _move_workflow(
        store, "source", WorkflowUpdate(action="update", new_id="folder/source")
    )

    loaded = store.get_workflow("parent")
    assert loaded.graph.nodes[0].source.workflow_id == "folder/source"  # type: ignore[union-attr]
    assert loaded.artifact_hash == before_hash


def test_direct_and_transitive_source_containment_cycles_are_rejected(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    for name in ("a", "b"):
        store.create_workflow(WorkflowCreate(name=name))
    a = store.get_workflow("a")
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
                        "workflow_id": "a",
                        "artifact_hash": a.artifact_hash,
                    },
                }
            ],
        }
    )
    store.save_workflow("b", WorkflowSaveBody(graph=b_with_a))
    b = store.get_workflow("b")
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
                        "workflow_id": "b",
                        "artifact_hash": b.artifact_hash,
                    },
                }
            ],
        }
    )

    with pytest.raises(
        ValueError, match="a -> b-instance -> a-instance -> source:a"
    ):
        store.save_workflow("a", WorkflowSaveBody(graph=a_with_b))


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
    adapter = _ArchiveAdapter()
    store = WorkflowStoreService(
        tmp_path / "workflows",
        ToolRegistryService(),
        archive_adapter=adapter,
    )
    store.create_workflow(WorkflowCreate(name="demo"))

    filename, content = store.export_workflow_archive("demo")

    assert filename == "demo.bioimageflow.zip"
    assert content == b"archive"
    assert adapter.exported is not None
    assert adapter.exported["schema_version"] == 1
    assert "platform_document_version" not in adapter.exported


def test_nested_portable_export_uses_one_safe_archive_filename(tmp_path: Path) -> None:
    adapter = _ArchiveAdapter()
    store = WorkflowStoreService(
        tmp_path / "workflows",
        ToolRegistryService(),
        archive_adapter=adapter,
    )
    store.create_workflow(WorkflowCreate(name="folder/demo"))

    filename, content = store.export_workflow_archive("folder/demo")

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


def test_archive_import_persists_canonical_graph_only(tmp_path: Path) -> None:
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

    imported = store.import_workflow_archive(
        b"archive", filename="portable.bioimageflow.zip"
    )
    raw = store._read_raw("portable")

    assert imported.info.display_name == "Portable"
    assert raw["graph"]["name"] == "portable"
    assert "derived" not in raw
    assert "secondary_projection" not in raw


def test_duplicate_failure_does_not_publish_partial_copy(tmp_path: Path, monkeypatch) -> None:
    store = _store(tmp_path)
    store.create_workflow(WorkflowCreate(name="source"))
    tools = store.workflow_dir("source") / "tools"
    tools.mkdir(exist_ok=True)
    (tools / "tool.py").write_text("# editable tool")

    def fail_copy(*args, **kwargs):
        raise OSError("copy failed")

    monkeypatch.setattr("bioimageflow_server.services.workflow_store.shutil.copytree", fail_copy)
    with pytest.raises(OSError, match="copy failed"):
        store.patch_workflow("source", WorkflowUpdate(action="duplicate", new_name="copy"))
    assert not (store.root_dir / "copy").exists()
    assert not list(store.root_dir.glob(".workflow-copy-*"))


def test_duplicate_rejects_recreated_source_identity(tmp_path: Path) -> None:
    from bioimageflow_server.services.workflow_store import WorkflowIdentityGenerationConflictError

    store = _store(tmp_path)
    original = store.create_workflow(WorkflowCreate(name="source"))
    store.delete_workflow("source")
    store.create_workflow(WorkflowCreate(name="source"))
    with pytest.raises(WorkflowIdentityGenerationConflictError):
        store.patch_workflow("source", WorkflowUpdate(
            action="duplicate", new_name="copy", graph=_graph("snapshot"),
            expected_identity_generation=original.identity_generation,
        ))
    assert not (store.root_dir / "copy").exists()


def test_update_rejects_duplicate_only_graph() -> None:
    with pytest.raises(ValidationError, match="only supported when duplicating"):
        WorkflowUpdate(action="update", graph=_graph("snapshot"))
