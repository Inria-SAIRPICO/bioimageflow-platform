"""Real archive preservation and passive viewer readiness without blocking Run."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from bioimageflow.storage import Storage
from bioimageflow_dev_tools.tools import SeedNumbers
from packaging.specifiers import SpecifierSet

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowSaveBody
from bioimageflow_server.routers.dev import _SEED_TOOLS
from bioimageflow_server.services.graph_compiler import GraphCompiler
from bioimageflow_server.services.napari_environments import NapariEnvironmentService
from bioimageflow_server.services.napari_resolver import NapariResolverService
from bioimageflow_server.services.result_store import ResultStoreService
from bioimageflow_server.services.settings_store import SettingsStore
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.viewer_preferences import ViewerPreferenceStore
from bioimageflow_server.services.workflow_store import WorkflowStoreService


@pytest.mark.anyio
async def test_real_archive_import_preserves_grouped_requirements_and_unknown_snapshot_without_blocking_execution(
    tmp_path: Path,
) -> None:
    registry = ToolRegistryService()
    metadata = next(tool for tool in _SEED_TOOLS if tool.name == "SeedNumbers")
    registry.register_tool(metadata.name, metadata, SeedNumbers)
    store = WorkflowStoreService(tmp_path / "workflows", registry)
    store.create_workflow(WorkflowCreate(name="original"))
    requirement = {"napari": {"required_packages": [{
        "distribution": "Unavailable_Reader", "normalized_name": "unavailable-reader", "version": ">=2,<3",
    }]}}
    graph = GraphState.model_validate({
        "schema_version": 2, "name": "original", "display_name": "Original",
        "nodes": [{
            "type": "tool", "id": name, "name": name, "tool_name": "SeedNumbers",
            "position": [100 + index * 200, 100], "parameters": {},
            "viewer_additions": {"number": requirement},
        } for index, name in enumerate(["first", "second"])],
        "edges": [], "interface": {"inputs": [], "outputs": []},
        "config": {"engine": "direct", "execution": "sequential"},
    })
    store.save_workflow("original", WorkflowSaveBody(graph=graph))
    filename, exported = store.export_workflow_archive("original")
    with zipfile.ZipFile(BytesIO(exported)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    document = json.loads(files["workflow.json"])
    # Use the unchanged ordinary installed declaration. Only viewer metadata is
    # deliberately incomplete, as permitted for an external export snapshot.
    document["custom_sources"] = []
    for node in document["workflow"]["nodes"]:
        node.pop("source_module", None)
        node["tool_module"] = "bioimageflow_dev_tools.tools"
        node["tool_class"] = "SeedNumbers"
    manifest = document["viewing_requirements"]
    known = [identity for identity in manifest["outputs"] if identity.endswith("/number")]
    unknown = next(identity for identity in manifest["outputs"] if identity.endswith("/label"))
    assert len(known) == 2
    manifest["complete"] = False
    manifest["outputs"][unknown] = {
        "status": "unknown", "viewer": None,
        "reason": "Exporter could not resolve viewer metadata for this output.",
    }
    files["workflow.json"] = json.dumps(document).encode()
    archive_bytes = BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    imported = store.import_workflow_archive(
        archive_bytes.getvalue(), filename=filename, name_override="imported",
    )
    assert imported.missing_tools == []
    assert imported.missing_packages == []
    assert imported.viewing_requirements.model_dump(mode="json", by_alias=True) == manifest

    reopened = WorkflowStoreService(tmp_path / "workflows", registry).get_workflow("imported")
    assert reopened.info.identity_generation == imported.info.identity_generation
    assert reopened.graph.name == "imported"
    restored = reopened.graph.nodes[0].viewer_additions["number"].napari
    assert restored is not None
    assert restored.required_packages[0].normalized_name == "unavailable-reader"
    assert SpecifierSet(restored.required_packages[0].version) == SpecifierSet(">=2,<3")
    settings = SettingsStore(tmp_path / "settings.json")
    await settings.load()
    environments = NapariEnvironmentService(settings)
    preferences = ViewerPreferenceStore(tmp_path / "viewer-preferences.json")
    resolver = NapariResolverService(
        environments, preferences, ResultStoreService(tmp_path / "runtime", registry), lambda: store,
    )
    before = settings.path.read_bytes() if settings.path.exists() else None
    report = resolver.viewing_readiness(imported.viewing_requirements)
    assert report.summary.not_covered_outputs == 2
    assert report.summary.unknown_outputs == 1
    assert report.summary.covered_outputs == 1
    assert report.summary.outputs_needing_setup == 3
    assert len(report.groups) == 1
    assert sorted(report.groups[0].members) == sorted(known)
    assert report.groups[0].managed_create_prefill.requested_packages == ["unavailable-reader<3,>=2"]
    assert next(output for output in report.outputs if output.output_identity == unknown).manifest_reason == manifest["outputs"][unknown]["reason"]
    assert environments.snapshot().environments == []
    assert (settings.path.read_bytes() if settings.path.exists() else None) == before

    storage_path = store.get_storage_path("imported")
    compiled = GraphCompiler(registry).compile(reopened.graph, storage_path=storage_path)
    assert compiled.errors == []
    assert compiled.workflow is not None
    assert compiled.workflow.engine_type == "direct"
    assert compiled.workflow.execution == "sequential"
    compiled.workflow.compute()
    results = ResultStoreService(storage_path, registry)
    identities = []
    for node in ("first", "second"):
        identity = results.capture_latest_result_identity(node)
        assert identity is not None
        frame = results.load_result_dataframe(identity)
        assert frame is not None
        assert frame["number"].tolist() == [1, 2, 3]
        assert frame["label"].tolist() == ["one", "two", "three"]
        identities.append(identity)
    assert identities[0].run_id == identities[1].run_id
    run = json.loads((Storage(storage_path).run_dir(identities[0].run_id) / "run.json").read_text())
    assert run["engine"] == "direct:sequential"
    assert run["status"] == "succeeded"
    assert Path(run["storage_path"]) == storage_path
    assert environments.snapshot().environments == []
    assert (settings.path.read_bytes() if settings.path.exists() else None) == before
