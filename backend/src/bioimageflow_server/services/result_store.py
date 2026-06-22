"""Locate and load persisted node DataFrame outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pandas as pd
from bioimageflow.cache import cache_load
from bioimageflow.storage import validate_relative_posix_path

from bioimageflow_server.services.tool_registry import ToolRegistryService


class ResultDataNotReadyError(Exception):
    """Raised when a node cache file exists but is not yet readable."""


class ResultStoreService:
    """Filesystem-backed reader for cached node DataFrames."""

    def __init__(self, storage_path: Path, tool_registry: ToolRegistryService):
        self.storage_path = Path(storage_path)
        self.tool_registry = tool_registry

    def get_latest_dataframe(
        self, node_id: str, storage_path: Path | None = None
    ) -> pd.DataFrame | None:
        record_dir = self._latest_record_dir(node_id, storage_path=storage_path)
        if record_dir is None:
            return None
        data_path = self._dataframe_path(record_dir)
        if data_path is None:
            return None
        try:
            return cache_load(data_path)
        except (OSError, pd.errors.EmptyDataError) as exc:
            raise ResultDataNotReadyError(
                f"Output data for node '{node_id}' is not ready"
            ) from exc

    def get_csv_path(
        self, node_id: str, storage_path: Path | None = None
    ) -> Path | None:
        record_dir = self._latest_record_dir(node_id, storage_path=storage_path)
        if record_dir is None:
            return None
        csv_path = record_dir / "dataframe.csv"
        if csv_path.is_file():
            return csv_path
        return None

    def has_data(self, node_id: str, storage_path: Path | None = None) -> bool:
        record_dir = self._latest_record_dir(node_id, storage_path=storage_path)
        if record_dir is None:
            return False
        try:
            return self._dataframe_path(record_dir) is not None
        except ResultDataNotReadyError:
            return False

    def get_column_types(
        self, df: pd.DataFrame, tool_name: str | None = None
    ) -> dict[str, str]:
        declared = self._declared_output_types(tool_name)
        return {
            str(column): declared.get(str(column), self._infer_series_type(cast(pd.Series, df[column])))
            for column in df.columns
        }

    def _root(self, storage_path: Path | None = None) -> Path:
        root = Path(storage_path) if storage_path is not None else self.storage_path
        return root

    def _latest_record_dir(
        self, node_id: str, storage_path: Path | None = None
    ) -> Path | None:
        root = self._root(storage_path)
        latest_link = self._latest_node_link(root, node_id)
        if latest_link is None:
            return None
        if not latest_link.is_file():
            return None

        node_view = self._resolve_link(latest_link, root)
        if node_view is None:
            return None
        record_link = node_view / "record.bioimageflow-link.json"
        if record_link.is_file():
            return self._resolve_link(record_link, root)

        result_path = node_view / "result.json"
        if not result_path.is_file():
            return None
        try:
            payload = json.loads(result_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ResultDataNotReadyError(
                f"Output metadata for node '{node_id}' is not ready"
            ) from exc
        canonical = payload.get("canonical")
        if not isinstance(canonical, str):
            return None
        return self._resolve_relative(result_path.parent, canonical, root)

    @staticmethod
    def _latest_node_link(root: Path, node_id: str) -> Path | None:
        try:
            safe_node_id = validate_relative_posix_path(str(node_id))
        except ValueError:
            return None
        parts = safe_node_id.split("/")
        parent = root / "latest"
        for part in parts[:-1]:
            parent /= part
        return parent / f"{parts[-1]}.bioimageflow-link.json"

    def _resolve_link(self, link_path: Path, root: Path) -> Path | None:
        try:
            payload = json.loads(link_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ResultDataNotReadyError(
                f"Output link '{link_path}' is not ready"
            ) from exc
        if payload.get("kind") != "directory":
            return None
        target = payload.get("target")
        if not isinstance(target, str):
            return None
        return self._resolve_relative(link_path.parent, target, root)

    @staticmethod
    def _resolve_relative(base: Path, target: str, root: Path) -> Path | None:
        target_path = (base / target).resolve()
        try:
            target_path.relative_to(root.resolve())
        except ValueError:
            return None
        return target_path

    @staticmethod
    def _dataframe_path(hash_dir: Path) -> Path | None:
        parquet = hash_dir / "dataframe.parquet"
        if parquet.is_file():
            if parquet.stat().st_size == 0:
                raise ResultDataNotReadyError(
                    f"Output cache file '{parquet}' is not ready"
                )
            return parquet
        csv = hash_dir / "dataframe.csv"
        if csv.is_file():
            if csv.stat().st_size == 0:
                raise ResultDataNotReadyError(
                    f"Output cache file '{csv}' is not ready"
                )
            return csv
        return None

    def _declared_output_types(self, tool_name: str | None) -> dict[str, str]:
        if not tool_name:
            return {}
        metadata = self.tool_registry.get_tool(tool_name)
        if metadata is None:
            return {}

        outputs = metadata.outputs or {}
        if outputs.get("_passthrough") is True:
            return {}

        declared: dict[str, str] = {}
        for name, spec in outputs.items():
            if name == "_passthrough":
                continue
            if isinstance(spec, dict) and isinstance(spec.get("type"), str):
                declared[name] = spec["type"]
            else:
                type_value = getattr(spec, "type", None)
                if isinstance(type_value, str):
                    declared[name] = type_value
        return declared

    @staticmethod
    def _infer_series_type(series: pd.Series) -> str:
        from pandas.api import types as pd_types

        if pd_types.is_bool_dtype(series):
            return "bool"
        if pd_types.is_integer_dtype(series):
            return "int"
        if pd_types.is_float_dtype(series):
            return "float"
        if pd_types.is_string_dtype(series) or series.dtype == object:
            return "str"
        return "str"
