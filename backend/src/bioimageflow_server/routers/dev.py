"""Development-only endpoints for seeding test data."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from bioimageflow_server.models.tools import (
    InputFieldSchema,
    OutputFieldSchema,
    PackageInfo,
    ToolMetadata,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService

router = APIRouter(prefix="/dev", tags=["dev"])


def get_tool_registry() -> ToolRegistryService:  # pragma: no cover
    raise RuntimeError("tool_registry dependency not configured")


_SEED_TOOLS: list[ToolMetadata] = [
    ToolMetadata(
        name="CellposeSegmenter",
        display_name="Cellpose Segmenter",
        package="bioimageflow-cellpose",
        package_version="1.2.0",
        tool_type="ProcessingTool",
        documentation="Segment cells using Cellpose deep learning models.",
        tags=["segmentation", "deep-learning"],
        categories=["Segmentation"],
        inputs={
            "input_image": InputFieldSchema(
                type="ImagePath",
                connectable=True,
                description="Input intensity image",
            ),
            "diameter": InputFieldSchema(
                type="float",
                connectable=False,
                default=30.0,
                min=1.0,
                max=500.0,
                step=0.5,
                group="general",
                description="Expected cell diameter in pixels",
            ),
        },
        outputs={
            "mask": OutputFieldSchema(type="ImagePath"),
            "cell_count": OutputFieldSchema(type="int"),
        },
    ),
    ToolMetadata(
        name="GaussianBlur",
        display_name="Gaussian Blur",
        package="bioimageflow-filters",
        package_version="0.5.0",
        tool_type="ProcessingTool",
        documentation="Apply Gaussian blur to images.",
        tags=["preprocessing", "filter"],
        categories=["Preprocessing"],
        inputs={
            "input_image": InputFieldSchema(
                type="ImagePath",
                connectable=True,
                description="Image to blur",
            ),
            "sigma": InputFieldSchema(
                type="float",
                connectable=False,
                default=1.0,
                min=0.1,
                max=50.0,
                step=0.1,
                description="Blur radius (sigma)",
            ),
        },
        outputs={
            "output_image": OutputFieldSchema(type="ImagePath"),
        },
    ),
    ToolMetadata(
        name="ThresholdBinarize",
        display_name="Threshold Binarize",
        package="bioimageflow-filters",
        package_version="0.5.0",
        tool_type="ProcessingTool",
        documentation="Binarize images using a threshold value.",
        tags=["segmentation", "threshold"],
        categories=["Segmentation"],
        inputs={
            "input_image": InputFieldSchema(
                type="ImagePath",
                connectable=True,
                description="Image to threshold",
            ),
            "threshold": InputFieldSchema(
                type="float",
                connectable=False,
                default=128.0,
                min=0.0,
                max=255.0,
                step=1.0,
                description="Threshold value",
            ),
        },
        outputs={
            "binary_mask": OutputFieldSchema(type="ImagePath"),
        },
    ),
]

_SEED_PACKAGES: list[PackageInfo] = [
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
        registry.register_tool(tool.name, tool)
    for pkg in _SEED_PACKAGES:
        registry.register_package(pkg.name, pkg)
    return {"tools": len(_SEED_TOOLS), "packages": len(_SEED_PACKAGES)}
