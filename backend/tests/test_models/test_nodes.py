"""Tests for node output API models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.nodes import NodeDataResponse


def test_node_data_response_construction() -> None:
    response = NodeDataResponse(
        columns=["mask", "cell_count"],
        index=["img_001"],
        rows=[{"mask": "/tmp/mask.tif", "cell_count": 42}],
        absolute_rows=[0],
        total_rows=1,
        unfiltered_total_rows=1,
        page=0,
        page_size=50,
        column_types={"mask": "ImageFile", "cell_count": "int"},
    )
    assert response.total_rows == 1
    assert response.page == 0
    assert response.column_types["mask"] == "ImageFile"


def test_node_data_response_empty() -> None:
    response = NodeDataResponse(
        columns=[],
        index=[],
        rows=[],
        absolute_rows=[],
        total_rows=0,
        unfiltered_total_rows=0,
        page=0,
        page_size=50,
        column_types={},
    )
    assert response.rows == []
    assert response.columns == []
    assert response.absolute_rows == []


def test_node_data_response_unicode_columns() -> None:
    response = NodeDataResponse(
        columns=["cellen_zahl", "masque_é"],
        index=["0"],
        rows=[{"cellen_zahl": 3, "masque_é": "m.tif"}],
        absolute_rows=[0],
        total_rows=1,
        unfiltered_total_rows=1,
        page=0,
        page_size=50,
        column_types={"cellen_zahl": "int", "masque_é": "ImageFile"},
    )
    assert response.column_types["masque_é"] == "ImageFile"


def test_absolute_rows_length_must_match_rows() -> None:
    with pytest.raises(ValidationError):
        NodeDataResponse(
            columns=["x"],
            index=["0"],
            rows=[{"x": 1}],
            absolute_rows=[],
            total_rows=1,
            unfiltered_total_rows=1,
            page=0,
            page_size=50,
            column_types={"x": "int"},
        )


def test_row_keys_must_match_columns() -> None:
    with pytest.raises(ValidationError):
        NodeDataResponse(
            columns=["x"],
            index=["0"],
            rows=[{"x": 1, "_absolute_row": 0}],
            absolute_rows=[0],
            total_rows=1,
            unfiltered_total_rows=1,
            page=0,
            page_size=50,
            column_types={"x": "int"},
        )


def test_column_types_keys_must_match_columns() -> None:
    with pytest.raises(ValidationError):
        NodeDataResponse(
            columns=["x"],
            index=["0"],
            rows=[{"x": 1}],
            absolute_rows=[0],
            total_rows=1,
            unfiltered_total_rows=1,
            page=0,
            page_size=50,
            column_types={"y": "int"},
        )
