"""Tests for tool and package metadata models."""

import pytest

from bioimageflow_server.models.tools import (
    AppConfig,
    InputFieldSchema,
    OutputFieldSchema,
    PackageInfo,
    ToolCreate,
    ToolMetadata,
    ToolRename,
)

pytestmark = pytest.mark.anyio


# --- Task 1 tests ---


def test_tool_metadata_full_construction():
    meta = ToolMetadata(
        name="Cellpose",
        display_name="Cellpose Segmentation",
        package="cellpose",
        package_version="2.0",
        tool_type="ProcessingTool",
        documentation="Segment cells.",
        tags=["segmentation"],
        categories=["analysis"],
        inputs={
            "diameter": InputFieldSchema(
                type="float",
                description="Cell diameter",
                min=0.0,
                max=500.0,
                step=1.0,
            ),
        },
        outputs={
            "masks": OutputFieldSchema(type="image"),
        },
        environment={"python": "3.10"},
    )

    assert meta.name == "Cellpose"
    assert meta.inputs["diameter"].min == 0.0
    assert meta.inputs["diameter"].max == 500.0
    assert meta.outputs["masks"].type == "image"
    assert meta.environment == {"python": "3.10"}


def test_tool_metadata_defaults():
    meta = ToolMetadata(
        name="MyTool",
        display_name="My Tool",
        package="pkg",
        package_version="1.0",
        tool_type="ProcessingTool",
    )

    assert meta.documentation == ""
    assert meta.tags == []
    assert meta.categories == []
    assert meta.inputs == {}
    assert meta.outputs == {}
    assert meta.environment is None


def test_input_field_schema_connectable_default():
    field = InputFieldSchema(type="float")
    assert field.connectable is True


# --- Task 2 tests ---


def test_package_info_full():
    info = PackageInfo(
        name="cellpose",
        installed_versions=["2.0", "2.1"],
        available_versions=["2.0", "2.1", "3.0"],
        tools={"2.1": ["Cellpose", "CellposeModel"]},
        environment_status="running",
    )
    assert info.name == "cellpose"
    assert info.installed_versions == ["2.0", "2.1"]
    assert info.environment_status == "running"


def test_package_info_defaults():
    info = PackageInfo(name="cellpose")
    assert info.installed_versions == []
    assert info.available_versions == []
    assert info.tools == {}
    assert info.environment_status == "stopped"


def test_tool_create():
    tc = ToolCreate(name="MyTool", tool_type="ProcessingTool")
    assert tc.name == "MyTool"
    assert tc.tool_type == "ProcessingTool"


def test_tool_rename():
    tr = ToolRename(new_name="BetterName")
    assert tr.new_name == "BetterName"


def test_app_config_defaults():
    cfg = AppConfig()
    assert cfg.tool_registry is None
    assert cfg.workflow_root is None
    assert cfg.deployment_mode == "desktop"
    assert cfg.package_installer is None
    assert cfg.datasets_root is None
    assert cfg.max_upload_size is None


def test_app_config_dataset_overrides():
    from pathlib import Path as _P

    cfg = AppConfig(datasets_root=_P("/tmp/datasets"), max_upload_size=1_000_000)
    assert cfg.datasets_root == _P("/tmp/datasets")
    assert cfg.max_upload_size == 1_000_000
