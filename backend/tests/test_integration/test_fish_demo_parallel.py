"""Parallel Fish demo result paths and four-image summary against the selected library."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest
from bioimageflow import DataFrameTool, Workflow, WorkflowExecutionContext
from bioimageflow.storage import Storage
from bioimageflow_core import Arguments, EnvironmentSpec, IOModel, ProcessingTool, RowConsumption


class _ImageRows(DataFrameTool):
    accepts_upstream = False

    class Inputs(IOModel):
        pass

    class Outputs(IOModel):
        source_image: str

    def transform(self, df, arguments):
        return pd.DataFrame(
            {"source_image": [f"image_{index}.tif" for index in range(4)]},
            index=[str(index) for index in range(4)],
        )


class _OverlapRows(ProcessingTool):
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(name="fish_demo_parallel_test", dependencies={})

    class Inputs(IOModel):
        source_image: str

    class Outputs(IOModel):
        source_image: str
        reference_label: int
        spot_label: int
        overlap_count: int

    def process_row(self, arguments: Arguments, *, context=None):
        return [
            self.Outputs(
                source_image=arguments.source_image,
                reference_label=1,
                spot_label=1,
                overlap_count=1,
            )
        ]


@pytest.mark.integration
def test_parallel_marker_branches_publish_views_and_four_image_summary(tmp_path: Path) -> None:
    tool_path = (
        Path(__file__).resolve().parents[2]
        / "src/bioimageflow_server/data/demo_workflows/fish-analysis/tools/average_spots_per_nucleus.py"
    )
    spec = importlib.util.spec_from_file_location("fish_parallel_average", tool_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    marker = Workflow(name="marker", storage_path=tmp_path / "marker", engine="direct")
    with marker:
        source_image = marker.input("input_image", str, id="image-input")
        overlaps = _OverlapRows()(source_image=source_image, name="measure_nucleus_overlaps")
        for column in ("source_image", "reference_label", "spot_label", "overlap_count"):
            marker.output(column, overlaps[column], id=f"{column}-output")

    root = Workflow(
        name="fish",
        storage_path=tmp_path / "results",
        engine="direct",
        execution="parallel",
    )
    with root:
        images = _ImageRows()(name="images")
        fols2 = marker(input_image=images["source_image"], name="fols2")
        csf1r = marker(input_image=images["source_image"], name="csf1r")
        average = module.AverageSpotsPerNucleus()(fols2, csf1r, name="avg_spots_per_nucleus")
        root.output("source_image", average["source_image"], id="image-output")

    context = WorkflowExecutionContext()
    result = root.compute(run_context=context)

    assert result["source_image"].tolist() == [
        "image_0.tif", "image_1.tif", "image_2.tif", "image_3.tif", "Global average"
    ]
    storage = Storage(tmp_path / "results")
    for key in (
        "fols2/measure_nucleus_overlaps",
        "csf1r/measure_nucleus_overlaps",
        "avg_spots_per_nucleus",
    ):
        retained = storage.read_run_node_result(context.run_id, key)
        assert retained.node_key == key
