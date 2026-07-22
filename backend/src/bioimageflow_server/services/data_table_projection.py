"""Build obvious, lossless DataFrame projections for the Node Data panel."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import pandas as pd
from bioimageflow_core.arguments import parse_index_lineage

from bioimageflow_server.models.data_table import (
    DataTableColumn,
    DataTableFilter,
    DataTableMergedResponse,
    DataTableMergedRow,
    DataTableSource,
    DataTableStackedResponse,
)
from bioimageflow_server.services.dataframe_query import (
    DataFrameQueryError,
    filter_positions,
    sort_positions,
)
from bioimageflow_server.services.result_store import (
    ResultDataNotReadyError,
    ResultStoreService,
)


class DataTableProjectionInputError(ValueError):
    """Raised when a projection request references invalid source data."""


@dataclass
class CsvProjection:
    dataframe: pd.DataFrame
    columns: list[DataTableColumn]


@dataclass
class _LoadedSource:
    spec: DataTableSource
    dataframe: pd.DataFrame
    index_values: list[str]
    positions: dict[str, int]
    column_types: dict[str, str]


_FALLBACK_MESSAGES = {
    "non_unique_index": "The selected data contain duplicate indices and cannot be aligned safely.",
    "anchor_rows_would_be_lost": "Merging would hide rows from an explicitly selected node.",
    "incompatible_lineage": "The selected data do not have an obvious index or parent/child alignment.",
    "incompatible_empty_results": "Empty and non-empty selected results cannot be aligned without hiding data.",
}


class DataTableProjectionService:
    def __init__(self, result_store: ResultStoreService):
        self.result_store = result_store

    def query(
        self,
        sources: list[DataTableSource],
        *,
        storage_path: Path | None,
        page: int,
        page_size: int,
        sort_by: str | None,
        sort_order: Literal["asc", "desc"],
        filters: list[DataTableFilter] | None = None,
    ) -> DataTableMergedResponse | DataTableStackedResponse:
        loaded = self._load_sources(sources, storage_path)
        built = self._build(loaded)
        if isinstance(built, DataTableStackedResponse):
            return built
        dataframe, columns, source_rows = built
        unfiltered_total_rows = len(dataframe)
        try:
            positions = filter_positions(dataframe, filters or [])
        except DataFrameQueryError as exc:
            raise DataTableProjectionInputError(str(exc)) from exc
        dataframe = dataframe.iloc[positions]
        source_rows = [source_rows[position] for position in positions]
        dataframe, source_rows = self._sort(dataframe, source_rows, sort_by, sort_order)
        total_rows = len(dataframe)
        start = page * page_size
        page_df = dataframe.iloc[start : start + page_size]
        page_source_rows = source_rows[start : start + page_size]
        rows = [
            DataTableMergedRow(
                index=str(index),
                values=cast(dict[str, object], row),
                source_rows=page_source_rows[offset],
            )
            for offset, (index, row) in enumerate(
                zip(page_df.index.tolist(), page_df.to_dict(orient="records"), strict=True)
            )
        ]
        return DataTableMergedResponse(
            sources=sources,
            columns=columns,
            rows=rows,
            total_rows=total_rows,
            unfiltered_total_rows=unfiltered_total_rows,
            page=page,
            page_size=page_size,
        )

    def csv(
        self,
        sources: list[DataTableSource],
        *,
        storage_path: Path | None,
        sort_by: str | None,
        sort_order: Literal["asc", "desc"],
        filters: list[DataTableFilter] | None = None,
    ) -> CsvProjection | DataTableStackedResponse:
        loaded = self._load_sources(sources, storage_path)
        built = self._build(loaded)
        if isinstance(built, DataTableStackedResponse):
            return built
        dataframe, columns, source_rows = built
        try:
            positions = filter_positions(dataframe, filters or [])
        except DataFrameQueryError as exc:
            raise DataTableProjectionInputError(str(exc)) from exc
        dataframe = dataframe.iloc[positions]
        source_rows = [source_rows[position] for position in positions]
        dataframe, _ = self._sort(dataframe, source_rows, sort_by, sort_order)
        dataframe = dataframe.copy()
        dataframe.columns = [column.label for column in columns]
        return CsvProjection(dataframe=dataframe, columns=columns)

    def _load_sources(
        self, sources: list[DataTableSource], storage_path: Path | None
    ) -> list[_LoadedSource]:
        records: list[tuple[DataTableSource, Path]] = []
        for source in sources:
            record_dir = self.result_store.get_latest_record_dir(
                source.node_id, storage_path=storage_path
            )
            if record_dir is None:
                raise DataTableProjectionInputError(
                    f"No output data for node '{source.node_id}'"
                )
            records.append((source, record_dir))

        loaded: list[_LoadedSource] = []
        for source, record_dir in records:
            try:
                dataframe = self.result_store.get_dataframe_from_record(
                    record_dir, node_id=source.node_id
                )
            except ResultDataNotReadyError:
                raise
            if dataframe is None:
                raise DataTableProjectionInputError(
                    f"No DataFrame output for node '{source.node_id}'"
                )
            dataframe = dataframe.copy()
            dataframe.columns = [str(column) for column in dataframe.columns]
            if source.columns is not None:
                missing = [column for column in source.columns if column not in dataframe.columns]
                if missing:
                    raise DataTableProjectionInputError(
                        f"Unknown columns for node '{source.node_id}': {', '.join(missing)}"
                    )
                dataframe = dataframe.loc[:, source.columns]
            index_values = [str(value) for value in dataframe.index.tolist()]
            types = self.result_store.get_column_types(
                dataframe, tool_name=source.tool_name
            )
            loaded.append(
                _LoadedSource(
                    spec=source,
                    dataframe=dataframe,
                    index_values=index_values,
                    positions={value: position for position, value in enumerate(index_values)},
                    column_types=types,
                )
            )
        return loaded

    def _fallback(
        self, sources: list[DataTableSource], reason: str
    ) -> DataTableStackedResponse:
        return DataTableStackedResponse(
            sources=sources,
            reason=reason,
            message=_FALLBACK_MESSAGES[reason],
        )

    @staticmethod
    def _is_descendant(index: str, ancestor: str) -> bool:
        index_parts = parse_index_lineage(index)
        ancestor_parts = parse_index_lineage(ancestor)
        return len(index_parts) >= len(ancestor_parts) and index_parts[: len(ancestor_parts)] == ancestor_parts

    @classmethod
    def _source_position(cls, source: _LoadedSource, candidate: str) -> int | None:
        parts = parse_index_lineage(candidate)
        for length in range(len(parts), 0, -1):
            ancestor = "::".join(parts[:length])
            position = source.positions.get(ancestor)
            if position is not None:
                return position
        return None

    def _build(
        self, loaded: list[_LoadedSource]
    ) -> tuple[pd.DataFrame, list[DataTableColumn], list[dict[str, int]]] | DataTableStackedResponse:
        sources = [source.spec for source in loaded]
        if any(len(source.positions) != len(source.index_values) for source in loaded):
            return self._fallback(sources, "non_unique_index")

        anchors = [source for source in loaded if source.spec.role == "anchor"]
        empty_anchors = [source for source in anchors if source.dataframe.empty]
        if empty_anchors:
            if len(empty_anchors) != len(anchors) or any(
                not source.dataframe.empty for source in loaded if source.spec.role == "context"
            ):
                return self._fallback(sources, "incompatible_empty_results")
            candidate_indices: list[str] = []
        else:
            candidate = max(
                anchors,
                key=lambda source: (
                    max((len(parse_index_lineage(index)) for index in source.index_values), default=0),
                    len(source.index_values),
                    -loaded.index(source),
                ),
            )
            candidate_indices = candidate.index_values
            for anchor in anchors:
                if any(
                    not any(self._is_descendant(candidate_index, anchor_index) for candidate_index in candidate_indices)
                    for anchor_index in anchor.index_values
                ):
                    return self._fallback(sources, "anchor_rows_would_be_lost")
                if any(
                    self._source_position(anchor, candidate_index) is None
                    for candidate_index in candidate_indices
                ):
                    return self._fallback(sources, "anchor_rows_would_be_lost")

        resolved_positions: list[dict[str, int]] = []
        for candidate_index in candidate_indices:
            positions: dict[str, int] = {}
            for source in loaded:
                position = self._source_position(source, candidate_index)
                if position is None:
                    return self._fallback(sources, "incompatible_lineage")
                positions[source.spec.node_id] = position
            resolved_positions.append(positions)

        raw_labels: list[str] = []
        for source in loaded:
            raw_labels.extend(
                source.spec.column_aliases.get(str(column), str(column))
                for column in source.dataframe.columns
            )
        collisions = {label for label in raw_labels if raw_labels.count(label) > 1}
        columns: list[DataTableColumn] = []
        for source_number, source in enumerate(loaded):
            for column in source.dataframe.columns:
                original = str(column)
                base_label = source.spec.column_aliases.get(original, original)
                label = f"{source.spec.label}: {base_label}" if base_label in collisions else base_label
                columns.append(
                    DataTableColumn(
                        id=f"s{source_number}:{original}",
                        label=label,
                        type=source.column_types.get(original, "str"),
                        source_node_id=source.spec.node_id,
                        source_column=original,
                    )
                )

        records: list[dict[str, object]] = []
        for positions in resolved_positions:
            record: dict[str, object] = {}
            for source_number, source in enumerate(loaded):
                row = source.dataframe.iloc[positions[source.spec.node_id]]
                for column in source.dataframe.columns:
                    record[f"s{source_number}:{column}"] = row[column]
            records.append(record)
        dataframe = pd.DataFrame(records, columns=[column.id for column in columns])
        dataframe.index = pd.Index(candidate_indices)
        return dataframe, columns, resolved_positions

    @staticmethod
    def _sort(
        dataframe: pd.DataFrame,
        source_rows: list[dict[str, int]],
        sort_by: str | None,
        sort_order: Literal["asc", "desc"],
    ) -> tuple[pd.DataFrame, list[dict[str, int]]]:
        if sort_by is None:
            return dataframe, source_rows
        if sort_by not in dataframe.columns:
            raise DataTableProjectionInputError(f"Unknown sort column: '{sort_by}'")
        try:
            positions = sort_positions(dataframe, sort_by, sort_order)
        except DataFrameQueryError as exc:
            raise DataTableProjectionInputError(str(exc)) from exc
        return dataframe.iloc[positions], [source_rows[position] for position in positions]
