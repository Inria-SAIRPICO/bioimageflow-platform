from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pandas as pd
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig

pytestmark = pytest.mark.anyio


def configured_store(frames: dict[str, pd.DataFrame]) -> MagicMock:
    store = MagicMock()
    store.get_latest_record_dir.side_effect = lambda node_id, **_: Path("/records") / node_id
    store.get_dataframe_from_record.side_effect = lambda _record, node_id: frames[node_id]
    store.get_column_types.side_effect = lambda dataframe, **_: {
        str(column): "int" for column in dataframe.columns
    }
    return store


async def client_for(store: MagicMock) -> httpx.AsyncClient:
    app = create_app(AppConfig(result_store=store))
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def payload() -> dict[str, object]:
    return {
        "workflow_id": None,
        "sources": [
            {"node_id": "a", "role": "context", "label": "A"},
            {"node_id": "b", "role": "anchor", "label": "B"},
        ],
        "page": 0,
        "page_size": 50,
        "sort_order": "asc",
    }


async def test_query_returns_merged_contract() -> None:
    store = configured_store({
        "a": pd.DataFrame({"x": [1]}, index=["r0"]),
        "b": pd.DataFrame({"y": [2]}, index=["r0"]),
    })
    async with await client_for(store) as client:
        response = await client.post("/api/v1/data-table/query", json=payload())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "merged"
    assert body["rows"] == [{
        "index": "r0",
        "values": {"s0:x": 1, "s1:y": 2},
        "source_rows": {"a": 0, "b": 0},
    }]


async def test_query_returns_stacked_contract_for_unsafe_alignment() -> None:
    store = configured_store({
        "a": pd.DataFrame({"x": [1, 2]}, index=["r0", "r1"]),
        "b": pd.DataFrame({"y": [2]}, index=["r0"]),
    })
    request = payload()
    request["sources"] = [
        {"node_id": "a", "role": "anchor", "label": "A"},
        {"node_id": "b", "role": "anchor", "label": "B"},
    ]
    async with await client_for(store) as client:
        response = await client.post("/api/v1/data-table/query", json=request)

    assert response.status_code == 200
    assert response.json()["reason"] == "anchor_rows_would_be_lost"


async def test_csv_is_full_sorted_projection_and_fallback_is_conflict() -> None:
    store = configured_store({
        "a": pd.DataFrame({"x": [1, 2]}, index=["r0", "r1"]),
        "b": pd.DataFrame({"y": [10, 20]}, index=["r0", "r1"]),
    })
    request = payload()
    request.pop("page")
    request.pop("page_size")
    request["sort_by"] = "s1:y"
    request["sort_order"] = "desc"
    async with await client_for(store) as client:
        response = await client.post("/api/v1/data-table/csv", json=request)

    assert response.status_code == 200
    assert response.text == ",x,y\nr1,2,20\nr0,1,10\n"

    unsafe = configured_store({
        "a": pd.DataFrame({"x": [1]}, index=["left"]),
        "b": pd.DataFrame({"y": [2]}, index=["right"]),
    })
    async with await client_for(unsafe) as client:
        conflict = await client.post("/api/v1/data-table/csv", json=request)
    assert conflict.status_code == 409


async def test_query_validates_sources_and_resolves_workflow_storage() -> None:
    store = configured_store({
        "a": pd.DataFrame({"x": [1]}, index=["r0"]),
        "b": pd.DataFrame({"y": [2]}, index=["r0"]),
    })
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = Path("/workflows/wf")
    app = create_app(AppConfig(result_store=store, workflow_store=workflow_store))
    request = payload()
    request["workflow_id"] = "wf"
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/data-table/query", json=request)
        invalid = await client.post(
            "/api/v1/data-table/query",
            json={"sources": [{"node_id": "a", "role": "context", "label": "A"}]},
        )

    assert response.status_code == 200
    assert invalid.status_code == 422
    workflow_store.get_storage_path.assert_called_with("wf")
    assert store.get_latest_record_dir.call_args.kwargs["storage_path"] == Path("/workflows/wf")
