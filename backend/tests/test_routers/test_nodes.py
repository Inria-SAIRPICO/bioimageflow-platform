"""Tests for node output data endpoints."""

from __future__ import annotations

import os
import json
import logging
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import httpx
import pandas as pd
import pytest
import tifffile
from httpx import ASGITransport
from PIL import Image
from bioimageflow_core import ViewerSpec as LibraryViewerSpec

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.routers import nodes as nodes_router
from bioimageflow_server.services.result_store import DATAFRAME_RECORD_DIR_ATTR
from bioimageflow_server.models.results import ResultArtifactIdentity
from bioimageflow_server.services.result_store import DATAFRAME_RESULT_IDENTITY_ATTR
from bioimageflow_server.services.result_store import DATAFRAME_RESULT_METADATA_ATTR, ResultColumnMetadata
from bioimageflow_server.services.result_store import ResultStoreService

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _client(result_store: MagicMock, thumbnail_manager: MagicMock | None = None):
    app = create_app(
        AppConfig(
            result_store=result_store,
            thumbnail_manager=thumbnail_manager or _default_thumbnail_mock(),
        )
    )
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _client_with_workflow_store(
    result_store: MagicMock,
    workflow_store: MagicMock,
    thumbnail_manager: MagicMock | None = None,
):
    app = create_app(
        AppConfig(
            result_store=result_store,
            workflow_store=workflow_store,
            thumbnail_manager=thumbnail_manager or _default_thumbnail_mock(),
        )
    )
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _default_thumbnail_mock() -> MagicMock:
    """A no-op manager whose async API returns a small placeholder PNG."""
    from unittest.mock import AsyncMock

    mgr = MagicMock()
    placeholder = b"\x89PNG\r\n\x1a\nplaceholder"
    mgr.placeholder_png.return_value = placeholder
    mgr.get_or_queue = AsyncMock(return_value=placeholder)
    return mgr


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
    assert body["unfiltered_total_rows"] == 3


async def test_post_node_data_filters_before_sorting_and_paging() -> None:
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({
        "path": ["/a/one.tif", "/b/two.tif", "/a/three.tif"],
        "score": [1, 3, 2],
    })
    store.get_column_types.return_value = {"path": "Path", "score": "int"}
    async with await _client(store) as client:
        response = await client.post(
            "/api/v1/nodes/n1/data/query",
            json={
                "page_size": 1,
                "sort_by": "score",
                "sort_order": "desc",
                "filters": [{"column": "path", "operator": "starts_with", "value": "/a"}],
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rows"] == [{"path": "/a/three.tif", "score": 2}]
    assert body["absolute_rows"] == [2]
    assert body["total_rows"] == 2
    assert body["unfiltered_total_rows"] == 3


async def test_pagination_reuses_captured_result_after_latest_changes() -> None:
    identity = ResultArtifactIdentity(
        run_id="run_old",
        node_key="n1",
        result_key="rk_old",
        record_id="rec_old",
    )
    initial = pd.DataFrame({"x": [1, 2]})
    initial.attrs[DATAFRAME_RESULT_IDENTITY_ATTR] = identity
    retained = pd.DataFrame({"x": [1, 2]})
    retained.attrs[DATAFRAME_RESULT_IDENTITY_ATTR] = identity
    store = MagicMock()
    store.get_latest_dataframe.return_value = initial
    store.load_result_dataframe.return_value = retained
    store.get_column_types.return_value = {"x": "int"}
    retained_viewer = LibraryViewerSpec.from_dict({
        "napari": {
            "required_packages": [],
            "recommended_packages": [],
            "napari_version": None,
            "reader_id": "retained.reader",
        }
    })
    for dataframe in (initial, retained):
        dataframe.attrs[DATAFRAME_RESULT_METADATA_ATTR] = ResultColumnMetadata(
            identity=identity, types={"x": "int"}, viewers={"x": retained_viewer},
        )
    async with await _client(store) as client:
        first = await client.get("/api/v1/nodes/n1/data", params={"page_size": 1})
        second = await client.post(
            "/api/v1/nodes/n1/data/query",
            json={
                "page": 1,
                "page_size": 1,
                "result_identity": identity.model_dump(mode="json"),
            },
        )

    assert first.json()["source_identity"] == identity.model_dump(mode="json")
    assert first.json()["column_viewers"]["x"]["napari"]["reader_id"] == "retained.reader"
    assert second.json()["rows"] == [{"x": 2}]
    store.load_result_dataframe.assert_called_once_with(identity, storage_path=None)
    store.result_viewers.assert_not_called()


async def test_legacy_node_data_marks_viewer_metadata_unknown() -> None:
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"image": ["old.tif"]})
    store.get_column_types.return_value = {"image": "ImageFile"}
    async with await _client(store) as client:
        response = await client.get("/api/v1/nodes/n1/data")

    assert response.status_code == 200
    assert response.json()["identity_status"] == "legacy_unpinned"
    assert response.json()["column_viewers"] == {"image": None}
    store.result_viewers.assert_not_called()


async def test_post_node_data_rejects_incompatible_filter() -> None:
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"label": ["cell"]})
    store.get_column_types.return_value = {"label": "str"}
    async with await _client(store) as client:
        response = await client.post(
            "/api/v1/nodes/n1/data/query",
            json={"filters": [{"column": "label", "operator": "gt", "value": 1}]},
        )

    assert response.status_code == 422
    assert "requires a numeric column" in response.json()["detail"]


async def test_get_node_data_accepts_scoped_node_ids() -> None:
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"mask": ["/tmp/m.tif"]})
    store.get_column_types.return_value = {"mask": "ImageFile"}
    async with await _client(store) as client:
        resp = await client.get("/api/v1/nodes/sub_1%2Fsegment_1/data")

    assert resp.status_code == 200, resp.text
    assert resp.json()["page_size"] == 250
    store.get_latest_dataframe.assert_called_once()
    assert store.get_latest_dataframe.call_args.args[0] == "sub_1/segment_1"


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


async def test_get_node_data_returns_409_when_cache_not_ready() -> None:
    from bioimageflow_server.services.result_store import ResultDataNotReadyError

    store = MagicMock()
    store.get_latest_dataframe.side_effect = ResultDataNotReadyError(
        "dataframe.parquet is not ready"
    )
    async with await _client(store) as client:
        resp = await client.get("/api/v1/nodes/n1/data")

    assert resp.status_code == 409
    assert "not ready" in resp.json()["detail"]
    assert resp.json()["error"] == "result_pending"


async def test_node_data_returns_409_if_captured_viewer_metadata_becomes_corrupt() -> None:
    identity = ResultArtifactIdentity(
        run_id="run_0123456789abcdef0123456789abcdef",
        node_key="n1",
        result_key="rk_current",
        record_id="rec_current",
    )
    dataframe = pd.DataFrame({"x": [2]})
    dataframe.attrs[DATAFRAME_RESULT_IDENTITY_ATTR] = identity
    dataframe.attrs[DATAFRAME_RESULT_METADATA_ATTR] = ResultColumnMetadata(
        identity=identity.model_copy(update={"record_id": "rec_other"}), types={"x": "int"}, viewers={},
    )
    store = MagicMock()
    store.get_latest_dataframe.return_value = dataframe
    store.get_column_types.return_value = {"x": "int"}
    async with await _client(store) as client:
        response = await client.post("/api/v1/nodes/n1/data/query", json={})

    assert response.status_code == 409
    assert "metadata identity does not match" in response.json()["detail"]
    assert response.json()["error"] == "result_unavailable"
    store.result_viewers.assert_not_called()


async def test_get_node_data_forwards_tool_name() -> None:
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"x": [1]})
    store.get_column_types.return_value = {"x": "int"}
    async with await _client(store) as client:
        await client.get("/api/v1/nodes/n1/data", params={"tool_name": "ToolA"})
    assert store.get_column_types.call_args.kwargs["tool_name"] == "ToolA"


async def test_get_node_data_resolves_workflow_storage_path(tmp_path: Path) -> None:
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"x": [1]})
    store.get_column_types.return_value = {"x": "int"}
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path / "workflows" / "wf_a"
    async with await _client_with_workflow_store(store, workflow_store) as client:
        resp = await client.get(
            "/api/v1/nodes/n1/data",
            params={"workflow_name": "wf_a"},
        )

    assert resp.status_code == 200
    workflow_store.get_storage_path.assert_called_once_with("wf_a")
    assert (
        store.get_latest_dataframe.call_args.kwargs["storage_path"]
        == tmp_path / "workflows" / "wf_a"
    )


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


async def test_download_csv_uses_verified_modern_record_instead_of_companion_file(
    tmp_path: Path,
) -> None:
    companion = tmp_path / "dataframe.csv"
    companion.write_text("x\n99\n")
    identity = ResultArtifactIdentity(
        run_id="run_0123456789abcdef0123456789abcdef",
        node_key="n1",
        result_key="rk_current",
        record_id="rec_current",
    )
    store = MagicMock()
    store.capture_latest_result_identity.return_value = identity
    store.get_csv_path.return_value = companion
    store.load_result_dataframe.return_value = pd.DataFrame({"x": [2]})
    async with await _client(store) as client:
        response = await client.get("/api/v1/nodes/n1/data/csv")

    assert response.status_code == 200
    assert response.text == ",x\n0,2\n"
    store.load_result_dataframe.assert_called_once_with(identity, storage_path=None)
    store.get_csv_path.assert_not_called()


async def test_download_csv_rejects_corrupt_modern_provenance() -> None:
    from bioimageflow_server.services.result_store import ResultDataNotReadyError

    store = MagicMock()
    store.capture_latest_result_identity.side_effect = ResultDataNotReadyError(
        "Output data for node 'n1' is not ready"
    )
    async with await _client(store) as client:
        response = await client.get("/api/v1/nodes/n1/data/csv")

    assert response.status_code == 409
    store.get_csv_path.assert_not_called()


@pytest.mark.parametrize("node_id", ["n1", "child/inner"])
async def test_forged_in_root_latest_view_refuses_node_data_and_csv(
    tmp_path: Path, node_id: str
) -> None:
    from bioimageflow.cache import dataframe_publish, dataframe_result_key
    from bioimageflow.storage import Storage

    run_id = "run_1123456789abcdef0123456789abcdef"
    dataframe_publish(
        tmp_path, node_id, "historical", pd.DataFrame({"x": [9]}),
        run_id=run_id, engine="direct:parallel", tool_identity="tests:node-data",
    )
    storage = Storage(tmp_path)
    result_key = dataframe_result_key(node_id, "historical")
    pointer = storage.load_current(result_key)
    assert pointer is not None
    storage.write_run_metadata(
        run_id, workflow_identity="test", engine="direct", status="succeeded",
        target_nodes=[node_id],
    )
    storage.write_run_node_result(
        run_id, node_id, result_key=result_key, record_id=pointer.record_id,
        cache_hit=False,
    )
    storage.update_latest_node(node_id, run_id)
    historical = ResultArtifactIdentity(
        run_id=run_id, node_key=node_id, result_key=result_key,
        record_id=pointer.record_id,
    )
    forged = tmp_path / "forged" / "nodes" / node_id
    forged.mkdir(parents=True)
    (forged / "result.json").write_bytes(
        (storage.run_node_dir(run_id, node_id) / "result.json").read_bytes()
    )
    latest = tmp_path / "views" / "latest" / f"{node_id}.bioimageflow-link.json"
    latest.write_text(json.dumps({
        "schema": "bioimageflow.link.v1", "kind": "directory",
        "target": os.path.relpath(forged, latest.parent).replace(os.sep, "/"),
    }))

    store = ResultStoreService(tmp_path, MagicMock(get_tool=MagicMock(return_value=None)))
    async with await _client(store) as client:
        query = await client.post(f"/api/v1/nodes/{node_id}/data/query", json={})
        csv = await client.get(f"/api/v1/nodes/{node_id}/data/csv")

    assert query.status_code == 409
    assert csv.status_code == 409
    assert store.load_result_dataframe(historical)["x"].tolist() == [9]


async def test_download_filtered_csv_honors_filters_sort_and_columns() -> None:
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({
        "label": ["a", "b", "c"],
        "score": [1, 3, 2],
    })
    async with await _client(store) as client:
        response = await client.post(
            "/api/v1/nodes/n1/data/csv",
            json={
                "columns": ["label"],
                "sort_by": "score",
                "sort_order": "desc",
                "filters": [{"column": "score", "operator": "gte", "value": 2}],
            },
        )

    assert response.status_code == 200, response.text
    assert response.text == ",label\n1,b\n2,c\n"


async def test_download_csv_generates_csv_when_only_dataframe_is_available() -> None:
    store = MagicMock()
    store.get_csv_path.return_value = None
    store.get_latest_dataframe.return_value = pd.DataFrame(
        {"x": [1, 2]},
        index=pd.Index(["row0", "row1"]),
    )
    async with await _client(store) as client:
        resp = await client.get("/api/v1/nodes/n1/data/csv")

    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "n1.csv" in resp.headers["content-disposition"]
    assert resp.text == ",x\nrow0,1\nrow1,2\n"


async def test_download_csv_filters_columns_for_scoped_node_id() -> None:
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame(
        {"mask": ["/tmp/m.tif"], "score": [0.9]},
        index=pd.Index(["row0"]),
    )
    async with await _client(store) as client:
        resp = await client.get(
            "/api/v1/nodes/sub_1%2Fsegment_1/data/csv",
            params=[("columns", "mask")],
        )

    assert resp.status_code == 200
    assert resp.text == ",mask\nrow0,/tmp/m.tif\n"
    store.get_csv_path.assert_not_called()
    store.get_latest_dataframe.assert_called_once()
    assert store.get_latest_dataframe.call_args.args[0] == "sub_1/segment_1"


async def test_download_csv_resolves_workflow_storage_path(tmp_path: Path) -> None:
    csv = tmp_path / "dataframe.csv"
    csv.write_text("x\n1\n")
    store = MagicMock()
    store.get_csv_path.return_value = csv
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path / "workflows" / "wf_a"
    async with await _client_with_workflow_store(store, workflow_store) as client:
        resp = await client.get(
            "/api/v1/nodes/n1/data/csv",
            params={"workflow_name": "wf_a"},
        )

    assert resp.status_code == 200
    workflow_store.get_storage_path.assert_called_once_with("wf_a")
    assert (
        store.get_csv_path.call_args.kwargs["storage_path"]
        == tmp_path / "workflows" / "wf_a"
    )


async def test_node_image_endpoint_serves_selected_image_file(tmp_path: Path) -> None:
    image = tmp_path / "mask.ome.tif"
    image.write_bytes(b"II*\x00fake-ome-tiff")
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"mask": [image]})

    async with await _client(store) as client:
        resp = await client.get("/api/v1/nodes/n1/image", params={"row": 0, "col": "mask"})

    assert resp.status_code == 200
    assert resp.content == b"II*\x00fake-ome-tiff"
    assert resp.headers["content-type"].startswith("image/tiff")
    assert "mask.ome.tif" in resp.headers["content-disposition"]
    assert resp.headers["accept-ranges"] == "bytes"


async def test_node_image_endpoint_accepts_filename_suffix_and_serves_inline(tmp_path: Path) -> None:
    image = tmp_path / "mask.ome.tif"
    image.write_bytes(b"II*\x00fake-ome-tiff")
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"mask": [image]})

    async with await _client(store) as client:
        resp = await client.get(
            "/api/v1/nodes/n1/image/mask.ome.tif",
            params={"row": 0, "col": "mask"},
        )

    assert resp.status_code == 200
    assert resp.content == b"II*\x00fake-ome-tiff"
    assert resp.headers["content-type"].startswith("image/tiff")
    assert resp.headers["content-disposition"].startswith("inline")


async def test_node_image_endpoint_can_convert_png_to_ome_tiff_for_avivator(
    tmp_path: Path,
) -> None:
    image = tmp_path / "mask.png"
    Image.fromarray(np.arange(16, dtype=np.uint8).reshape(4, 4)).save(image)
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"mask": [image]})

    async with await _client(store) as client:
        resp = await client.get(
            "/api/v1/nodes/n1/image/mask.ome.tif",
            params={"row": 0, "col": "mask", "format": "ome-tiff"},
        )

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("image/tiff")
    assert resp.headers["content-disposition"].startswith("inline")
    assert "mask.ome.tif" in resp.headers["content-disposition"]
    assert resp.headers["accept-ranges"] == "bytes"
    with tifffile.TiffFile(BytesIO(resp.content)) as tif:
        assert tif.ome_metadata
        assert tif.asarray().tolist() == np.arange(16, dtype=np.uint8).reshape(4, 4).tolist()


async def test_node_image_endpoint_returns_offsets_json_for_avivator(
    tmp_path: Path,
) -> None:
    image = tmp_path / "mask.ome.tiff"
    tifffile.imwrite(
        image,
        np.arange(16, dtype=np.uint8).reshape(4, 4),
        ome=True,
        metadata={"axes": "YX"},
    )
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"mask": [image]})

    with tifffile.TiffFile(image) as tif:
        expected_offsets = [page.offset for page in tif.pages]

    async with await _client(store) as client:
        resp = await client.get(
            "/api/v1/nodes/n1/image/mask.offsets.json",
            params={"row": 0, "col": "mask", "format": "ome-tiff"},
        )

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == expected_offsets


async def test_node_image_endpoint_logs_unreadable_avivator_image(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    image = tmp_path / "broken.png"
    image.write_bytes(b"not an image")
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"mask": [image]})

    async with await _client(store) as client:
        with caplog.at_level(logging.WARNING, logger="bioimageflow_server.routers.nodes"):
            resp = await client.get(
                "/api/v1/nodes/n1/image/broken.ome.tif",
                params={"row": 0, "col": "mask", "format": "ome-tiff"},
            )

    assert resp.status_code == 422
    assert "Could not read image for Avivator" in caplog.text
    assert str(image) in caplog.text


async def test_node_image_endpoint_prunes_stale_avivator_cache_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir = tmp_path / "avivator-cache"
    cache_dir.mkdir()
    stale = cache_dir / "stale.ome.tif"
    fresh = cache_dir / "fresh.ome.tif"
    stale.write_bytes(b"old")
    fresh.write_bytes(b"new")
    os.utime(stale, (1, 1))

    monkeypatch.setattr(nodes_router, "_OME_TIFF_CACHE_DIR", cache_dir)
    monkeypatch.setattr(nodes_router, "_OME_TIFF_CACHE_MAX_AGE_SECONDS", 10)

    image = tmp_path / "mask.png"
    Image.fromarray(np.arange(16, dtype=np.uint8).reshape(4, 4)).save(image)
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"mask": [image]})

    async with await _client(store) as client:
        resp = await client.get(
            "/api/v1/nodes/n1/image/mask.ome.tif",
            params={"row": 0, "col": "mask", "format": "ome-tiff"},
        )

    assert resp.status_code == 200, resp.text
    assert not stale.exists()
    assert fresh.exists()


async def test_node_image_endpoint_allows_private_network_preflight() -> None:
    store = MagicMock()

    async with await _client(store) as client:
        resp = await client.options(
            "/api/v1/nodes/n1/image/mask.ome.tif",
            headers={
                "Origin": "https://avivator.gehlenborglab.org",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "range",
                "Access-Control-Request-Private-Network": "true",
            },
        )

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-private-network"] == "true"


async def test_node_image_endpoint_resolves_workflow_storage_path(tmp_path: Path) -> None:
    image = tmp_path / "mask.tif"
    image.write_bytes(b"tiff")
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"mask": [image]})
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path / "workflows" / "wf_a"

    async with await _client_with_workflow_store(store, workflow_store) as client:
        resp = await client.get(
            "/api/v1/nodes/n1/image",
            params={"row": 0, "col": "mask", "workflow_name": "wf_a"},
        )

    assert resp.status_code == 200
    workflow_store.get_storage_path.assert_called_once_with("wf_a")
    assert (
        store.get_latest_dataframe.call_args.kwargs["storage_path"]
        == tmp_path / "workflows" / "wf_a"
    )


async def test_node_image_endpoint_resolves_record_relative_asset_paths(tmp_path: Path) -> None:
    record_dir = tmp_path / "cache" / "v1" / "results" / "aa" / "bb" / "rk_test" / "records" / "rec_test"
    image = record_dir / "assets" / "mask.png"
    image.parent.mkdir(parents=True)
    Image.fromarray(np.arange(16, dtype=np.uint8).reshape(4, 4)).save(image)
    df = pd.DataFrame({"mask": ["assets/mask.png"]})
    df.attrs[DATAFRAME_RECORD_DIR_ATTR] = str(record_dir)
    store = MagicMock()
    store.get_latest_dataframe.return_value = df

    async with await _client(store) as client:
        resp = await client.get(
            "/api/v1/nodes/n1/image",
            params={"row": 0, "col": "mask"},
        )

    assert resp.status_code == 200, resp.text
    assert resp.content == image.read_bytes()


async def test_node_reveal_endpoint_resolves_record_relative_asset_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_dir = tmp_path / "cache" / "v1" / "results" / "aa" / "bb" / "rk_test" / "records" / "rec_test"
    image = record_dir / "assets" / "mask.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"png")
    df = pd.DataFrame({"mask": ["assets/mask.png"]})
    df.attrs[DATAFRAME_RECORD_DIR_ATTR] = str(record_dir)
    store = MagicMock()
    store.get_latest_dataframe.return_value = df
    reveal = MagicMock()
    monkeypatch.setattr(nodes_router, "reveal_in_file_browser", reveal)

    async with await _client(store) as client:
        resp = await client.post(
            "/api/v1/nodes/n1/reveal",
            params={"row": 0, "col": "mask"},
        )

    assert resp.status_code == 200, resp.text
    reveal.assert_called_once_with(str(image))


async def test_node_image_endpoint_validation(tmp_path: Path) -> None:
    missing = tmp_path / "missing.tif"
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"mask": [missing]})

    async with await _client(store) as client:
        missing_file = await client.get(
            "/api/v1/nodes/n1/image",
            params={"row": 0, "col": "mask"},
        )
        bad_col = await client.get(
            "/api/v1/nodes/n1/image",
            params={"row": 0, "col": "nope"},
        )
        bad_row = await client.get(
            "/api/v1/nodes/n1/image",
            params={"row": 2, "col": "mask"},
        )

    assert missing_file.status_code == 404
    assert bad_col.status_code == 422
    assert bad_row.status_code == 422


async def test_thumbnail_endpoint(tmp_path: Path) -> None:
    from unittest.mock import AsyncMock

    image_path = tmp_path / "m.tif"
    image_path.write_bytes(b"tiff")
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"mask": [image_path]})
    thumbs = MagicMock()
    real_png = b"\x89PNG\r\n\x1a\nrendered"
    placeholder = b"\x89PNG\r\n\x1a\nplaceholder"
    thumbs.placeholder_png.return_value = placeholder
    thumbs.get_or_queue = AsyncMock(return_value=real_png)
    async with await _client(store, thumbs) as client:
        resp = await client.get("/api/v1/nodes/n1/thumbnail", params={"row": 0, "col": "mask", "size": 64})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.headers["x-thumbnail-status"] == "ready"
    assert resp.content == real_png
    thumbs.get_or_queue.assert_awaited_once()
    args, kwargs = thumbs.get_or_queue.call_args
    assert args[0] == image_path
    assert args[1] == 64


async def test_thumbnail_endpoint_signals_pending_for_placeholder(tmp_path: Path) -> None:
    """When the manager returns the placeholder bytes, the endpoint must
    signal X-Thumbnail-Status: pending and Cache-Control: no-store so
    the frontend retries.
    """
    from unittest.mock import AsyncMock

    image_path = tmp_path / "m.tif"
    image_path.write_bytes(b"tiff")
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"mask": [image_path]})
    thumbs = MagicMock()
    placeholder = b"\x89PNG\r\n\x1a\nplaceholder"
    thumbs.placeholder_png.return_value = placeholder
    thumbs.get_or_queue = AsyncMock(return_value=placeholder)
    async with await _client(store, thumbs) as client:
        resp = await client.get("/api/v1/nodes/n1/thumbnail", params={"row": 0, "col": "mask"})
    assert resp.status_code == 200
    assert resp.headers["x-thumbnail-status"] == "pending"
    assert "no-store" in resp.headers["cache-control"]


async def test_thumbnail_endpoint_resolves_relative_paths_against_workflow_storage(tmp_path: Path) -> None:
    image_path = tmp_path / "outputs" / "mask.png"
    image_path.parent.mkdir()
    image_path.write_bytes(b"png")
    store = MagicMock()
    store.get_latest_dataframe.return_value = pd.DataFrame({"mask": ["outputs/mask.png"]})
    thumbs = _default_thumbnail_mock()
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path

    async with await _client_with_workflow_store(store, workflow_store, thumbs) as client:
        resp = await client.get(
            "/api/v1/nodes/sub_1%2Fsegment_1/thumbnail",
            params={"workflow_name": "wf_a", "row": 0, "col": "mask", "size": 64},
        )

    assert resp.status_code == 200
    workflow_store.get_storage_path.assert_called_once_with("wf_a")
    store.get_latest_dataframe.assert_called_once_with("sub_1/segment_1", storage_path=tmp_path)
    thumbs.get_or_queue.assert_awaited_once()
    args, kwargs = thumbs.get_or_queue.call_args
    assert args[0] == image_path
    assert args[1] == 64


async def test_thumbnail_endpoint_resolves_record_relative_asset_paths(tmp_path: Path) -> None:
    record_dir = tmp_path / "cache" / "v1" / "results" / "aa" / "bb" / "rk_test" / "records" / "rec_test"
    image_path = record_dir / "assets" / "mask.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"png")
    df = pd.DataFrame({"mask": ["assets/mask.png"]})
    df.attrs[DATAFRAME_RECORD_DIR_ATTR] = str(record_dir)
    store = MagicMock()
    store.get_latest_dataframe.return_value = df
    thumbs = _default_thumbnail_mock()

    async with await _client(store, thumbs) as client:
        resp = await client.get(
            "/api/v1/nodes/n1/thumbnail",
            params={"row": 0, "col": "mask", "size": 64},
        )

    assert resp.status_code == 200
    thumbs.get_or_queue.assert_awaited_once()
    args, kwargs = thumbs.get_or_queue.call_args
    assert args[0] == image_path
    assert args[1] == 64


@pytest.mark.parametrize("endpoint", ["image", "reveal", "thumbnail"])
async def test_node_image_actions_resolve_exact_record_asset_without_record_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    from unittest.mock import AsyncMock

    image_path = tmp_path / "assets" / "mask.png"
    image_path.parent.mkdir()
    image_path.write_bytes(b"image")
    identity = ResultArtifactIdentity(
        run_id="run_old", node_key="n1", result_key="rk_old", record_id="rec_old"
    )
    df = pd.DataFrame({"mask": ["assets/mask.png"]})
    df.attrs[DATAFRAME_RESULT_IDENTITY_ATTR] = identity
    store = MagicMock()
    store.get_latest_dataframe.return_value = df
    store.resolve_result_asset.return_value = image_path
    thumbs = _default_thumbnail_mock()
    thumbs.get_or_queue = AsyncMock(return_value=b"rendered")
    reveal = MagicMock()
    monkeypatch.setattr(nodes_router, "reveal_in_file_browser", reveal)

    async with await _client(store, thumbs) as client:
        if endpoint == "reveal":
            response = await client.post("/api/v1/nodes/n1/reveal", params={"col": "mask"})
        else:
            response = await client.get(f"/api/v1/nodes/n1/{endpoint}", params={"col": "mask"})

    assert response.status_code == 200, response.text
    store.resolve_result_asset.assert_called_once_with(
        identity, "assets/mask.png", storage_path=None
    )
    if endpoint == "image":
        assert response.content == b"image"
    elif endpoint == "reveal":
        reveal.assert_called_once_with(str(image_path))
    else:
        assert response.content == b"rendered"
        thumbs.get_or_queue.assert_awaited_once_with(
            image_path, 128, wait_timeout=nodes_router._THUMBNAIL_WAIT_TIMEOUT_SECONDS
        )


async def test_thumbnail_endpoint_keeps_exact_external_path(tmp_path: Path) -> None:
    image_path = tmp_path / "external.tif"
    image_path.write_bytes(b"tif")
    identity = ResultArtifactIdentity(
        run_id="run_old", node_key="n1", result_key="rk_old", record_id="rec_old"
    )
    df = pd.DataFrame({"mask": [str(image_path)]})
    df.attrs[DATAFRAME_RESULT_IDENTITY_ATTR] = identity
    store = MagicMock()
    store.get_latest_dataframe.return_value = df
    thumbs = _default_thumbnail_mock()

    async with await _client(store, thumbs) as client:
        response = await client.get("/api/v1/nodes/n1/thumbnail", params={"col": "mask"})

    assert response.status_code == 200
    store.resolve_result_asset.assert_not_called()
    assert thumbs.get_or_queue.call_args.args[0] == image_path


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
