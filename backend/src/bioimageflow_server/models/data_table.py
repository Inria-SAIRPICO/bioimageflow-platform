"""Models for consolidated Data Table APIs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class DataTableSource(BaseModel):
    """A frontend-resolved DataFrame output participating in a projection."""

    node_id: str = Field(min_length=1)
    role: Literal["anchor", "context"]
    label: str = Field(min_length=1)
    tool_name: str | None = None
    columns: list[str] | None = None
    column_aliases: dict[str, str] = Field(default_factory=dict)


class DataTableQueryRequest(BaseModel):
    """Consolidated Data Table query parameters."""

    workflow_id: str | None = None
    sources: list[DataTableSource] = Field(min_length=1)
    page: int = Field(default=0, ge=0)
    page_size: int = Field(default=50, ge=1, le=500)
    sort_by: str | None = None
    sort_order: Literal["asc", "desc"] = "asc"

    @model_validator(mode="after")
    def _require_anchor_and_unique_sources(self) -> "DataTableQueryRequest":
        if not any(source.role == "anchor" for source in self.sources):
            raise ValueError("at least one source must be an anchor")
        node_ids = [source.node_id for source in self.sources]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("source node_id values must be unique")
        return self


class DataTableCsvRequest(BaseModel):
    """Full consolidated CSV request."""

    workflow_id: str | None = None
    sources: list[DataTableSource] = Field(min_length=1)
    sort_by: str | None = None
    sort_order: Literal["asc", "desc"] = "asc"

    @model_validator(mode="after")
    def _require_anchor_and_unique_sources(self) -> "DataTableCsvRequest":
        if not any(source.role == "anchor" for source in self.sources):
            raise ValueError("at least one source must be an anchor")
        node_ids = [source.node_id for source in self.sources]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("source node_id values must be unique")
        return self


class DataTableColumn(BaseModel):
    id: str
    label: str
    type: str
    source_node_id: str
    source_column: str


class DataTableMergedRow(BaseModel):
    index: str
    values: dict[str, Any]
    source_rows: dict[str, int]


class DataTableMergedResponse(BaseModel):
    mode: Literal["merged"] = "merged"
    sources: list[DataTableSource]
    columns: list[DataTableColumn]
    rows: list[DataTableMergedRow]
    total_rows: int
    page: int
    page_size: int


class DataTableStackedResponse(BaseModel):
    mode: Literal["stacked"] = "stacked"
    sources: list[DataTableSource]
    reason: str
    message: str


DataTableQueryResponse = DataTableMergedResponse | DataTableStackedResponse
