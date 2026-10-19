"""Development-only endpoints for seeding test data."""

from __future__ import annotations

import numpy as np
import pandas as pd
from bioimageflow.cache import dataframe_publish, dataframe_result_key
from bioimageflow.storage import Storage
from fastapi import APIRouter, Depends
from PIL import Image

from bioimageflow_dev_tools.processing import GaussianBlur
from bioimageflow_dev_tools.tools import (
    ControlledDirectNumbers,
    ImageResultFixture,
    IncrementAgainNumbers,
    IncrementNumbers,
    ResultTableFixture,
    SeedNumbers,
)

from bioimageflow_server.models.tools import (
    InputFieldSchema,
    OutputFieldSchema,
    PackageInfo,
    ToolMetadata,
)
from bioimageflow_server.services.result_store import ResultStoreService
from bioimageflow_server.services.tool_registry import ToolRegistryService

router = APIRouter(prefix="/dev", tags=["dev"])


def get_tool_registry() -> ToolRegistryService:  # pragma: no cover
    raise RuntimeError("tool_registry dependency not configured")


def get_result_store() -> ResultStoreService:  # pragma: no cover
    raise RuntimeError("result_store dependency not configured")


_SEED_TOOLS: list[ToolMetadata] = [
    ToolMetadata(
        name="SeedNumbers",
        display_name="Seed Numbers",
        package="bioimageflow-dev-seed",
        package_version="0.1.0",
        tool_type="DataFrameTool",
        row_consumption=None,
        accepts_upstream=False,
        documentation=SeedNumbers.documentation,
        tags=SeedNumbers.tags,
        categories=["Utilities"],
        outputs={
            "number": OutputFieldSchema(type="int"),
            "label": OutputFieldSchema(type="str"),
        },
    ),
    ToolMetadata(
        name="ResultTableFixture",
        display_name="Result Table Fixture",
        package="bioimageflow-dev-seed",
        package_version="0.1.0",
        tool_type="DataFrameTool",
        row_consumption=None,
        accepts_upstream=False,
        documentation=ResultTableFixture.documentation,
        tags=ResultTableFixture.tags,
        categories=["Utilities"],
        outputs={
            "source_row": OutputFieldSchema(type="int"),
            "label": OutputFieldSchema(type="str"),
            "score": OutputFieldSchema(type="int"),
        },
    ),
    ToolMetadata(
        name="IncrementNumbers",
        display_name="Increment Numbers",
        package="bioimageflow-dev-seed",
        package_version="0.1.0",
        tool_type="DataFrameTool",
        row_consumption=None,
        documentation=IncrementNumbers.documentation,
        tags=IncrementNumbers.tags,
        categories=["Utilities"],
        inputs={
            "number": InputFieldSchema(
                type="int",
                required=True,
                connectable="never",
                description="Number column to increment",
            ),
        },
        outputs={
            "number_plus_one": OutputFieldSchema(type="int"),
        },
    ),
    ToolMetadata(
        name="ControlledDirectNumbers",
        display_name="Controlled Direct Numbers",
        package="bioimageflow-dev-seed",
        package_version="0.1.0",
        tool_type="DataFrameTool",
        row_consumption=None,
        documentation=ControlledDirectNumbers.documentation,
        tags=ControlledDirectNumbers.tags,
        categories=["Utilities"],
        inputs={
            "fail": InputFieldSchema(
                type="bool",
                required=False,
                connectable="never",
                default=False,
                description="Raise a controlled execution error",
            ),
        },
        outputs={"number_plus_one": OutputFieldSchema(type="int")},
    ),
    ToolMetadata(
        name="ImageResultFixture",
        display_name="Image Result Fixture",
        package="bioimageflow-dev-seed",
        package_version="0.1.0",
        tool_type="DataFrameTool",
        row_consumption=None,
        accepts_upstream=False,
        documentation=ImageResultFixture.documentation,
        tags=ImageResultFixture.tags,
        categories=["Utilities"],
        outputs={
            "mask": OutputFieldSchema(type="ImageFile"),
            "report": OutputFieldSchema(type="Path"),
        },
    ),
    ToolMetadata(
        name="IncrementAgainNumbers",
        display_name="Increment Again",
        package="bioimageflow-dev-seed",
        package_version="0.1.0",
        tool_type="DataFrameTool",
        row_consumption=None,
        documentation=IncrementAgainNumbers.documentation,
        tags=IncrementAgainNumbers.tags,
        categories=["Utilities"],
        inputs={
            "number_plus_one": InputFieldSchema(
                type="int",
                required=True,
                connectable="never",
                description="Incremented number column to increment again",
            ),
        },
        outputs={
            "number_plus_two": OutputFieldSchema(type="int"),
        },
    ),
    ToolMetadata(
        name="CellposeSegmenter",
        display_name="Cellpose Segmenter",
        package="bioimageflow-cellpose",
        package_version="1.2.0",
        tool_type="ProcessingTool",
        row_consumption="mapped",
        documentation="Segment cells using Cellpose deep learning models.",
        tags=["segmentation", "deep-learning"],
        categories=["Segmentation"],
        inputs={
            "input_image": InputFieldSchema(
                type="ImageFile",
                required=True,
                connectable="by_default",
                description="Input intensity image",
            ),
            "diameter": InputFieldSchema(
                type="float",
                required=False,
                connectable="not_by_default",
                default=30.0,
                min=1.0,
                max=500.0,
                step=0.5,
                group="general",
                description="Expected cell diameter in pixels",
            ),
        },
        outputs={
            "mask": OutputFieldSchema(type="ImageFile"),
            "cell_count": OutputFieldSchema(type="int"),
        },
    ),
    ToolMetadata(
        name="GaussianBlur",
        display_name="Gaussian Blur",
        package="bioimageflow-filters",
        package_version="0.5.0",
        tool_type="ProcessingTool",
        row_consumption="mapped",
        documentation="Apply Gaussian blur to images.",
        tags=["preprocessing", "filter"],
        categories=["Preprocessing"],
        inputs={
            "input_image": InputFieldSchema(
                type="ImageFile",
                required=True,
                connectable="by_default",
                description="Image to blur",
            ),
            "sigma": InputFieldSchema(
                type="float",
                required=False,
                connectable="not_by_default",
                default=1.0,
                min=0.1,
                max=50.0,
                step=0.1,
                description="Blur radius (sigma)",
            ),
        },
        outputs={
            "output_image": OutputFieldSchema(type="ImageFile"),
        },
    ),
    ToolMetadata(
        name="ThresholdBinarize",
        display_name="Threshold Binarize",
        package="bioimageflow-filters",
        package_version="0.5.0",
        tool_type="ProcessingTool",
        row_consumption="mapped",
        documentation="Binarize images using a threshold value.",
        tags=["segmentation", "threshold"],
        categories=["Segmentation"],
        inputs={
            "input_image": InputFieldSchema(
                type="ImageFile",
                required=True,
                connectable="by_default",
                description="Image to threshold",
            ),
            "threshold": InputFieldSchema(
                type="float",
                required=False,
                connectable="not_by_default",
                default=128.0,
                min=0.0,
                max=255.0,
                step=1.0,
                description="Threshold value",
            ),
        },
        outputs={
            "binary_mask": OutputFieldSchema(type="ImageFile"),
        },
    ),
]

_SEED_PACKAGES: list[PackageInfo] = [
    PackageInfo(
        name="bioimageflow-dev-seed",
        installed_versions=["0.1.0"],
        available_versions=["0.1.0"],
        active_version="0.1.0",
        tools={
            "0.1.0": [
                "SeedNumbers",
                "ResultTableFixture",
                "IncrementNumbers",
                "ControlledDirectNumbers",
                "IncrementAgainNumbers",
                "ImageResultFixture",
            ]
        },
        environment_status="stopped",
    ),
    PackageInfo(
        name="bioimageflow-cellpose",
        installed_versions=["1.1.0", "1.2.0"],
        available_versions=["1.0.0", "1.1.0", "1.2.0"],
        tools={"1.2.0": ["CellposeSegmenter"]},
        environment_status="stopped",
    ),
    PackageInfo(
        name="bioimageflow-filters",
        installed_versions=["0.5.0"],
        available_versions=["0.4.0", "0.5.0"],
        tools={"0.5.0": ["GaussianBlur", "ThresholdBinarize"]},
        environment_status="stopped",
    ),
]


@router.post("/seed")
async def seed_tools(
    registry: ToolRegistryService = Depends(get_tool_registry),
) -> dict[str, int]:
    """Register demo tools and packages for E2E testing."""
    for tool in _SEED_TOOLS:
        tool_class = {
            "SeedNumbers": SeedNumbers,
            "ResultTableFixture": ResultTableFixture,
            "IncrementNumbers": IncrementNumbers,
            "ControlledDirectNumbers": ControlledDirectNumbers,
            "IncrementAgainNumbers": IncrementAgainNumbers,
            "ImageResultFixture": ImageResultFixture,
            "GaussianBlur": GaussianBlur,
        }.get(tool.name)
        registry.register_tool(tool.name, tool, tool_class=tool_class)
    for pkg in _SEED_PACKAGES:
        registry.register_package(pkg.name, pkg)
    return {"tools": len(_SEED_TOOLS), "packages": len(_SEED_PACKAGES)}


@router.post("/seed-image-output")
async def seed_image_output(
    result_store: ResultStoreService = Depends(get_result_store),
) -> dict[str, str]:
    """Write a tiny image-output cache entry for E2E viewer tests."""
    node_id = "avivator_image_node"
    column = "mask"
    storage_path = result_store.storage_path
    image_dir = storage_path / "dev-images"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_path = image_dir / "mask.png"
    Image.fromarray(np.arange(64, dtype=np.uint8).reshape(8, 8)).save(image_path)

    sig_hash = "dev-seed"
    run_id = "run_00000000000000000000000000000000"
    dataframe_publish(
        storage_path,
        node_id,
        sig_hash,
        pd.DataFrame({column: [str(image_path)]}),
        run_id=run_id,
        engine="direct:parallel",
        tool_identity="bioimageflow-platform:dev-seed",
    )
    storage = Storage(storage_path)
    result_key = dataframe_result_key(node_id, sig_hash)
    pointer = storage.load_current(result_key)
    if pointer is None:
        raise RuntimeError("Failed to seed dev image output cache record")
    storage.write_run_metadata(
        run_id,
        workflow_identity="dev-seed",
        engine="direct",
        status="succeeded",
        target_nodes=[node_id],
    )
    storage.write_run_node_result(
        run_id,
        node_id,
        result_key=result_key,
        record_id=pointer.record_id,
        cache_hit=False,
    )
    storage.update_latest_node(node_id, run_id)
    return {
        "node_id": node_id,
        "column": column,
        "filename": "mask.ome.tif",
        "source_path": str(image_path),
    }
