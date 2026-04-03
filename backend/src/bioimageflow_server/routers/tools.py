"""Tools panel router."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from bioimageflow_server.models.tools import (
    PackageInfo,
    ToolCreate,
    ToolMetadata,
    ToolRename,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService

router = APIRouter(prefix="/tools", tags=["tools"])


# ---------------------------------------------------------------------------
# Dependency stubs – overridden via app.dependency_overrides in create_app()
# ---------------------------------------------------------------------------


def get_tool_registry() -> ToolRegistryService:  # pragma: no cover
    raise RuntimeError("tool_registry dependency not configured")


def get_workflow_root() -> Path | None:  # pragma: no cover
    return None


def get_deployment_mode() -> str:  # pragma: no cover
    return "desktop"


def get_package_installer() -> Any:  # pragma: no cover
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _name_to_snake(name: str) -> str:
    return _CAMEL_BOUNDARY.sub("_", name).lower().replace(" ", "_")


def _name_to_display(name: str) -> str:
    spaced = _CAMEL_BOUNDARY.sub(" ", name)
    return spaced.replace("_", " ").strip()


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_PROCESSING_TEMPLATE = '''\
"""Auto-generated ProcessingTool: {display_name}."""


class {class_name}:
    """Processing tool that operates on individual rows."""

    display_name = "{display_name}"

    def process_row(self, row):
        raise NotImplementedError
'''

_DATAFRAME_TEMPLATE = '''\
"""Auto-generated DataFrameTool: {display_name}."""


class {class_name}:
    """DataFrame tool that transforms an entire dataframe."""

    display_name = "{display_name}"

    def transform(self, df):
        raise NotImplementedError
'''

_TEMPLATES = {
    "ProcessingTool": _PROCESSING_TEMPLATE,
    "DataFrameTool": _DATAFRAME_TEMPLATE,
}


# ---------------------------------------------------------------------------
# GET endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_tools(
    registry: ToolRegistryService = Depends(get_tool_registry),
) -> list[ToolMetadata]:
    return registry.list_tools()


@router.get("/packages")
async def list_packages(
    registry: ToolRegistryService = Depends(get_tool_registry),
) -> list[PackageInfo]:
    return registry.list_packages()


@router.get("/{tool_name}/source")
async def get_tool_source(
    tool_name: str,
    workflow_root: Path | None = Depends(get_workflow_root),
) -> dict[str, str]:
    if workflow_root is None:
        raise HTTPException(status_code=404, detail="No workflow root configured")
    snake = _name_to_snake(tool_name)
    path = workflow_root / "tools" / f"{snake}.py"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Source for '{tool_name}' not found")
    return {"path": str(path)}


# ---------------------------------------------------------------------------
# POST / PATCH / DELETE endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201)
async def create_tool(
    body: ToolCreate,
    workflow_root: Path | None = Depends(get_workflow_root),
    mode: str = Depends(get_deployment_mode),
) -> dict[str, str]:
    if mode == "webapp":
        raise HTTPException(status_code=403, detail="Tool creation disabled in webapp mode")
    if workflow_root is None:
        raise HTTPException(status_code=400, detail="No workflow root configured")

    snake = _name_to_snake(body.name)
    display = _name_to_display(body.name)
    dest = workflow_root / "tools" / f"{snake}.py"

    if dest.exists():
        raise HTTPException(status_code=409, detail=f"Tool file '{snake}.py' already exists")

    dest.parent.mkdir(parents=True, exist_ok=True)

    template = _TEMPLATES[body.tool_type]
    dest.write_text(template.format(class_name=body.name, display_name=display))

    return {"path": str(dest)}


@router.patch("/{tool_name}")
async def rename_tool(
    tool_name: str,
    body: ToolRename,
    workflow_root: Path | None = Depends(get_workflow_root),
    mode: str = Depends(get_deployment_mode),
) -> dict[str, str]:
    if workflow_root is None:
        raise HTTPException(status_code=400, detail="No workflow root configured")

    old_snake = _name_to_snake(tool_name)
    old_path = workflow_root / "tools" / f"{old_snake}.py"
    if not old_path.exists():
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    new_snake = _name_to_snake(body.new_name)
    new_path = workflow_root / "tools" / f"{new_snake}.py"
    old_path.rename(new_path)

    return {"path": str(new_path)}


@router.delete("/{tool_name}", status_code=200)
async def delete_tool(
    tool_name: str,
    workflow_root: Path | None = Depends(get_workflow_root),
    mode: str = Depends(get_deployment_mode),
) -> dict[str, str]:
    if workflow_root is None:
        raise HTTPException(status_code=400, detail="No workflow root configured")

    snake = _name_to_snake(tool_name)
    path = workflow_root / "tools" / f"{snake}.py"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    path.unlink()
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Package install/uninstall
# ---------------------------------------------------------------------------


@router.post("/packages/{package_name}/install")
async def install_package(
    package_name: str,
    installer: Any = Depends(get_package_installer),
) -> dict[str, str]:
    if installer is None:
        raise HTTPException(status_code=500, detail="Package installer not configured")
    try:
        await installer.install(package_name)
    except PackageNotFoundError:
        raise HTTPException(status_code=404, detail=f"Package '{package_name}' not found")
    except PackageNetworkError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"status": "installed"}


@router.delete("/packages/{package_name}")
async def uninstall_package(
    package_name: str,
    installer: Any = Depends(get_package_installer),
) -> dict[str, str]:
    if installer is None:
        raise HTTPException(status_code=500, detail="Package installer not configured")
    try:
        await installer.uninstall(package_name)
    except PackageNotFoundError:
        raise HTTPException(status_code=404, detail=f"Package '{package_name}' not found")
    except PackageNetworkError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"status": "uninstalled"}


# ---------------------------------------------------------------------------
# Environment start/stop
# ---------------------------------------------------------------------------


@router.post("/environments/{env_name}/start")
async def start_environment(env_name: str) -> dict[str, str]:
    return {"environment": env_name, "status": "creating"}


@router.post("/environments/{env_name}/stop")
async def stop_environment(env_name: str) -> dict[str, str]:
    return {"environment": env_name, "status": "stopped"}


# ---------------------------------------------------------------------------
# Import exception classes lazily to avoid circular deps
# ---------------------------------------------------------------------------

from bioimageflow_server.services.package_installer import (  # noqa: E402
    PackageNetworkError,
    PackageNotFoundError,
)
