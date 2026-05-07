"""Development-only endpoints for seeding test data."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from bioimageflow import DataFrameTool
from bioimageflow_core import IOModel
from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import ProcessingTool
from bioimageflow_core.types import ImageSpec
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


class SeedNumberInputs(IOModel):
    pass


class SeedNumberOutputs(IOModel):
    number: int
    label: str


class SeedNumbers(DataFrameTool):
    """Small deterministic source tool used by hermetic E2E execution tests."""

    display_name = "Seed Numbers"
    documentation = "Create a deterministic three-row dataframe for development tests."
    tags = ["source", "e2e"]
    accepts_upstream = False
    Inputs = SeedNumberInputs
    Outputs = SeedNumberOutputs

    def transform(self, df: Any, arguments: Any) -> Any:
        import pandas as pd

        return pd.DataFrame(
            {
                "number": [1, 2, 3],
                "label": ["one", "two", "three"],
            },
        )


class IncrementNumberInputs(IOModel):
    number: int


class IncrementNumberOutputs(IOModel):
    number_plus_one: int


class IncrementNumbers(DataFrameTool):
    """Deterministic transform tool used by graph-validation E2E tests."""

    display_name = "Increment Numbers"
    documentation = "Add one to an upstream number column for development tests."
    tags = ["transform", "e2e"]
    Inputs = IncrementNumberInputs
    Outputs = IncrementNumberOutputs

    def transform(self, df: Any, arguments: Any) -> Any:
        result = df.copy()
        result["number_plus_one"] = result["number"] + 1
        return result


class GaussianBlurInputs(IOModel):
    input_image: Annotated[Path, ImageSpec()]
    sigma: float = 1.0


class GaussianBlurOutputs(IOModel):
    output_image: Annotated[Path, ImageSpec()]


class GaussianBlur(ProcessingTool):
    """Tiny executable image-processing fixture for E2E graph validation."""

    environment = EnvironmentSpec(name="bioimageflow-e2e", dependencies={})
    Inputs = GaussianBlurInputs
    Outputs = GaussianBlurOutputs

    def process_row(self, arguments: Any) -> Any:
        return self.Outputs(output_image=Path("output.tif"))


_SEED_TOOLS: list[ToolMetadata] = [
    ToolMetadata(
        name="SeedNumbers",
        display_name="Seed Numbers",
        package="bioimageflow-dev-seed",
        package_version="0.1.0",
        tool_type="DataFrameTool",
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
        name="IncrementNumbers",
        display_name="Increment Numbers",
        package="bioimageflow-dev-seed",
        package_version="0.1.0",
        tool_type="DataFrameTool",
        documentation=IncrementNumbers.documentation,
        tags=IncrementNumbers.tags,
        categories=["Utilities"],
        inputs={
            "number": InputFieldSchema(
                type="int",
                required=True,
                connectable="by_default",
                description="Number column to increment",
            ),
        },
        outputs={
            "number_plus_one": OutputFieldSchema(type="int"),
        },
    ),
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
        tools={"0.1.0": ["SeedNumbers", "IncrementNumbers"]},
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
            "IncrementNumbers": IncrementNumbers,
            "GaussianBlur": GaussianBlur,
        }.get(tool.name)
        registry.register_tool(tool.name, tool, tool_class=tool_class)
    for pkg in _SEED_PACKAGES:
        registry.register_package(pkg.name, pkg)
    return {"tools": len(_SEED_TOOLS), "packages": len(_SEED_PACKAGES)}
