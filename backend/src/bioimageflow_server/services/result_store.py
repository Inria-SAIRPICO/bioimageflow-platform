"""Locate and load persisted node DataFrame outputs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, cast

import pandas as pd
import pyarrow as pa
from bioimageflow.cache import cache_load
from bioimageflow.storage import (
    CacheCorruptionError,
    RunNodeResult,
    Storage,
    validate_relative_posix_path,
)
from bioimageflow.validation import serialize_output_schema
from bioimageflow_core import DECLARATION_CONTRACT_VERSION, IOModel, ImageSpec, ViewerSpec
from bioimageflow_core.type_descriptors import decode_annotation

from bioimageflow_server.models.results import ResultArtifactIdentity
from bioimageflow_server.services.tool_registry import ToolRegistryService

DATAFRAME_RECORD_DIR_ATTR = "bioimageflow_record_dir"
DATAFRAME_RESULT_IDENTITY_ATTR = "bioimageflow_result_identity"
DATAFRAME_RESULT_METADATA_ATTR = "bioimageflow_result_metadata"


class ResultDataNotReadyError(Exception):
    """Raised when a node cache file exists but is not yet readable."""

    retryable = True
    code = "result_pending"


class ResultDataUnavailableError(ResultDataNotReadyError):
    """A rejected result cannot become readable by waiting for publication."""

    retryable = False
    code = "result_unavailable"


@dataclass(frozen=True)
class ResultColumnMetadata:
    """Request-local presentation facts from one admitted producer snapshot."""

    identity: ResultArtifactIdentity
    types: dict[str, str]
    viewers: dict[str, ViewerSpec]


def dataframe_result_metadata(dataframe: pd.DataFrame) -> ResultColumnMetadata | None:
    metadata = dataframe.attrs.get(DATAFRAME_RESULT_METADATA_ATTR)
    if metadata is None:
        return None
    if not isinstance(metadata, ResultColumnMetadata) or metadata.identity != dataframe.attrs.get(
        DATAFRAME_RESULT_IDENTITY_ATTR,
    ):
        raise ResultDataUnavailableError("Captured result metadata identity does not match")
    return metadata


def dataframe_column_viewers(dataframe: pd.DataFrame) -> dict[str, ViewerSpec]:
    """Project carried viewer facts without storage or current-catalog access."""

    metadata = dataframe_result_metadata(dataframe)
    return dict(metadata.viewers) if metadata is not None else {}


def _retained_output_types(retained: RunNodeResult) -> dict[str, str]:
    """Use public finite annotation decoding and canonical GUI serialization."""

    try:
        provenance = retained.provenance
        if provenance is None or "tool" not in provenance:
            return {}
        tool = provenance["tool"]
        if not isinstance(tool, Mapping):
            raise ValueError("Producer tool metadata is not a mapping")
        if "executable" not in tool:
            return {}
        executable = tool["executable"]
        if not isinstance(executable, Mapping):
            raise ValueError("Producer executable metadata is not a mapping")
        if "declaration" not in executable:
            return {}
        if executable.get("declaration_contract") != DECLARATION_CONTRACT_VERSION:
            raise ValueError("Producer declaration contract is unavailable")
        declaration = executable["declaration"]
        if not isinstance(declaration, Mapping):
            raise ValueError("Producer declaration is not a mapping")
        outputs = declaration["outputs"]
        if outputs is None:
            return {}
        if not isinstance(outputs, Mapping):
            raise ValueError("Producer output declaration is not a mapping")
        names, fields = outputs.get("field_names"), outputs.get("fields")
        if (
            type(outputs.get("passthrough")) is not bool
            or not isinstance(names, list)
            or any(not isinstance(name, str) or not name for name in names)
            or len(set(names)) != len(names)
            or not isinstance(fields, Mapping)
            or set(fields) != set(names)
        ):
            raise ValueError("Producer output fields are unavailable")
        annotations = {}
        for name in names:
            field = fields[name]
            if not isinstance(field, Mapping):
                raise ValueError("Producer output field is not a mapping")
            annotation = decode_annotation(field.get("type_spec"))
            image = field["image_spec"]
            if image is not None:
                if not isinstance(image, Mapping) or set(image) != {
                    "semantics", "layouts", "dtypes", "formats",
                } or any(
                    not isinstance(values, list) or any(not isinstance(value, str) for value in values)
                    for values in image.values()
                ):
                    raise ValueError("Producer image metadata is unavailable")
                annotation = Annotated[annotation, ImageSpec(**image)]
            annotations[name] = annotation
        # The holder contains annotations only: no defaults, callbacks, source
        # imports or IOModel instances are admitted to table presentation.
        outputs_model = type("RetainedOutputs", (IOModel,), {"__annotations__": annotations})
        holder = type("RetainedOutputSchema", (), {"Outputs": outputs_model})
        schema = serialize_output_schema(holder)
        return {name: schema[name]["type"] for name in names}
    except (KeyError, TypeError, ValueError) as exc:
        raise ResultDataUnavailableError("Captured output declaration is unavailable") from exc


class ResultStoreService:
    """Filesystem-backed reader for cached node DataFrames."""

    def __init__(self, storage_path: Path, tool_registry: ToolRegistryService):
        self.storage_path = Path(storage_path)
        self.tool_registry = tool_registry

    def get_latest_dataframe(
        self, node_id: str, storage_path: Path | None = None
    ) -> pd.DataFrame | None:
        retained = self._capture_latest_result(
            node_id, storage_path=storage_path
        )
        if retained is not None:
            # The capture already verified the exact run-node relation. Reuse
            # it in this read rather than admitting that same relation again.
            return self._load_retained_dataframe(retained, storage_path=storage_path)
        record_dir = self.get_latest_record_dir(node_id, storage_path=storage_path)
        if record_dir is None:
            return None
        dataframe = self.get_dataframe_from_record(record_dir, node_id=node_id)
        return dataframe

    def capture_latest_result_identity(
        self, node_id: str, storage_path: Path | None = None
    ) -> ResultArtifactIdentity | None:
        """Capture latest once, then validate its exact retained identity."""

        retained = self._capture_latest_result(node_id, storage_path=storage_path)
        return self._result_identity(retained) if retained is not None else None

    def _capture_latest_result(
        self, node_id: str, *, storage_path: Path | None = None
    ) -> RunNodeResult | None:
        """Admit one latest relation for reuse within the current operation."""

        root = self._root(storage_path)
        latest_link = self._latest_node_link(root, node_id)
        if latest_link is None or not latest_link.is_file():
            return None
        node_view = self._resolve_link(latest_link, root)
        storage = Storage(root)
        result_path = node_view / "result.json"
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            # Pre-provenance views remain readable through the legacy immutable
            # record-link path, but cannot be used for exact viewer opening.
            return None
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ResultDataUnavailableError(
                f"Output metadata for node '{node_id}' is not ready"
            ) from exc
        run_id = payload.get("run_id") if isinstance(payload, dict) else None
        node_key = payload.get("node_key") if isinstance(payload, dict) else None
        if not isinstance(run_id, str) or node_key != node_id:
            raise ResultDataUnavailableError(f"Output metadata for node '{node_id}' is not ready")
        try:
            safe_run_id = validate_relative_posix_path(run_id)
            validate_relative_posix_path(node_key)
        except ValueError as exc:
            raise ResultDataUnavailableError(
                f"Output metadata for node '{node_id}' is not ready"
            ) from exc
        if "/" in safe_run_id:
            raise ResultDataUnavailableError(f"Output metadata for node '{node_id}' is not ready")
        try:
            expected_view = storage.run_node_dir(safe_run_id, node_key).resolve()
        except (ValueError, OSError, RuntimeError) as exc:
            raise ResultDataUnavailableError(
                f"Output metadata for node '{node_id}' is not ready"
            ) from exc
        if node_view != expected_view:
            raise ResultDataUnavailableError(f"Output metadata for node '{node_id}' is not ready")
        try:
            retained = storage.read_run_node_result(safe_run_id, node_key)
        except CacheCorruptionError as exc:
            raise ResultDataUnavailableError(
                f"Saved output for node '{node_id}' cannot be read: {exc} "
                "It may use an unsupported cache format or have failed validation. "
                "Re-run this node and its required upstream nodes to regenerate the output. "
                "Existing result files have been kept."
            ) from exc
        except (FileNotFoundError, OSError) as exc:
            raise ResultDataNotReadyError(
                f"Output data for node '{node_id}' is not ready"
            ) from exc
        return retained

    @staticmethod
    def _result_identity(retained: RunNodeResult) -> ResultArtifactIdentity:
        return ResultArtifactIdentity(
            run_id=retained.run_id,
            node_key=retained.node_key,
            result_key=retained.result_key,
            record_id=retained.record_id,
        )

    def read_run_node_result(
        self,
        identity: ResultArtifactIdentity,
        *,
        storage_path: Path | None = None,
    ):
        """Read and verify one exact retained result through public library APIs."""

        try:
            safe_run_id = validate_relative_posix_path(identity.run_id)
            validate_relative_posix_path(identity.node_key)
        except ValueError as exc:
            raise ResultDataUnavailableError("Captured result identity is invalid") from exc
        if "/" in safe_run_id:
            raise ResultDataUnavailableError("Captured result identity is invalid")
        try:
            retained = Storage(self._root(storage_path)).read_run_node_result(
                identity.run_id, identity.node_key
            )
        except CacheCorruptionError as exc:
            raise ResultDataUnavailableError(
                f"Saved result cannot be read: {exc} Re-run the affected node to regenerate its output."
            ) from exc
        except (FileNotFoundError, OSError) as exc:
            raise ResultDataNotReadyError("Captured result is not ready") from exc
        if (
            retained.result_key != identity.result_key
            or retained.record_id != identity.record_id
        ):
            raise ResultDataUnavailableError("Captured result identity no longer matches")
        return retained

    def load_result_dataframe(
        self,
        identity: ResultArtifactIdentity,
        *,
        storage_path: Path | None = None,
    ) -> pd.DataFrame:
        """Load one exact record without consulting current/latest pointers."""

        retained = self.read_run_node_result(identity, storage_path=storage_path)
        return self._load_retained_dataframe(retained, storage_path=storage_path)

    def _load_retained_dataframe(
        self, retained: RunNodeResult, *, storage_path: Path | None = None
    ) -> pd.DataFrame:
        identity = self._result_identity(retained)
        metadata = ResultColumnMetadata(
            identity=identity,
            types=_retained_output_types(retained),
            viewers={item.output: item.viewer for item in retained.viewers},
        )
        try:
            dataframe = Storage(self._root(storage_path)).load_record_dataframe(
                identity.result_key, identity.record_id
            )
        except (CacheCorruptionError, pa.ArrowInvalid) as exc:
            raise ResultDataUnavailableError(
                f"Saved output for node '{identity.node_key}' failed validation: {exc} "
                "Re-run the affected node to regenerate its output."
            ) from exc
        except (FileNotFoundError, OSError) as exc:
            raise ResultDataNotReadyError(
                f"Output data for node '{identity.node_key}' is not ready"
            ) from exc
        dataframe.attrs[DATAFRAME_RESULT_IDENTITY_ATTR] = identity
        dataframe.attrs[DATAFRAME_RESULT_METADATA_ATTR] = metadata
        return dataframe

    def result_viewer(
        self,
        identity: ResultArtifactIdentity,
        output_key: str,
        *,
        storage_path: Path | None = None,
    ):
        """Return producer-snapshot viewer metadata for one exact output."""

        return self.result_viewers(identity, storage_path=storage_path).get(output_key)

    def result_viewers(
        self,
        identity: ResultArtifactIdentity,
        *,
        storage_path: Path | None = None,
    ) -> dict[str, object]:
        """Return all producer-snapshot viewer metadata for one exact result."""

        retained = self.read_run_node_result(identity, storage_path=storage_path)
        return {item.output: item.viewer for item in retained.viewers}

    def resolve_result_asset(
        self,
        identity: ResultArtifactIdentity,
        relative_path: str,
        *,
        storage_path: Path | None = None,
    ) -> Path:
        """Resolve an asset named by the exact immutable record manifest."""

        self.read_run_node_result(identity, storage_path=storage_path)
        return Storage(self._root(storage_path)).resolve_record_asset(
            identity.result_key,
            identity.record_id,
            relative_path,
        )

    def get_latest_record_dir(
        self, node_id: str, storage_path: Path | None = None
    ) -> Path | None:
        """Resolve the immutable record currently published for a node."""

        return self._latest_record_dir(node_id, storage_path=storage_path)

    def get_dataframe_from_record(
        self, record_dir: Path, *, node_id: str
    ) -> pd.DataFrame | None:
        """Load a DataFrame from an already-resolved immutable record."""

        data_path = self._dataframe_path(record_dir)
        if data_path is None:
            return None
        try:
            df = cache_load(data_path)
        except pa.ArrowInvalid as exc:
            raise ResultDataUnavailableError(
                f"Saved output for node '{node_id}' is unreadable: {exc}"
            ) from exc
        except (OSError, pd.errors.EmptyDataError) as exc:
            raise ResultDataNotReadyError(
                f"Output data for node '{node_id}' is not ready"
            ) from exc
        df.attrs[DATAFRAME_RECORD_DIR_ATTR] = str(record_dir)
        return df

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
        metadata = dataframe_result_metadata(df)
        if isinstance(df.attrs.get(DATAFRAME_RESULT_IDENTITY_ATTR), ResultArtifactIdentity):
            # Missing/dynamic producer facts remain unknown. Current catalog
            # metadata cannot supply authority for a retained modern result.
            declared = metadata.types if metadata is not None else {}
        else:
            declared = self._declared_output_types(tool_name)
        return {
            str(column): (
                declared[str(column)] if str(column) in declared
                else self._infer_series_type(cast(pd.Series, df[column]))
            )
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
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ResultDataUnavailableError(
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
        parent = root / "views" / "latest"
        for part in parts[:-1]:
            parent /= part
        latest = parent / f"{parts[-1]}.bioimageflow-link.json"
        if latest.is_file():
            return latest

        legacy_parent = root / "latest"
        for part in parts[:-1]:
            legacy_parent /= part
        return legacy_parent / f"{parts[-1]}.bioimageflow-link.json"

    def _resolve_link(self, link_path: Path, root: Path) -> Path:
        try:
            payload = json.loads(link_path.read_text())
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ResultDataUnavailableError(
                f"Output link '{link_path}' is not ready"
            ) from exc
        if (
            not isinstance(payload, dict)
            or payload.get("schema") != "bioimageflow.link.v1"
            or payload.get("kind") != "directory"
        ):
            raise ResultDataUnavailableError(f"Output link '{link_path}' is not ready")
        target = payload.get("target")
        if not isinstance(target, str) or not target:
            raise ResultDataUnavailableError(f"Output link '{link_path}' is not ready")
        return self._resolve_relative(link_path.parent, target, root)

    @staticmethod
    def _resolve_relative(base: Path, target: str, root: Path) -> Path:
        try:
            if Path(target).is_absolute():
                raise ResultDataUnavailableError("Output link target must be relative")
            target_path = (base / target).resolve()
            target_path.relative_to(root.resolve())
        except (ValueError, OSError, RuntimeError) as exc:
            raise ResultDataUnavailableError("Output link target is not ready") from exc
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
