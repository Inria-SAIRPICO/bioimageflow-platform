"""Tests for shared Node Data filtering and sorting."""

import pandas as pd
import pytest

from bioimageflow_server.models.data_table import DataTableFilter, DataTableFilterOperator
from bioimageflow_server.services.dataframe_query import (
    DataFrameQueryError,
    filter_positions,
    sort_positions,
)


def item(
    column: str,
    operator: DataTableFilterOperator,
    value=None,
    second_value=None,
) -> DataTableFilter:
    payload = {"column": column, "operator": operator}
    if value is not None:
        payload["value"] = value
    if second_value is not None:
        payload["second_value"] = second_value
    return DataTableFilter.model_validate(payload)


def test_text_filters_are_case_insensitive_and_combine_with_and() -> None:
    dataframe = pd.DataFrame({
        "path": ["/A/Cells.TIF", "/b/cells.tif", "/a/mask.tif"],
        "score": [1, 3, 5],
    })

    positions = filter_positions(dataframe, [
        item("path", "starts_with", "/a"),
        item("path", "contains", "tif"),
        item("score", "gte", 2),
    ])

    assert positions == [2]


def test_numeric_between_and_empty_filters() -> None:
    dataframe = pd.DataFrame({
        "score": [1.0, 2.0, 3.0, 4.0],
        "label": [None, "", "cell", " "],
    })

    assert filter_positions(dataframe, [item("score", "between", 2, 3)]) == [1, 2]
    assert filter_positions(dataframe, [item("label", "is_empty")]) == [0, 1]
    assert filter_positions(dataframe, [item("label", "is_not_empty")]) == [2, 3]


def test_invalid_filter_column_and_operator_type_are_rejected() -> None:
    dataframe = pd.DataFrame({"label": ["one"]})

    with pytest.raises(DataFrameQueryError, match="Unknown filter column"):
        filter_positions(dataframe, [item("missing", "equals", "one")])
    with pytest.raises(DataFrameQueryError, match="requires a numeric column"):
        filter_positions(dataframe, [item("label", "gt", 1)])


def test_sort_positions_are_stable_and_validate_columns() -> None:
    dataframe = pd.DataFrame({"score": [2, 1, 2]})

    assert sort_positions(dataframe, "score", "asc") == [1, 0, 2]
    with pytest.raises(DataFrameQueryError, match="Unknown sort column"):
        sort_positions(dataframe, "missing", "asc")
