"""Helpers for resolving optional workflow-scoped runtime context."""

from __future__ import annotations

from pathlib import Path

from bioimageflow_server.services.workflow_store import WorkflowStoreService


def resolve_workflow_storage_path(
    workflow_name: str | None,
    workflow_store: WorkflowStoreService | None,
    fallback_storage_path: Path | None,
) -> Path | None:
    """Return the storage root for a named workflow, or the fallback root."""
    if workflow_name and workflow_store is not None:
        return workflow_store.get_storage_path(workflow_name)
    return fallback_storage_path
