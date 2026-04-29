"""Tool and package metadata models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from bioimageflow_server.models.settings import Settings
    from bioimageflow_server.services.known_packages import KnownPackagesService
    from bioimageflow_server.services.napari_launcher import NapariLauncher
    from bioimageflow_server.services.package_catalog import PackageCatalogService
    from bioimageflow_server.services.package_installer import PackageInstallerService
    from bioimageflow_server.services.pypi_versions import PyPIVersionService
    from bioimageflow_server.services.result_store import ResultStoreService
    from bioimageflow_server.services.settings_store import SettingsStore
    from bioimageflow_server.services.thumbnail_manager import ThumbnailManager
    from bioimageflow_server.services.tool_registry import ToolRegistryService
    from bioimageflow_server.ws.handler import ConnectionManager


# --- Field schemas ---


class InputFieldSchema(BaseModel):
    type: str
    required: bool
    nullable: bool = False
    connectable: Literal["never", "not_by_default", "by_default"]
    default: Any = None
    display_name: str | None = None
    description: str | None = None
    group: str | None = None
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: list[str] | None = None
    image_spec: dict[str, list[str]] | None = None


class OutputFieldSchema(BaseModel):
    type: str
    default: Any = None
    image_spec: dict[str, list[str]] | None = None


# Passthrough marker for DataFrameTool outputs that inherit upstream columns.
# When present, `ToolMetadata.outputs` is ``{"_passthrough": True}`` instead of
# a per-field dict. Modelled as ``dict[str, Any]`` to keep OpenAPI generation
# straightforward.
#
# --- Tool metadata ---


class ToolMetadata(BaseModel):
    name: str
    display_name: str
    package: str
    package_version: str
    tool_type: Literal["ProcessingTool", "DataFrameTool"]
    accepts_upstream: bool = True
    dynamic_outputs: bool = False
    documentation: str = ""
    tags: list[str] = []
    categories: list[str] = []
    inputs: dict[str, InputFieldSchema] = {}
    outputs: dict[str, Any] = {}
    environment: dict[str, Any] | None = None


# --- Package info ---


class PackageInfo(BaseModel):
    name: str
    installed_versions: list[str] = []
    available_versions: list[str] = []
    # The version currently active for the workflow. There is one active
    # version per package — switching it via POST /tools/packages/{name}/use
    # rebinds the library registry's class index so every node from this
    # package resolves to the chosen version's class. ``None`` while no
    # version is installed.
    active_version: str | None = None
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
    known_packages: KnownPackagesService | None = None
    pypi_versions: PyPIVersionService | None = None
    package_catalog: PackageCatalogService | None = None
    static_dir: Path | None = None
    datasets_root: Path | None = None
    max_upload_size: int | None = None
    storage_path: Path | None = None
    result_store: ResultStoreService | None = None
    thumbnail_manager: ThumbnailManager | None = None
    execution_manager: Any | None = None
    settings: Settings | None = None
    # Authoritative live source when set; ``settings`` becomes a snapshot
    # fallback used only when ``settings_store`` is None (CLI / tests).
    settings_store: SettingsStore | None = None
    connection_manager: ConnectionManager | None = None
    napari_launcher: NapariLauncher | None = None
    # Set True in tests that don't want a watchdog Observer running. The
    # production app builds the service inside ``create_app`` from the
    # resolved registry + connection_manager + tool-store path.
    disable_hot_reload: bool = False
