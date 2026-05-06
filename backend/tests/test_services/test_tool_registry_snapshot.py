"""Snapshot test locking the `GET /tools` wire format.

This snapshot locks the wire format of `ToolMetadata` produced by
`ToolRegistryService`. If you're changing it intentionally, update the
fixture JSON and coordinate with the frontend generated types plus
`platform_specs_v1.md`.

The picked tool (`CellposeSAM` from `bioimageflow_common_tools`) exercises:
- `ImageFile` inputs with `ImageSpec` (semantics, layouts).
- `GUIMeta` annotations with `min` / `max` / `step` / `display_name`.
- Required vs. defaulted inputs.
- Multiple outputs including a templated `ImageFile` default and a plain
  `int` field.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bioimageflow_server.services.tool_registry import ToolRegistryService

FIXTURE_PATH = (
    Path(__file__).parent.parent / "fixtures" / "tool_metadata_snapshot.json"
)


@pytest.fixture
def registry_with_cellpose() -> ToolRegistryService:
    pytest.importorskip("bioimageflow.tool_loader")
    from bioimageflow.tool_loader import load_versioned_package

    package_name, version = "bioimageflow_common_tools", "0.1.1"
    try:
        mod = load_versioned_package(package_name, version)
    except Exception as exc:  # pragma: no cover - env-dependent
        pytest.skip(f"{package_name}=={version} not installed: {exc}")

    cls = getattr(mod, "CellposeSAM", None)
    if cls is None:  # pragma: no cover - env-dependent
        pytest.skip("CellposeSAM missing from bioimageflow_common_tools")

    reg = ToolRegistryService()
    reg._register_tool_from_class(cls, "CellposeSAM", package_name, version)
    return reg


def test_cellpose_sam_wire_format_snapshot(registry_with_cellpose: ToolRegistryService):
    meta = registry_with_cellpose.get_tool("CellposeSAM")
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
    meta = registry_with_cellpose.get_tool("CellposeSAM")
    assert meta is not None
    assert meta.tool_type != "BaseTool"
    # The Literal type on ToolMetadata already excludes BaseTool, but
    # verify no tool in the registry sneaked it through.
    for tool in registry_with_cellpose.list_tools():
        assert tool.tool_type in ("ProcessingTool", "DataFrameTool"), (
            f"{tool.name} has unexpected tool_type={tool.tool_type!r}"
        )
