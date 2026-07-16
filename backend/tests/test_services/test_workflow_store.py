"""Tests for workflow filesystem persistence."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from bioimageflow_server.models.graph import ColumnRefEdge, GraphState, NodeState
from bioimageflow_server.models.tools import PackageInfo, ToolMetadata
from bioimageflow_server.models.workflow import (
    ExportedWorkflow,
    WorkflowCreate,
    WorkflowExportDocument,
    WorkflowSaveBody,
    WorkflowUpdate,
)
from bioimageflow_server.models.workflow_draft import WorkflowDraftResponse
from bioimageflow_server.services.workflow_store import (
    WorkflowStoreService,
    normalize_workflow_draft_identity,
)
from bioimageflow_server.services.workflow_draft import WorkflowDraftService
from bioimageflow_server.services.tool_registry import ToolRegistryService


@pytest.fixture
def registry() -> ToolRegistryService:
    reg = ToolRegistryService()
    reg.register_package(
        "missing-pkg",
        PackageInfo(
            name="missing-pkg",
            installed_versions=["1.0.0"],
            active_version="1.0.0",
            tools={"1.0.0": ["ExistingTool"]},
        ),
    )
    return reg


@pytest.fixture
def store(tmp_path: Path, registry: ToolRegistryService) -> WorkflowStoreService:
    return WorkflowStoreService(
        root_dir=tmp_path / "workflows",
        tool_registry=registry,
        storage_base_dir=tmp_path / "outputs",
    )


class _FakeArchiveAdapter:
    def __init__(self, library: dict | None = None) -> None:
        self.library = library or {"nodes": [], "edges": []}
        self.export_calls: list[tuple[Path, Path]] = []
        self.import_calls: list[Path] = []
        self.extract_calls: list[Path] = []
        self.import_payload: bytes | None = None

    def export_archive(self, workflow_path: Path, archive_path: Path) -> None:
        self.export_calls.append((workflow_path, archive_path))
        archive_path.write_bytes(b"fake zip")

    def read_archive(self, archive_path: Path, *, extract_to: Path | None = None) -> dict:
        self.import_calls.append(archive_path)
        self.import_payload = archive_path.read_bytes()
        if extract_to is not None:
            self.extract_calls.append(extract_to)
            if zipfile.is_zipfile(archive_path):
                extract_to.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(archive_path) as archive:
                    archive.extractall(extract_to)
        return self.library


def _workflow_json(store: WorkflowStoreService, name: str) -> Path:
    return store.root_dir / name / "workflow.json"


def _draft_json(store: WorkflowStoreService, name: str) -> Path:
    return store.root_dir / name / ".bioimageflow" / "draft.json"


def _draft_payload(workflow_id: str, revision: int = 7) -> dict:
    return {
        "draft_version": 1,
        "workflow_id": workflow_id,
        "base_saved_revision": "sha256:saved-before-move",
        "draft_revision": revision,
        "updated_at": "2026-07-16T04:30:00Z",
        "updated_by": "agent",
        "dirty_against_saved": True,
        "graph": {
            "nodes": [
                {
                    "id": "draft-node",
                    "name": "Draft node",
                    "tool_name": "MissingTool",
                    "position": [12, 34],
                    "parameters": {"threshold": 0.75},
                    "enabled": True,
                    "collapsed": False,
                }
            ],
            "edges": [],
        },
        "validation": {
            "valid": False,
            "node_statuses": {
                "draft-node": {
                    "node_id": "draft-node",
                    "status": "out_of_date",
                    "cached": True,
                    "result_key": "cached-result",
                }
            },
            "errors": [
                {
                    "type": "missing_tool",
                    "detail": "MissingTool is unavailable",
                    "node": "draft-node",
                }
            ],
        },
        "future_compatible": {"preserve": [1, 2, 3]},
    }


def _write_draft(store: WorkflowStoreService, workflow_id: str, revision: int = 7) -> dict:
    payload = _draft_payload(workflow_id, revision)
    path = _draft_json(store, workflow_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _export_document(
    *,
    name: str = "imported",
    library: dict | None = None,
    graph: dict | None = None,
    gui: dict | None = None,
    metadata: dict | None = None,
) -> WorkflowExportDocument:
    return WorkflowExportDocument(
        exported_at="2026-04-30T10:30:00Z",
        workflow=ExportedWorkflow(
            name=name,
            display_name="Imported",
            description="desc",
            storage_path="/other/machine/outputs/imported",
            graph=graph or {"nodes": [], "edges": []},
            library=library or {"nodes": [], "edges": []},
            gui=gui or {"nodes": {}},
            metadata=metadata
            or {
                "display_name": "Imported",
                "description": "desc",
                "storage_path": "/other/machine/outputs/imported",
            },
        ),
        required_packages=[],
        local_tools=[],
    )


def test_create_list_and_get_empty_workflow(store: WorkflowStoreService) -> None:
    info = store.create_workflow(WorkflowCreate(name="wf", display_name="Workflow"))
    assert info.name == "wf"
    assert info.display_name == "Workflow"
    assert info.storage_path is not None
    assert info.path == str(_workflow_json(store, "wf"))
    assert _workflow_json(store, "wf").exists()
    assert (store.root_dir / "wf" / "tools").is_dir()
    assert not (store.root_dir / "wf" / "__init__.py").exists()
    assert not (store.root_dir / "wf.json").exists()
    assert [item.name for item in store.list_workflows()] == ["wf"]

    workflow = store.get_workflow("wf")
    assert workflow.info.name == "wf"
    assert workflow.graph == GraphState(nodes=[], edges=[])
    assert workflow.gui == {"nodes": {}}


def test_create_nested_workflow_and_tree(store: WorkflowStoreService) -> None:
    info = store.create_workflow(WorkflowCreate(name="segmentation/nuclei", display_name="Nuclei"))

    assert info.id == "segmentation/nuclei"
    assert info.name == "nuclei"
    assert info.folder == "segmentation"
    assert (store.root_dir / "segmentation" / "nuclei" / "workflow.json").exists()

    tree = store.workflow_tree()
    assert tree.folders[0].path == "segmentation"
    assert tree.folders[0].workflows[0].id == "segmentation/nuclei"


def test_workflow_folders_create_delete_and_rename(store: WorkflowStoreService) -> None:
    folder = store.create_folder("segmentation/quantification")
    assert folder.path == "segmentation/quantification"
    assert (store.root_dir / "segmentation" / "quantification").is_dir()

    renamed = store.rename_folder("segmentation/quantification", "analysis/intensity")
    assert renamed.path == "analysis/intensity"
    assert not (store.root_dir / "segmentation" / "quantification").exists()
    assert (store.root_dir / "analysis" / "intensity").is_dir()

    store.delete_folder("analysis/intensity")
    assert not (store.root_dir / "analysis" / "intensity").exists()


def test_workflow_folders_accept_spaces_and_move_children(
    store: WorkflowStoreService,
) -> None:
    folder = store.create_folder("My Project/Quality Control")
    assert folder.path == "My Project/Quality Control"
    assert (store.root_dir / "My Project" / "Quality Control").is_dir()

    store.create_workflow(
        WorkflowCreate(name="My Project/Quality Control/nuclei", display_name="Nuclei")
    )
    store.create_folder("Archive 2026")

    moved = store.rename_folder(
        "My Project/Quality Control",
        "Archive 2026/Quality Control",
    )

    assert moved.path == "Archive 2026/Quality Control"
    workflow = store.get_workflow("Archive 2026/Quality Control/nuclei").info
    assert workflow.id == "Archive 2026/Quality Control/nuclei"
    assert workflow.folder == "Archive 2026/Quality Control"


def test_delete_non_empty_folder_rejected(store: WorkflowStoreService) -> None:
    store.create_workflow(WorkflowCreate(name="segmentation/nuclei"))

    with pytest.raises(FileExistsError):
        store.delete_folder("segmentation")


def test_workflow_tree_ignores_workflow_internal_tools_folder(
    store: WorkflowStoreService,
) -> None:
    store.create_workflow(WorkflowCreate(name="Untitled"))
    nested_tool_file = store.root_dir / "Untitled" / "tools" / "helper" / "workflow.json"
    nested_tool_file.parent.mkdir(parents=True)
    nested_tool_file.write_text(json.dumps({"metadata": {"display_name": "Not a workflow"}}))

    tree = store.workflow_tree()

    assert [folder.path for folder in tree.folders] == []
    assert [workflow.id for workflow in tree.workflows] == ["Untitled"]
    assert [workflow.id for workflow in store.list_workflows()] == ["Untitled"]


def test_folder_api_rejects_workflow_internal_paths(store: WorkflowStoreService) -> None:
    store.create_workflow(WorkflowCreate(name="Untitled"))
    store.create_folder("reports")

    with pytest.raises(ValueError):
        store.create_folder("Untitled/tools/custom")
    with pytest.raises(FileNotFoundError):
        store.delete_folder("Untitled/tools")
    with pytest.raises(ValueError):
        store.rename_folder("reports", "Untitled/reports")

    assert (store.root_dir / "reports").is_dir()
    assert not (store.root_dir / "Untitled" / "tools" / "custom").exists()


def test_delete_folder_can_move_children_up(store: WorkflowStoreService) -> None:
    store.create_workflow(WorkflowCreate(name="segmentation/nuclei"))
    store.create_folder("segmentation/reports")

    store.delete_folder("segmentation", "move_children_up")

    assert (store.root_dir / "nuclei" / "workflow.json").exists()
    assert (store.root_dir / "reports").is_dir()
    assert not (store.root_dir / "segmentation").exists()


def test_delete_folder_can_delete_children(store: WorkflowStoreService) -> None:
    store.create_workflow(WorkflowCreate(name="segmentation/nuclei"))
    store.create_folder("segmentation/reports")

    store.delete_folder("segmentation", "delete_children")

    assert not (store.root_dir / "segmentation").exists()


def test_folder_can_move_into_another_folder(store: WorkflowStoreService) -> None:
    store.create_folder("segmentation/reports")
    store.create_folder("archive")

    moved = store.rename_folder("segmentation/reports", "archive/reports")

    assert moved.path == "archive/reports"
    assert (store.root_dir / "archive" / "reports").is_dir()
    assert not (store.root_dir / "segmentation" / "reports").exists()


def test_folder_move_updates_child_workflow_ids_and_managed_storage(
    store: WorkflowStoreService,
) -> None:
    info = store.create_workflow(WorkflowCreate(name="segmentation/nuclei"))
    nested_tool_file = (
        store.root_dir / "segmentation" / "nuclei" / "tools" / "helper" / "workflow.json"
    )
    nested_tool_file.parent.mkdir(parents=True)
    nested_tool_file.write_text("not a platform workflow")
    storage_path = Path(info.storage_path)
    storage_path.mkdir(parents=True)
    (storage_path / "result.txt").write_text("ok")

    store.rename_folder("segmentation", "analysis")

    moved = store.get_workflow("analysis/nuclei").info
    assert moved.id == "analysis/nuclei"
    assert moved.folder == "analysis"
    assert Path(moved.storage_path) == store.storage_base_dir / "analysis" / "nuclei"
    assert (Path(moved.storage_path) / "result.txt").read_text() == "ok"
    assert not storage_path.exists()
    with pytest.raises(FileNotFoundError):
        store.get_workflow("segmentation/nuclei")


def test_delete_folder_move_children_up_updates_workflow_storage(
    store: WorkflowStoreService,
) -> None:
    info = store.create_workflow(WorkflowCreate(name="segmentation/nuclei"))
    storage_path = Path(info.storage_path)
    storage_path.mkdir(parents=True)
    (storage_path / "result.txt").write_text("ok")

    store.delete_folder("segmentation", "move_children_up")

    moved = store.get_workflow("nuclei").info
    assert moved.id == "nuclei"
    assert moved.folder == ""
    assert Path(moved.storage_path) == store.storage_base_dir / "nuclei"
    assert (Path(moved.storage_path) / "result.txt").read_text() == "ok"
    assert not storage_path.exists()


def test_delete_folder_delete_children_removes_managed_storage(
    store: WorkflowStoreService,
) -> None:
    info = store.create_workflow(WorkflowCreate(name="segmentation/nuclei"))
    storage_path = Path(info.storage_path)
    storage_path.mkdir(parents=True)

    store.delete_folder("segmentation", "delete_children")

    assert not storage_path.exists()


def test_folder_cannot_move_into_itself(store: WorkflowStoreService) -> None:
    store.create_folder("segmentation/reports")

    with pytest.raises(ValueError):
        store.rename_folder("segmentation", "segmentation/reports/archive")


def test_move_workflow_between_folders(store: WorkflowStoreService) -> None:
    store.create_workflow(WorkflowCreate(name="segmentation/nuclei"))

    moved = store.patch_workflow(
        "segmentation/nuclei",
        WorkflowUpdate(action="update", folder="analysis"),
    )

    assert moved.id == "analysis/nuclei"
    assert moved.identity_generation == 1
    assert store.workflow_generation("segmentation/nuclei") == 2
    assert (store.root_dir / "analysis" / "nuclei" / "workflow.json").exists()
    assert not (store.root_dir / "segmentation" / "nuclei").exists()


def test_direct_workflow_move_rewrites_only_existing_draft_identity(
    store: WorkflowStoreService,
) -> None:
    old_id = "segmentation/nuclei"
    new_id = "analysis/renamed-nuclei"
    store.create_workflow(WorkflowCreate(name=old_id))
    original = _write_draft(store, old_id)

    moved = store.patch_workflow(
        old_id,
        WorkflowUpdate(action="update", new_id=new_id),
    )

    expected = {**original, "workflow_id": new_id}
    assert moved.id == new_id
    assert json.loads(_draft_json(store, new_id).read_text(encoding="utf-8")) == expected
    snapshot = WorkflowDraftService(lambda: store).get_draft_snapshot(new_id)
    assert snapshot == WorkflowDraftResponse.model_validate(expected)
    assert not store.workflow_dir(old_id).exists()
    assert not _draft_json(store, old_id).exists()
    with pytest.raises(FileNotFoundError):
        store.get_workflow(old_id)


def test_folder_move_rewrites_all_child_draft_identities(
    store: WorkflowStoreService,
) -> None:
    moves = {
        "project/one": "archive/moved/one",
        "project/nested/two": "archive/moved/nested/two",
    }
    originals: dict[str, dict] = {}
    for revision, old_id in enumerate(moves, start=3):
        store.create_workflow(WorkflowCreate(name=old_id))
        originals[old_id] = _write_draft(store, old_id, revision)
    no_draft_old_id = "project/no-draft"
    no_draft_new_id = "archive/moved/no-draft"
    store.create_workflow(WorkflowCreate(name=no_draft_old_id))

    store.rename_folder("project", "archive/moved")

    for old_id, new_id in moves.items():
        expected = {**originals[old_id], "workflow_id": new_id}
        assert json.loads(_draft_json(store, new_id).read_text(encoding="utf-8")) == expected
        assert WorkflowDraftService(lambda: store).get_draft_snapshot(new_id).workflow_id == new_id
        assert not _draft_json(store, old_id).exists()
    assert not _draft_json(store, no_draft_old_id).exists()
    assert not _draft_json(store, no_draft_new_id).exists()


def test_delete_folder_promotes_child_drafts_with_new_identities(
    store: WorkflowStoreService,
) -> None:
    moves = {
        "project/one": "one",
        "project/nested/two": "nested/two",
    }
    originals: dict[str, dict] = {}
    for revision, old_id in enumerate(moves, start=8):
        store.create_workflow(WorkflowCreate(name=old_id))
        originals[old_id] = _write_draft(store, old_id, revision)

    store.delete_folder("project", "move_children_up")

    for old_id, new_id in moves.items():
        expected = {**originals[old_id], "workflow_id": new_id}
        assert json.loads(_draft_json(store, new_id).read_text(encoding="utf-8")) == expected
        assert not _draft_json(store, old_id).exists()


def test_moving_workflow_without_draft_does_not_create_one(
    store: WorkflowStoreService,
) -> None:
    old_id = "project/no-draft"
    new_id = "archive/no-draft"
    store.create_workflow(WorkflowCreate(name=old_id))
    assert not _draft_json(store, old_id).exists()

    store.patch_workflow(
        old_id,
        WorkflowUpdate(action="update", new_id=new_id),
    )

    assert not _draft_json(store, old_id).exists()
    assert not _draft_json(store, new_id).exists()


def test_direct_move_rejects_malformed_draft_before_moving_workflow(
    store: WorkflowStoreService,
) -> None:
    old_id = "project/malformed"
    new_id = "archive/malformed"
    store.create_workflow(WorkflowCreate(name=old_id))
    draft_path = _draft_json(store, old_id)
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        store.patch_workflow(
            old_id,
            WorkflowUpdate(action="update", new_id=new_id),
        )

    assert store.get_workflow(old_id).info.id == old_id
    assert draft_path.read_text(encoding="utf-8") == "{not-json"
    assert not store.workflow_dir(new_id).exists()


def test_folder_move_preflights_all_child_drafts_before_renaming(
    store: WorkflowStoreService,
) -> None:
    workflow_ids = ["project/one", "project/nested/two"]
    for workflow_id in workflow_ids:
        store.create_workflow(WorkflowCreate(name=workflow_id))
        _write_draft(store, workflow_id)
    invalid_path = _draft_json(store, "project/nested/two")
    invalid_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a JSON object"):
        store.rename_folder("project", "archive/moved")

    for workflow_id in workflow_ids:
        assert store.get_workflow(workflow_id).info.id == workflow_id
    assert (
        json.loads(_draft_json(store, "project/one").read_text(encoding="utf-8"))["workflow_id"]
        == "project/one"
    )
    assert invalid_path.read_text(encoding="utf-8") == "[]"
    assert not (store.root_dir / "archive" / "moved").exists()


def test_draft_identity_repair_cleans_temp_file_when_replace_fails(
    store: WorkflowStoreService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_id = "project/repair"
    store.create_workflow(WorkflowCreate(name=workflow_id))
    draft_path = _draft_json(store, workflow_id)
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    original = _draft_payload("legacy/location")
    draft_path.write_text(json.dumps(original, indent=2), encoding="utf-8")

    def fail_replace(_source: str, _target: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("bioimageflow_server.services.workflow_store.os.replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        normalize_workflow_draft_identity(store.workflow_dir(workflow_id), workflow_id)

    assert json.loads(draft_path.read_text(encoding="utf-8")) == original
    assert not list(draft_path.parent.glob(".draft.json.*.tmp"))


def test_move_workflow_to_folder_with_spaces(store: WorkflowStoreService) -> None:
    store.create_workflow(WorkflowCreate(name="segmentation/nuclei"))
    store.create_folder("Analysis Results")

    moved = store.patch_workflow(
        "segmentation/nuclei",
        WorkflowUpdate(action="update", folder="Analysis Results"),
    )

    assert moved.id == "Analysis Results/nuclei"
    assert moved.folder == "Analysis Results"
    assert (store.root_dir / "Analysis Results" / "nuclei" / "workflow.json").exists()


def test_get_storage_path_reads_metadata_directly(store: WorkflowStoreService) -> None:
    info = store.create_workflow(WorkflowCreate(name="wf"))

    assert store.get_storage_path("wf") == Path(info.storage_path)


def test_create_workflow_anchors_relative_storage_path_once(
    store: WorkflowStoreService,
) -> None:
    info = store.create_workflow(WorkflowCreate(name="wf", storage_path="relative-results"))

    expected = Path.cwd() / "relative-results"
    assert info.storage_path == str(expected)
    assert store.get_storage_path("wf") == expected

    raw = json.loads(_workflow_json(store, "wf").read_text())
    assert raw["metadata"]["storage_path"] == str(expected)
    assert raw["workflow"]["config"]["storage_path"] == str(expected)


def test_save_preserves_invalid_graph_losslessly(store: WorkflowStoreService) -> None:
    store.create_workflow(WorkflowCreate(name="wf"))
    graph = GraphState(
        nodes=[
            NodeState(
                id="bad",
                name="Bad",
                tool_name="MissingTool",
                position=(12, 34),
                parameters={"value": 1},
            )
        ],
        edges=[],
    )

    store.save_workflow("wf", WorkflowSaveBody(graph=graph))
    restored = store.get_workflow("wf")

    assert restored.graph == graph
    assert restored.missing_tools == []
    raw = json.loads(_workflow_json(store, "wf").read_text())
    assert raw["graph"]["nodes"][0]["tool_name"] == "MissingTool"
    assert raw["workflow"]["nodes"] == []


def test_stray_json_files_are_ignored_without_side_effects(
    store: WorkflowStoreService,
) -> None:
    raw = {
        "workflow": {
            "nodes": [
                {
                    "name": "n1",
                    "tool_class": "RemovedTool",
                    "tool_package": "missing-pkg",
                    "tool_package_version": "9.9.9",
                    "constants": {},
                }
            ],
            "edges": [],
        },
        "gui": {"nodes": {"n1": {"position": [1, 2]}}},
        "metadata": {"display_name": "Not a platform workflow"},
    }
    store.root_dir.mkdir(parents=True, exist_ok=True)
    stray_path = store.root_dir / "stray.json"
    stray_workflow_path = store.root_dir / "stray.workflow.json"
    stray_path.write_text(json.dumps(raw), encoding="utf-8")
    stray_workflow_path.write_text(json.dumps(raw), encoding="utf-8")

    assert store.list_workflows() == []
    with pytest.raises(FileNotFoundError):
        store.get_workflow("stray")

    assert stray_path.exists()
    assert stray_workflow_path.exists()
    assert not _workflow_json(store, "stray").exists()


def test_create_workflow_ignores_stray_json_file_collision(
    store: WorkflowStoreService,
) -> None:
    store.root_dir.mkdir(parents=True)
    stray = store.root_dir / "wf.json"
    stray.write_text("{}", encoding="utf-8")

    info = store.create_workflow(WorkflowCreate(name="wf", display_name="Workflow"))

    assert info.id == "wf"
    assert stray.exists()
    assert _workflow_json(store, "wf").exists()


def test_delete_workflow_requires_current_layout_and_leaves_stray_json(
    store: WorkflowStoreService,
) -> None:
    store.root_dir.mkdir(parents=True)
    stray = store.root_dir / "wf.json"
    stray.write_text("{}", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        store.delete_workflow("wf")

    assert stray.exists()
    assert not _workflow_json(store, "wf").exists()


def test_folder_rename_moves_regular_json_files_without_treating_them_as_workflows(
    store: WorkflowStoreService,
) -> None:
    info = store.create_workflow(WorkflowCreate(name="Analysis Results/nuclei"))
    storage_path = Path(info.storage_path)
    storage_path.mkdir(parents=True)
    (storage_path / "result.txt").write_text("ok")
    notes = store.root_dir / "Analysis Results" / "notes.json"
    notes.write_text('{"kind": "notes"}', encoding="utf-8")
    unrelated_storage = store.storage_base_dir / "Analysis Results" / "notes"
    unrelated_storage.mkdir(parents=True)

    store.rename_folder("Analysis Results", "Archive 2026")

    workflow = store.get_workflow("Archive 2026/nuclei").info
    assert workflow.id == "Archive 2026/nuclei"
    assert Path(workflow.storage_path) == store.storage_base_dir / "Archive 2026" / "nuclei"
    assert (Path(workflow.storage_path) / "result.txt").read_text() == "ok"
    assert not storage_path.exists()
    assert (store.root_dir / "Archive 2026" / "notes.json").read_text(
        encoding="utf-8"
    ) == '{"kind": "notes"}'
    assert unrelated_storage.exists()


def test_delete_folder_delete_children_removes_storage_only_for_current_workflows(
    store: WorkflowStoreService,
) -> None:
    info = store.create_workflow(WorkflowCreate(name="Analysis Results/nuclei"))
    storage_path = Path(info.storage_path)
    storage_path.mkdir(parents=True)
    unrelated_storage = store.storage_base_dir / "Analysis Results" / "notes"
    unrelated_storage.mkdir(parents=True)
    notes = store.root_dir / "Analysis Results" / "notes.json"
    notes.write_text("{}", encoding="utf-8")

    store.delete_folder("Analysis Results", "delete_children")

    assert not storage_path.exists()
    assert unrelated_storage.exists()
    assert not (store.root_dir / "Analysis Results").exists()


def test_duplicate_and_update_metadata(store: WorkflowStoreService) -> None:
    store.create_workflow(WorkflowCreate(name="wf", display_name="Workflow"))
    source_tool = store.root_dir / "wf" / "tools" / "custom_tool.py"
    source_tool.write_text("VALUE = 1\n", encoding="utf-8")

    updated = store.patch_workflow(
        "wf",
        WorkflowUpdate(action="update", display_name="Renamed", description="desc"),
    )
    assert updated.display_name == "Renamed"
    assert updated.description == "desc"

    duplicate = store.patch_workflow(
        updated.name,
        WorkflowUpdate(action="duplicate", new_name="copy", display_name="Copy"),
    )
    assert duplicate.name == "copy"
    assert duplicate.display_name == "Copy"
    assert store.get_workflow("copy").info.name == "copy"
    assert (store.root_dir / "copy" / "tools" / "custom_tool.py").read_text(
        encoding="utf-8"
    ) == "VALUE = 1\n"

    duplicate_custom = store.patch_workflow(
        updated.name,
        WorkflowUpdate(
            action="duplicate",
            new_name="copy_custom",
            storage_path="copy-relative-results",
        ),
    )
    assert duplicate_custom.storage_path == str(Path.cwd() / "copy-relative-results")


def test_display_name_update_preserves_identity_and_managed_storage(
    store: WorkflowStoreService,
) -> None:
    info = store.create_workflow(WorkflowCreate(name="Untitled", display_name="Untitled"))
    old_storage = Path(info.storage_path)
    old_storage.mkdir(parents=True)
    marker = old_storage / "result.txt"
    marker.write_text("kept", encoding="utf-8")

    updated = store.patch_workflow(
        "Untitled",
        WorkflowUpdate(action="update", display_name="New workflow"),
    )

    assert updated.id == "Untitled"
    assert updated.name == "Untitled"
    assert updated.display_name == "New workflow"
    assert _workflow_json(store, "Untitled").exists()
    assert not (store.root_dir / "new_workflow").exists()
    assert updated.storage_path == str(old_storage)
    assert marker.read_text() == "kept"
    raw = json.loads(_workflow_json(store, "Untitled").read_text())
    assert raw["metadata"]["storage_path"] == str(old_storage)
    assert raw["workflow"]["config"]["storage_path"] == str(old_storage)


def test_display_name_update_ignores_unrelated_managed_storage_collision(
    store: WorkflowStoreService,
) -> None:
    info = store.create_workflow(WorkflowCreate(name="Untitled", display_name="Untitled"))
    old_storage = Path(info.storage_path)
    target_storage = store.storage_base_dir / "new_workflow"
    target_storage.mkdir(parents=True)

    updated = store.patch_workflow(
        "Untitled",
        WorkflowUpdate(action="update", display_name="New workflow"),
    )

    assert updated.id == "Untitled"
    assert updated.display_name == "New workflow"
    assert not old_storage.exists()
    assert _workflow_json(store, "Untitled").exists()
    assert not (store.root_dir / "new_workflow").exists()
    assert target_storage.exists()


def test_display_name_update_preserves_custom_storage_path(
    tmp_path: Path,
    store: WorkflowStoreService,
) -> None:
    custom_storage = tmp_path / "external-results"
    store.create_workflow(
        WorkflowCreate(
            name="Untitled",
            display_name="Untitled",
            storage_path=str(custom_storage),
        )
    )

    updated = store.patch_workflow(
        "Untitled",
        WorkflowUpdate(action="update", display_name="New workflow"),
    )

    assert updated.name == "Untitled"
    assert updated.storage_path == str(custom_storage)


def test_update_workflow_anchors_relative_storage_path_once(
    store: WorkflowStoreService,
) -> None:
    store.create_workflow(WorkflowCreate(name="wf"))

    updated = store.patch_workflow(
        "wf",
        WorkflowUpdate(action="update", storage_path="updated-relative-results"),
    )

    expected = Path.cwd() / "updated-relative-results"
    assert updated.storage_path == str(expected)
    raw = json.loads(_workflow_json(store, "wf").read_text())
    assert raw["metadata"]["storage_path"] == str(expected)
    assert raw["workflow"]["config"]["storage_path"] == str(expected)


def test_display_name_update_with_custom_storage_ignores_managed_target_collision(
    tmp_path: Path,
    store: WorkflowStoreService,
) -> None:
    custom_storage = tmp_path / "external-results"
    store.create_workflow(
        WorkflowCreate(
            name="Untitled",
            display_name="Untitled",
            storage_path=str(custom_storage),
        )
    )
    target_storage = store.storage_base_dir / "new_workflow"
    target_storage.mkdir(parents=True)

    updated = store.patch_workflow(
        "Untitled",
        WorkflowUpdate(action="update", display_name="New workflow"),
    )

    assert updated.id == "Untitled"
    assert updated.display_name == "New workflow"
    assert updated.storage_path == str(custom_storage)
    assert target_storage.exists()


def test_display_name_update_without_valid_slug_keeps_canonical_identity(
    store: WorkflowStoreService,
) -> None:
    info = store.create_workflow(WorkflowCreate(name="Untitled", display_name="Untitled"))

    updated = store.patch_workflow(
        "Untitled",
        WorkflowUpdate(action="update", display_name="测试"),
    )

    assert updated.name == "Untitled"
    assert updated.display_name == "测试"
    assert updated.storage_path == info.storage_path
    assert _workflow_json(store, "Untitled").exists()
    assert not (store.root_dir / ".json").exists()
    raw = json.loads(_workflow_json(store, "Untitled").read_text())
    assert raw["metadata"]["display_name"] == "测试"
    assert raw["metadata"]["storage_path"] == info.storage_path
    assert raw["workflow"]["config"]["storage_path"] == info.storage_path


def test_save_after_display_name_update_retains_graph_edges(store: WorkflowStoreService) -> None:
    store.create_workflow(WorkflowCreate(name="Untitled", display_name="Untitled"))
    graph = GraphState(
        nodes=[
            NodeState(
                id="a",
                name="A",
                tool_name="MissingSource",
                position=(0, 0),
                parameters={},
            ),
            NodeState(
                id="b",
                name="B",
                tool_name="MissingTarget",
                position=(100, 0),
                parameters={},
            ),
        ],
        edges=[
            ColumnRefEdge(
                id="e1",
                source_node="a",
                target_node="b",
                source_output="result",
                target_input="image",
            )
        ],
    )

    renamed = store.patch_workflow(
        "Untitled",
        WorkflowUpdate(action="update", display_name="New workflow"),
    )
    store.save_workflow(renamed.name, WorkflowSaveBody(graph=graph))
    restored = store.get_workflow(renamed.name)

    assert restored.graph.edges == graph.edges


def test_delete_removes_only_managed_storage(
    tmp_path: Path,
    store: WorkflowStoreService,
) -> None:
    store.create_workflow(
        WorkflowCreate(
            name="wf",
            storage_path=str(tmp_path / "external"),
        )
    )
    managed = store.storage_base_dir / "wf"
    managed.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()

    store.delete_workflow("wf")

    assert not (store.root_dir / "wf").exists()
    assert not managed.exists()
    assert external.exists()


def test_suggest_name(store: WorkflowStoreService) -> None:
    store.create_workflow(WorkflowCreate(name="wf"))
    store.create_workflow(WorkflowCreate(name="wf_2"))
    assert store.suggest_name("wf") == "wf_3"


def test_suggest_name_skips_managed_storage_collisions(
    store: WorkflowStoreService,
) -> None:
    store.create_workflow(WorkflowCreate(name="wf"))
    (store.storage_base_dir / "wf_2").mkdir(parents=True)

    assert store.suggest_name("wf") == "wf_3"


def test_export_workflow_preserves_raw_sections_and_required_packages(
    store: WorkflowStoreService,
) -> None:
    raw = {
        "graph": {
            "nodes": [
                {
                    "id": "n1",
                    "name": "Node",
                    "tool_name": "ExistingTool",
                    "position": [1, 2],
                    "parameters": {},
                }
            ],
            "edges": [],
            "sub_workflow": {"kept": True},
        },
        "workflow": {
            "nodes": [
                {
                    "name": "n1",
                    "tool_class": "ExistingTool",
                    "tool_package": "missing-pkg",
                    "tool_package_version": "1.0.0",
                },
                {
                    "name": "n2",
                    "tool_class": "ExistingTool",
                    "tool_package": "missing-pkg",
                    "tool_package_version": "1.0.0",
                },
            ],
            "edges": [],
        },
        "gui": {"nodes": {"n1": {"position": [1, 2]}}},
        "metadata": {
            "display_name": "Workflow",
            "description": "desc",
            "storage_path": "/tmp/old",
        },
    }
    store.root_dir.mkdir(parents=True, exist_ok=True)
    _workflow_json(store, "wf").parent.mkdir(parents=True)
    _workflow_json(store, "wf").write_text(json.dumps(raw), encoding="utf-8")

    document = store.export_workflow("wf")

    assert _workflow_json(store, "wf").exists()
    assert document.bioimageflow_export is True
    assert document.export_version == "1.0"
    assert document.workflow.name == "wf"
    assert document.workflow.graph == raw["graph"]
    assert document.workflow.library == raw["workflow"]
    assert document.workflow.gui == raw["gui"]
    assert document.workflow.metadata == raw["metadata"]
    assert [item.model_dump() for item in document.required_packages] == [
        {"name": "missing-pkg", "version": "1.0.0"}
    ]
    assert document.local_tools == []


def test_export_workflow_falls_back_to_registry_and_marks_local_tools(
    store: WorkflowStoreService,
    registry: ToolRegistryService,
) -> None:
    registry.register_tool(
        "RegistryTool",
        ToolMetadata(
            name="RegistryTool",
            display_name="Registry Tool",
            package="registry-pkg",
            package_version="2.0.0",
            tool_type="ProcessingTool",
        ),
    )
    raw = {
        "graph": {"nodes": [], "edges": []},
        "workflow": {
            "nodes": [
                {"name": "registry_1", "tool_class": "RegistryTool"},
                {"name": "local_1", "tool_class": "LocalTool"},
                {"name": "local_2", "tool_class": "LocalTool"},
            ],
            "edges": [],
        },
        "gui": {"nodes": {}},
        "metadata": {"display_name": "Workflow"},
    }
    store.root_dir.mkdir(parents=True, exist_ok=True)
    _workflow_json(store, "wf").parent.mkdir(parents=True)
    _workflow_json(store, "wf").write_text(json.dumps(raw), encoding="utf-8")

    document = store.export_workflow("wf")

    assert [item.model_dump() for item in document.required_packages] == [
        {"name": "registry-pkg", "version": "2.0.0"}
    ]
    assert len(document.local_tools) == 1
    assert document.local_tools[0].tool_name == "LocalTool"
    assert document.local_tools[0].node_ids == ["local_1", "local_2"]


def test_export_workflow_marks_graph_only_local_tools(
    store: WorkflowStoreService,
) -> None:
    raw = {
        "graph": {
            "nodes": [
                {
                    "id": "local_1",
                    "name": "Local",
                    "tool_name": "LocalTool",
                    "position": [0, 0],
                    "parameters": {},
                }
            ],
            "edges": [],
        },
        "workflow": {"nodes": [], "edges": []},
        "gui": {"nodes": {}},
        "metadata": {"display_name": "Workflow"},
    }
    store.root_dir.mkdir(parents=True, exist_ok=True)
    _workflow_json(store, "wf").parent.mkdir(parents=True)
    _workflow_json(store, "wf").write_text(json.dumps(raw), encoding="utf-8")

    document = store.export_workflow("wf")

    assert document.required_packages == []
    assert len(document.local_tools) == 1
    assert document.local_tools[0].tool_name == "LocalTool"
    assert document.local_tools[0].node_ids == ["local_1"]


def test_export_workflow_collects_nested_sub_workflow_packages(
    store: WorkflowStoreService,
) -> None:
    raw = {
        "graph": {"nodes": [], "edges": []},
        "workflow": {
            "nodes": [
                {
                    "name": "sub_1",
                    "tool_class": "__sub_workflow__",
                    "sub_workflow": {
                        "nodes": [
                            {
                                "name": "inner_1",
                                "tool_class": "InnerTool",
                                "tool_package": "inner-pkg",
                                "tool_package_version": "0.1.0",
                            }
                        ],
                        "edges": [],
                    },
                }
            ],
            "edges": [],
        },
        "gui": {"nodes": {}},
        "metadata": {"display_name": "Workflow"},
    }
    store.root_dir.mkdir(parents=True, exist_ok=True)
    _workflow_json(store, "wf").parent.mkdir(parents=True)
    _workflow_json(store, "wf").write_text(json.dumps(raw), encoding="utf-8")

    document = store.export_workflow("wf")

    assert [item.model_dump() for item in document.required_packages] == [
        {"name": "inner-pkg", "version": "0.1.0"}
    ]


def test_export_workflow_archive_delegates_to_adapter(
    tmp_path: Path,
    registry: ToolRegistryService,
) -> None:
    archive_adapter = _FakeArchiveAdapter()
    store = WorkflowStoreService(
        root_dir=tmp_path / "workflows",
        tool_registry=registry,
        storage_base_dir=tmp_path / "outputs",
        archive_adapter=archive_adapter,
    )
    store.create_workflow(WorkflowCreate(name="wf"))

    filename, payload = store.export_workflow_archive("wf")

    assert filename == "wf.bioimageflow.zip"
    assert payload == b"fake zip"
    assert archive_adapter.export_calls[0][0] == _workflow_json(store, "wf")
    assert archive_adapter.export_calls[0][1].name == "wf.bioimageflow.zip"


def test_import_workflow_saves_with_managed_storage_path(
    store: WorkflowStoreService,
) -> None:
    document = _export_document(name="imported")

    response = store.import_workflow(document)

    assert response.info.name == "imported"
    assert response.info.identity_generation == 1
    assert response.info.display_name == "Imported"
    assert response.info.storage_path == str(store.storage_base_dir / "imported")
    assert [item.name for item in store.list_workflows()] == ["imported"]
    raw = json.loads(_workflow_json(store, "imported").read_text(encoding="utf-8"))
    assert raw["metadata"]["storage_path"] == str(store.storage_base_dir / "imported")
    assert raw["workflow"]["config"]["storage_path"] == str(store.storage_base_dir / "imported")


def test_import_workflow_archive_delegates_to_adapter_and_saves_layout(
    tmp_path: Path,
    registry: ToolRegistryService,
) -> None:
    archive_adapter = _FakeArchiveAdapter(
        library={
            "nodes": [
                {
                    "name": "n1",
                    "display_name": "Node",
                    "tool_class": "ExistingTool",
                    "constants": {"threshold": 3},
                }
            ],
            "edges": [],
        }
    )
    store = WorkflowStoreService(
        root_dir=tmp_path / "workflows",
        tool_registry=registry,
        storage_base_dir=tmp_path / "outputs",
        archive_adapter=archive_adapter,
    )

    response = store.import_workflow_archive(
        b"fake zip",
        filename="imported.bioimageflow.zip",
    )

    assert response.info.name == "imported"
    assert response.info.identity_generation == 1
    assert archive_adapter.import_payload == b"fake zip"
    assert archive_adapter.extract_calls == [store.root_dir / "imported"]
    assert _workflow_json(store, "imported").exists()
    assert (store.root_dir / "imported" / "tools").is_dir()
    raw = json.loads(_workflow_json(store, "imported").read_text(encoding="utf-8"))
    assert raw["workflow"]["nodes"][0]["name"] == "n1"
    assert raw["graph"]["nodes"][0]["id"] == "n1"
    assert raw["metadata"]["storage_path"] == str(store.storage_base_dir / "imported")


def test_import_workflow_archive_copies_tools_from_zip_before_temp_cleanup(
    tmp_path: Path,
    registry: ToolRegistryService,
) -> None:
    archive_adapter = _FakeArchiveAdapter()
    store = WorkflowStoreService(
        root_dir=tmp_path / "workflows",
        tool_registry=registry,
        storage_base_dir=tmp_path / "outputs",
        archive_adapter=archive_adapter,
    )
    archive_path = tmp_path / "imported.bioimageflow.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("workflow.json", '{"nodes": [], "edges": []}')
        archive.writestr("tools/__init__.py", "")
        archive.writestr("tools/custom_tool.py", "VALUE = 1\n")

    response = store.import_workflow_archive(
        archive_path.read_bytes(),
        filename="imported.bioimageflow.zip",
    )

    assert response.info.name == "imported"
    assert archive_adapter.extract_calls == [store.root_dir / "imported"]
    assert (store.root_dir / "imported" / "tools" / "__init__.py").exists()
    assert (store.root_dir / "imported" / "tools" / "custom_tool.py").read_text(
        encoding="utf-8"
    ) == "VALUE = 1\n"


def test_import_workflow_name_override_and_conflict(
    store: WorkflowStoreService,
) -> None:
    store.create_workflow(WorkflowCreate(name="imported"))
    document = _export_document(name="imported")

    with pytest.raises(FileExistsError):
        store.import_workflow(document)

    response = store.import_workflow(document, name_override="imported_copy")

    assert response.info.name == "imported_copy"
    assert _workflow_json(store, "imported_copy").exists()


def test_import_workflow_reports_missing_packages_and_tools(
    store: WorkflowStoreService,
) -> None:
    library = {
        "nodes": [
            {
                "name": "removed_1",
                "tool_class": "RemovedTool",
                "tool_package": "missing-pkg",
                "tool_package_version": "9.9.9",
            }
        ],
        "edges": [],
    }
    graph = {
        "nodes": [
            {
                "id": "removed_1",
                "name": "Removed",
                "tool_name": "RemovedTool",
                "position": [0, 0],
                "parameters": {},
            }
        ],
        "edges": [],
    }
    document = _export_document(name="imported", library=library, graph=graph)

    response = store.import_workflow(document)

    assert response.missing_packages[0].package_name == "missing-pkg"
    assert response.missing_packages[0].required_version == "9.9.9"
    assert response.missing_tools[0].node_id == "removed_1"
    assert response.missing_tools[0].tool_name == "RemovedTool"


def test_import_workflow_preserves_sub_workflow_without_missing_outer_marker(
    store: WorkflowStoreService,
    registry: ToolRegistryService,
) -> None:
    registry.register_tool(
        "ExistingTool",
        ToolMetadata(
            name="ExistingTool",
            display_name="Existing Tool",
            package="missing-pkg",
            package_version="1.0.0",
            tool_type="ProcessingTool",
        ),
    )
    sub_workflow = {
        "nodes": [
            {
                "name": "inner_1",
                "tool_class": "ExistingTool",
                "tool_package": "missing-pkg",
                "tool_package_version": "1.0.0",
            }
        ],
        "edges": [],
    }
    library = {
        "nodes": [
            {
                "name": "sub_1",
                "tool_class": "__sub_workflow__",
                "sub_workflow": sub_workflow,
            }
        ],
        "edges": [],
    }
    document = _export_document(
        name="imported",
        library=library,
        graph={
            "nodes": [
                {
                    "id": "sub_1",
                    "name": "Sub",
                    "tool_name": "__sub_workflow__",
                    "position": [0, 0],
                    "parameters": {},
                }
            ],
            "edges": [],
        },
    )

    response = store.import_workflow(document)

    assert response.missing_packages == []
    assert response.missing_tools == []
    raw = json.loads(_workflow_json(store, "imported").read_text(encoding="utf-8"))
    assert raw["workflow"]["nodes"][0]["sub_workflow"] == sub_workflow


def test_import_workflow_preserves_raw_graph_nested_sub_workflow_fields(
    store: WorkflowStoreService,
) -> None:
    graph = {
        "nodes": [
            {
                "id": "sub_1",
                "name": "Sub",
                "tool_name": "__sub_workflow__",
                "position": [0, 0],
                "parameters": {},
                "sub_workflow": {
                    "nodes": [
                        {
                            "id": "inner_1",
                            "name": "Inner",
                            "tool_name": "InnerTool",
                            "position": [1, 2],
                            "parameters": {},
                        }
                    ],
                    "edges": [],
                },
            }
        ],
        "edges": [],
    }
    document = _export_document(name="imported", graph=graph)

    store.import_workflow(document)

    raw = json.loads(_workflow_json(store, "imported").read_text(encoding="utf-8"))
    assert raw["graph"]["nodes"][0]["sub_workflow"] == graph["nodes"][0]["sub_workflow"]
