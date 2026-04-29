"""Models for node output data APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, model_validator


class NodeDataResponse(BaseModel):
    """Paginated DataFrame payload for the Data Table panel."""

    columns: list[str]
    index: list[str]
    rows: list[dict[str, Any]]
    absolute_rows: list[int]
    total_rows: int
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
