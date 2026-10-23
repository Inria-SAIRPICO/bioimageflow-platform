"""Safety and measurement-shape controls for the standalone loading benchmark."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from bioimageflow_server.models.workflow import WorkflowDocument
from bioimageflow_server.services.workflow_artifacts import artifact_hash
from tests.graph_factory import graph_state

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/benchmark_workflow_loading.py"
spec = importlib.util.spec_from_file_location("loading_benchmark", SCRIPT)
assert spec is not None and spec.loader is not None
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def _fixture(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    graph = graph_state()
    document = WorkflowDocument(graph=graph, metadata={}, artifact_hash=artifact_hash(graph, []))
    (source / "workflow.json").write_text(document.model_dump_json())
    return source


def test_snapshot_excludes_original_results_and_other_workspace_state(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    (source / "results").mkdir()
    (source / "results" / "private-original").write_text("must not be copied")
    (source / "tools").mkdir()
    (source / "tools" / "helper.py").write_text("VALUE = 1\n")
    before = (source / "workflow.json").read_bytes()
    target = benchmark.snapshot(source, tmp_path / "owned", None, 1024 * 1024)
    assert not (target / "results").exists()
    assert (target / "tools" / "helper.py").read_text() == "VALUE = 1\n"
    assert (source / "workflow.json").read_bytes() == before
    assert (source / "results" / "private-original").read_text() == "must not be copied"


def test_snapshot_refuses_source_links_and_bounds_fixture_size(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    (source / "tools").mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("VALUE = 1")
    (source / "tools" / "helper.py").symlink_to(outside)
    with pytest.raises(ValueError, match="symbolic link"):
        benchmark.snapshot(source, tmp_path / "owned", None, 1024 * 1024)
    (source / "tools" / "helper.py").unlink()
    with pytest.raises(ValueError, match="copy limit"):
        benchmark.snapshot(source, tmp_path / "bounded", None, 1)


@pytest.mark.integration
@pytest.mark.slow
def test_driver_separates_fresh_warm_and_profile_counts_without_source_writes(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    store = tmp_path / "read-only-store"
    store.mkdir()
    receipt = tmp_path / "receipt.json"
    before = (source / "workflow.json").read_bytes()
    poison = tmp_path / "inherited-pythonpath"
    poison.mkdir()
    (poison / "bioimageflow.py").write_text("raise AssertionError('inherited source override')\n")
    subprocess.run([
        sys.executable, str(SCRIPT), "--workflow-dir", str(source), "--tool-store", str(store),
        "--case", "empty-cache", "--fresh-processes", "2", "--warm-operations", "3",
        "--baseline-python", sys.executable, "--candidate-python", sys.executable,
        "--output", str(receipt),
    ], check=True, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(poison)})
    result = json.loads(receipt.read_text())
    assert result["order"] == ["baseline", "candidate", "candidate", "baseline"]
    for name in ("baseline", "candidate"):
        assert len(result["workers"][name]) == 2
        assert result["workers"][name][0]["platform_root"] == str(SCRIPT.parents[1])
        assert "graph_builder.py" in result["workers"][name][0]["platform_services_sha256"]
        summary = result["summary"][name]
        assert summary["cold"]["projected_draft_seconds"]["samples"] == 2
        assert summary["warm"]["projected_draft_seconds"]["samples"] == 3
        assert result["operation_counts"][name]["projected_draft"].get("scientific_callbacks", 0) == 0
        assert set(result["warm_operation_counts"][name]) == set(benchmark.STAGES)
        assert all(counts.get("scientific_callbacks", 0) == 0
                   for counts in result["warm_operation_counts"][name].values())
    assert result["unmeasured"] == [
        "HTTP transport", "canvas presentation", "actual Run setup and scientific execution",
    ]
    assert (source / "workflow.json").read_bytes() == before
    assert not (source / ".bioimageflow").exists()
    assert not list(store.iterdir())


@pytest.mark.integration
def test_worker_refuses_to_time_an_unresolved_tool_as_a_fast_workflow(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    document = json.loads((source / "workflow.json").read_text())
    document["graph"]["nodes"] = [{
        "type": "tool", "id": "missing", "name": "missing", "tool_name": "UnavailableTool",
        "position": [0, 0], "parameters": {},
    }]
    (source / "workflow.json").write_text(json.dumps(document))
    store = tmp_path / "store"
    store.mkdir()
    result = subprocess.run([
        sys.executable, str(SCRIPT), "--worker", json.dumps({
            "workflow_dir": str(source), "tool_store": str(store), "case": "empty-cache",
            "warm_operations": 0, "max_fixture_bytes": 1024 * 1024,
        }),
    ], capture_output=True, text=True)
    assert result.returncode != 0
    assert "refusing misleading timings" in result.stderr
