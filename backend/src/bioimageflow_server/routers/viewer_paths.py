"""Shared workflow-result path resolution for desktop image viewers."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from bioimageflow_server.routers.nodes import (
    _coerce_image_path,
    _dataframe_record_dir,
    _get_dataframe_cell,
    _get_node_dataframe,
)
from bioimageflow_server.services.result_store import ResultStoreService
from bioimageflow_server.services.workflow_context import resolve_workflow_storage_path
from bioimageflow_server.services.workflow_store import WorkflowStoreService


def resolve_selected_image_path(
    *,
    node_id: str,
    row: int,
    col: str,
    workflow_name: str | None,
    result_store: ResultStoreService,
    workflow_store: WorkflowStoreService | None,
) -> Path:
    try:
        storage_path = resolve_workflow_storage_path(workflow_name, workflow_store, None)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_name}' not found") from exc

    dataframe = _get_node_dataframe(node_id, result_store, storage_path)
    value = _get_dataframe_cell(dataframe, row, col)
    try:
        return _coerce_image_path(value, storage_path, _dataframe_record_dir(dataframe))
    except HTTPException as exc:
        if exc.status_code == 404:
            raise FileNotFoundError(str(exc.detail)) from exc
        raise
