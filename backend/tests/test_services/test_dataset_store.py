"""Tests for the DatasetStore service (Task 2)."""

from __future__ import annotations

import base64
import asyncio
import sqlite3
import threading
from collections.abc import AsyncIterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from bioimageflow_server.services.dataset_store import (
    CatalogConflictError,
    DatasetNotFoundError,
    DatasetPublicationError,
    DatasetStore,
    FileTooLargeError,
    InvalidMoveError,
    NameConflictError,
    PathTraversalError,
)
from bioimageflow_server.services import dataset_store as store_module


pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _bytes_stream(chunks: list[bytes]) -> AsyncIterable[bytes]:
    for chunk in chunks:
        yield chunk


def _make_store(tmp_path: Path, cap: int = 10_000_000) -> DatasetStore:
    return DatasetStore(datasets_root=tmp_path / "datasets", max_upload_size=cap)


# ---------------------------------------------------------------------------
# list()
# ---------------------------------------------------------------------------


async def test_list_empty_when_dir_missing(tmp_path: Path):
    store = DatasetStore(datasets_root=tmp_path / "not-yet", max_upload_size=1_000_000)
    # Ensure the constructor doesn't crash even though we point at a non-existent
    # path — it should mkdir on construction per plan.
    assert store.list() == []


async def test_list_empty_dir(tmp_path: Path):
    store = _make_store(tmp_path)
    assert store.list() == []


async def test_list_returns_items_newest_first(tmp_path: Path):
    store = _make_store(tmp_path)
    # Use the raw filename convention so we can control timestamp ordering
    (store.root / "20260101T010000_a.tif").write_bytes(b"a")
    (store.root / "20260421T143022_b.tif").write_bytes(b"bb")
    (store.root / "20260215T000000_c.tif").write_bytes(b"ccc")

    result = store.list()
    assert [d.original_filename for d in result] == ["b.tif", "c.tif", "a.tif"]


# ---------------------------------------------------------------------------
# store()
# ---------------------------------------------------------------------------


async def test_store_writes_file(tmp_path: Path):
    store = _make_store(tmp_path)
    meta = await store.store("cells.tif", _bytes_stream([b"hello", b"world"]))
    assert meta.original_filename == "cells.tif"
    assert meta.size == 10
    assert meta.content_type == "image/tiff"
    stored = Path(meta.path)
    assert stored.is_file()
    assert stored.read_bytes() == b"helloworld"
    # Timestamp prefix convention is YYYYMMDDTHHMMSS_<stem>.<ext>
    assert stored.name.endswith("_cells.tif")


async def test_streaming_upload_is_not_published_by_a_concurrent_store(tmp_path: Path):
    store = _make_store(tmp_path)
    during_upload = []

    async def chunks() -> AsyncIterable[bytes]:
        yield b"hello"
        observer = _make_store(tmp_path)
        during_upload.extend(observer.list())
        yield b"world"

    record = await store.store("cells.tif", chunks())

    assert during_upload == []
    reopened = _make_store(tmp_path)
    assert reopened.list() == [record]
    assert record.size == 10
    assert Path(record.path).read_bytes() == b"helloworld"


async def test_store_rejects_oversize(tmp_path: Path):
    store = _make_store(tmp_path, cap=4)
    with pytest.raises(FileTooLargeError):
        await store.store("big.bin", _bytes_stream([b"12", b"345"]))
    # No partial file left behind
    assert not any(path.is_file() and not path.name.startswith(".bioimageflow") for path in store.root.iterdir())
    assert not list(store.root.glob(".bioimageflow-upload-*"))


async def test_store_cleans_up_on_error(tmp_path: Path):
    store = _make_store(tmp_path, cap=10)

    async def exploding() -> AsyncIterable[bytes]:
        yield b"ab"
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await store.store("boom.bin", exploding())
    assert not any(path.is_file() and not path.name.startswith(".bioimageflow") for path in store.root.iterdir())
    assert not list(store.root.glob(".bioimageflow-upload-*"))


@pytest.mark.parametrize("progress", [2, 0])
async def test_store_handles_partial_or_zero_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, progress: int,
):
    store = _make_store(tmp_path)
    write = store_module.os.write
    monkeypatch.setattr(store_module.os, "write", lambda fd, chunk: write(fd, chunk[:progress]))
    if progress:
        record = await store.store("cells.tif", _bytes_stream([b"hello", b"world"]))
        assert record.size == 10
        assert Path(record.path).read_bytes() == b"helloworld"
    else:
        with pytest.raises(OSError, match="no progress"):
            await store.store("cells.tif", _bytes_stream([b"hello"]))
        assert store.list() == []
    assert not list(store.root.glob(".bioimageflow-upload-*"))


async def test_store_cancellation_removes_only_owned_staging(tmp_path: Path):
    store = _make_store(tmp_path)
    sibling = await store.store("keep.tif", _bytes_stream([b"keep"]))
    entered = asyncio.Event()

    async def blocked():
        yield b"partial"
        entered.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(store.store("cancel.tif", blocked()))
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert Path(sibling.path).read_bytes() == b"keep"
    assert store.list() == [sibling]
    assert not list(store.root.glob(".bioimageflow-upload-*"))


async def test_store_close_failure_removes_unpublished_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    store = _make_store(tmp_path)
    close = store_module.os.close
    failed = False

    def failing_close(fd):
        nonlocal failed
        close(fd)
        if not failed:
            failed = True
            raise OSError("staging close failed")

    monkeypatch.setattr(store_module.os, "close", failing_close)
    with pytest.raises(OSError, match="staging close failed"):
        await store.store("cells.tif", _bytes_stream([b"complete but unclosed"]))
    assert not list(store.root.glob(".bioimageflow-upload-*"))
    assert store.list() == []


async def test_store_refuses_folder_removed_during_streaming(tmp_path: Path):
    store = _make_store(tmp_path)
    folder = store.create_folder("removed")

    async def chunks():
        yield b"complete"
        other = _make_store(tmp_path)
        preview = other.preview_delete([], [folder.id])
        other.delete_selection([], [folder.id], expected_revision=preview.revision)

    with pytest.raises(store_module.FolderNotFoundError):
        await store.store("cells.tif", chunks(), folder_id=folder.id)
    assert store.list() == []
    assert store.list_folders() == []
    assert not list(store.root.glob(".bioimageflow-upload-*"))


@pytest.mark.parametrize("fault", [
    "insert", "commit_held", "commit_rolled_back", "commit_accepted", "close_accepted",
    "programming", "interface", "cleanup",
])
async def test_publication_failure_preserves_commit_ownership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str,
):
    store = _make_store(tmp_path)
    open_connection = store._open_connection

    class FaultConnection:
        def __init__(self):
            self.connection = open_connection()

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def execute(self, sql, *args):
            if sql.startswith("INSERT INTO datasets"):
                if fault in {"insert", "cleanup"}:
                    raise sqlite3.IntegrityError("original insert failure")
                if fault == "programming":
                    raise sqlite3.ProgrammingError("original programming failure")
                if fault == "interface":
                    raise sqlite3.InterfaceError("original interface failure")
            return self.connection.execute(sql, *args)

        def commit(self):
            if fault == "commit_held":
                raise sqlite3.OperationalError("commit still held")
            if fault == "commit_rolled_back":
                self.connection.rollback()
                raise sqlite3.OperationalError("commit outcome ambiguous")
            self.connection.commit()
            if fault == "commit_accepted":
                raise sqlite3.OperationalError("accepted commit acknowledgement failed")

        def rollback(self):
            self.connection.rollback()
            if fault == "cleanup":
                raise sqlite3.OperationalError("secondary rollback failure")

        def close(self):
            self.connection.close()
            if fault in {"cleanup", "close_accepted"}:
                raise sqlite3.OperationalError("secondary close failure")

    monkeypatch.setattr(store, "_open_connection", FaultConnection)
    error = {
        "programming": sqlite3.ProgrammingError, "interface": sqlite3.InterfaceError,
    }.get(fault, DatasetPublicationError)
    with pytest.raises(error) as failure:
        await store.store("cells.tif", _bytes_stream([b"complete bytes"]))
    if fault == "cleanup":
        assert "original insert failure" in str(failure.value.__cause__)
    assert not list(store.root.glob(".bioimageflow-upload-*"))
    physical = [p for p in store.root.iterdir() if not p.name.startswith(".bioimageflow")]
    retained = fault in {"commit_rolled_back", "commit_accepted", "close_accepted"}
    assert len(physical) == int(retained)
    if retained:
        assert physical[0].read_bytes() == b"complete bytes"
    # Reopen uses the real connection and reconciles only complete legacy bytes.
    reopened = _make_store(tmp_path)
    records = reopened.list()
    assert len(records) == int(retained)
    if retained:
        assert Path(records[0].path).read_bytes() == b"complete bytes"
        assert records[0].size == len(b"complete bytes")


async def test_failed_publication_rename_preserves_unowned_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    store = _make_store(tmp_path)
    folder = store.create_folder("Experiment")
    sibling = await store.store("sibling.tif", _bytes_stream([b"accepted sibling"]), folder_id=folder.id)
    before = store.preview_delete([], [folder.id])
    candidate: Path | None = None
    rename = Path.rename

    def fail_upload_rename(source: Path, target: Path) -> Path:
        nonlocal candidate
        if source.parent == store.root and source.name.startswith(".bioimageflow-upload-"):
            assert source.read_bytes() == b"upload bytes"
            candidate = target
            # An entry appearing after reservation is not owned by this upload.
            target.write_bytes(b"unowned candidate sentinel")
            raise OSError("controlled rename failure")
        return rename(source, target)

    monkeypatch.setattr(Path, "rename", fail_upload_rename)
    with pytest.raises(OSError, match="controlled rename failure"):
        await store.store("cells.tif", _bytes_stream([b"upload bytes"]), folder_id=folder.id)

    assert candidate is not None
    assert candidate.read_bytes() == b"unowned candidate sentinel"
    assert Path(sibling.path).read_bytes() == b"accepted sibling"
    assert not list(store.root.glob(".bioimageflow-upload-*"))
    # Use the catalog projection, avoiding legacy reconciliation of the sentinel.
    assert store.preview_delete([], [folder.id]) == before
    assert store.resolve_selection([sibling.id], []) == [sibling]


async def test_publication_preserves_dangling_entry_and_reserved_catalog_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    store = _make_store(tmp_path)
    monkeypatch.setattr(store_module, "_now_compact", lambda: "20260101T010000")
    dangling = store.root / "20260101T010000_cells.tif"
    missing = store.root / "missing.tif"
    dangling.symlink_to(missing)
    reserved = await store.store("cells.tif", _bytes_stream([b"first"]))
    Path(reserved.path).unlink()
    replacement = await store.store("cells.tif", _bytes_stream([b"second"]))
    assert dangling.is_symlink()
    assert dangling.readlink() == missing
    assert replacement.id != reserved.id
    assert Path(replacement.path).read_bytes() == b"second"
    assert Path(replacement.path).name.endswith("_cells_2.tif")


@pytest.mark.parametrize("operation", ["folder", "upload", "delete"])
async def test_catalog_admission_waits_for_competing_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str,
):
    owner, contender = _make_store(tmp_path), _make_store(tmp_path)
    dataset = await owner.store("keep.tif", _bytes_stream([b"keep"]))
    preview = owner.preview_delete([dataset.id], [])
    entered, release, admission = threading.Event(), threading.Event(), threading.Event()
    bump = owner._bump_revision

    def held_bump(connection):
        # The public folder operation has already inserted and owns SQLite's
        # real writer here; pause before its revision and commit become visible.
        entered.set()
        assert release.wait(timeout=5), "writer fixture was not released"
        bump(connection)

    monkeypatch.setattr(owner, "_bump_revision", held_bump)
    open_connection = contender._open_connection

    def observed_connection():
        connection = open_connection()
        # Explicit and SQLite implicit BEGIN both reach this physical boundary.
        connection.set_trace_callback(lambda sql: admission.set() if sql.startswith("BEGIN") else None)
        return connection

    monkeypatch.setattr(contender, "_open_connection", observed_connection)

    def competing_operation():
        if operation == "folder":
            return contender.create_folder("taken")
        if operation == "upload":
            return asyncio.run(contender.store("Taken", _bytes_stream([b"upload"])))
        return contender.delete_selection([dataset.id], [], expected_revision=preview.revision)

    with ThreadPoolExecutor(max_workers=2) as executor:
        winner = executor.submit(owner.create_folder, "Taken")
        loser = None
        try:
            assert entered.wait(timeout=2)
            loser = executor.submit(competing_operation)
            assert admission.wait(timeout=2)
            assert Path(dataset.path).read_bytes() == b"keep"
        finally:
            release.set()
        winner.result(timeout=5)
        assert loser is not None
        if operation == "upload":
            record = loser.result(timeout=5)
            assert record.display_name == "Taken (2)"
            assert Path(record.path).read_bytes() == b"upload"
        else:
            with pytest.raises(NameConflictError if operation == "folder" else CatalogConflictError):
                loser.result(timeout=5)
    assert Path(dataset.path).read_bytes() == b"keep"
    assert [folder.name for folder in _make_store(tmp_path).list_folders()] == ["Taken"]


async def test_store_sanitizes_path_traversal(tmp_path: Path):
    store = _make_store(tmp_path)
    # Leading "../.." should be stripped; the resulting file must still live in root
    meta = await store.store("../../etc/passwd", _bytes_stream([b"x"]))
    assert Path(meta.path).parent == store.root


async def test_store_rejects_empty_stem(tmp_path: Path):
    store = _make_store(tmp_path)
    with pytest.raises(ValueError):
        await store.store("/", _bytes_stream([b"x"]))


async def test_store_rejects_nul_byte(tmp_path: Path):
    store = _make_store(tmp_path)
    with pytest.raises(ValueError):
        await store.store("a\x00b.tif", _bytes_stream([b"x"]))


@pytest.mark.parametrize("reserved", ["con", "prn", "nul", "aux", "com1"])
async def test_store_escapes_windows_reserved_names(tmp_path: Path, reserved: str):
    store = _make_store(tmp_path)
    meta = await store.store(reserved, _bytes_stream([b"x"]))
    filename = Path(meta.path).name
    # The stem, after the timestamp prefix, must NOT be the bare reserved name
    _, _, stem = filename.partition("_")
    assert stem.lower() != reserved.lower()


async def test_store_truncates_long_utf8_names(tmp_path: Path):
    store = _make_store(tmp_path)
    # 200 multi-byte chars -> 600 bytes, well over 255
    stem = "é" * 200
    meta = await store.store(f"{stem}.tif", _bytes_stream([b"x"]))
    name = Path(meta.path).name
    # Full filename (timestamp + underscore + stem + extension) must fit within
    # 255 bytes utf-8, and preserve the extension.
    assert len(name.encode("utf-8")) <= 255
    assert name.endswith(".tif")


async def test_store_handles_no_extension(tmp_path: Path):
    store = _make_store(tmp_path)
    meta = await store.store("README", _bytes_stream([b"x"]))
    assert meta.original_filename == "README"
    assert meta.content_type is None
    stored = Path(meta.path)
    assert stored.is_file()

    ids = [d.id for d in store.list()]
    assert meta.id in ids


async def test_store_blocks_absolute_path_escape(tmp_path: Path):
    store = _make_store(tmp_path)
    # After sanitization, an absolute path must not escape the root.
    meta = await store.store("/etc/passwd", _bytes_stream([b"x"]))
    assert Path(meta.path).parent == store.root
    # Ensure nothing was written outside root
    assert Path("/etc/passwd").read_bytes() != b"x"  # sanity, not a real risk


# ---------------------------------------------------------------------------
# collision disambiguation
# ---------------------------------------------------------------------------


async def test_store_disambiguates_colliding_names(tmp_path: Path, monkeypatch):
    store = _make_store(tmp_path)

    # Freeze the timestamp so both stores land in the same "second"
    monkeypatch.setattr(
        "bioimageflow_server.services.dataset_store._now_compact",
        lambda: "20260421T143022",
    )

    meta1 = await store.store("cells.tif", _bytes_stream([b"a"]))
    meta2 = await store.store("cells.tif", _bytes_stream([b"b"]))
    assert meta1.path != meta2.path
    names = sorted(
        p.name for p in store.root.iterdir()
        if p.is_file() and not p.name.startswith(".bioimageflow")
    )
    assert names == [
        "20260421T143022_cells.tif",
        "20260421T143022_cells_1.tif",
    ]
    # Both visible via list()
    assert len(store.list()) == 2


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------


async def test_delete_removes_file(tmp_path: Path):
    store = _make_store(tmp_path)
    meta = await store.store("cells.tif", _bytes_stream([b"x"]))
    store.delete(meta.id)
    assert not Path(meta.path).exists()
    assert store.list() == []


@pytest.mark.parametrize("unknown", ["malformed", "catalog", "unmanaged", "alias"])
async def test_delete_unknown_raises(tmp_path: Path, unknown: str):
    store = _make_store(tmp_path)
    dataset = await store.store("keep.tif", _bytes_stream([b"managed bytes"]))
    unmanaged = store.root / "notes.txt"
    unmanaged.write_bytes(b"unmanaged bytes")
    catalog = store.root / ".bioimageflow-datasets.sqlite3"
    catalog_bytes = catalog.read_bytes()
    if unknown == "malformed":
        dataset_id = "d_unknown"
    elif unknown == "alias":
        dataset_id = dataset.id + "="
    else:
        name = catalog.name if unknown == "catalog" else unmanaged.name
        dataset_id = "d_" + base64.urlsafe_b64encode(name.encode()).rstrip(b"=").decode()
    with pytest.raises(DatasetNotFoundError):
        store.delete(dataset_id)
    assert catalog.read_bytes() == catalog_bytes
    assert unmanaged.read_bytes() == b"unmanaged bytes"
    assert Path(dataset.path).read_bytes() == b"managed bytes"
    reopened = _make_store(tmp_path)
    assert [item.id for item in reopened.list()] == [dataset.id]
    reopened.delete(dataset.id)
    assert reopened.list() == []


async def test_delete_rejects_traversal_id(tmp_path: Path):
    store = _make_store(tmp_path)
    # A maliciously crafted id that decodes to an absolute path must not delete
    # anything outside the store.
    import base64

    evil = base64.urlsafe_b64encode(b"../../../etc/passwd").rstrip(b"=").decode("ascii")
    with pytest.raises(PathTraversalError):
        store.delete(f"d_{evil}")


@pytest.mark.parametrize("outside", [False, True])
async def test_delete_owns_symlink_entry_not_destination(tmp_path: Path, outside: bool):
    store = _make_store(tmp_path)
    selected = await store.store("selected.tif", _bytes_stream([b"selected bytes"]))
    sibling = await store.store("sibling.tif", _bytes_stream([b"sibling bytes"]))
    external = tmp_path / "external.tif"
    external.write_bytes(b"external bytes")
    selected_path = Path(selected.path)
    selected_path.unlink()
    selected_path.symlink_to(external if outside else Path(sibling.path))

    if outside:
        with pytest.raises(PathTraversalError):
            store.delete(selected.id)
        assert selected_path.is_symlink()
    else:
        store.delete(selected.id)
        assert not selected_path.is_symlink()
        assert [item.id for item in _make_store(tmp_path).list()] == [sibling.id]
    assert Path(sibling.path).read_bytes() == b"sibling bytes"
    assert external.read_bytes() == b"external bytes"


# ---------------------------------------------------------------------------
# id round-trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "cells.tif",
        "cells_1.tif",
        "a.b.c.tif",
        "no_extension",
        "mask_2.png",
        "sub.something_1.tif",
    ],
)
async def test_id_round_trip(tmp_path: Path, name: str):
    store = _make_store(tmp_path)
    meta = await store.store(name, _bytes_stream([b"x"]))
    [row] = store.list()
    assert row.id == meta.id
    # Delete works using the id derived from listing
    store.delete(row.id)
    assert store.list() == []


# ---------------------------------------------------------------------------
# Logical folders and catalog-backed dataset metadata
# ---------------------------------------------------------------------------


async def test_legacy_files_are_catalogued_without_moving(tmp_path: Path):
    root = tmp_path / "datasets"
    root.mkdir()
    legacy = root / "20260101T010000_cells.tif"
    legacy.write_bytes(b"cells")

    store = DatasetStore(datasets_root=root, max_upload_size=1_000_000)

    [dataset] = store.list()
    assert Path(dataset.path) == legacy
    assert dataset.display_name == "cells.tif"
    assert dataset.folder_id is None
    sibling = await store.store("keep.tif", _bytes_stream([b"keep"]))
    store.delete(dataset.id)
    assert not legacy.exists()
    assert Path(sibling.path).read_bytes() == b"keep"
    assert [item.id for item in _make_store(tmp_path).list()] == [sibling.id]


async def test_folder_rename_and_move_do_not_change_dataset_path(tmp_path: Path):
    store = _make_store(tmp_path)
    parent = store.create_folder("Experiment")
    child = store.create_folder("Controls", parent_id=parent.id)
    dataset = await store.store("cells.tif", _bytes_stream([b"x"]), folder_id=child.id)
    original_path = dataset.path

    store.update_folder(child.id, name="Renamed")
    store.update_folder(child.id, parent_id=None)
    renamed = store.update_dataset(dataset.id, display_name="Control image.tif")

    assert renamed.path == original_path
    assert renamed.display_name == "Control image.tif"
    assert renamed.folder_id == child.id


async def test_sibling_names_are_case_insensitively_unique(tmp_path: Path):
    store = _make_store(tmp_path)
    store.create_folder("Controls")

    with pytest.raises(NameConflictError):
        store.create_folder("controls")


async def test_folder_move_rejects_descendant_cycle(tmp_path: Path):
    store = _make_store(tmp_path)
    parent = store.create_folder("Parent")
    child = store.create_folder("Child", parent_id=parent.id)

    with pytest.raises(InvalidMoveError):
        store.update_folder(parent.id, parent_id=child.id)


async def test_resolve_selection_recurses_and_deduplicates(tmp_path: Path):
    store = _make_store(tmp_path)
    parent = store.create_folder("Experiment")
    child = store.create_folder("Controls", parent_id=parent.id)
    first = await store.store("b.tif", _bytes_stream([b"b"]), folder_id=parent.id)
    second = await store.store("a.tif", _bytes_stream([b"a"]), folder_id=child.id)

    resolved = store.resolve_selection([second.id], [parent.id])

    assert [item.id for item in resolved] == [first.id, second.id]


async def test_recursive_delete_requires_current_preview_revision(tmp_path: Path):
    store = _make_store(tmp_path)
    folder = store.create_folder("Experiment")
    dataset = await store.store("a.tif", _bytes_stream([b"a"]), folder_id=folder.id)
    preview = store.preview_delete([], [folder.id])
    store.create_folder("Other")

    with pytest.raises(CatalogConflictError):
        store.delete_selection([], [folder.id], expected_revision=preview.revision)

    fresh = store.preview_delete([], [folder.id])
    result = store.delete_selection([], [folder.id], expected_revision=fresh.revision)
    assert result.deleted_dataset_ids == [dataset.id]
    assert result.deleted_folder_ids == [folder.id]


async def test_recursive_delete_commits_successes_and_preserves_failed_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    store = _make_store(tmp_path)
    folder = store.create_folder("Experiment")
    good, escaped, denied = [
        await store.store(name, _bytes_stream([name.encode()]), folder_id=folder.id)
        for name in ["good.tif", "escaped.tif", "denied.tif"]
    ]
    outside = tmp_path / "outside.tif"
    outside.write_bytes(b"outside")
    escaped_path = Path(escaped.path)
    escaped_path.unlink()
    escaped_path.symlink_to(outside)
    unlink = Path.unlink

    def fail_selected(path, *args, **kwargs):
        if path == Path(denied.path):
            raise OSError("selected deletion denied")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_selected)
    preview = store.preview_delete([], [folder.id])
    result = store.delete_selection([], [folder.id], expected_revision=preview.revision)
    assert result.deleted_dataset_ids == [good.id]
    assert result.deleted_folder_ids == []
    assert {error["id"] for error in result.errors} == {escaped.id, denied.id}
    assert not Path(good.path).exists()
    assert escaped_path.is_symlink()
    assert outside.read_bytes() == b"outside"
    assert Path(denied.path).read_bytes() == b"denied.tif"
    assert store.preview_delete([], [folder.id]).dataset_count == 2
    with pytest.raises(DatasetNotFoundError):
        store.preview_delete([good.id], [])
    escaped_path.unlink()
    escaped_path.write_bytes(b"escaped.tif")
    reopened = _make_store(tmp_path)
    assert {record.id for record in reopened.list()} == {escaped.id, denied.id}
    assert [item.id for item in reopened.list_folders()] == [folder.id]
