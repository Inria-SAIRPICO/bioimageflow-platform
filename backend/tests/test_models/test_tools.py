"""Tests for tool and package metadata models."""

import pytest

from bioimageflow_server.models.tools import (
    AppConfig,
    InputFieldSchema,
    OutputFieldSchema,
    PackageInfo,
    ToolCreate,
    ToolCreateResponse,
    ToolDeleteResponse,
    ToolMetadata,
    ToolRename,
    ToolRenameResponse,
    ToolUsageResponse,
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
                required=True,
                connectable="not_by_default",
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


def test_input_field_schema_connectable_three_state():
    field = InputFieldSchema(type="float", required=True, connectable="not_by_default")
    assert field.connectable == "not_by_default"
    assert field.required is True


def test_input_field_schema_nullable_default_false():
    # Older fixtures and library schemas without `nullable` must keep working.
    field = InputFieldSchema(type="int", required=True, connectable="not_by_default")
    assert field.nullable is False


def test_input_field_schema_nullable_round_trip():
    field = InputFieldSchema(
        type="int",
        required=False,
        nullable=True,
        connectable="not_by_default",
        default=None,
    )
    assert field.nullable is True
    # Validate that a dict containing `nullable` (as the library will emit)
    # round-trips through Pydantic validation.
    rebuilt = InputFieldSchema.model_validate(field.model_dump())
    assert rebuilt.nullable is True


@pytest.mark.parametrize("mode", ["file", "folder", "both"])
def test_input_field_schema_path_picker_round_trip(mode):
    field = InputFieldSchema(
        type="Path",
        required=True,
        connectable="never",
        path_picker=mode,
    )

    rebuilt = InputFieldSchema.model_validate(field.model_dump())

    assert rebuilt.path_picker == mode


def test_input_field_schema_path_picker_defaults_to_none():
    field = InputFieldSchema(type="Path", required=True, connectable="never")
    assert field.path_picker is None


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
    assert info.load_errors == {}


def test_package_info_defaults():
    info = PackageInfo(name="cellpose")
    assert info.installed_versions == []
    assert info.available_versions == []
    assert info.tools == {}
    assert info.load_errors == {}
    assert info.environment_status == "stopped"


def test_tool_create():
    tc = ToolCreate(name="MyTool", tool_type="ProcessingTool")
    assert tc.name == "MyTool"
    assert tc.tool_type == "ProcessingTool"


@pytest.mark.parametrize("name", ["class", "myTool", "My Tool", "../MyTool", "My/Tool"])
def test_tool_create_rejects_invalid_class_names(name: str):
    with pytest.raises(ValueError):
        ToolCreate(name=name, tool_type="ProcessingTool")


def test_tool_create_rejects_invalid_tool_type():
    with pytest.raises(ValueError):
        ToolCreate(name="MyTool", tool_type="SourceTool")


def test_tool_rename():
    tr = ToolRename(new_name="BetterName")
    assert tr.new_name == "BetterName"


@pytest.mark.parametrize("name", ["for", "betterName", "Better Name", "Better/Name"])
def test_tool_rename_rejects_invalid_class_names(name: str):
    with pytest.raises(ValueError):
        ToolRename(new_name=name)


def test_tool_metadata_source_defaults_to_package_not_editable():
    meta = ToolMetadata(
        name="PkgTool",
        display_name="Pkg Tool",
        package="pkg",
        package_version="1.0",
        tool_type="ProcessingTool",
    )
    assert meta.source_kind == "package"
    assert meta.editable is False


def test_custom_tool_response_models_round_trip(tmp_path):
    path = tmp_path / "tools" / "my_tool.py"
    create = ToolCreateResponse(
        name="MyTool",
        tool_type="ProcessingTool",
        path=str(path),
    )
    usage = ToolUsageResponse(
        tool_name="MyTool",
        affected_workflows=["wf"],
    )
    rename = ToolRenameResponse(old_name="MyTool", new_name="BetterTool", path=str(path))
    delete = ToolDeleteResponse(
        deleted=True,
        warning="Tool is used by saved workflows.",
        affected_workflows=["wf"],
    )

    assert create.source_kind == "custom"
    assert create.editable is True
    assert usage.in_open_workflow is None
    assert rename.old_name == "MyTool"
    assert delete.deleted is True


def test_app_config_defaults():
    cfg = AppConfig()
    assert cfg.tool_registry is None
    assert cfg.workflow_root is None
    assert cfg.deployment_mode == "desktop"
    assert cfg.package_installer is None
    assert cfg.datasets_root is None
    assert cfg.max_upload_size is None
    assert cfg.napari_launcher is None


def test_app_config_dataset_overrides():
    from pathlib import Path as _P

    cfg = AppConfig(datasets_root=_P("/tmp/datasets"), max_upload_size=1_000_000)
    assert cfg.datasets_root == _P("/tmp/datasets")
    assert cfg.max_upload_size == 1_000_000


def test_app_config_napari_launcher_override():
    sentinel = object()
    cfg = AppConfig(napari_launcher=sentinel)  # type: ignore[arg-type]
    assert cfg.napari_launcher is sentinel
