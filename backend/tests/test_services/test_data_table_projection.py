from pathlib import Path

import pandas as pd

from bioimageflow_server.models.data_table import (
    DataTableFilter,
    DataTableSource,
    DataTableStackedResponse,
)
from bioimageflow_server.services.data_table_projection import DataTableProjectionService


class FakeResultStore:
    def __init__(self, frames: dict[str, pd.DataFrame]):
        self.frames = frames
        self.resolved: list[str] = []
        self.loaded: list[str] = []

    def get_latest_record_dir(self, node_id: str, storage_path: Path | None = None) -> Path:
        self.resolved.append(node_id)
        return Path("/records") / node_id

    def get_dataframe_from_record(self, record_dir: Path, *, node_id: str) -> pd.DataFrame:
        assert self.resolved == list(self.frames), "all record pointers must be resolved before loading"
        self.loaded.append(node_id)
        return self.frames[node_id]

    def get_column_types(self, dataframe: pd.DataFrame, tool_name: str | None = None):
        return {str(column): "int" for column in dataframe.columns}


def source(node_id: str, role: str = "anchor", label: str | None = None) -> DataTableSource:
    return DataTableSource(node_id=node_id, role=role, label=label or node_id)


def query(frames: dict[str, pd.DataFrame], sources: list[DataTableSource], **kwargs):
    store = FakeResultStore(frames)
    result = DataTableProjectionService(store).query(
        sources,
        storage_path=None,
        page=kwargs.get("page", 0),
        page_size=kwargs.get("page_size", 50),
        sort_by=kwargs.get("sort_by"),
        sort_order=kwargs.get("sort_order", "asc"),
        filters=kwargs.get("filters", []),
    )
    return result, store


def test_exact_indices_merge_and_snapshot_records_before_loading() -> None:
    result, store = query(
        {
            "a": pd.DataFrame({"input": [1, 2]}, index=["r0", "r1"]),
            "b": pd.DataFrame({"output": [10, 20]}, index=["r0", "r1"]),
        },
        [source("a", "context"), source("b")],
    )

    assert result.mode == "merged"
    assert [row.values for row in result.rows] == [
        {"s0:input": 1, "s1:output": 10},
        {"s0:input": 2, "s1:output": 20},
    ]
    assert result.rows[1].source_rows == {"a": 1, "b": 1}
    assert store.resolved == ["a", "b"]
    assert store.loaded == ["a", "b"]


def test_parent_values_expand_to_finest_selected_lineage() -> None:
    result, _ = query(
        {
            "a": pd.DataFrame({"input": [7]}, index=["r0"]),
            "b": pd.DataFrame({"tile": [1, 2]}, index=["r0::0", "r0::1"]),
            "c": pd.DataFrame({"score": [0.5, 0.7]}, index=["r0::0", "r0::1"]),
        },
        [source("a"), source("b"), source("c")],
    )

    assert result.mode == "merged"
    assert [row.index for row in result.rows] == ["r0::0", "r0::1"]
    assert [row.values["s0:input"] for row in result.rows] == [7, 7]


def test_filtered_selected_anchor_falls_back_instead_of_losing_rows() -> None:
    result, _ = query(
        {
            "a": pd.DataFrame({"input": [1, 2]}, index=["r0", "r1"]),
            "b": pd.DataFrame({"output": [10]}, index=["r0"]),
        },
        [source("a"), source("b")],
    )

    assert isinstance(result, DataTableStackedResponse)
    assert result.reason == "anchor_rows_would_be_lost"


def test_extra_context_rows_may_be_omitted() -> None:
    result, _ = query(
        {
            "a": pd.DataFrame({"input": [1, 2]}, index=["r0", "r1"]),
            "b": pd.DataFrame({"output": [10]}, index=["r0"]),
        },
        [source("a", "context"), source("b")],
    )

    assert result.mode == "merged"
    assert [row.index for row in result.rows] == ["r0"]


def test_duplicate_and_divergent_indices_fall_back() -> None:
    duplicate, _ = query(
        {"a": pd.DataFrame({"x": [1, 2]}, index=["r0", "r0"])},
        [source("a")],
    )
    divergent, _ = query(
        {
            "a": pd.DataFrame({"x": [1]}, index=["r0::left"]),
            "b": pd.DataFrame({"y": [2]}, index=["r0::right"]),
        },
        [source("a"), source("b")],
    )

    assert duplicate.mode == "stacked"
    assert duplicate.reason == "non_unique_index"
    assert divergent.mode == "stacked"


def test_colliding_labels_are_qualified_and_sort_happens_before_paging() -> None:
    first = source("a", "context", "Input")
    second = source("b", label="Result")
    first.column_aliases = {"value": "measurement"}
    second.column_aliases = {"value": "measurement"}
    result, _ = query(
        {
            "a": pd.DataFrame({"value": [1, 2, 3]}, index=["r0", "r1", "r2"]),
            "b": pd.DataFrame({"value": [10, 30, 20]}, index=["r0", "r1", "r2"]),
        },
        [first, second],
        page_size=2,
        sort_by="s1:value",
        sort_order="desc",
    )

    assert result.mode == "merged"
    assert [column.label for column in result.columns] == [
        "Input: measurement",
        "Result: measurement",
    ]
    assert [row.index for row in result.rows] == ["r1", "r2"]
    assert result.rows[0].source_rows == {"a": 1, "b": 1}


def test_filters_apply_before_sorting_and_paging_and_report_both_totals() -> None:
    result, _ = query(
        {
            "a": pd.DataFrame({"input": [1, 2, 3, 4]}, index=["r0", "r1", "r2", "r3"]),
            "b": pd.DataFrame({"score": [10, 40, 20, 30]}, index=["r0", "r1", "r2", "r3"]),
        },
        [source("a", "context"), source("b")],
        page_size=2,
        sort_by="s1:score",
        sort_order="desc",
        filters=[DataTableFilter(column="s1:score", operator="gte", value=20)],
    )

    assert result.mode == "merged"
    assert result.total_rows == 3
    assert result.unfiltered_total_rows == 4
    assert [row.index for row in result.rows] == ["r1", "r3"]


def test_empty_sources_merge_only_when_all_requested_sources_are_empty() -> None:
    merged, _ = query(
        {
            "a": pd.DataFrame({"x": []}),
            "b": pd.DataFrame({"y": []}),
        },
        [source("a", "context"), source("b")],
    )
    fallback, _ = query(
        {
            "a": pd.DataFrame({"x": [1]}, index=["r0"]),
            "b": pd.DataFrame({"y": []}),
        },
        [source("a", "context"), source("b")],
    )

    assert merged.mode == "merged"
    assert merged.rows == []
    assert fallback.mode == "stacked"
    assert fallback.reason == "incompatible_empty_results"
