"""Imported tools are editable files and each run captures their current bytes."""

from __future__ import annotations

import hashlib
import base64
import json
from pathlib import Path

import pytest

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.workflow import WorkflowUpdate, WorkflowCreate
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.graph_validator import validate_graph
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.result_store import ResultStoreService
from bioimageflow_server.services.workflow_artifacts import (
    OwnedWorkflowSources,
    resolve_local_source,
)
from bioimageflow_server.services.workflow_store import WorkflowStoreService
from tests.test_services.test_workflow_store import _ArchiveAdapter


SOURCE = """from bioimageflow import DataFrameTool
from bioimageflow_core import IOModel
import pandas as pd

class Outputs(IOModel):
    number_plus_one: int

class QaIncrement(DataFrameTool):
    accepts_upstream = False
    Outputs = Outputs

    def transform(self, df, arguments):
        return pd.DataFrame({"number_plus_one": [n + 1 for n in [1, 2, 3]]})
"""


def source_record(source: str = SOURCE, source_id: str = "increment") -> dict:
    return {
        "id": source_id,
        "module": "qa_increment",
        "filename": "qa_increment.py",
        "source_hash": hashlib.sha256(source.encode()).hexdigest(),
        "source": source,
    }


def archive_payload(source: str = SOURCE) -> dict:
    return {
        "archive_version": 1,
        "custom_sources": [source_record(source)],
        "workflow": {
            "schema_version": 1,
            "name": "reference",
            "display_name": "QA Reference Workflow",
            "nodes": [
                {
                    "type": "tool",
                    "name": "increment",
                    "tool_class": "QaIncrement",
                    "tool_module": "qa_increment",
                    "tool_package": None,
                    "tool_package_version": None,
                    "source_module": "increment",
                    "constants": {},
                }
            ],
            "edges": [],
            "interface": {"inputs": [], "outputs": []},
            "config": {"engine": "direct", "execution": "sequential"},
        },
    }


def imported_store(tmp_path: Path) -> WorkflowStoreService:
    store = WorkflowStoreService(
        tmp_path / "workflows",
        ToolRegistryService(),
        archive_adapter=_ArchiveAdapter(archive_payload()),
    )
    store.import_workflow_archive(b"fixture", filename="reference.bioimageflow.zip")
    return store


def run(
    store: WorkflowStoreService, name: str = "reference", graph: GraphState | None = None
) -> list[int]:
    built = build_workflow(
        graph or store.get_workflow(name).graph,
        store.tool_registry,
        storage_path=store.get_storage_path(name),
    )
    assert built.errors == []
    built.workflow.compute(dev_mode=True)
    return (
        ResultStoreService(
            storage_path=store.get_storage_path(name), tool_registry=store.tool_registry
        )
        .get_latest_dataframe("increment")["number_plus_one"]
        .tolist()
    )


def test_import_materializes_editable_file_and_immediate_run_uses_saved_bytes(tmp_path: Path):
    store = imported_store(tmp_path)
    sources = OwnedWorkflowSources(store.workflow_dir("reference"))
    path = sources.source_path("increment")
    assert path == store.workflow_dir("reference") / "tools/increment/qa_increment.py"
    assert "source" not in json.loads((path.parent / "module.json").read_text())
    assert not (store.workflow_dir("reference") / ".bioimageflow/dependencies").exists()
    assert run(store) == [2, 3, 4]
    path.write_text(SOURCE.replace("n + 1", "n + 20"))
    assert run(store) == [21, 22, 23]


def test_execution_snapshot_and_other_import_remain_independent(tmp_path: Path):
    store = imported_store(tmp_path)
    store.import_workflow_archive(b"fixture", filename="other.bioimageflow.zip")
    graph = store.get_workflow("reference").graph
    captured = build_workflow(
        graph, store.tool_registry, storage_path=store.get_storage_path("reference")
    )
    OwnedWorkflowSources(store.workflow_dir("reference")).source_path("increment").write_text(
        SOURCE.replace("n + 1", "n + 20")
    )
    captured.workflow.compute(dev_mode=True)
    assert ResultStoreService(
        storage_path=store.get_storage_path("reference"), tool_registry=store.tool_registry
    ).get_latest_dataframe("increment")["number_plus_one"].tolist() == [2, 3, 4]
    assert run(store) == [21, 22, 23]
    assert run(store, "other") == [2, 3, 4]


def test_duplicate_and_export_include_edits(tmp_path: Path):
    store = imported_store(tmp_path)
    OwnedWorkflowSources(store.workflow_dir("reference")).source_path("increment").write_text(
        SOURCE.replace("n + 1", "n + 20")
    )
    store.patch_workflow("reference", WorkflowUpdate(action="duplicate", new_name="copy"))
    assert run(store, "copy") == [21, 22, 23]
    store.export_workflow_archive("copy")
    assert "n + 20" in store.archive_adapter.exported["custom_sources"][0]["source"]
    OwnedWorkflowSources(store.workflow_dir("copy")).source_path("increment").write_text(SOURCE)
    assert run(store) == [21, 22, 23]


def test_scoped_metadata_comes_from_executed_source(tmp_path: Path):
    store = imported_store(tmp_path)
    result = validate_graph(
        store.get_workflow("reference").graph,
        store.tool_registry,
        storage_path=store.get_storage_path("reference"),
    )
    assert result.valid
    assert result.node_tools["increment"].outputs["number_plus_one"]["type"] == "int"
    assert store.tool_registry.get_tool("QaIncrement") is None


def test_invalid_edit_blocks_execution_instead_of_reusing_old_code(tmp_path: Path):
    store = imported_store(tmp_path)
    assert run(store) == [2, 3, 4]
    OwnedWorkflowSources(store.workflow_dir("reference")).source_path("increment").write_text(
        "invalid Python !!!"
    )
    validation = validate_graph(
        store.get_workflow("reference").graph,
        store.tool_registry,
        storage_path=store.get_storage_path("reference"),
    )
    assert not validation.valid
    assert "qa_increment.py" in validation.errors[0].detail


def test_package_helper_edits_are_captured_and_not_reused_from_python_import_cache(tmp_path: Path):
    contents = {
        "tools/__init__.py": "",
        "tools/helper.py": "OFFSET = 1\n",
        "tools/qa_increment.py": SOURCE.replace(
            "import pandas as pd", "import pandas as pd\nfrom .helper import OFFSET"
        ).replace("n + 1", "n + OFFSET"),
    }
    files = []
    digest = hashlib.sha256()
    for path, source in sorted(contents.items()):
        file_hash = hashlib.sha256(source.encode()).hexdigest()
        digest.update(path.encode() + b"\0" + file_hash.encode() + b"\0")
        files.append(
            {
                "path": path,
                "encoding": "base64",
                "source_hash": file_hash,
                "content": base64.b64encode(source.encode()).decode(),
            }
        )
    payload = archive_payload()
    payload["workflow"]["nodes"][0]["tool_module"] = "tools.qa_increment"
    payload["custom_sources"] = [
        {
            "id": "increment",
            "module": "tools.qa_increment",
            "filename": "qa_increment.py",
            "root_package": "tools",
            "source_hash": digest.hexdigest(),
            "files": files,
        }
    ]
    store = WorkflowStoreService(
        tmp_path / "workflows", ToolRegistryService(), archive_adapter=_ArchiveAdapter(payload)
    )
    store.import_workflow_archive(b"fixture", filename="reference.bioimageflow.zip")
    source = OwnedWorkflowSources(store.workflow_dir("reference")).source_path(
        "increment", "tools.qa_increment"
    )
    assert run(store) == [2, 3, 4]
    source.with_name("helper.py").write_text("OFFSET = 20\n")
    assert run(store) == [21, 22, 23]


@pytest.mark.parametrize("filename", ["../escape.py", "/tmp/escape.py", "a\\escape.py"])
def test_import_rejects_unsafe_source_paths(tmp_path: Path, filename: str):
    record = source_record()
    record["filename"] = filename
    with pytest.raises(ValueError, match="source path"):
        OwnedWorkflowSources(tmp_path).stage([record])


def test_invalid_later_record_leaves_no_staged_source_files(tmp_path: Path):
    invalid = source_record(source_id="invalid")
    invalid["filename"] = "module.json"
    with pytest.raises(ValueError, match="Python file"):
        OwnedWorkflowSources(tmp_path).stage([source_record(), invalid])
    assert not (tmp_path / "tools").exists()


def test_known_local_source_can_be_opened_to_repair_invalid_python(tmp_path: Path):
    from unittest.mock import Mock

    path = tmp_path / "tools" / "unexpected_filename.py"
    path.parent.mkdir()
    path.write_text("invalid Python !!!")
    registry = Mock(resolve_tool_source=Mock(return_value=path))
    assert resolve_local_source(tmp_path, "QaIncrement", registry) == path


def test_owned_source_engine_does_not_depend_on_same_named_catalog_tool(tmp_path: Path):
    from unittest.mock import Mock
    from bioimageflow import DataFrameTool
    from bioimageflow_server.services.graph_translator import graph_requires_wetlands

    store = imported_store(tmp_path)
    registry = Mock(get_tool_class=Mock(return_value=DataFrameTool))
    assert graph_requires_wetlands(store.get_workflow("reference").graph, registry)
    registry.get_tool_class.assert_not_called()


def test_embedding_transfers_independent_sources_before_graph_insertion(tmp_path: Path):
    from bioimageflow_server.services.workflow_sources import WorkflowSourceService

    store = imported_store(tmp_path)
    store.create_workflow(WorkflowCreate(name="parent"))
    service = WorkflowSourceService(lambda: store)
    prepared = service.prepare_embedding(
        "parent",
        "reference",
        identity_generation=store.workflow_generation("parent"),
    )
    source_id = prepared.graph.nodes[0].source_module
    assert source_id != "increment"
    assert store.get_workflow("parent").graph.nodes == []
    path = OwnedWorkflowSources(store.workflow_dir("parent")).source_path(source_id)
    path.write_text(SOURCE.replace("n + 1", "n + 20"))
    assert run(store, "parent", prepared.graph) == [21, 22, 23]
    assert run(store) == [2, 3, 4]
    store.delete_workflow("reference")
    assert run(store, "parent", prepared.graph) == [21, 22, 23]


def test_embedding_rejects_stale_destination_and_self_containment(tmp_path: Path):
    from bioimageflow_server.services.workflow_sources import (
        WorkflowSourceService,
        WorkflowSourceConflict,
    )

    store = imported_store(tmp_path)
    store.create_workflow(WorkflowCreate(name="parent"))
    service = WorkflowSourceService(lambda: store)
    with pytest.raises(WorkflowSourceConflict):
        service.prepare_embedding("parent", "reference", identity_generation=999)
    with pytest.raises(ValueError, match="contain itself"):
        service.prepare_embedding(
            "reference", "reference", identity_generation=store.workflow_generation("reference")
        )
