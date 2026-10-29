"""Tests for platform latest-output mode policy."""

import errno
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
from bioimageflow import Workflow
from bioimageflow.cache import dataframe_publish, dataframe_result_key
from bioimageflow.storage import OutputViewCapability, RunNodeResult, Storage

from bioimageflow_server.services import output_views


def _capability(mode: str, supported: bool) -> OutputViewCapability:
    return OutputViewCapability(
        mode=mode,
        supported=supported,
        code="ok" if supported else "permission_denied",
    )


def _capabilities(*, symlink: bool = True) -> dict[str, OutputViewCapability]:
    return {
        "pointer": _capability("pointer", True),
        "symlink": _capability("symlink", symlink),
    }


def test_auto_uses_symlinks_when_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(output_views, "probe_latest_output_modes", lambda _path: _capabilities())

    resolved = output_views.resolve_latest_output_mode(Path("/outputs"))

    assert resolved.effective == "symlink"
    assert resolved.warning is None


def test_auto_falls_back_to_pointer_without_copying(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        output_views,
        "probe_latest_output_modes",
        lambda _path: _capabilities(symlink=False),
    )

    resolved = output_views.resolve_latest_output_mode(Path("/outputs"))

    assert resolved.effective == "pointer"
    assert "permissions" in (resolved.warning or "")


def test_runtime_symlink_failure_falls_back_to_pointer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(output_views, "probe_latest_output_modes", lambda _path: _capabilities())
    workflow = MagicMock()
    workflow.export_outputs.side_effect = [OSError("links denied"), [Path("pointer")]]
    resolved = output_views.materialize_latest_outputs(
        workflow,
        storage_path=Path("/outputs"),
    )

    assert resolved.effective == "pointer"
    assert workflow.export_outputs.call_args_list[0].kwargs == {
        "mode": "symlink",
        "scope": "latest",
    }
    assert workflow.export_outputs.call_args_list[1].kwargs == {
        "mode": "pointer",
        "scope": "latest",
    }


_RETAINED_VALUES = {"group/first": [2, 3], "second": [5]}


def _retained_records(root: Path) -> tuple[Storage, dict[str, RunNodeResult]]:
    """Publish ordinary retained data, without computing a scientific workflow."""
    storage = Storage(root)
    records = {}
    for index, (node_id, values) in enumerate(_RETAINED_VALUES.items(), start=1):
        run_id = f"run_{index:032x}"
        signature = f"output-view-{index}"
        dataframe_publish(
            root, node_id, signature, pd.DataFrame({"value": values}),
            run_id=run_id, engine="direct:parallel", tool_identity="tests:output-views",
        )
        result_key = dataframe_result_key(node_id, signature)
        current = storage.load_current(result_key)
        assert current is not None
        storage.write_run_metadata(
            run_id, workflow_identity="output-view-control", engine="direct",
            status="succeeded", target_nodes=[node_id],
        )
        storage.write_run_node_result(
            run_id, node_id, result_key=result_key, record_id=current.record_id, cache_hit=False,
        )
        storage.update_latest_node(node_id, run_id)
        records[node_id] = storage.read_run_node_result(run_id, node_id)
    return storage, records


def _canonical_hashes(storage: Storage) -> dict[str, str]:
    return {
        path.relative_to(storage.storage_path).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for root in (storage.cache_root, storage.views_root)
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def _assert_real_projection(
    storage: Storage, records: dict[str, RunNodeResult], mode: str,
) -> None:
    for node_id, record in records.items():
        canonical = storage.result_dir(record.result_key) / "records" / record.record_id / "dataframe.parquet"
        destination = storage.outputs_root / "latest" / node_id / "dataframe.parquet"
        if mode == "symlink":
            assert destination.is_symlink()
            assert destination.resolve() == canonical.resolve()
            readable = destination
        else:
            assert not destination.exists() and not destination.is_symlink()
            pointer = destination.with_name(f"{destination.name}.bioimageflow-link.json")
            assert pointer.is_file() and not pointer.is_symlink()
            payload = json.loads(pointer.read_text())
            assert payload["schema"] == "bioimageflow.link.v1"
            assert payload["kind"] == "file"
            assert not Path(payload["target"]).is_absolute()
            readable = (pointer.parent / payload["target"]).resolve()
            assert readable == canonical.resolve()
        assert hashlib.sha256(readable.read_bytes()).digest() == hashlib.sha256(canonical.read_bytes()).digest()
        pd.testing.assert_frame_equal(pd.read_parquet(readable), pd.DataFrame({"value": _RETAINED_VALUES[node_id]}))
        assert storage.read_latest_node_result(node_id) == record
    assert not list(storage.storage_path.glob(".output-view-probe-*"))


def test_real_latest_projection_preserves_record_identity_after_reopen(tmp_path: Path) -> None:
    storage, records = _retained_records(tmp_path / "results")
    before = _canonical_hashes(storage)
    capabilities = output_views.probe_latest_output_modes(storage.storage_path)
    assert capabilities["pointer"].supported
    expected_mode = "symlink" if capabilities["symlink"].supported else "pointer"
    assert len({record.run_id for record in records.values()}) == 2

    resolved = output_views.materialize_latest_outputs(
        Workflow(storage.storage_path, engine="direct"), storage_path=storage.storage_path,
    )

    assert resolved.effective == expected_mode
    assert (resolved.warning is None) == (expected_mode == "symlink")
    _assert_real_projection(storage, records, expected_mode)
    reopened = Storage(storage.storage_path)
    _assert_real_projection(reopened, records, expected_mode)
    republished = output_views.materialize_latest_outputs(
        Workflow(reopened.storage_path, engine="direct"), storage_path=reopened.storage_path,
    )
    assert republished == resolved
    _assert_real_projection(reopened, records, expected_mode)
    assert _canonical_hashes(reopened) == before


@pytest.mark.parametrize("denial_stage", ["probe", "publication"])
def test_real_latest_pointer_fallback_preserves_canonical_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, denial_stage: str,
) -> None:
    storage, records = _retained_records(tmp_path / "results")
    before = _canonical_hashes(storage)
    original_symlink = os.symlink
    denied = []

    def deny_symlink(
        source: str | os.PathLike[str], destination: str | os.PathLike[str],
        target_is_directory: bool = False, *, dir_fd: int | None = None,
    ) -> None:
        destination_path = Path(destination)
        is_probe = any(part.startswith(".output-view-probe-") for part in destination_path.parts)
        if denial_stage == "probe" or not is_probe:
            denied.append(destination_path)
            raise PermissionError(errno.EPERM, "Owned output-view control denies symbolic links")
        original_symlink(source, destination, target_is_directory=target_is_directory, dir_fd=dir_fd)

    monkeypatch.setattr(os, "symlink", deny_symlink)
    resolved = output_views.materialize_latest_outputs(
        Workflow(storage.storage_path, engine="direct"), storage_path=storage.storage_path,
    )

    assert denied
    assert resolved.effective == "pointer"
    if denial_stage == "probe":
        assert "permissions" in (resolved.warning or "")
        assert all(any(part.startswith(".output-view-probe-") for part in path.parts) for path in denied)
    else:
        assert "execution time" in (resolved.warning or "")
        assert all(not any(part.startswith(".output-view-probe-") for part in path.parts) for path in denied)
    _assert_real_projection(Storage(storage.storage_path), records, "pointer")
    assert _canonical_hashes(storage) == before


def test_real_latest_projection_refusal_preserves_canonical_records(tmp_path: Path) -> None:
    storage, records = _retained_records(tmp_path / "results")
    before = _canonical_hashes(storage)
    obstruction = storage.outputs_root
    obstruction.write_bytes(b"owned projection-parent obstruction\n")
    sentinel = tmp_path / "unrelated.txt"
    sentinel.write_bytes(b"unrelated owned sentinel\n")

    with pytest.raises(OSError):
        output_views.materialize_latest_outputs(
            Workflow(storage.storage_path, engine="direct"), storage_path=storage.storage_path,
        )

    assert obstruction.is_file() and not obstruction.is_symlink()
    assert obstruction.read_bytes() == b"owned projection-parent obstruction\n"
    assert sentinel.read_bytes() == b"unrelated owned sentinel\n"
    assert _canonical_hashes(storage) == before
    reopened = Storage(storage.storage_path)
    for node_id, record in records.items():
        assert reopened.read_latest_node_result(node_id) == record
    assert not list(storage.storage_path.glob(".output-view-probe-*"))
