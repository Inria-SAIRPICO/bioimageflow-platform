"""Snapshot test locking the `GET /tools` wire format.

This snapshot locks the wire format of `ToolMetadata` produced by
`ToolRegistryService`. If you're changing it intentionally, update the
fixture JSON and coordinate with the frontend generated types plus
`platform_specs_v1.md`.

The local Cellpose-like fixture tool exercises:
- `ImageFile` inputs with `ImageSpec` (semantics, layouts).
- `GUIMeta` annotations with `min` / `max` / `step` / `display_name`.
- Required vs. defaulted inputs.
- Multiple outputs including a templated `ImageFile` default and a plain
  `int` field.
"""

import json
from pathlib import Path
from typing import Annotated, Any

import pytest

from bioimageflow_core import (
    Arguments,
    Category,
    Connectable,
    GENERAL_ENV,
    GUIMeta,
    IOModel,
    ImageSpec,
    Layout,
    ProcessingTool,
    Semantic,
    Template,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService

FIXTURE_PATH = (
    Path(__file__).parent.parent / "fixtures" / "tool_metadata_snapshot.json"
)


class SnapshotInputs(IOModel):
    input_image: Annotated[
        Path,
        ImageSpec(
            semantics={Semantic.INTENSITY},
            layouts={Layout.PLANAR, Layout.PLANAR_CHANNEL},
        ),
        GUIMeta(
            display_name="Input image",
            description="Fluorescence or brightfield image to segment.",
            connectable=Connectable.BY_DEFAULT,
        ),
    ]
    diameter: Annotated[
        float,
        GUIMeta(
            display_name="Cell diameter",
            description="Approximate cell diameter in pixels.",
            min=0.0,
            max=500.0,
            step=0.5,
        ),
    ] = 0.0
    model_type: Annotated[
        str,
        GUIMeta(display_name="Model", description="Pretrained model name."),
    ] = "cyto3"


class SnapshotOutputs(IOModel):
    mask: Annotated[
        Path,
        ImageSpec(semantics={Semantic.LABEL}, layouts={Layout.PLANAR}),
        GUIMeta(display_name="Mask", description="Labeled segmentation mask."),
    ] = Template("{input_image.stem}_mask{ext}")
    cell_count: int


class SnapshotCellpose(ProcessingTool):
    display_name = "Snapshot Cellpose"
    documentation = "Cellpose-like local fixture for metadata serialization tests."
    category = Category.SEGMENTATION
    tags = ["segmentation", "cellpose", "snapshot"]
    environment = GENERAL_ENV
    Inputs = SnapshotInputs
    Outputs = SnapshotOutputs

    def process_row(self, arguments: Arguments, *, context: Any = None) -> Any:
        return {}


@pytest.fixture
def registry_with_cellpose() -> ToolRegistryService:
    reg = ToolRegistryService()
    reg._register_tool_from_class(
        SnapshotCellpose,
        "SnapshotCellpose",
        "test-snapshot-tools",
        "1.0.0",
    )
    return reg


def test_cellpose_sam_wire_format_snapshot(registry_with_cellpose: ToolRegistryService):
    meta = registry_with_cellpose.get_tool("SnapshotCellpose")
    assert meta is not None

    serialized = meta.model_dump(mode="json")
    # Environment is environment-dependent; drop it for snapshot stability.
    serialized.pop("environment", None)

    actual = json.dumps(serialized, indent=2, sort_keys=True)

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not FIXTURE_PATH.exists():
        FIXTURE_PATH.write_text(actual + "\n")
        pytest.skip(f"Wrote new snapshot fixture to {FIXTURE_PATH}; re-run to verify.")

    expected = FIXTURE_PATH.read_text().rstrip("\n")
    assert actual == expected, (
        "Wire format for CellposeSAM drifted. Update "
        f"{FIXTURE_PATH.relative_to(Path.cwd())} intentionally and coordinate "
        "with frontend types + platform_specs_v1.md."
    )


def test_no_basetool_type(registry_with_cellpose: ToolRegistryService):
    """No registered tool should have tool_type == 'BaseTool'."""
    meta = registry_with_cellpose.get_tool("SnapshotCellpose")
    assert meta is not None
    assert meta.tool_type != "BaseTool"
    # The Literal type on ToolMetadata already excludes BaseTool, but
    # verify no tool in the registry sneaked it through.
    for tool in registry_with_cellpose.list_tools():
        assert tool.tool_type in ("ProcessingTool", "DataFrameTool"), (
            f"{tool.name} has unexpected tool_type={tool.tool_type!r}"
        )
