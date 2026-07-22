"""Models for node output data APIs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from bioimageflow_server.models.data_table import DataTableFilter


class NodeDataQueryRequest(BaseModel):
    """Server-side query for one node's output DataFrame."""

    workflow_name: str | None = None
    tool_name: str | None = None
    page: int = Field(default=0, ge=0)
    page_size: int = Field(default=250, ge=1, le=500)
    sort_by: str | None = None
    sort_order: Literal["asc", "desc"] = "asc"
    filters: list[DataTableFilter] = Field(default_factory=list)


class NodeDataCsvRequest(BaseModel):
    """Full filtered CSV query for one node's output DataFrame."""

    workflow_name: str | None = None
    columns: list[str] | None = None
    sort_by: str | None = None
    sort_order: Literal["asc", "desc"] = "asc"
    filters: list[DataTableFilter] = Field(default_factory=list)


class NodeDataResponse(BaseModel):
    """Paginated DataFrame payload for the Node Data panel."""

    columns: list[str]
    index: list[str]
    rows: list[dict[str, Any]]
    absolute_rows: list[int]
    total_rows: int
    unfiltered_total_rows: int
    page: int
    page_size: int
    column_types: dict[str, str]

    @model_validator(mode="after")
    def _validate_parallel_shapes(self) -> "NodeDataResponse":
        if len(self.absolute_rows) != len(self.rows):
            raise ValueError("absolute_rows length must match rows length")

        column_set = set(self.columns)
        if set(self.column_types) != column_set:
            raise ValueError("column_types keys must match columns")

        for row in self.rows:
            if set(row) != column_set:
                raise ValueError("row keys must match columns")

        return self
