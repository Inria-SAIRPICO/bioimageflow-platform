"""Tests for copied workflow result exports."""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import zipfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

import pytest
import pandas as pd
from bioimageflow.cache import _write_canonical_parquet
from bioimageflow.storage import (
    RecordManifest,
    Storage,
    asset_digest_and_size,
    canonical_dataframe_identity,
    make_record_id,
    make_result_key,
)

from bioimageflow_server.services.workflow_archive import safe_workflow_export_stem
from bioimageflow_server.services.workflow_exports import (
    OUTPUT_EXPORT_MARKER,
    OUTPUT_EXPORT_MARKER_SCHEMA,
    RESULTS_BUNDLE_MANIFEST,
    RESULTS_BUNDLE_SCHEMA,
    WorkflowExportError,
    WorkflowExportService,
)


class _Store:
    def __init__(self, root: Path, *, archive: bytes = b"workflow archive") -> None:
        self.root_dir = root / "workspace" / "workflows"
        self.workspace_dir = root / "workspace"
        self.archive = archive
        self.locked = False

    @contextmanager
    def workflow_mutation(self, workflow_id: str):
        assert workflow_id == "folder/wf"
        assert not self.locked
        self.locked = True
        try:
            yield
        finally:
            self.locked = False

    def workflow_dir(self, workflow_id: str) -> Path:
        return self.root_dir.joinpath(*workflow_id.split("/"))

    def get_storage_path(self, workflow_id: str) -> Path:
        assert self.locked
        workflow_dir = self.workflow_dir(workflow_id)
        workflow_path = workflow_dir / "workflow.json"
        if not workflow_path.exists():
            raise FileNotFoundError(workflow_id)
        return workflow_dir / "results"

    def export_workflow_archive(self, workflow_id: str) -> tuple[str, bytes]:
        assert self.locked
        return "ignored.bioimageflow.zip", self.archive


@pytest.fixture
def store(tmp_path: Path) -> _Store:
    result = _Store(tmp_path)
    workflow_dir = result.workflow_dir("folder/wf")
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "workflow.json").write_text("{}")
    return result


def _copying_export(
    storage_path: Path,
    *,
    destination: Path,
    replace: bool,
    mode: str,
    scope: str,
    run_id: str | None = None,
) -> list[Path]:
    del storage_path
    assert mode == "copy"
    if destination.exists():
        if not replace:
            raise FileExistsError(destination)
        shutil.rmtree(destination)
    if scope == "latest":
        node = destination / "latest" / "node"
    else:
        assert run_id is not None
        node = destination / "runs" / run_id / "nodes" / "node" / "outputs"
    node.mkdir(parents=True)
    asset = node / "asset.txt"
    provenance = node / "provenance.json"
    asset.write_text("copied")
    provenance.write_text('{"source": "canonical"}')
    return [asset, provenance]


def _seed_canonical_results(storage_path: Path) -> tuple[str, str]:
    storage = Storage(storage_path)
    result_key = make_result_key({"node": "platform-export"})
    provisional = storage.result_dir(result_key) / "records" / "provisional"
    provisional.mkdir(parents=True)
    frame = pd.DataFrame({"value": [1]}, index=["row"])
    parquet = provisional / "dataframe.parquet"
    _write_canonical_parquet(frame, parquet)
    logical_schema, logical_digest = canonical_dataframe_identity(frame)
    transport_digest = f"sha256:{hashlib.sha256(parquet.read_bytes()).hexdigest()}"
    identity_asset = provisional / "identity.txt"
    identity_asset.write_bytes(b"canonical asset")
    size, digest = asset_digest_and_size(identity_asset)
    identity_asset.unlink()
    outputs: list[dict[str, object]] = [
        {
            "path": "assets/mask.txt",
            "kind": "owned_asset",
            "asset_type": "file",
            "size": size,
            "digest": digest,
        }
    ]
    record_id = make_record_id(
        {
            "schema": "bioimageflow.cache.record.v1",
            "result_key": result_key,
            "dataframe": {
                "path": "dataframe.parquet",
                "format": "parquet",
                "logical_digest": logical_digest,
                "logical_schema": logical_schema,
                "transport_digest": transport_digest,
            },
            "outputs": outputs,
        }
    )
    record_dir = storage.result_dir(result_key) / "records" / record_id
    provisional.rename(record_dir)
    asset = record_dir / "assets" / "mask.txt"
    asset.parent.mkdir()
    asset.write_bytes(b"canonical asset")
    manifest = RecordManifest(
        result_key=result_key,
        record_id=record_id,
        dataframe_logical_digest=logical_digest,
        dataframe_transport_digest=transport_digest,
        dataframe_logical_schema=logical_schema,
        outputs=outputs,
    )
    (record_dir / "manifest.json").write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True)
    )
    run_id = "run-platform"
    node_id = "Node_1"
    storage.write_run_metadata(
        run_id,
        workflow_identity="folder/wf",
        engine="direct:parallel",
        status="succeeded",
        target_nodes=[node_id],
    )
    storage.write_run_node_result(
        run_id,
        node_id,
        result_key=result_key,
        record_id=record_id,
        cache_hit=False,
        provenance={"test": "platform"},
    )
    storage.update_latest_node(node_id, run_id)
    storage.update_latest_success_run(run_id)
    return node_id, run_id


def test_safe_export_stem_preserves_flat_and_disambiguates_nested_ids() -> None:
    assert safe_workflow_export_stem("wf") == "wf"
    assert safe_workflow_export_stem("a/b").startswith("a--b-")
    assert safe_workflow_export_stem("a/b") != safe_workflow_export_stem("a--b")
    assert safe_workflow_export_stem("a/b") != safe_workflow_export_stem("a--b/c")


def test_safe_export_stem_caps_long_nested_ids_without_losing_identity() -> None:
    first = "/".join(f"segment-{index:02d}-alpha" for index in range(30))
    second = f"{first}-different"

    first_stem = safe_workflow_export_stem(first)
    second_stem = safe_workflow_export_stem(second)

    assert len(first_stem.encode("utf-8")) <= 129
    assert len(f"{first_stem}.bioimageflow.zip".encode("utf-8")) < 255
    assert first_stem != second_stem
    assert first_stem.endswith(
        hashlib.sha256(first.encode("utf-8")).hexdigest()[:8]
    )


def test_latest_results_zip_contains_copies_and_provenance(
    store: _Store,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports.export_outputs",
        _copying_export,
    )

    prepared = WorkflowExportService(store).prepare_latest_results("folder/wf")  # type: ignore[arg-type]

    assert prepared.filename.startswith("folder--wf-")
    with zipfile.ZipFile(prepared.path) as archive:
        assert archive.namelist() == [
            "latest/node/asset.txt",
            "latest/node/provenance.json",
        ]
        assert archive.read("latest/node/asset.txt") == b"copied"
        assert archive.read("latest/node/provenance.json") == (
            b'{"source": "canonical"}'
        )
        assert all(
            not (info.external_attr >> 16) & 0o170000 == 0o120000
            for info in archive.infolist()
        )
    shutil.rmtree(prepared.cleanup_root)


def test_real_folder_export_materializes_owned_asset_and_provenance_as_copies(
    store: _Store,
    tmp_path: Path,
) -> None:
    storage_path = store.workflow_dir("folder/wf") / "results"
    node_id, _ = _seed_canonical_results(storage_path)
    destination_parent = tmp_path / "exports"
    destination_parent.mkdir()

    exported = WorkflowExportService(store).export_latest_results_folder(  # type: ignore[arg-type]
        "folder/wf",
        destination_parent=str(destination_parent),
        replace=False,
    )

    node = exported.destination / "latest" / node_id
    asset = node / "mask.txt"
    provenance = node / "provenance.json"
    assert asset.read_bytes() == b"canonical asset"
    assert json.loads(provenance.read_text())["run"]["run_id"] == "run-platform"
    assert not any(path.is_symlink() for path in exported.destination.rglob("*"))
    shutil.rmtree(storage_path)
    assert asset.read_bytes() == b"canonical asset"


def test_latest_results_empty_export_cleans_temporary_root(
    store: _Store,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cleanup = tmp_path / "controlled-temporary"
    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports._temporary_root",
        lambda: cleanup,
    )
    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports.export_outputs",
        lambda *args, **kwargs: [],
    )

    with pytest.raises(WorkflowExportError) as caught:
        WorkflowExportService(store).prepare_latest_results("folder/wf")  # type: ignore[arg-type]

    assert caught.value.code == "results_not_available"
    assert not cleanup.exists()


def test_latest_results_zip_failure_cleans_temporary_root(
    store: _Store,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cleanup = tmp_path / "controlled-zip"
    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports._temporary_root",
        lambda: cleanup,
    )
    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports.export_outputs",
        _copying_export,
    )
    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports._zip_tree",
        Mock(side_effect=OSError("zip failed")),
    )

    with pytest.raises(OSError, match="zip failed"):
        WorkflowExportService(store).prepare_latest_results("folder/wf")  # type: ignore[arg-type]

    assert not cleanup.exists()


def test_bundle_pins_latest_success_once_and_writes_manifest(
    store: _Store,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = Mock()
    storage.latest_success_run_id.return_value = "run-42"
    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports.Storage",
        lambda path: storage,
    )
    calls: list[dict[str, object]] = []

    def export(*args: object, **kwargs: object) -> list[Path]:
        calls.append(dict(kwargs))
        return _copying_export(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports.export_outputs",
        export,
    )

    prepared = WorkflowExportService(store).prepare_workflow_run_bundle("folder/wf")  # type: ignore[arg-type]

    assert storage.latest_success_run_id.call_count == 1
    assert calls == [
        {
            "destination": prepared.cleanup_root / "bundle" / "results",
            "replace": False,
            "mode": "copy",
            "scope": "runs",
            "run_id": "run-42",
        }
    ]
    with zipfile.ZipFile(prepared.path) as archive:
        members = set(archive.namelist())
        nested = next(
            member
            for member in members
            if member.startswith("workflow/") and member.endswith(".bioimageflow.zip")
        )
        assert RESULTS_BUNDLE_MANIFEST in members
        assert "results/runs/run-42/nodes/node/outputs/asset.txt" in members
        manifest = json.loads(archive.read(RESULTS_BUNDLE_MANIFEST))
        assert manifest == {
            "schema": RESULTS_BUNDLE_SCHEMA,
            "kind": "workflow-with-results",
            "workflow_id": "folder/wf",
            "workflow": {
                "archive": nested,
                "sha256": hashlib.sha256(store.archive).hexdigest(),
            },
            "results": {
                "kind": "latest-successful-run",
                "run_id": "run-42",
                "path": "results/runs/run-42",
            },
        }
    shutil.rmtree(prepared.cleanup_root)


def test_bundle_materialization_failure_cleans_staging_and_retry_preserves_source(
    store: _Store,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bioimageflow_server.services import workflow_exports

    storage_path = store.workflow_dir("folder/wf") / "results"
    node_id, run_id = _seed_canonical_results(storage_path)
    source_files = {
        path.relative_to(storage_path): path.read_bytes()
        for path in storage_path.rglob("*")
        if path.is_file()
    }
    failed_root = tmp_path / "failed-bundle"
    monkeypatch.setattr(workflow_exports, "_temporary_root", lambda: failed_root)
    real_zip_tree = workflow_exports._zip_tree
    monkeypatch.setattr(
        workflow_exports,
        "_zip_tree",
        Mock(side_effect=OSError("bundle zip failed")),
    )

    with pytest.raises(OSError, match="bundle zip failed"):
        WorkflowExportService(store).prepare_workflow_run_bundle("folder/wf")  # type: ignore[arg-type]

    assert not failed_root.exists()
    assert {
        path.relative_to(storage_path): path.read_bytes()
        for path in storage_path.rglob("*")
        if path.is_file()
    } == source_files

    monkeypatch.setattr(workflow_exports, "_zip_tree", real_zip_tree)
    retry_root = tmp_path / "retry-bundle"
    monkeypatch.setattr(workflow_exports, "_temporary_root", lambda: retry_root)
    prepared = WorkflowExportService(store).prepare_workflow_run_bundle("folder/wf")  # type: ignore[arg-type]
    with zipfile.ZipFile(prepared.path) as archive:
        manifest = json.loads(archive.read(RESULTS_BUNDLE_MANIFEST))
        assert manifest["results"]["run_id"] == run_id
        prefix = f"results/runs/{run_id}/nodes/{node_id}/outputs/"
        assert archive.read(f"{prefix}assets/mask.txt") == b"canonical asset"
        assert json.loads(archive.read(f"{prefix}provenance.json"))["run"]["run_id"] == run_id
    assert {
        path.relative_to(storage_path): path.read_bytes()
        for path in storage_path.rglob("*")
        if path.is_file()
    } == source_files


def test_bundle_without_successful_run_is_unavailable(
    store: _Store,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cleanup = tmp_path / "controlled-bundle"
    storage = Mock()
    storage.latest_success_run_id.return_value = None
    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports._temporary_root",
        lambda: cleanup,
    )
    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports.Storage",
        lambda path: storage,
    )

    with pytest.raises(WorkflowExportError) as caught:
        WorkflowExportService(store).prepare_workflow_run_bundle("folder/wf")  # type: ignore[arg-type]

    assert caught.value.code == "results_not_available"
    assert not cleanup.exists()


def test_folder_export_marks_target_and_only_replaces_matching_export(
    store: _Store,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination_parent = tmp_path / "exports"
    destination_parent.mkdir()
    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports.export_outputs",
        _copying_export,
    )
    service = WorkflowExportService(store)  # type: ignore[arg-type]

    first = service.export_latest_results_folder(
        "folder/wf",
        destination_parent=str(destination_parent),
        replace=False,
    )

    assert first.exported_items == 2
    marker = first.destination / OUTPUT_EXPORT_MARKER
    assert json.loads(marker.read_text()) == {
        "schema": OUTPUT_EXPORT_MARKER_SCHEMA,
        "workflow_id": "folder/wf",
    }
    with pytest.raises(WorkflowExportError) as exists:
        service.export_latest_results_folder(
            "folder/wf",
            destination_parent=str(destination_parent),
            replace=False,
        )
    assert exists.value.code == "export_destination_exists"

    replaced = service.export_latest_results_folder(
        "folder/wf",
        destination_parent=str(destination_parent),
        replace=True,
    )
    assert replaced.destination == first.destination

    marker.write_text('{"workflow_id": "another"}')
    with pytest.raises(WorkflowExportError) as unsafe:
        service.export_latest_results_folder(
            "folder/wf",
            destination_parent=str(destination_parent),
            replace=True,
        )
    assert unsafe.value.code == "unsafe_export_replacement"


def test_empty_folder_export_preserves_previous_marked_export(
    store: _Store,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination_parent = tmp_path / "exports"
    destination_parent.mkdir()
    service = WorkflowExportService(store)  # type: ignore[arg-type]
    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports.export_outputs",
        _copying_export,
    )
    previous = service.export_latest_results_folder(
        "folder/wf",
        destination_parent=str(destination_parent),
        replace=False,
    )
    previous_asset = previous.destination / "latest" / "node" / "asset.txt"
    previous_asset.write_text("previous")
    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports.export_outputs",
        lambda *args, **kwargs: [],
    )

    with pytest.raises(WorkflowExportError) as caught:
        service.export_latest_results_folder(
            "folder/wf",
            destination_parent=str(destination_parent),
            replace=True,
        )

    assert caught.value.code == "results_not_available"
    assert previous_asset.read_text() == "previous"
    assert not list(destination_parent.glob(".*.tmp"))


def test_marker_failure_preserves_previous_export(
    store: _Store,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination_parent = tmp_path / "exports"
    destination_parent.mkdir()
    service = WorkflowExportService(store)  # type: ignore[arg-type]
    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports.export_outputs",
        _copying_export,
    )
    previous = service.export_latest_results_folder(
        "folder/wf",
        destination_parent=str(destination_parent),
        replace=False,
    )
    previous_asset = previous.destination / "latest" / "node" / "asset.txt"
    previous_asset.write_text("previous")
    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports._write_marker",
        Mock(side_effect=OSError("marker failed")),
    )

    with pytest.raises(OSError, match="marker failed"):
        service.export_latest_results_folder(
            "folder/wf",
            destination_parent=str(destination_parent),
            replace=True,
        )

    assert previous_asset.read_text() == "previous"
    assert not list(destination_parent.glob(".*.tmp"))


def test_install_failure_rolls_back_previous_export(
    store: _Store,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination_parent = tmp_path / "exports"
    destination_parent.mkdir()
    service = WorkflowExportService(store)  # type: ignore[arg-type]
    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports.export_outputs",
        _copying_export,
    )
    previous = service.export_latest_results_folder(
        "folder/wf",
        destination_parent=str(destination_parent),
        replace=False,
    )
    previous_asset = previous.destination / "latest" / "node" / "asset.txt"
    previous_asset.write_text("previous")
    real_replace = os.replace

    def fail_new_install(source: str | Path, target: str | Path) -> None:
        if Path(target) == previous.destination and Path(source).name.endswith(".tmp"):
            raise OSError("install failed")
        real_replace(source, target)

    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports.os.replace",
        fail_new_install,
    )

    with pytest.raises(OSError, match="install failed"):
        service.export_latest_results_folder(
            "folder/wf",
            destination_parent=str(destination_parent),
            replace=True,
        )

    assert previous_asset.read_text() == "previous"
    assert not list(destination_parent.glob(".*.tmp"))
    assert not list(destination_parent.glob(".*.backup"))


def test_folder_export_allows_home_descendant_outside_workspace(
    store: _Store,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination_parent = tmp_path / "home" / "Desktop"
    destination_parent.mkdir(parents=True)
    monkeypatch.setattr(
        Path,
        "home",
        classmethod(lambda cls: tmp_path / "home"),
    )
    monkeypatch.setattr(
        "bioimageflow_server.services.workflow_exports.export_outputs",
        _copying_export,
    )

    exported = WorkflowExportService(store).export_latest_results_folder(  # type: ignore[arg-type]
        "folder/wf",
        destination_parent=str(destination_parent),
        replace=False,
    )

    assert exported.destination.parent == destination_parent


def test_folder_export_rejects_symlink_parent_and_target(
    store: _Store,
    tmp_path: Path,
) -> None:
    real_parent = tmp_path / "real-exports"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-exports"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    service = WorkflowExportService(store)  # type: ignore[arg-type]

    with pytest.raises(WorkflowExportError) as parent_error:
        service.export_latest_results_folder(
            "folder/wf",
            destination_parent=str(linked_parent),
            replace=False,
        )
    assert parent_error.value.code == "unsafe_export_destination"

    target = real_parent / f"{safe_workflow_export_stem('folder/wf')}-latest-results"
    target.symlink_to(tmp_path / "somewhere", target_is_directory=True)
    with pytest.raises(WorkflowExportError) as target_error:
        service.export_latest_results_folder(
            "folder/wf",
            destination_parent=str(real_parent),
            replace=True,
        )
    assert target_error.value.code == "unsafe_export_destination"


@pytest.mark.parametrize("raw_parent", ["relative", "/"])
def test_folder_export_rejects_unsafe_parent(
    store: _Store,
    raw_parent: str,
) -> None:
    with pytest.raises(WorkflowExportError) as caught:
        WorkflowExportService(store).export_latest_results_folder(  # type: ignore[arg-type]
            "folder/wf",
            destination_parent=raw_parent,
            replace=False,
        )

    assert caught.value.code in {
        "invalid_export_destination",
        "unsafe_export_destination",
    }
