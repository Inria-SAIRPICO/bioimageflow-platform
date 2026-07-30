"""Safe, self-contained workflow result exports."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from bioimageflow import export_outputs
from bioimageflow.storage import Storage
from bioimageflow.storage.models import CacheCorruptionError

from bioimageflow_server.services.workflow_archive import safe_workflow_export_stem
from bioimageflow_server.services.workflow_store import WorkflowStoreService

RESULTS_BUNDLE_MANIFEST = "bioimageflow-results-bundle.json"
RESULTS_BUNDLE_SCHEMA = "bioimageflow-results-bundle/v1"
OUTPUT_EXPORT_MARKER = ".bioimageflow-output-export.json"
OUTPUT_EXPORT_MARKER_SCHEMA = "bioimageflow.platform.output-export.v1"


class WorkflowExportError(Exception):
    """Expected export failure with a stable API code."""

    def __init__(self, code: str, detail: str, *, status_code: int) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class PreparedDownload:
    """Completed temporary download and the directory that owns it."""

    path: Path
    filename: str
    cleanup_root: Path


@dataclass(frozen=True)
class FolderExport:
    """Completed persistent folder export."""

    destination: Path
    exported_items: int


def _raise(code: str, detail: str, status_code: int) -> NoReturn:
    raise WorkflowExportError(code, detail, status_code=status_code)


def _temporary_root() -> Path:
    return Path(tempfile.mkdtemp(prefix="bioimageflow-export-"))


def _remove_tree(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _zip_tree(source: Path, destination: Path) -> None:
    """Write regular files below source without following or storing symlinks."""

    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                _raise(
                    "results_export_conflict",
                    "Exported results unexpectedly contained a symbolic link",
                    409,
                )
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())


def _translate_library_error(exc: Exception) -> NoReturn:
    if isinstance(exc, CacheCorruptionError):
        _raise("results_export_conflict", str(exc), 409)
    if isinstance(exc, FileExistsError):
        _raise("export_destination_exists", str(exc), 409)
    if isinstance(exc, PermissionError):
        _raise("export_destination_forbidden", str(exc), 403)
    if isinstance(exc, ValueError):
        _raise("unsafe_export_destination", str(exc), 403)
    raise exc


def _ensure_materialized(paths: list[Path]) -> None:
    if not paths:
        _raise(
            "results_not_available",
            "This workflow has no latest results to export",
            409,
        )


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
    except ValueError:
        return False
    return True


def _paths_overlap(first: Path, second: Path) -> bool:
    return _is_relative_to(first, second) or _is_relative_to(second, first)


def _validate_destination_parent(
    raw_parent: str,
    *,
    workspace: Path,
    workflow_dir: Path,
    results_dir: Path,
) -> Path:
    requested = Path(raw_parent)
    if not requested.is_absolute():
        _raise(
            "invalid_export_destination",
            "The export destination parent must be an absolute path",
            422,
        )
    normalized = Path(os.path.abspath(requested))
    try:
        resolved = normalized.resolve(strict=True)
    except FileNotFoundError:
        _raise(
            "invalid_export_destination",
            "The export destination parent must already exist",
            422,
        )
    except PermissionError as exc:
        _raise("export_destination_forbidden", str(exc), 403)
    if normalized != resolved:
        _raise(
            "unsafe_export_destination",
            "Symbolic links are not allowed in an export destination path",
            403,
        )
    if not resolved.is_dir():
        _raise(
            "invalid_export_destination",
            "The export destination parent must be a directory",
            422,
        )

    root = Path(resolved.anchor)
    home = Path.home().resolve()
    protected_trees = (
        workspace.resolve(),
        workflow_dir.resolve(),
        results_dir.resolve(),
    )
    contains_home = _is_relative_to(home, resolved)
    if resolved == root or contains_home or any(
        _paths_overlap(resolved, path) for path in protected_trees
    ):
        _raise(
            "unsafe_export_destination",
            "The export destination must not be the filesystem root or home folder, "
            "and must be outside workspace and workflow data trees",
            403,
        )
    return resolved


def _marker_matches(destination: Path, workflow_id: str) -> bool:
    marker = destination / OUTPUT_EXPORT_MARKER
    if marker.is_symlink() or not marker.is_file():
        return False
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return value == {
        "schema": OUTPUT_EXPORT_MARKER_SCHEMA,
        "workflow_id": workflow_id,
    }


def _write_marker(destination: Path, workflow_id: str) -> None:
    marker = destination / OUTPUT_EXPORT_MARKER
    marker.write_text(
        json.dumps(
            {
                "schema": OUTPUT_EXPORT_MARKER_SCHEMA,
                "workflow_id": workflow_id,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


class WorkflowExportService:
    """Build downloads and persistent copied result folders for one live store."""

    def __init__(self, store: WorkflowStoreService) -> None:
        self.store = store

    def prepare_latest_results(self, workflow_id: str) -> PreparedDownload:
        cleanup_root = _temporary_root()
        stem = safe_workflow_export_stem(workflow_id)
        try:
            with self.store.workflow_mutation(workflow_id):
                storage_path = self.store.get_storage_path(workflow_id)
                try:
                    exported = export_outputs(
                        storage_path,
                        destination=cleanup_root / "staging" / "results",
                        replace=False,
                        mode="copy",
                        scope="latest",
                    )
                except Exception as exc:
                    _translate_library_error(exc)
                _ensure_materialized(exported)
                archive_path = cleanup_root / f"{stem}-latest-results.zip"
                _zip_tree(cleanup_root / "staging" / "results", archive_path)
            return PreparedDownload(
                path=archive_path,
                filename=archive_path.name,
                cleanup_root=cleanup_root,
            )
        except Exception:
            _remove_tree(cleanup_root)
            raise

    def export_latest_results_folder(
        self,
        workflow_id: str,
        *,
        destination_parent: str,
        replace: bool,
    ) -> FolderExport:
        with self.store.workflow_mutation(workflow_id):
            storage_path = self.store.get_storage_path(workflow_id)
            workflow_dir = self.store.workflow_dir(workflow_id)
            parent = _validate_destination_parent(
                destination_parent,
                workspace=self.store.workspace_dir,
                workflow_dir=workflow_dir,
                results_dir=storage_path,
            )
            destination = parent / f"{safe_workflow_export_stem(workflow_id)}-latest-results"
            if destination.is_symlink():
                _raise(
                    "unsafe_export_destination",
                    "The generated export destination must not be a symbolic link",
                    403,
                )
            if destination.exists():
                if not replace:
                    _raise(
                        "export_destination_exists",
                        f"Export destination already exists: {destination}",
                        409,
                    )
                if not destination.is_dir() or not _marker_matches(
                    destination, workflow_id
                ):
                    _raise(
                        "unsafe_export_replacement",
                        "Only a matching BioImageFlow results export can be replaced",
                        409,
                    )
            staging = parent / f".{destination.name}.{uuid.uuid4().hex}.tmp"
            backup = parent / f".{destination.name}.{uuid.uuid4().hex}.backup"
            moved_previous = False
            installed = False
            try:
                try:
                    exported = export_outputs(
                        storage_path,
                        destination=staging,
                        replace=False,
                        mode="copy",
                        scope="latest",
                    )
                except Exception as exc:
                    _translate_library_error(exc)
                _ensure_materialized(exported)
                _write_marker(staging, workflow_id)
                if destination.exists():
                    os.replace(destination, backup)
                    moved_previous = True
                try:
                    os.replace(staging, destination)
                    installed = True
                except BaseException:
                    if moved_previous:
                        os.replace(backup, destination)
                        moved_previous = False
                    raise
                if moved_previous:
                    _remove_tree(backup)
                    moved_previous = False
            except PermissionError as exc:
                _raise("export_destination_forbidden", str(exc), 403)
            finally:
                _remove_tree(staging)
                if (
                    moved_previous
                    and not installed
                    and not (destination.exists() or destination.is_symlink())
                ):
                    os.replace(backup, destination)
                    moved_previous = False
                if not moved_previous:
                    _remove_tree(backup)
            return FolderExport(destination=destination, exported_items=len(exported))

    def prepare_workflow_run_bundle(self, workflow_id: str) -> PreparedDownload:
        cleanup_root = _temporary_root()
        stem = safe_workflow_export_stem(workflow_id)
        bundle_root = cleanup_root / "bundle"
        try:
            with self.store.workflow_mutation(workflow_id):
                filename, workflow_payload = self.store.export_workflow_archive(workflow_id)
                storage_path = self.store.get_storage_path(workflow_id)
                try:
                    run_id = Storage(storage_path).latest_success_run_id()
                except CacheCorruptionError as exc:
                    _translate_library_error(exc)
                if run_id is None:
                    _raise(
                        "results_not_available",
                        "This workflow has no successful run to export",
                        409,
                    )

                nested_filename = filename
                workflow_path = bundle_root / "workflow" / nested_filename
                workflow_path.parent.mkdir(parents=True, exist_ok=True)
                workflow_path.write_bytes(workflow_payload)
                try:
                    exported = export_outputs(
                        storage_path,
                        destination=bundle_root / "results",
                        replace=False,
                        mode="copy",
                        scope="runs",
                        run_id=run_id,
                    )
                except Exception as exc:
                    _translate_library_error(exc)
                if not exported:
                    _raise(
                        "results_export_conflict",
                        f"Successful run '{run_id}' contained no exportable results",
                        409,
                    )

                workflow_member = f"workflow/{nested_filename}"
                results_member = f"results/runs/{run_id}"
                manifest = {
                    "schema": RESULTS_BUNDLE_SCHEMA,
                    "kind": "workflow-with-results",
                    "workflow_id": workflow_id,
                    "workflow": {
                        "archive": workflow_member,
                        "sha256": hashlib.sha256(workflow_payload).hexdigest(),
                    },
                    "results": {
                        "kind": "latest-successful-run",
                        "run_id": run_id,
                        "path": results_member,
                    },
                }
                (bundle_root / RESULTS_BUNDLE_MANIFEST).write_text(
                    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                archive_path = cleanup_root / f"{stem}-workflow-and-results.zip"
                _zip_tree(bundle_root, archive_path)
            return PreparedDownload(
                path=archive_path,
                filename=archive_path.name,
                cleanup_root=cleanup_root,
            )
        except Exception:
            _remove_tree(cleanup_root)
            raise
