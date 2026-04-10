"""Tool and package metadata models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from bioimageflow_server.services.package_installer import PackageInstallerService
    from bioimageflow_server.services.tool_registry import ToolRegistryService


# --- Field schemas ---


class InputFieldSchema(BaseModel):
    type: str
    connectable: bool = True
    default: Any = None
    description: str = ""
    min: float | None = None
    max: float | None = None
    step: float | None = None
    group: str | None = None


class OutputFieldSchema(BaseModel):
    type: str


# --- Tool metadata ---


class ToolMetadata(BaseModel):
    name: str
    display_name: str
    package: str
    package_version: str
    tool_type: str
    documentation: str = ""
    tags: list[str] = []
    categories: list[str] = []
    inputs: dict[str, InputFieldSchema] = {}
    outputs: dict[str, OutputFieldSchema] = {}
    environment: dict[str, Any] | None = None


# --- Package info ---


class PackageInfo(BaseModel):
    name: str
    installed_versions: list[str] = []
    available_versions: list[str] = []
    tools: dict[str, list[str]] = {}
    environment_status: str = "stopped"


# --- Request/Response models ---


class ToolCreate(BaseModel):
    name: str
    tool_type: Literal["ProcessingTool", "DataFrameTool"]


class ToolRename(BaseModel):
    new_name: str


# --- App configuration ---


@dataclass
class AppConfig:
    tool_registry: ToolRegistryService | None = None
    workflow_root: Path | None = None
    deployment_mode: str = "desktop"
    package_installer: PackageInstallerService | None = None
    static_dir: Path | None = None
