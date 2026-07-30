"""Workflow result export API models."""

from __future__ import annotations

from pydantic import BaseModel


class WorkflowResultsFolderExportRequest(BaseModel):
    """Destination selected for a desktop results-folder export."""

    destination_parent: str
    replace: bool = False


class WorkflowResultsFolderExportResponse(BaseModel):
    """Materialized desktop results-folder export."""

    destination: str
    exported_items: int
