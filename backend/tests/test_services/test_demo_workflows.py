"""Bundled demo workflow installation and provenance tests."""

from __future__ import annotations

import json
import importlib.util
import shutil
from pathlib import Path

import pytest

from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowSaveBody
from bioimageflow_server.services.demo_workflows import (
    DemoWorkflowConflictError,
    DemoWorkflowService,
)
from bioimageflow_server.services.workflow_artifacts import artifact_hash
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService


def _service(tmp_path: Path) -> tuple[DemoWorkflowService, WorkflowStoreService]:
    registry = ToolRegistryService()
    store = WorkflowStoreService(
        tmp_path / "workflows",
        registry,
    )
    return DemoWorkflowService(store, registry), store


def test_bundled_graphs_are_recursively_schema_v2(tmp_path: Path) -> None:
    service, _store = _service(tmp_path)
    assert service.bundle_version == 3

    def assert_schema_v2(graph: dict) -> None:
        assert graph["schema_version"] == 2
        for node in graph["nodes"]:
            if node["type"] == "workflow":
                assert_schema_v2(node["workflow"])

    for template in service.templates:
        payload = json.loads(
            (service.resource_root / template.directory / "workflow.json").read_text()
        )
        assert_schema_v2(payload["graph"])


def test_bundled_graphs_flow_left_to_right_without_overlapping_nodes(tmp_path: Path) -> None:
    service, _store = _service(tmp_path)

    def assert_layered(graph: dict) -> None:
        positions = {node["id"]: tuple(node["position"]) for node in graph["nodes"]}
        assert len(positions) == len(set(positions.values()))
        for edge in graph["edges"]:
            assert positions[edge["source_node"]][0] < positions[edge["target_node"]][0]
        for node in graph["nodes"]:
            if node["type"] == "workflow":
                assert_layered(node["workflow"])

    for template in service.templates:
        payload = json.loads(
            (service.resource_root / template.directory / "workflow.json").read_text()
        )
        assert_layered(payload["graph"])


def test_install_publishes_exact_self_contained_demo_identities(tmp_path: Path) -> None:
    service, store = _service(tmp_path)

    assert service.status().status == "missing"
    installed = service.install()

    assert installed.status == "installed"
    assert [item.workflow_id for item in installed.workflows] == [
        "Demo/Fish Analysis",
        "Demo/Parameters Space Exploration",
    ]
    for item in installed.workflows:
        document = store.read_workflow_document(item.workflow_id)
        assert document.metadata.bundled_template is not None
        assert document.metadata.bundled_template.id == item.id
        assert store.get_storage_path(item.workflow_id) == (
            store.workflow_dir(item.workflow_id) / "results"
        )
        assert list(store.workflow_tools_dir(item.workflow_id).glob("*.py"))
        assert all(
            node.source_module is None for node in document.graph.nodes if node.type == "tool"
        )
    assert store.get_workflow("Demo/Fish Analysis").graph.interface.inputs == []
    parameter_inputs = store.get_workflow(
        "Demo/Parameters Space Exploration"
    ).graph.interface.inputs
    assert [item.name for item in parameter_inputs] == ["marker_channel"]
    fish = store.get_workflow("Demo/Fish Analysis")
    fish_document = store.read_workflow_document("Demo/Fish Analysis")
    assert fish_document.artifact_hash == artifact_hash(fish_document.graph, [])
    assert fish_document.graph.config.execution == "parallel"
    branches = {
        node.id: node
        for node in fish_document.graph.nodes
        if node.type == "workflow"
    }
    assert {
        node_id: (node.name, node.workflow.display_name)
        for node_id, node in branches.items()
    } == {
        "fols2_marker_spot_analysis": (
            "FOLS2 Marker Spot Analysis", "FOLS2 Marker Spot Analysis"
        ),
        "csf1r_marker_spot_analysis": (
            "CSF1R Marker Spot Analysis", "CSF1R Marker Spot Analysis"
        ),
    }
    assert {item.package_name for item in fish.missing_packages} == {
        "bioimageflow_common_tools",
        "bioimageflow_io_tools",
        "bioimageflow_segmentation_tools",
        "bioimageflow_spot_tools",
    }
    assert "DownloadImages" not in {item.tool_name for item in fish.missing_tools}
    assert "AverageSpotsPerNucleus" not in {item.tool_name for item in fish.missing_tools}
    assert "FishLabelOverlaps" not in {item.tool_name for item in fish.missing_tools}
    for branch in branches.values():
        overlap = next(node for node in branch.workflow.nodes if node.id.endswith("measure_nucleus_overlaps"))
        assert overlap.tool_name == "FishLabelOverlaps"
        assert any(output.name == "source_image" for output in branch.workflow.interface.outputs)
    branch_node_ids = [node.id for branch in branches.values() for node in branch.workflow.nodes]
    assert len(branch_node_ids) == len(set(branch_node_ids))


def test_fish_average_keeps_image_origins_and_adds_weighted_global_average() -> None:
    import pandas as pd

    path = Path(__file__).resolve().parents[2] / "src/bioimageflow_server/data/demo_workflows/v3/fish-analysis/tools/average_spots_per_nucleus.py"
    spec = importlib.util.spec_from_file_location("fish_average_demo", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tool = module.AverageSpotsPerNucleus()
    fols2 = pd.DataFrame([
        {"source_image": "a.tif", "reference_label": 1, "spot_label": 1, "overlap_count": 3},
        {"source_image": "a.tif", "reference_label": 2, "spot_label": 0, "overlap_count": 4},
        {"source_image": "b.tif", "reference_label": 1, "spot_label": 1, "overlap_count": 2},
        {"source_image": "b.tif", "reference_label": 1, "spot_label": 2, "overlap_count": 2},
    ], index=["0::0", "0::1", "1::0", "1::1"])
    csf1r = pd.DataFrame([
        {"source_image": "a.tif", "reference_label": 1, "spot_label": 1, "overlap_count": 3},
        {"source_image": "a.tif", "reference_label": 2, "spot_label": 1, "overlap_count": 2},
        {"source_image": "b.tif", "reference_label": 1, "spot_label": 0, "overlap_count": 4},
    ], index=["0::0", "0::1", "1::0"])

    result = tool.merge_dataframes([fols2, csf1r], None)

    assert result["source_image"].tolist() == ["a.tif", "b.tif", "Global average"]
    assert result["avg_fols2_per_nucleus"].tolist() == [0.5, 2.0, 1.0]
    assert result["avg_csf1r_per_nucleus"].tolist() == [1.0, 0.0, 2 / 3]
    assert result.loc["global", "total_nuclei"] == 3
    assert result["total_nuclei"].dtype.kind in "iu"


def test_install_is_idempotent_and_never_overwrites_installed_demo(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    service.install()
    fish_path = store.workflow_dir("Demo/Fish Analysis") / "workflow.json"
    before = fish_path.read_bytes()
    fish = store.get_workflow("Demo/Fish Analysis")
    edited = fish.graph.model_copy(update={"display_name": "My edited demo"})
    store.save_workflow("Demo/Fish Analysis", WorkflowSaveBody(graph=edited))
    edited_bytes = fish_path.read_bytes()

    restarted = DemoWorkflowService(store, service.registry)
    result = restarted.install()

    assert result.status == "installed"
    assert fish_path.read_bytes() == edited_bytes
    assert fish_path.read_bytes() != before

    changed_bundle = tmp_path / "changed-bundle"
    shutil.copytree(service.resource_root, changed_bundle)
    manifest_path = changed_bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["bundle_version"] = service.bundle_version + 1
    manifest_path.write_text(json.dumps(manifest))

    upgraded = DemoWorkflowService(store, service.registry, resource_root=changed_bundle)
    assert upgraded.install().status == "installed"
    assert fish_path.read_bytes() == edited_bytes


def test_missing_demo_can_be_reinstalled_without_touching_other_demo(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    service.install()
    fish_path = store.workflow_dir("Demo/Fish Analysis") / "workflow.json"
    fish_bytes = fish_path.read_bytes()
    store.delete_workflow("Demo/Parameters Space Exploration")

    assert service.status().status == "partial"
    assert service.install().status == "installed"
    assert fish_path.read_bytes() == fish_bytes


def test_unrelated_workflow_at_canonical_path_is_a_visible_conflict(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    store.create_workflow(
        WorkflowCreate(name="Demo/Fish Analysis", display_name="Unrelated workflow")
    )

    status = service.status()

    assert status.status == "conflict"
    assert status.can_install is False
    with pytest.raises(DemoWorkflowConflictError):
        service.install()
