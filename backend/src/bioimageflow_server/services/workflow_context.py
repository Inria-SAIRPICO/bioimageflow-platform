"""Helpers for resolving optional workflow-scoped runtime context."""

from __future__ import annotations

from pathlib import Path

from bioimageflow_server.services.workflow_store import WorkflowStoreService


def normalize_workflow_storage_path(path: Path | str | None) -> Path | None:
    """Return an absolute server-side workflow storage path."""
    if path is None:
        return None
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return Path.cwd() / candidate


def resolve_workflow_storage_path(
    workflow_name: str | None,
    workflow_store: WorkflowStoreService | None,
    fallback_storage_path: Path | None,
) -> Path | None:
    """Return the storage root for a named workflow, or the fallback root."""
    if workflow_name and workflow_store is not None:
        return normalize_workflow_storage_path(workflow_store.get_storage_path(workflow_name))
    return normalize_workflow_storage_path(fallback_storage_path)
