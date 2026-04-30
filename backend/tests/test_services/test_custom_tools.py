"""Tests for custom tool filesystem and registry service."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from bioimageflow_server.models.tools import ToolMetadata
from bioimageflow_server.services.custom_tools import CustomToolService
from bioimageflow_server.services.tool_registry import ToolRegistryService


def test_rendered_templates_parse_and_use_requested_class_name(tmp_path: Path):
    service = CustomToolService(tmp_path, ToolRegistryService())

    for tool_type in ("ProcessingTool", "DataFrameTool"):
        source = service.render_template("MySegmenter", tool_type)
        ast.parse(source)
        assert "class MySegmenter(" in source
        assert "OldName" not in source


def test_create_registers_custom_metadata_and_source(tmp_path: Path):
    registry = ToolRegistryService()
    service = CustomToolService(tmp_path, registry)

    path = service.create("MySegmenter", "ProcessingTool")

    assert path == tmp_path / "tools" / "my_segmenter.py"
    meta = registry.get_tool("MySegmenter")
    assert meta is not None
    assert meta.source_kind == "custom"
    assert meta.editable is True
    assert registry.resolve_tool_source("MySegmenter") == path


def test_create_rejects_duplicate_file(tmp_path: Path):
    service = CustomToolService(tmp_path, ToolRegistryService())
    service.create("MySegmenter", "ProcessingTool")

    with pytest.raises(FileExistsError):
        service.create("MySegmenter", "ProcessingTool")


def test_create_rejects_registry_conflict(tmp_path: Path):
    registry = ToolRegistryService()
    registry.register_tool(
        "PackageTool",
        ToolMetadata(
            name="PackageTool",
            display_name="Package Tool",
            package="pkg",
            package_version="1.0",
            tool_type="ProcessingTool",
        ),
    )
    service = CustomToolService(tmp_path, registry)

    with pytest.raises(FileExistsError):
        service.create("PackageTool", "ProcessingTool")


def test_rename_rewrites_file_class_metadata_and_registry(tmp_path: Path):
    registry = ToolRegistryService()
    service = CustomToolService(tmp_path, registry)
    old_path = service.create("OldName", "ProcessingTool")

    new_path = service.rename("OldName", "NewName")

    assert not old_path.exists()
    assert new_path == tmp_path / "tools" / "new_name.py"
    source = new_path.read_text()
    assert "class OldName(" not in source
    assert "class NewName(" in source
    assert 'display_name = "Old Name"' not in source
    assert registry.get_tool("OldName") is None
    assert registry.get_tool("NewName") is not None


def test_rename_rejects_target_conflict(tmp_path: Path):
    service = CustomToolService(tmp_path, ToolRegistryService())
    service.create("OldName", "ProcessingTool")
    service.create("NewName", "ProcessingTool")

    with pytest.raises(FileExistsError):
        service.rename("OldName", "NewName")


def test_delete_forgets_custom_tool(tmp_path: Path):
    registry = ToolRegistryService()
    service = CustomToolService(tmp_path, registry)
    path = service.create("TrashTool", "ProcessingTool")

    service.delete("TrashTool")

    assert not path.exists()
    assert registry.get_tool("TrashTool") is None
    assert registry.resolve_tool_source("TrashTool") is None


def test_registry_reloads_custom_tool_source(tmp_path: Path):
    registry = ToolRegistryService()
    service = CustomToolService(tmp_path, registry)
    path = service.create("ReloadMe", "ProcessingTool")
    original = registry.get_tool("ReloadMe")
    assert original is not None
    assert registry.resolve_package_for_path(path) == ("__custom__", "ReloadMe")

    path.write_text(
        path.read_text().replace(
            'display_name = "Reload Me"',
            'display_name = "Reloaded Tool"',
        )
    )

    reloaded = registry.reload_package("__custom__", "ReloadMe")

    assert reloaded["ReloadMe"].display_name == "Reloaded Tool"
    assert registry.get_tool("ReloadMe") == reloaded["ReloadMe"]


def test_registry_scans_existing_custom_tool_sources(tmp_path: Path):
    registry = ToolRegistryService()
    service = CustomToolService(tmp_path, registry)
    source = service.render_template("ExistingTool", "ProcessingTool")
    custom_root = tmp_path / "tools"
    custom_root.mkdir()
    path = custom_root / "custom_name.py"
    path.write_text(source, encoding="utf-8")

    registered = registry.register_custom_tools_directory(custom_root)

    assert list(registered) == ["ExistingTool"]
    assert registry.get_tool("ExistingTool") is not None
    assert registry.resolve_tool_source("ExistingTool") == path
    assert registry.resolve_package_for_path(path) == ("__custom__", "ExistingTool")


def test_rename_uses_registered_custom_source_path(tmp_path: Path):
    registry = ToolRegistryService()
    service = CustomToolService(tmp_path, registry)
    source = service.render_template("ExistingTool", "ProcessingTool")
    custom_root = tmp_path / "tools"
    custom_root.mkdir()
    old_path = custom_root / "custom_name.py"
    old_path.write_text(source, encoding="utf-8")
    registry.register_custom_tools_directory(custom_root)

    new_path = service.rename("ExistingTool", "RenamedTool")

    assert not old_path.exists()
    assert new_path == custom_root / "renamed_tool.py"
    assert "class RenamedTool(" in new_path.read_text(encoding="utf-8")
    assert registry.get_tool("ExistingTool") is None
    assert registry.get_tool("RenamedTool") is not None


def test_delete_rejects_package_tool(tmp_path: Path):
    registry = ToolRegistryService()
    registry.register_tool(
        "PackageTool",
        ToolMetadata(
            name="PackageTool",
            display_name="Package Tool",
            package="pkg",
            package_version="1.0",
            tool_type="ProcessingTool",
        ),
    )
    service = CustomToolService(tmp_path, registry)

    with pytest.raises(PermissionError):
        service.delete("PackageTool")
