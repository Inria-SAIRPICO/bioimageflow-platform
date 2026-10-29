"""Saved viewing inspection uses the same source authority as normal loading."""

from pathlib import Path

import pytest
from bioimageflow import Workflow
from bioimageflow.env_manager import WetlandsEnvManager

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowSaveBody
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService


SOURCE = '''from bioimageflow import DataFrameTool
from bioimageflow_core import IOModel

class LocalNumbers(DataFrameTool):
    accepts_upstream = False
    class Outputs(IOModel):
        number: int
    def transform(self, df, arguments):
        raise AssertionError("Viewing inspection must not execute scientific code")
'''


def _store(tmp_path: Path) -> tuple[WorkflowStoreService, Path]:
    registry = ToolRegistryService()
    store = WorkflowStoreService(tmp_path / "workflows", registry)
    store.create_workflow(WorkflowCreate(name="local"))
    source = store.workflow_dir("local") / "tools" / "local_numbers.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(SOURCE)
    return store, source


def _graph(*, nested: bool = False) -> GraphState:
    tool = {
        "type": "tool", "id": "numbers", "name": "Numbers", "tool_name": "LocalNumbers",
        "tool_module": "tools.local_numbers", "tool_class": "LocalNumbers",
        "position": [100, 100], "parameters": {},
        "viewer_additions": {"number": {"napari": {"required_packages": [{
            "distribution": "example-reader", "normalized_name": "example-reader", "version": ">=2",
        }]}}},
    }
    body = {
        "schema_version": 2, "name": "local", "display_name": "Local",
        "nodes": [tool], "edges": [], "interface": {"inputs": [], "outputs": []},
        "config": {"engine": "direct", "execution": "sequential"},
    }
    if nested:
        body["nodes"] = [{
            "type": "workflow", "id": "nested", "name": "Nested", "position": [100, 100],
            "workflow": {**body, "nodes": [tool], "interface": {"inputs": [], "outputs": [{
                "id": "published", "name": "Published", "source": {"node": "numbers", "column": "number"},
            }]}}, "bindings": {},
        }]
    return GraphState.model_validate(body)


@pytest.mark.parametrize("nested", [False, True])
def test_saved_local_viewing_metadata_is_complete_without_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, nested: bool,
) -> None:
    store, source = _store(tmp_path)
    store.save_workflow("local", WorkflowSaveBody(graph=_graph(nested=nested)))
    saved = store._path_for("local").read_bytes()
    original_source = source.read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("Viewing inspection must not plan, provision or execute")

    monkeypatch.setattr(Workflow, "compute", forbidden)
    monkeypatch.setattr(Workflow, "plan", forbidden)
    monkeypatch.setattr(WetlandsEnvManager, "admit_runtime", forbidden)
    monkeypatch.setattr(WetlandsEnvManager, "get_or_create", forbidden)
    manifest = store.viewing_requirements("local")

    assert manifest.complete is True
    assert all(entry.status == "known" for entry in manifest.outputs.values())
    identity = "nested/numbers::tool-output/number" if nested else "numbers::tool-output/number"
    viewer = manifest.outputs[identity].viewer
    assert viewer is not None and viewer.napari is not None
    assert viewer.napari.required_packages[0].distribution == "example-reader"
    if nested:
        assert "nested::workflow-output/published" in manifest.outputs
    assert store._path_for("local").read_bytes() == saved
    assert source.read_bytes() == original_source
    assert not list(store.get_storage_path("local").rglob("run.json"))


def test_viewing_inspection_preserves_invalid_source_diagnostic(tmp_path: Path) -> None:
    store, source = _store(tmp_path)
    store.save_workflow("local", WorkflowSaveBody(graph=_graph()))
    source.write_text("def broken(:\n")

    manifest = store.viewing_requirements("local")

    assert manifest.complete is False
    entry = manifest.outputs["numbers::tool-output/*"]
    assert entry.status == "unknown"
    assert "invalid syntax" in entry.reason
    assert "local_numbers.py" in entry.reason


def test_viewing_inspection_preserves_missing_tool_diagnostic(tmp_path: Path) -> None:
    store, _source = _store(tmp_path)
    graph = _graph()
    graph.nodes[0].tool_module = "unavailable_viewing_tool_package"
    graph.nodes[0].tool_class = "MissingTool"
    graph.nodes[0].tool_name = "MissingTool"
    store.save_workflow("local", WorkflowSaveBody(graph=graph))

    manifest = store.viewing_requirements("local")

    assert manifest.complete is False
    entry = manifest.outputs["numbers::tool-output/*"]
    assert entry.status == "unknown"
    assert "unavailable_viewing_tool_package" in entry.reason
    assert "No module named" in entry.reason


def test_viewing_inspection_preserves_missing_local_file_diagnostic(tmp_path: Path) -> None:
    store, source = _store(tmp_path)
    store.save_workflow("local", WorkflowSaveBody(graph=_graph()))
    source.unlink()

    manifest = store.viewing_requirements("local")

    assert manifest.complete is False
    entry = manifest.outputs["numbers::tool-output/*"]
    assert entry.status == "unknown"
    assert "tools/local_numbers.py" in entry.reason
    assert "missing" in entry.reason


@pytest.mark.parametrize("healthy_sibling", [False, True])
def test_nested_missing_tool_remains_unknown_with_its_scoped_diagnostic(
    tmp_path: Path, healthy_sibling: bool,
) -> None:
    store, _source = _store(tmp_path)
    graph = _graph(nested=True)
    child = graph.nodes[0].workflow
    missing = child.nodes[0]
    if healthy_sibling:
        child.nodes.append(missing.model_copy(deep=True, update={"id": "healthy"}))
    missing.tool_module = "unavailable_nested_viewing_tool"
    missing.tool_class = "MissingTool"
    missing.tool_name = "MissingTool"
    store.save_workflow("local", WorkflowSaveBody(graph=graph))

    manifest = store.viewing_requirements("local")

    assert manifest.complete is False
    unknown = manifest.outputs["nested/numbers::tool-output/*"]
    assert unknown.status == "unknown"
    assert "nested/numbers" in unknown.reason
    assert "unavailable_nested_viewing_tool" in unknown.reason
    if healthy_sibling:
        assert manifest.outputs["nested/healthy::tool-output/number"].status == "known"


def test_empty_saved_workflow_has_complete_empty_viewing_metadata(tmp_path: Path) -> None:
    store, _source = _store(tmp_path)

    manifest = store.viewing_requirements("local")

    assert manifest.complete is True
    assert manifest.outputs == {}


def test_viewing_inspection_forwards_the_selected_tool_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _source = _store(tmp_path)
    selected = tmp_path / "selected-tool-store"
    selected.mkdir()
    store.tool_registry.scan_tool_store(selected)
    store.save_workflow("local", WorkflowSaveBody(graph=_graph()))
    original = Workflow.from_dict
    selected_paths = []

    def observed(*args, **kwargs):
        selected_paths.append(kwargs.get("tool_store_path"))
        return original(*args, **kwargs)

    monkeypatch.setattr(Workflow, "from_dict", observed)

    assert store.viewing_requirements("local").complete is True
    assert selected_paths == [selected]
