"""Retained producer declarations own table semantics without new storage reads."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated
from unittest.mock import MagicMock

import pandas as pd
import pytest
from bioimageflow.storage import OutputViewerMetadata, RunNodeResult
from bioimageflow_core import DECLARATION_CONTRACT_VERSION, IOModel, ImageSpec, ViewerSpec, describe_io_model

from bioimageflow_server.models.data_table import DataTableSource
from bioimageflow_server.models.results import ResultArtifactIdentity
from bioimageflow_server.routers.nodes import _node_data_response
from bioimageflow_server.services import result_store as result_store_module
from bioimageflow_server.services.data_table_projection import DataTableProjectionService
from bioimageflow_server.services.result_store import ResultDataNotReadyError, ResultStoreService


class _Outputs(IOModel):
    path: Path | None
    image: Annotated[Path | None, ImageSpec()]


def _loaded_store(tmp_path, monkeypatch, dataframe, declaration, *, omit_outputs=False):
    identity = ResultArtifactIdentity(
        run_id="run_retained", node_key="node", result_key="rk_retained", record_id="rec_retained",
    )
    viewer = ViewerSpec.from_dict({
        "napari": {
            "required_packages": [], "recommended_packages": [],
            "napari_version": None, "reader_id": "retained.reader",
        },
    })
    retained = RunNodeResult(
        run_id=identity.run_id, node_key=identity.node_key,
        result_key=identity.result_key, record_id=identity.record_id,
        cache_hit=False, canonical="record", outputs=(),
        provenance=(None if declaration == "missing" else {
            "tool": {"executable": {
                "declaration_contract": DECLARATION_CONTRACT_VERSION,
                "declaration": {} if omit_outputs else {"outputs": declaration},
            }},
        }),
        viewers=(OutputViewerMetadata(output="image", viewer=viewer),),
    )
    registry = MagicMock()
    registry.get_tool.return_value = SimpleNamespace(outputs={
        column: {"type": "str"} for column in dataframe.columns
    })
    store = ResultStoreService(tmp_path, registry)
    reads = []
    loads = []

    def admitted_result(captured, *, storage_path=None):
        assert captured == identity
        reads.append(captured)
        return retained

    class ExactRecordStorage:
        def __init__(self, root):
            assert root == tmp_path

        def load_record_dataframe(self, result_key, record_id):
            assert (result_key, record_id) == (identity.result_key, identity.record_id)
            loads.append((result_key, record_id))
            return dataframe.copy(deep=True)

    def refuse_model_instance(*args, **kwargs):
        raise AssertionError("Table metadata must not construct IOModel/native-value owners")

    monkeypatch.setattr(store, "read_run_node_result", admitted_result)
    monkeypatch.setattr(result_store_module, "Storage", ExactRecordStorage)
    monkeypatch.setattr(IOModel, "__init__", refuse_model_instance)
    return store, identity, registry, reads, loads


def _table(store, identity, consumer):
    if consumer == "individual":
        dataframe = store.load_result_dataframe(identity)
        response = _node_data_response(
            dataframe, store, page=0, page_size=50, sort_by=None, sort_order="asc",
            filters=[], tool_name="SameName", storage_path=None,
        )
        assert response.source_identity == identity
        assert response.identity_status == "captured"
        return response.column_types, response.column_viewers
    response = DataTableProjectionService(store).query(
        [DataTableSource(
            node_id=identity.node_key, role="anchor", label="Retained", tool_name="SameName",
            result_identity=identity,
        )],
        storage_path=None, page=0, page_size=50, sort_by=None, sort_order="asc",
    )
    assert response.mode == "merged"
    assert response.sources[0].result_identity == identity
    assert all(column.viewer_status == "captured" for column in response.columns)
    return (
        {column.source_column: column.type for column in response.columns},
        {column.source_column: column.viewer for column in response.columns},
    )


@pytest.mark.parametrize("consumer", ["individual", "merged"])
@pytest.mark.parametrize("values", [["retained.tif"], [None], []], ids=["present", "null", "empty"])
def test_retained_declared_types_and_viewers_ignore_current_catalog_without_rereading(
    tmp_path, monkeypatch, consumer, values,
):
    store, identity, registry, reads, loads = _loaded_store(
        tmp_path, monkeypatch,
        pd.DataFrame({"path": pd.Series(values, dtype=object), "image": pd.Series(values, dtype=object)}),
        describe_io_model(_Outputs),
    )

    types, viewers = _table(store, identity, consumer)

    assert types == {"path": "Path", "image": "ImageFile"}
    assert viewers["path"] is None
    assert viewers["image"].napari.reader_id == "retained.reader"
    registry.get_tool.assert_not_called()
    assert reads == [identity]
    assert loads == [(identity.result_key, identity.record_id)]


@pytest.mark.parametrize("declaration", [None, "missing"], ids=["dynamic", "missing"])
def test_unknown_modern_declarations_infer_values_without_catalog(
    tmp_path, monkeypatch, declaration,
):
    store, identity, registry, reads, loads = _loaded_store(
        tmp_path, monkeypatch, pd.DataFrame({"amount": [7]}), declaration,
    )

    types, _viewers = _table(store, identity, "individual")

    assert types == {"amount": "int"}
    registry.get_tool.assert_not_called()
    assert reads == [identity]
    assert loads == [(identity.result_key, identity.record_id)]


def test_passthrough_declared_extra_retains_null_type_and_infers_unclaimed_column(
    tmp_path, monkeypatch,
):
    store, identity, registry, reads, loads = _loaded_store(
        tmp_path, monkeypatch, pd.DataFrame({"path": [None], "amount": [7]}),
        describe_io_model(_Outputs, passthrough=True),
    )

    types, _viewers = _table(store, identity, "merged")

    assert types == {"path": "Path", "amount": "int"}
    registry.get_tool.assert_not_called()
    assert reads == [identity]
    assert loads == [(identity.result_key, identity.record_id)]


@pytest.mark.parametrize("malformation", ["type_spec", "missing_outputs"])
def test_malformed_present_retained_descriptor_is_unavailable_before_catalog_fallback(
    tmp_path, monkeypatch, malformation,
):
    declaration = deepcopy(describe_io_model(_Outputs))
    if malformation == "type_spec":
        declaration["fields"]["path"]["type_spec"] = {"kind": "arbitrary-import", "module": "untrusted"}
    store, identity, registry, _reads, _loads = _loaded_store(
        tmp_path, monkeypatch, pd.DataFrame({"path": ["retained.tif"]}), declaration,
        omit_outputs=malformation == "missing_outputs",
    )

    with pytest.raises(ResultDataNotReadyError):
        _table(store, identity, "individual")
    registry.get_tool.assert_not_called()
