"""Tests for ResultStoreService."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from bioimageflow_server.models.tools import ToolMetadata
from bioimageflow_server.services.result_store import (
    ResultDataNotReadyError,
    ResultStoreService,
)


def _store(tmp_path: Path, registry: MagicMock | None = None) -> ResultStoreService:
    return ResultStoreService(
        storage_path=tmp_path,
        tool_registry=registry or MagicMock(get_tool=MagicMock(return_value=None)),
    )


def _hash_dir(tmp_path: Path, node_id: str, name: str) -> Path:
    path = tmp_path / "data" / node_id / name
    path.mkdir(parents=True)
    return path


def test_get_latest_dataframe_returns_none_for_missing_node(tmp_path: Path) -> None:
    assert _store(tmp_path).get_latest_dataframe("n1") is None


def test_get_latest_dataframe_returns_none_for_empty_node_dir(tmp_path: Path) -> None:
    (tmp_path / "data" / "n1").mkdir(parents=True)
    assert _store(tmp_path).get_latest_dataframe("n1") is None


def test_get_latest_dataframe_loads_latest_by_mtime(tmp_path: Path, monkeypatch) -> None:
    old_dir = _hash_dir(tmp_path, "n1", "20260101_000000_oldhash")
    new_dir = _hash_dir(tmp_path, "n1", "20260101_000000_newhash")
    (old_dir / "dataframe.csv").write_text("x\n1\n")
    (new_dir / "dataframe.csv").write_text("x\n2\n")
    os.utime(old_dir, (100, 100))
    os.utime(new_dir, (200, 200))

    loaded_paths: list[Path] = []

    def fake_load(path: Path) -> pd.DataFrame:
        loaded_paths.append(path)
        return pd.DataFrame({"x": [2]})

    monkeypatch.setattr("bioimageflow_server.services.result_store.cache_load", fake_load)
    df = _store(tmp_path).get_latest_dataframe("n1")

    assert df is not None
    assert loaded_paths == [new_dir / "dataframe.csv"]


def test_get_latest_dataframe_prefers_parquet_over_csv(tmp_path: Path, monkeypatch) -> None:
    hash_dir = _hash_dir(tmp_path, "n1", "20260101_000000_hash")
    (hash_dir / "dataframe.csv").write_text("x\n1\n")
    (hash_dir / "dataframe.parquet").write_bytes(b"parquet")

    loaded_paths: list[Path] = []

    def fake_load(path: Path) -> pd.DataFrame:
        loaded_paths.append(path)
        return pd.DataFrame({"x": [1]})

    monkeypatch.setattr("bioimageflow_server.services.result_store.cache_load", fake_load)
    _store(tmp_path).get_latest_dataframe("n1")
    assert loaded_paths == [hash_dir / "dataframe.parquet"]


def test_get_latest_dataframe_raises_not_ready_for_zero_byte_parquet(
    tmp_path: Path,
) -> None:
    hash_dir = _hash_dir(tmp_path, "n1", "20260101_000000_hash")
    (hash_dir / "dataframe.parquet").write_bytes(b"")

    with pytest.raises(ResultDataNotReadyError):
        _store(tmp_path).get_latest_dataframe("n1")


def test_zero_byte_latest_hash_does_not_fall_back_to_stale_data(
    tmp_path: Path,
    monkeypatch,
) -> None:
    old_dir = _hash_dir(tmp_path, "n1", "20260101_000000_oldhash")
    new_dir = _hash_dir(tmp_path, "n1", "20260101_000000_newhash")
    (old_dir / "dataframe.csv").write_text("x\n1\n")
    (new_dir / "dataframe.parquet").write_bytes(b"")
    os.utime(old_dir, (100, 100))
    os.utime(new_dir, (200, 200))

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
        outputs={"mask": {"type": "ImagePath", "default": None, "image_spec": {}}},
    )
    df = pd.DataFrame({"mask": ["/tmp/m.tif"], "score": [1.5]})
    assert _store(tmp_path, registry).get_column_types(df, "T") == {
        "mask": "ImagePath",
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
    hash_dir = _hash_dir(tmp_path, "n1", "20260101_000000_hash")
    csv_path = hash_dir / "dataframe.csv"
    csv_path.write_text("x\n1\n")
    store = _store(tmp_path)
    assert store.get_csv_path("n1") == csv_path
    assert store.has_data("n1") is True
    assert store.get_csv_path("missing") is None
    assert store.has_data("missing") is False
