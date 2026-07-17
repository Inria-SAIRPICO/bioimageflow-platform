"""Tests for the DatasetStore service (Task 2)."""

from __future__ import annotations

from collections.abc import AsyncIterable
from pathlib import Path

import pytest

from bioimageflow_server.services.dataset_store import (
    CatalogConflictError,
    DatasetNotFoundError,
    DatasetStore,
    FileTooLargeError,
    InvalidMoveError,
    NameConflictError,
    PathTraversalError,
)


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


async def test_store_rejects_oversize(tmp_path: Path):
    store = _make_store(tmp_path, cap=4)
    with pytest.raises(FileTooLargeError):
        await store.store("big.bin", _bytes_stream([b"12", b"345"]))
    # No partial file left behind
    assert not any(path.is_file() and not path.name.startswith(".bioimageflow") for path in store.root.iterdir())


async def test_store_cleans_up_on_error(tmp_path: Path):
    store = _make_store(tmp_path, cap=10)

    async def exploding() -> AsyncIterable[bytes]:
        yield b"ab"
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await store.store("boom.bin", exploding())
    assert not any(path.is_file() and not path.name.startswith(".bioimageflow") for path in store.root.iterdir())


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


async def test_delete_unknown_raises(tmp_path: Path):
    store = _make_store(tmp_path)
    with pytest.raises(DatasetNotFoundError):
        store.delete("d_unknown")


async def test_delete_rejects_traversal_id(tmp_path: Path):
    store = _make_store(tmp_path)
    # A maliciously crafted id that decodes to an absolute path must not delete
    # anything outside the store.
    import base64

    evil = base64.urlsafe_b64encode(b"../../../etc/passwd").rstrip(b"=").decode("ascii")
    with pytest.raises((PathTraversalError, DatasetNotFoundError)):
        store.delete(f"d_{evil}")


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
