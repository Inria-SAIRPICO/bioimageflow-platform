"""Tests for ResultStoreService."""

from __future__ import annotations

import os
import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from bioimageflow_server.models.tools import ToolMetadata
from bioimageflow_server.services.result_store import (
    DATAFRAME_RECORD_DIR_ATTR,
    ResultDataNotReadyError,
    ResultStoreService,
)


def _store(tmp_path: Path, registry: MagicMock | None = None) -> ResultStoreService:
    return ResultStoreService(
        storage_path=tmp_path,
        tool_registry=registry or MagicMock(get_tool=MagicMock(return_value=None)),
    )


def _record_dir(
    tmp_path: Path,
    node_id: str,
    run_id: str = "run_1",
    *,
    legacy: bool = False,
) -> Path:
    path = tmp_path / "cache" / "v1" / "results" / "aa" / "bb" / "rk_test" / "records" / "rec_test"
    path.mkdir(parents=True)
    node_dir = tmp_path / ("runs" if legacy else "views/runs") / run_id / "nodes" / node_id
    node_dir.mkdir(parents=True)
    (node_dir / "result.json").write_text(
        json.dumps(
            {
                "schema": "bioimageflow.run.node_result.v1",
                "run_id": run_id,
                "node_key": node_id,
                "result_key": "rk_test",
                "record_id": "rec_test",
                "cache_hit": False,
                "canonical": os.path.relpath(path, start=node_dir).replace(os.sep, "/"),
                "outputs": [],
            }
        )
    )
    (node_dir / "record.bioimageflow-link.json").write_text(
        json.dumps(
            {
                "schema": "bioimageflow.link.v1",
                "kind": "directory",
                "target": os.path.relpath(path, start=node_dir).replace(os.sep, "/"),
            }
        )
    )
    latest_parent = tmp_path / ("latest" if legacy else "views/latest")
    parts = node_id.split("/")
    for part in parts[:-1]:
        latest_parent /= part
    latest_parent.mkdir(parents=True)
    latest_link = latest_parent / f"{parts[-1]}.bioimageflow-link.json"
    latest_link.write_text(
        json.dumps(
            {
                "schema": "bioimageflow.link.v1",
                "kind": "directory",
                "target": os.path.relpath(node_dir, start=latest_parent).replace(os.sep, "/"),
            }
        )
    )
    return path


def test_get_latest_dataframe_returns_none_for_missing_node(tmp_path: Path) -> None:
    assert _store(tmp_path).get_latest_dataframe("n1") is None


def test_get_latest_dataframe_returns_none_for_missing_latest_link(tmp_path: Path) -> None:
    (tmp_path / "views" / "runs" / "run_1" / "nodes" / "n1").mkdir(parents=True)
    assert _store(tmp_path).get_latest_dataframe("n1") is None


def test_get_latest_dataframe_loads_latest_link_record(tmp_path: Path, monkeypatch) -> None:
    record_dir = _record_dir(tmp_path, "n1")
    (record_dir / "dataframe.csv").write_text("x\n2\n")

    loaded_paths: list[Path] = []

    def fake_load(path: Path) -> pd.DataFrame:
        loaded_paths.append(path)
        return pd.DataFrame({"x": [2]})

    monkeypatch.setattr("bioimageflow_server.services.result_store.cache_load", fake_load)
    df = _store(tmp_path).get_latest_dataframe("n1")

    assert df is not None
    assert loaded_paths == [record_dir / "dataframe.csv"]
    assert df.attrs[DATAFRAME_RECORD_DIR_ATTR] == str(record_dir)


def test_get_latest_dataframe_falls_back_to_legacy_latest_link(
    tmp_path: Path,
    monkeypatch,
) -> None:
    record_dir = _record_dir(tmp_path, "n1", legacy=True)
    (record_dir / "dataframe.csv").write_text("x\n2\n")

    monkeypatch.setattr(
        "bioimageflow_server.services.result_store.cache_load",
        lambda path: pd.DataFrame({"x": [2]}),
    )

    df = _store(tmp_path).get_latest_dataframe("n1")

    assert df is not None
    assert df["x"].tolist() == [2]


def test_get_latest_dataframe_loads_library_generated_v1_view(tmp_path: Path) -> None:
    from bioimageflow.cache import dataframe_publish, dataframe_result_key
    from bioimageflow.storage import Storage

    node_id = "n1"
    sig_hash = "sig"
    dataframe_publish(tmp_path, node_id, sig_hash, pd.DataFrame({"x": [2]}))
    storage = Storage(tmp_path)
    result_key = dataframe_result_key(node_id, sig_hash)
    pointer = storage.load_current(result_key)
    assert pointer is not None
    storage.write_run_metadata(
        "run_1",
        workflow_identity="test",
        engine="direct",
        status="succeeded",
        target_nodes=[node_id],
    )
    storage.write_run_node_result(
        "run_1",
        node_id,
        result_key=result_key,
        record_id=pointer.record_id,
        cache_hit=False,
    )
    storage.update_latest_node(node_id, "run_1")

    df = _store(tmp_path).get_latest_dataframe(node_id)

    assert df is not None
    assert df["x"].tolist() == [2]


def test_get_latest_dataframe_prefers_parquet_over_csv(tmp_path: Path, monkeypatch) -> None:
    record_dir = _record_dir(tmp_path, "n1")
    (record_dir / "dataframe.csv").write_text("x\n1\n")
    (record_dir / "dataframe.parquet").write_bytes(b"parquet")

    loaded_paths: list[Path] = []

    def fake_load(path: Path) -> pd.DataFrame:
        loaded_paths.append(path)
        return pd.DataFrame({"x": [1]})

    monkeypatch.setattr("bioimageflow_server.services.result_store.cache_load", fake_load)
    _store(tmp_path).get_latest_dataframe("n1")
    assert loaded_paths == [record_dir / "dataframe.parquet"]


def test_malformed_node_id_does_not_probe_outside_latest(tmp_path: Path) -> None:
    assert _store(tmp_path).get_latest_dataframe("../escape") is None
    assert _store(tmp_path).has_data("../escape") is False


def test_get_latest_dataframe_raises_not_ready_for_zero_byte_parquet(
    tmp_path: Path,
) -> None:
    record_dir = _record_dir(tmp_path, "n1")
    (record_dir / "dataframe.parquet").write_bytes(b"")

    with pytest.raises(ResultDataNotReadyError):
        _store(tmp_path).get_latest_dataframe("n1")


def test_zero_byte_latest_hash_does_not_fall_back_to_stale_data(
    tmp_path: Path,
    monkeypatch,
) -> None:
    record_dir = _record_dir(tmp_path, "n1")
    (record_dir / "dataframe.parquet").write_bytes(b"")

    monkeypatch.setattr(
        "bioimageflow_server.services.result_store.cache_load",
        lambda path: pd.DataFrame({"x": [1]}),
    )

    with pytest.raises(ResultDataNotReadyError):
        _store(tmp_path).get_latest_dataframe("n1")


def test_get_column_types_infers_pandas_dtypes(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "i": pd.Series([1, pd.NA], dtype="Int64"),
            "f": [1.2, 3.4],
            "s": ["a", "b"],
            "b": pd.Series([True, False], dtype="boolean"),
        }
    )
    assert _store(tmp_path).get_column_types(df) == {
        "i": "int",
        "f": "float",
        "s": "str",
        "b": "bool",
    }


def test_get_column_types_uses_registered_tool_outputs(tmp_path: Path) -> None:
    registry = MagicMock()
    registry.get_tool.return_value = ToolMetadata(
        name="T",
        display_name="T",
        package="pkg",
        package_version="1",
        tool_type="ProcessingTool",
        outputs={"mask": {"type": "ImageFile", "default": None, "image_spec": {}}},
    )
    df = pd.DataFrame({"mask": ["/tmp/m.tif"], "score": [1.5]})
    assert _store(tmp_path, registry).get_column_types(df, "T") == {
        "mask": "ImageFile",
        "score": "float",
    }


def test_get_column_types_passthrough_falls_back(tmp_path: Path) -> None:
    registry = MagicMock()
    registry.get_tool.return_value = ToolMetadata(
        name="T",
        display_name="T",
        package="pkg",
        package_version="1",
        tool_type="DataFrameTool",
        outputs={"_passthrough": True},
    )
    df = pd.DataFrame({"path": ["/tmp/a.tif"]})
    assert _store(tmp_path, registry).get_column_types(df, "T") == {"path": "str"}


def test_get_csv_path_and_has_data(tmp_path: Path) -> None:
    record_dir = _record_dir(tmp_path, "n1")
    csv_path = record_dir / "dataframe.csv"
    csv_path.write_text("x\n1\n")
    store = _store(tmp_path)
    assert store.get_csv_path("n1") == csv_path
    assert store.has_data("n1") is True
    assert store.get_csv_path("missing") is None
    assert store.has_data("missing") is False


def test_methods_accept_storage_path_override(tmp_path: Path, monkeypatch) -> None:
    fallback = tmp_path / "fallback"
    override = tmp_path / "override"
    record_dir = _record_dir(override, "n1")
    (record_dir / "dataframe.csv").write_text("x\n1\n")

    monkeypatch.setattr(
        "bioimageflow_server.services.result_store.cache_load",
        lambda path: pd.DataFrame({"x": [1]}),
    )
    store = _store(fallback)

    assert store.get_latest_dataframe("n1", storage_path=override) is not None
    assert store.get_csv_path("n1", storage_path=override) == record_dir / "dataframe.csv"
    assert store.has_data("n1", storage_path=override) is True
