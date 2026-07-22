"""Shared filtering and sorting primitives for Node Data queries."""

from __future__ import annotations

import re
from typing import Literal, cast

import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

from bioimageflow_server.models.data_table import DataTableFilter


class DataFrameQueryError(ValueError):
    """Raised when a Node Data query cannot be applied to a DataFrame."""


def filter_positions(
    dataframe: pd.DataFrame,
    filters: list[DataTableFilter],
) -> list[int]:
    """Return zero-based positions matching every requested filter."""
    if not filters:
        return list(range(len(dataframe)))

    combined = pd.Series(True, index=range(len(dataframe)), dtype=bool)
    for item in filters:
        if item.column not in dataframe.columns:
            raise DataFrameQueryError(f"Unknown filter column: '{item.column}'")
        series = cast(pd.Series, dataframe[item.column]).reset_index(drop=True)
        combined &= _filter_mask(series, item)
    return combined[combined].index.tolist()


def sort_positions(
    dataframe: pd.DataFrame,
    sort_by: str | None,
    sort_order: Literal["asc", "desc"],
) -> list[int]:
    """Return stable zero-based positions for the requested ordering."""
    if sort_by is None:
        return list(range(len(dataframe)))
    if sort_by not in dataframe.columns:
        raise DataFrameQueryError(f"Unknown sort column: '{sort_by}'")
    series = cast(pd.Series, dataframe[sort_by]).reset_index(drop=True)
    try:
        return series.sort_values(
            ascending=(sort_order == "asc"),
            kind="mergesort",
        ).index.tolist()
    except (TypeError, ValueError) as exc:
        raise DataFrameQueryError(
            f"Column '{sort_by}' cannot be sorted: {exc}"
        ) from exc


def _filter_mask(series: pd.Series, item: DataTableFilter) -> pd.Series:
    empty = series.isna() | series.map(lambda value: isinstance(value, str) and value == "")
    if item.operator == "is_empty":
        return empty
    if item.operator == "is_not_empty":
        return ~empty

    if item.operator in {"contains", "starts_with"}:
        if not isinstance(item.value, str):
            raise DataFrameQueryError(
                f"Filter '{item.operator}' for '{item.column}' requires text"
            )
        text = series.astype("string")
        if item.operator == "contains":
            return text.str.contains(
                re.escape(item.value), case=False, regex=True, na=False
            )
        return text.str.lower().str.startswith(item.value.lower(), na=False)

    if item.operator in {"equals", "not_equals"}:
        try:
            result = series.eq(item.value).fillna(False)
        except (TypeError, ValueError) as exc:
            raise DataFrameQueryError(
                f"Invalid value for filter on '{item.column}': {exc}"
            ) from exc
        return ~result if item.operator == "not_equals" else result

    if not is_numeric_dtype(series.dtype) or is_bool_dtype(series.dtype):
        raise DataFrameQueryError(
            f"Filter '{item.operator}' requires a numeric column, got '{item.column}'"
        )
    if isinstance(item.value, bool) or not isinstance(item.value, (int, float)):
        raise DataFrameQueryError(
            f"Filter '{item.operator}' for '{item.column}' requires a number"
        )

    try:
        if item.operator == "gt":
            return series.gt(item.value).fillna(False)
        if item.operator == "gte":
            return series.ge(item.value).fillna(False)
        if item.operator == "lt":
            return series.lt(item.value).fillna(False)
        if item.operator == "lte":
            return series.le(item.value).fillna(False)
        if item.operator == "between":
            if isinstance(item.second_value, bool) or not isinstance(
                item.second_value, (int, float)
            ):
                raise DataFrameQueryError(
                    f"Filter 'between' for '{item.column}' requires two numbers"
                )
            return series.between(item.value, item.second_value, inclusive="both").fillna(False)
    except (TypeError, ValueError) as exc:
        raise DataFrameQueryError(
            f"Invalid value for filter on '{item.column}': {exc}"
        ) from exc
    raise DataFrameQueryError(f"Unsupported filter operator: '{item.operator}'")
