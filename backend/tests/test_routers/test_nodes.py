"""Tests for node output data endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pandas as pd
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _client(result_store: MagicMock, thumbnail_service: MagicMock | None = None):
    app = create_app(
        AppConfig(
            result_store=result_store,
            thumbnail_service=thumbnail_service or MagicMock(),
        )
    )
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_get_node_data_returns_page_and_absolute_rows() -> None:
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"x": [3, 1, 2], "y": ["c", "a", "b"]})
    store.get_column_types.return_value = {"x": "int", "y": "str"}
    async with await _client(store) as client:
        resp = await client.get("/api/v1/nodes/n1/data", params={"page_size": 2})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["columns"] == ["x", "y"]
    assert body["rows"] == [{"x": 3, "y": "c"}, {"x": 1, "y": "a"}]
    assert body["absolute_rows"] == [0, 1]
    assert body["total_rows"] == 3


async def test_get_node_data_sort_desc_preserves_original_positions() -> None:
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"x": [3, 1, 2]})
    store.get_column_types.return_value = {"x": "int"}
    async with await _client(store) as client:
        resp = await client.get(
            "/api/v1/nodes/n1/data",
            params={"sort_by": "x", "sort_order": "desc"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [row["x"] for row in body["rows"]] == [3, 2, 1]
    assert body["absolute_rows"] == [0, 2, 1]


async def test_get_node_data_stable_sort() -> None:
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"x": [1, 1, 0], "label": ["a", "b", "c"]})
    store.get_column_types.return_value = {"x": "int", "label": "str"}
    async with await _client(store) as client:
        resp = await client.get("/api/v1/nodes/n1/data", params={"sort_by": "x"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [row["label"] for row in body["rows"]] == ["c", "a", "b"]
    assert body["absolute_rows"] == [2, 0, 1]


async def test_get_node_data_literal_absolute_row_column_round_trips() -> None:
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"_absolute_row": [9]})
    store.get_column_types.return_value = {"_absolute_row": "int"}
    async with await _client(store) as client:
        resp = await client.get("/api/v1/nodes/n1/data")
    assert resp.status_code == 200, resp.text
    assert resp.json()["rows"] == [{"_absolute_row": 9}]


async def test_get_node_data_404_and_422() -> None:
    store = MagicMock()
    store.get_latest_dataframe.return_value = None
    async with await _client(store) as client:
        missing = await client.get("/api/v1/nodes/n1/data")
    assert missing.status_code == 404

    store.get_latest_dataframe.return_value = pd.DataFrame({"x": [1]})
    store.get_column_types.return_value = {"x": "int"}
    async with await _client(store) as client:
        bad_sort = await client.get("/api/v1/nodes/n1/data", params={"sort_by": "nope"})
        bad_size = await client.get("/api/v1/nodes/n1/data", params={"page_size": 0})
    assert bad_sort.status_code == 422
    assert bad_size.status_code == 422


async def test_get_node_data_forwards_tool_name() -> None:
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"x": [1]})
    store.get_column_types.return_value = {"x": "int"}
    async with await _client(store) as client:
        await client.get("/api/v1/nodes/n1/data", params={"tool_name": "ToolA"})
    assert store.get_column_types.call_args.kwargs["tool_name"] == "ToolA"


async def test_download_csv(tmp_path: Path) -> None:
    csv = tmp_path / "dataframe.csv"
    csv.write_text("x\n1\n")
    store = MagicMock()
    store.get_csv_path.return_value = csv
    async with await _client(store) as client:
        resp = await client.get("/api/v1/nodes/n1/data/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "n1.csv" in resp.headers["content-disposition"]
    assert resp.text == "x\n1\n"


async def test_thumbnail_endpoint() -> None:
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"mask": [Path("/tmp/m.tif")]})
    thumbs = MagicMock()
    thumbs.get_thumbnail.return_value = b"\x89PNG\r\n\x1a\n"
    async with await _client(store, thumbs) as client:
        resp = await client.get("/api/v1/nodes/n1/thumbnail", params={"row": 0, "col": "mask", "size": 64})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    thumbs.get_thumbnail.assert_called_with("/tmp/m.tif", size=64)


async def test_thumbnail_endpoint_validation() -> None:
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"mask": ["m.tif"]})
    async with await _client(store) as client:
        bad_col = await client.get("/api/v1/nodes/n1/thumbnail", params={"row": 0, "col": "nope"})
        bad_row = await client.get("/api/v1/nodes/n1/thumbnail", params={"row": 2, "col": "mask"})
        bad_size = await client.get("/api/v1/nodes/n1/thumbnail", params={"row": 0, "col": "mask", "size": 8})
    assert bad_col.status_code == 422
    assert bad_row.status_code == 422
    assert bad_size.status_code == 422
