"""Locate and load persisted node DataFrame outputs."""

from __future__ import annotations

from pathlib import Path
import pandas as pd
from bioimageflow.cache import cache_load

from bioimageflow_server.services.tool_registry import ToolRegistryService


class ResultStoreService:
    """Filesystem-backed reader for cached node DataFrames."""

    def __init__(self, storage_path: Path, tool_registry: ToolRegistryService):
        self.storage_path = Path(storage_path)
        self.tool_registry = tool_registry

    def get_latest_dataframe(self, node_id: str) -> pd.DataFrame | None:
        latest_dir = self._latest_hash_dir(node_id)
        if latest_dir is None:
            return None
        data_path = self._dataframe_path(latest_dir)
        if data_path is None:
            return None
        return cache_load(data_path)

    def get_csv_path(self, node_id: str) -> Path | None:
        latest_dir = self._latest_hash_dir(node_id)
        if latest_dir is None:
            return None
        csv_path = latest_dir / "dataframe.csv"
        if csv_path.is_file():
            return csv_path
        return None

    def has_data(self, node_id: str) -> bool:
        latest_dir = self._latest_hash_dir(node_id)
        return latest_dir is not None and self._dataframe_path(latest_dir) is not None

    def get_column_types(
        self, df: pd.DataFrame, tool_name: str | None = None
    ) -> dict[str, str]:
        declared = self._declared_output_types(tool_name)
        return {
            str(column): declared.get(str(column), self._infer_series_type(df[column]))
            for column in df.columns
        }

    def _node_dir(self, node_id: str) -> Path:
        return self.storage_path / "data" / node_id

    def _latest_hash_dir(self, node_id: str) -> Path | None:
        node_dir = self._node_dir(node_id)
        if not node_dir.is_dir():
            return None

        candidates = [
            path
            for path in node_dir.iterdir()
            if path.is_dir() and self._dataframe_path(path) is not None
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.stat().st_mtime)

    @staticmethod
    def _dataframe_path(hash_dir: Path) -> Path | None:
        parquet = hash_dir / "dataframe.parquet"
        if parquet.is_file():
            return parquet
        csv = hash_dir / "dataframe.csv"
        if csv.is_file():
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
