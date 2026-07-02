"""Tools panel router."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from bioimageflow_server.models.errors import mark_exception_logged
from bioimageflow_server.models.tools import (
    PackageImportResponse,
    PackageImportUrlRequest,
    PackageInfo,
    ToolCreate,
    ToolCreateResponse,
    ToolDeleteResponse,
    ToolMetadata,
    ToolRename,
    ToolRenameResponse,
    ToolSourceResponse,
    ToolUsageResponse,
)
from bioimageflow_server.services.custom_tools import CustomToolService, name_to_snake
from bioimageflow_server.services.known_packages import KnownPackagesService
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService

router = APIRouter(prefix="/tools", tags=["tools"])
_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dependency stubs – overridden via app.dependency_overrides in create_app()
# ---------------------------------------------------------------------------


def get_tool_registry() -> ToolRegistryService:  # pragma: no cover
    raise RuntimeError("tool_registry dependency not configured")


def get_workflow_root() -> Path | None:  # pragma: no cover
    return None


def get_deployment_mode() -> str:  # pragma: no cover
    return "desktop"


def get_unsafe_webapp_features_enabled() -> bool:  # pragma: no cover
    return False


def get_package_installer() -> Any:  # pragma: no cover
    return None


def get_package_catalog() -> Any:  # pragma: no cover
    return None


def get_known_packages() -> KnownPackagesService | None:  # pragma: no cover
    return None


def get_workflow_store() -> WorkflowStoreService | None:  # pragma: no cover
    return None


def get_tool_environment_service() -> Any:  # pragma: no cover
    return None


def _custom_tool_service(
    *,
    workflow_name: str | None,
    workflow_root: Path | None,
    registry: ToolRegistryService,
    workflow_store: WorkflowStoreService | None,
) -> CustomToolService | None:
    _ = workflow_root
    if workflow_name and workflow_store is not None:
        return CustomToolService(workflow_store.workflow_dir(workflow_name), registry)
    return None


def _project_root_for_source(
    source_path: Path,
    *,
    source_kind: str,
    workflow_root: Path | None,
    registry: ToolRegistryService,
) -> Path:
    if source_kind != "custom":
        store_path = registry.tool_store_path()
        if store_path is not None:
            return store_path.resolve()
        return source_path.resolve().parent
    root_candidate = workflow_root.parent if workflow_root.name == "workflows" else workflow_root
    return root_candidate.resolve()


def resolve_tool_source_response(
    *,
    tool_name: str,
    workflow_name: str | None,
    workflow_root: Path | None,
    registry: ToolRegistryService,
    workflow_store: WorkflowStoreService | None,
) -> ToolSourceResponse:
    service = _custom_tool_service(
        workflow_name=workflow_name,
        workflow_root=workflow_root,
        registry=registry,
        workflow_store=workflow_store,
    )
    if service is not None:
        custom_source = service.root / f"{name_to_snake(tool_name)}.py"
        if custom_source.exists():
            return ToolSourceResponse(
                tool_name=tool_name,
                path=str(custom_source.resolve()),
                source_kind="custom",
                editable=True,
            )

    tool = registry.get_tool(tool_name)
    path = registry.resolve_tool_source(tool_name)
    if tool is not None and path is not None:
        return ToolSourceResponse(
            tool_name=tool_name,
            path=str(path),
            source_kind=tool.source_kind,
            editable=tool.editable,
        )
    if tool is not None:
        raise HTTPException(
            status_code=404,
            detail=f"Source for package tool '{tool_name}' could not be resolved",
        )
    raise HTTPException(status_code=404, detail=f"Source for '{tool_name}' not found")


def resolve_tool_project_open_paths(
    *,
    tool_name: str,
    workflow_name: str | None,
    workflow_root: Path | None,
    registry: ToolRegistryService,
    workflow_store: WorkflowStoreService | None,
) -> tuple[Path, Path]:
    source = resolve_tool_source_response(
        tool_name=tool_name,
        workflow_name=workflow_name,
        workflow_root=workflow_root,
        registry=registry,
        workflow_store=workflow_store,
    )
    source_path = Path(source.path)
    return (
        _project_root_for_source(
            source_path,
            source_kind=source.source_kind,
            workflow_root=workflow_root,
            registry=registry,
        ),
        source_path,
    )


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
    catalog: Any = Depends(get_package_catalog),
) -> list[PackageInfo]:
    if catalog is not None:
        return catalog.list_packages()
    return registry.list_packages()


@router.post("/packages/refresh")
async def refresh_packages(
    catalog: Any = Depends(get_package_catalog),
) -> dict[str, str]:
    if catalog is None:
        raise HTTPException(status_code=500, detail="Package catalog not configured")
    try:
        await catalog.refresh()
    except PackageNetworkError as exc:
        _logger.warning("Package catalog refresh failed: %s", exc)
        raise mark_exception_logged(HTTPException(status_code=502, detail=str(exc))) from exc
    return {"status": "refreshed"}


@router.get("/{tool_name}/source", response_model=ToolSourceResponse)
async def get_tool_source(
    tool_name: str,
    workflow_name: str | None = None,
    registry: ToolRegistryService = Depends(get_tool_registry),
    workflow_root: Path | None = Depends(get_workflow_root),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
) -> ToolSourceResponse:
    return resolve_tool_source_response(
        tool_name=tool_name,
        workflow_name=workflow_name,
        workflow_root=workflow_root,
        registry=registry,
        workflow_store=workflow_store,
    )


# ---------------------------------------------------------------------------
# POST / PATCH / DELETE endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201)
async def create_tool(
    body: ToolCreate,
    workflow_name: str | None = None,
    workflow_root: Path | None = Depends(get_workflow_root),
    mode: str = Depends(get_deployment_mode),
    unsafe_webapp_features_enabled: bool = Depends(get_unsafe_webapp_features_enabled),
    registry: ToolRegistryService = Depends(get_tool_registry),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
) -> ToolCreateResponse:
    if mode == "webapp" and not unsafe_webapp_features_enabled:
        raise HTTPException(status_code=403, detail="Tool creation disabled in webapp mode")
    service = _custom_tool_service(
        workflow_name=workflow_name,
        workflow_root=workflow_root,
        registry=registry,
        workflow_store=workflow_store,
    )
    if service is None:
        raise HTTPException(status_code=400, detail="No workflow root configured")
    try:
        path = service.create(body.name, body.tool_type)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=f"Tool '{body.name}' already exists") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ToolCreateResponse(name=body.name, tool_type=body.tool_type, path=str(path))


@router.get("/{tool_name}/usage")
async def get_tool_usage(
    tool_name: str,
    workflow_name: str | None = None,
    workflow_root: Path | None = Depends(get_workflow_root),
    registry: ToolRegistryService = Depends(get_tool_registry),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
) -> ToolUsageResponse:
    service = _custom_tool_service(
        workflow_name=workflow_name,
        workflow_root=workflow_root,
        registry=registry,
        workflow_store=workflow_store,
    )
    if service is None:
        raise HTTPException(status_code=400, detail="No workflow root configured")
    return ToolUsageResponse(
        tool_name=tool_name,
        affected_workflows=service.usage(tool_name, workflow_store),
    )


@router.patch("/{tool_name}")
async def rename_tool(
    tool_name: str,
    body: ToolRename,
    workflow_name: str | None = None,
    workflow_root: Path | None = Depends(get_workflow_root),
    mode: str = Depends(get_deployment_mode),
    unsafe_webapp_features_enabled: bool = Depends(get_unsafe_webapp_features_enabled),
    registry: ToolRegistryService = Depends(get_tool_registry),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
) -> ToolRenameResponse:
    if mode == "webapp" and not unsafe_webapp_features_enabled:
        raise HTTPException(status_code=403, detail="Tool renaming disabled in webapp mode")
    service = _custom_tool_service(
        workflow_name=workflow_name,
        workflow_root=workflow_root,
        registry=registry,
        workflow_store=workflow_store,
    )
    if service is None:
        raise HTTPException(status_code=400, detail="No workflow root configured")
    try:
        path = service.rename(tool_name, body.new_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found") from exc
    except FileExistsError as exc:
        raise HTTPException(
            status_code=409, detail=f"Tool '{body.new_name}' already exists"
        ) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail="Only custom tools can be renamed") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ToolRenameResponse(old_name=tool_name, new_name=body.new_name, path=str(path))


@router.delete("/{tool_name}", status_code=200)
async def delete_tool(
    tool_name: str,
    workflow_name: str | None = None,
    workflow_root: Path | None = Depends(get_workflow_root),
    mode: str = Depends(get_deployment_mode),
    unsafe_webapp_features_enabled: bool = Depends(get_unsafe_webapp_features_enabled),
    registry: ToolRegistryService = Depends(get_tool_registry),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
) -> ToolDeleteResponse:
    if mode == "webapp" and not unsafe_webapp_features_enabled:
        raise HTTPException(status_code=403, detail="Tool deletion disabled in webapp mode")
    service = _custom_tool_service(
        workflow_name=workflow_name,
        workflow_root=workflow_root,
        registry=registry,
        workflow_store=workflow_store,
    )
    if service is None:
        raise HTTPException(status_code=400, detail="No workflow root configured")
    affected = service.usage(tool_name, workflow_store)
    try:
        service.delete(tool_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail="Only custom tools can be deleted") from exc
    warning = "Tool is referenced by saved workflows." if affected else None
    return ToolDeleteResponse(affected_workflows=affected, warning=warning)


# ---------------------------------------------------------------------------
# Package install/uninstall
# ---------------------------------------------------------------------------


async def _refresh_package_catalog(catalog: Any) -> None:
    if catalog is None:
        return
    try:
        await catalog.refresh()
    except PackageNetworkError as exc:
        _logger.warning("Package catalog refresh failed after package operation: %s", exc)


def _package_import_response(result: Any) -> PackageImportResponse:
    return PackageImportResponse(
        status="installed",
        package=result.package,
        version=result.version,
    )


def _ensure_package_source_import_allowed(
    mode: str,
    unsafe_webapp_features_enabled: bool,
) -> None:
    if mode == "webapp" and not unsafe_webapp_features_enabled:
        raise HTTPException(
            status_code=403,
            detail="Custom package source install disabled in webapp mode",
        )


def _ensure_row_package_install_allowed(
    package_name: str,
    mode: str,
    unsafe_webapp_features_enabled: bool,
    known_packages: KnownPackagesService | None,
) -> None:
    if mode != "webapp" or unsafe_webapp_features_enabled:
        return
    known = set(known_packages.list_known_packages() if known_packages is not None else [])
    if package_name not in known:
        raise HTTPException(
            status_code=403,
            detail=f"Package '{package_name}' is not in the approved package list",
        )


def _raise_package_install_error(exc: Exception, package_name: str | None = None) -> None:
    if isinstance(exc, PackageInvalidError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, PackageNotFoundError):
        detail = str(exc) if package_name is None else f"Package '{package_name}' not found"
        raise HTTPException(status_code=404, detail=detail) from exc
    if isinstance(exc, PackageNetworkError):
        _logger.warning(
            "Package operation failed due to network error: package=%s detail=%s",
            package_name,
            exc,
        )
        raise mark_exception_logged(HTTPException(status_code=502, detail=str(exc))) from exc
    raise exc


@router.post("/packages/{package_name}/use")
async def use_package_version(
    package_name: str,
    body: dict[str, str] | None = None,
    registry: ToolRegistryService = Depends(get_tool_registry),
    catalog: Any = Depends(get_package_catalog),
) -> dict[str, str]:
    version = body.get("version") if body else None
    pkg = registry.get_package(package_name)
    if pkg is None:
        raise HTTPException(status_code=404, detail=f"Package '{package_name}' not found")
    if not version:
        return {"package": package_name, "version": "", "status": "active"}
    try:
        registry.set_active_version(package_name, version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # Catalog is the read model that GET /packages serves in production. It
    # was built from the registry but doesn't observe later mutations, so we
    # patch the matching snapshot entry so the next list_packages() reflects
    # the new active version without a PyPI round-trip.
    if catalog is not None and hasattr(catalog, "update_active_version"):
        catalog.update_active_version(package_name, version)
    return {"package": package_name, "version": version, "status": "active"}


@router.post("/packages/import-url", response_model=PackageImportResponse)
async def import_package_from_url(
    body: PackageImportUrlRequest,
    installer: Any = Depends(get_package_installer),
    catalog: Any = Depends(get_package_catalog),
    mode: str = Depends(get_deployment_mode),
    unsafe_webapp_features_enabled: bool = Depends(get_unsafe_webapp_features_enabled),
) -> PackageImportResponse:
    _ensure_package_source_import_allowed(mode, unsafe_webapp_features_enabled)
    if installer is None:
        raise HTTPException(status_code=500, detail="Package installer not configured")
    try:
        result = await installer.install_from_url(body.url)
    except Exception as exc:  # noqa: BLE001 — converted to API error when known
        _raise_package_install_error(exc)
    await _refresh_package_catalog(catalog)
    return _package_import_response(result)


@router.post("/packages/import-archive", response_model=PackageImportResponse)
async def import_package_from_archive(
    archive: UploadFile = File(...),
    installer: Any = Depends(get_package_installer),
    catalog: Any = Depends(get_package_catalog),
    mode: str = Depends(get_deployment_mode),
    unsafe_webapp_features_enabled: bool = Depends(get_unsafe_webapp_features_enabled),
) -> PackageImportResponse:
    _ensure_package_source_import_allowed(mode, unsafe_webapp_features_enabled)
    if installer is None:
        raise HTTPException(status_code=500, detail="Package installer not configured")
    filename = Path(archive.filename or "").name
    if not filename or Path(filename).suffix.lower() != ".zip":
        raise HTTPException(status_code=400, detail="Tool package archive must be a .zip file")

    try:
        with tempfile.TemporaryDirectory(prefix="bif-tool-package-upload-") as tmpdir:
            archive_path = Path(tmpdir) / filename
            with archive_path.open("wb") as handle:
                while chunk := await archive.read(1024 * 1024):
                    handle.write(chunk)
            result = await installer.install_from_archive(archive_path)
    except Exception as exc:  # noqa: BLE001 — converted to API error when known
        _raise_package_install_error(exc)
    finally:
        await archive.close()

    await _refresh_package_catalog(catalog)
    return _package_import_response(result)


@router.post("/packages/{package_name}/install")
async def install_package(
    package_name: str,
    body: dict[str, str] | None = None,
    installer: Any = Depends(get_package_installer),
    catalog: Any = Depends(get_package_catalog),
    mode: str = Depends(get_deployment_mode),
    unsafe_webapp_features_enabled: bool = Depends(get_unsafe_webapp_features_enabled),
    known_packages: KnownPackagesService | None = Depends(get_known_packages),
) -> dict[str, str]:
    _ensure_row_package_install_allowed(
        package_name,
        mode,
        unsafe_webapp_features_enabled,
        known_packages,
    )
    if installer is None:
        raise HTTPException(status_code=500, detail="Package installer not configured")
    version = body.get("version") if body else None
    try:
        await installer.install(package_name, version=version)
    except Exception as exc:  # noqa: BLE001 — converted to API error when known
        _raise_package_install_error(exc, package_name=package_name)
    await _refresh_package_catalog(catalog)
    return {"status": "installed"}


@router.delete("/packages/{package_name}")
async def uninstall_package(
    package_name: str,
    version: str | None = None,
    installer: Any = Depends(get_package_installer),
    catalog: Any = Depends(get_package_catalog),
) -> dict[str, str]:
    if installer is None:
        raise HTTPException(status_code=500, detail="Package installer not configured")
    try:
        await installer.uninstall(package_name, version=version)
    except Exception as exc:  # noqa: BLE001 — converted to API error when known
        _raise_package_install_error(exc, package_name=package_name)
    await _refresh_package_catalog(catalog)
    return {"status": "uninstalled"}


# ---------------------------------------------------------------------------
# Environment start/stop
# ---------------------------------------------------------------------------


@router.post("/environments/{env_name}/start")
async def start_environment(
    env_name: str,
    service: Any = Depends(get_tool_environment_service),
) -> dict[str, str]:
    if service is None:
        return {"environment": env_name, "status": "creating"}
    status = await service.start(env_name)
    return {"environment": env_name, "status": status}


@router.post("/environments/{env_name}/stop")
async def stop_environment(
    env_name: str,
    service: Any = Depends(get_tool_environment_service),
) -> dict[str, str]:
    if service is None:
        return {"environment": env_name, "status": "stopped"}
    status = await service.stop(env_name)
    return {"environment": env_name, "status": status}


# ---------------------------------------------------------------------------
# Import exception classes lazily to avoid circular deps
# ---------------------------------------------------------------------------

from bioimageflow_server.services.package_installer import (  # noqa: E402
    PackageInvalidError,
    PackageNetworkError,
    PackageNotFoundError,
)
