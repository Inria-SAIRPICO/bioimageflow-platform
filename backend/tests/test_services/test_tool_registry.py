"""Tests for ToolRegistryService."""

import pytest

from bioimageflow_server.models.tools import (
    InputFieldSchema,
    OutputFieldSchema,
    PackageInfo,
    ToolMetadata,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService

pytestmark = pytest.mark.anyio


def _make_tool(name: str = "Cellpose") -> ToolMetadata:
    return ToolMetadata(
        name=name,
        display_name=name,
        package="pkg",
        package_version="1.0",
        tool_type="ProcessingTool",
        inputs={
            "diameter": InputFieldSchema(
                type="float",
                required=True,
                connectable="not_by_default",
                min=0.0,
            )
        },
        outputs={"masks": OutputFieldSchema(type="image")},
    )


def _make_package(name: str = "cellpose") -> PackageInfo:
    return PackageInfo(name=name, installed_versions=["2.0"])


# --- Tools ---


def test_empty_registry_list_tools():
    reg = ToolRegistryService()
    assert reg.list_tools() == []


def test_empty_registry_get_tool():
    reg = ToolRegistryService()
    assert reg.get_tool("Nope") is None


def test_register_and_get_tool():
    reg = ToolRegistryService()
    meta = _make_tool("Cellpose")
    reg.register_tool("Cellpose", meta)
    assert reg.get_tool("Cellpose") is meta


def test_register_multiple_and_list():
    reg = ToolRegistryService()
    reg.register_tool("A", _make_tool("A"))
    reg.register_tool("B", _make_tool("B"))
    names = {t.name for t in reg.list_tools()}
    assert names == {"A", "B"}


# --- Packages ---


def test_empty_registry_list_packages():
    reg = ToolRegistryService()
    assert reg.list_packages() == []


def test_empty_registry_get_package():
    reg = ToolRegistryService()
    assert reg.get_package("nope") is None


def test_register_and_get_package():
    reg = ToolRegistryService()
    info = _make_package("cellpose")
    reg.register_package("cellpose", info)
    assert reg.get_package("cellpose") is info


def test_register_multiple_packages_and_list():
    reg = ToolRegistryService()
    reg.register_package("a", _make_package("a"))
    reg.register_package("b", _make_package("b"))
    names = {p.name for p in reg.list_packages()}
    assert names == {"a", "b"}


