"""Filesystem-backed dataset storage with a logical SQLite catalog."""

from __future__ import annotations

import base64
import mimetypes
import os
import re
import sqlite3
import uuid
from collections.abc import AsyncIterable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

_MAX_FILENAME_BYTES = 255
_STORED_NAME_RE = re.compile(r"^(\d{8}T\d{6})_(.+)$")
_CATALOG_NAME = ".bioimageflow-datasets.sqlite3"
_UNSET = object()
_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *{f"com{i}" for i in range(1, 10)},
    *{f"lpt{i}" for i in range(1, 10)},
}


class DatasetStoreError(Exception):
    """Base class for dataset-store errors."""


class FileTooLargeError(DatasetStoreError):
    pass


class DatasetNotFoundError(DatasetStoreError):
    pass


class FolderNotFoundError(DatasetStoreError):
    pass


class PathTraversalError(DatasetStoreError):
    pass


class NameConflictError(DatasetStoreError):
    pass


class InvalidMoveError(DatasetStoreError):
    pass


class CatalogConflictError(DatasetStoreError):
    pass


@dataclass(frozen=True)
class StoredDataset:
    id: str
    original_filename: str
    display_name: str
    path: str
    size: int
    upload_date: str
    content_type: str | None
    folder_id: str | None = None


@dataclass(frozen=True)
class StoredFolder:
    id: str
    name: str
    parent_id: str | None
    created_at: str


@dataclass(frozen=True)
class DeletePreview:
    revision: int
    dataset_count: int
    folder_count: int


@dataclass(frozen=True)
class DeleteResult:
    deleted_dataset_ids: list[str]
    deleted_folder_ids: list[str]
    errors: list[dict[str, str]]


def _now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _encode_id(stored_name: str) -> str:
    encoded = base64.urlsafe_b64encode(stored_name.encode()).rstrip(b"=").decode()
    return f"d_{encoded}"


def _decode_id(dataset_id: str) -> str:
    if not dataset_id.startswith("d_"):
        raise DatasetNotFoundError(dataset_id)
    encoded = dataset_id[2:]
    try:
        return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    except (ValueError, UnicodeDecodeError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
        raise DatasetNotFoundError(dataset_id) from exc


def _sanitize_filename(original: str) -> str:
    if "\x00" in original:
        raise ValueError("filename contains NUL byte")
    name = os.path.basename(original.replace("\\", "/"))
    if not name or name in (".", ".."):
        raise ValueError(f"invalid filename: {original!r}")
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    if stem.lower() in _WINDOWS_RESERVED:
        stem = f"_{stem}"
    ext_bytes = (f".{ext}" if ext else "").encode()
    budget = _MAX_FILENAME_BYTES - 24 - len(ext_bytes)
    stem_bytes = stem.encode()
    if len(stem_bytes) > budget:
        truncated = stem_bytes[:budget]
        while truncated and (truncated[-1] & 0xC0) == 0x80:
            truncated = truncated[:-1]
        stem = truncated.decode(errors="ignore")
        if not stem:
            raise ValueError(f"filename truncation left empty stem: {original!r}")
    return f"{stem}.{ext}" if ext else stem


def _split_stored_name(stored_name: str) -> tuple[str, str]:
    match = _STORED_NAME_RE.match(stored_name)
    if not match:
        raise ValueError(f"unrecognised stored name: {stored_name!r}")
    return match.group(1), match.group(2)


def _original_from_sanitized(sanitized: str) -> str:
    stem, dot, ext = sanitized.rpartition(".")
    if not dot:
        stem, ext = sanitized, ""
    match = re.match(r"^(.*?)_(\d+)$", stem)
    if match:
        stem = match.group(1)
    return f"{stem}.{ext}" if ext else stem


def _timestamp_to_iso(compact: str) -> str:
    return (
        f"{compact[0:4]}-{compact[4:6]}-{compact[6:8]}T"
        f"{compact[9:11]}:{compact[11:13]}:{compact[13:15]}Z"
    )


def _normal_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or cleaned in (".", "..") or any(c in cleaned for c in ("/", "\\", "\x00")):
        raise ValueError("invalid dataset entry name")
    return cleaned.casefold()


class DatasetStore:
    def __init__(self, datasets_root: Path, max_upload_size: int):
        self.root = Path(datasets_root)
        self.max_upload_size = max_upload_size
        self.root.mkdir(parents=True, exist_ok=True)
        self._resolved_root = self.root.resolve()
        self._catalog_path = self.root / _CATALOG_NAME
        self._initialize_catalog()
        self._reconcile()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._catalog_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_catalog(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                );
                INSERT OR IGNORE INTO metadata(key, value) VALUES ('revision', 0);
                CREATE TABLE IF NOT EXISTS folders (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    parent_id TEXT REFERENCES folders(id),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS datasets (
                    id TEXT PRIMARY KEY,
                    stored_name TEXT NOT NULL UNIQUE,
                    original_filename TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    folder_id TEXT REFERENCES folders(id),
                    size INTEGER NOT NULL,
                    upload_date TEXT NOT NULL,
                    content_type TEXT
                );
                """
            )

    def _revision(self, connection: sqlite3.Connection) -> int:
        return int(connection.execute(
            "SELECT value FROM metadata WHERE key = 'revision'"
        ).fetchone()[0])

    def _bump_revision(self, connection: sqlite3.Connection) -> None:
        connection.execute("UPDATE metadata SET value = value + 1 WHERE key = 'revision'")

    def _reconcile(self) -> None:
        with self._connect() as connection:
            changed = False
            known = {row[0]: row[1] for row in connection.execute("SELECT stored_name, id FROM datasets")}
            for path in self.root.iterdir():
                if not path.is_file() or path.name == _CATALOG_NAME or path.name.endswith(("-wal", "-shm")):
                    continue
                try:
                    timestamp, sanitized = _split_stored_name(path.name)
                except ValueError:
                    continue
                if path.name in known:
                    continue
                original = _original_from_sanitized(sanitized)
                display = self._unique_display_name(connection, original, None)
                connection.execute(
                    """INSERT INTO datasets VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?)""",
                    (
                        _encode_id(path.name), path.name, original, display,
                        display.casefold(), path.stat().st_size,
                        _timestamp_to_iso(timestamp), mimetypes.guess_type(original, strict=False)[0],
                    ),
                )
                changed = True
            for stored_name, dataset_id in known.items():
                if not (self.root / stored_name).is_file():
                    connection.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
                    changed = True
            if changed:
                self._bump_revision(connection)

    def _ensure_folder(self, connection: sqlite3.Connection, folder_id: str | None) -> None:
        if folder_id is None:
            return
        if connection.execute("SELECT 1 FROM folders WHERE id = ?", (folder_id,)).fetchone() is None:
            raise FolderNotFoundError(folder_id)

    def _name_taken(
        self,
        connection: sqlite3.Connection,
        normalized: str,
        parent_id: str | None,
        *,
        excluding_id: str | None = None,
    ) -> bool:
        params: tuple[Any, ...] = (normalized, parent_id, excluding_id or "")
        folder = connection.execute(
            "SELECT 1 FROM folders WHERE normalized_name = ? AND parent_id IS ? AND id != ?",
            params,
        ).fetchone()
        dataset = connection.execute(
            "SELECT 1 FROM datasets WHERE normalized_name = ? AND folder_id IS ? AND id != ?",
            params,
        ).fetchone()
        return folder is not None or dataset is not None

    def _unique_display_name(
        self, connection: sqlite3.Connection, desired: str, folder_id: str | None
    ) -> str:
        desired = desired.strip()
        if not self._name_taken(connection, _normal_name(desired), folder_id):
            return desired
        stem, dot, ext = desired.rpartition(".")
        if not dot:
            stem, ext = desired, ""
        counter = 2
        while True:
            candidate = f"{stem} ({counter}){'.' + ext if ext else ''}"
            if not self._name_taken(connection, candidate.casefold(), folder_id):
                return candidate
            counter += 1

    def _dataset_from_row(self, row: sqlite3.Row) -> StoredDataset:
        path = (self.root / row["stored_name"]).resolve()
        if not self._is_within_root(path):
            raise PathTraversalError(row["id"])
        return StoredDataset(
            id=row["id"], original_filename=row["original_filename"],
            display_name=row["display_name"], path=str(path), size=row["size"],
            upload_date=row["upload_date"], content_type=row["content_type"],
            folder_id=row["folder_id"],
        )

    def list(self) -> list[StoredDataset]:
        if not self.root.is_dir():
            return []
        self._reconcile()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM datasets ORDER BY upload_date DESC, id"
            ).fetchall()
            return [self._dataset_from_row(row) for row in rows]

    def list_folders(self) -> list[StoredFolder]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM folders ORDER BY normalized_name, id"
            ).fetchall()
            return [StoredFolder(row["id"], row["name"], row["parent_id"], row["created_at"]) for row in rows]

    async def store(
        self,
        filename: str,
        stream: AsyncIterable[bytes],
        *,
        folder_id: str | None = None,
    ) -> StoredDataset:
        sanitized = _sanitize_filename(filename)
        timestamp = _now_compact()
        target_path = self._reserve_target(timestamp, sanitized)
        written = 0
        fd = os.open(str(target_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            async for chunk in stream:
                if not chunk:
                    continue
                written += len(chunk)
                if written > self.max_upload_size:
                    raise FileTooLargeError(f"upload exceeded cap of {self.max_upload_size} bytes")
                os.write(fd, chunk)
        except BaseException:
            os.close(fd)
            target_path.unlink(missing_ok=True)
            raise
        else:
            os.close(fd)

        original = _original_from_sanitized(sanitized)
        try:
            with self._connect() as connection:
                self._ensure_folder(connection, folder_id)
                display = self._unique_display_name(connection, original, folder_id)
                connection.execute(
                    "INSERT INTO datasets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        _encode_id(target_path.name), target_path.name, original, display,
                        display.casefold(), folder_id, written, _timestamp_to_iso(timestamp),
                        mimetypes.guess_type(original, strict=False)[0],
                    ),
                )
                self._bump_revision(connection)
                row = connection.execute(
                    "SELECT * FROM datasets WHERE stored_name = ?", (target_path.name,)
                ).fetchone()
        except BaseException:
            target_path.unlink(missing_ok=True)
            raise
        return self._dataset_from_row(row)

    def create_folder(self, name: str, parent_id: str | None = None) -> StoredFolder:
        cleaned = name.strip()
        normalized = _normal_name(cleaned)
        with self._connect() as connection:
            self._ensure_folder(connection, parent_id)
            if self._name_taken(connection, normalized, parent_id):
                raise NameConflictError(cleaned)
            folder = StoredFolder(f"f_{uuid.uuid4().hex}", cleaned, parent_id, _now_iso())
            connection.execute(
                "INSERT INTO folders VALUES (?, ?, ?, ?, ?)",
                (folder.id, folder.name, normalized, folder.parent_id, folder.created_at),
            )
            self._bump_revision(connection)
            return folder

    def update_folder(
        self,
        folder_id: str,
        *,
        name: str | None = None,
        parent_id: str | None | object = _UNSET,
    ) -> StoredFolder:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM folders WHERE id = ?", (folder_id,)).fetchone()
            if row is None:
                raise FolderNotFoundError(folder_id)
            next_parent = cast(str | None, row["parent_id"] if parent_id is _UNSET else parent_id)
            self._ensure_folder(connection, next_parent)
            if next_parent == folder_id or next_parent in self._folder_descendants(connection, folder_id):
                raise InvalidMoveError(folder_id)
            next_name = row["name"] if name is None else name.strip()
            normalized = _normal_name(next_name)
            if self._name_taken(connection, normalized, next_parent, excluding_id=folder_id):
                raise NameConflictError(next_name)
            connection.execute(
                "UPDATE folders SET name = ?, normalized_name = ?, parent_id = ? WHERE id = ?",
                (next_name, normalized, next_parent, folder_id),
            )
            self._bump_revision(connection)
            return StoredFolder(folder_id, next_name, next_parent, row["created_at"])

    def update_dataset(
        self,
        dataset_id: str,
        *,
        display_name: str | None = None,
        folder_id: str | None | object = _UNSET,
    ) -> StoredDataset:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
            if row is None:
                raise DatasetNotFoundError(dataset_id)
            next_folder = cast(str | None, row["folder_id"] if folder_id is _UNSET else folder_id)
            self._ensure_folder(connection, next_folder)
            next_name = row["display_name"] if display_name is None else display_name.strip()
            normalized = _normal_name(next_name)
            if self._name_taken(connection, normalized, next_folder, excluding_id=dataset_id):
                raise NameConflictError(next_name)
            connection.execute(
                "UPDATE datasets SET display_name = ?, normalized_name = ?, folder_id = ? WHERE id = ?",
                (next_name, normalized, next_folder, dataset_id),
            )
            self._bump_revision(connection)
            return self._dataset_from_row(connection.execute(
                "SELECT * FROM datasets WHERE id = ?", (dataset_id,)
            ).fetchone())

    def _folder_descendants(self, connection: sqlite3.Connection, folder_id: str) -> set[str]:
        rows = connection.execute(
            """WITH RECURSIVE tree(id) AS (
                   SELECT id FROM folders WHERE parent_id = ?
                   UNION ALL SELECT folders.id FROM folders JOIN tree ON folders.parent_id = tree.id
               ) SELECT id FROM tree""",
            (folder_id,),
        ).fetchall()
        return {row[0] for row in rows}

    def _selection_ids(
        self,
        connection: sqlite3.Connection,
        dataset_ids: Iterable[str],
        folder_ids: Iterable[str],
    ) -> tuple[set[str], set[str]]:
        selected_folders: set[str] = set()
        for folder_id in folder_ids:
            self._ensure_folder(connection, folder_id)
            selected_folders.add(folder_id)
            selected_folders.update(self._folder_descendants(connection, folder_id))
        selected_datasets = set(dataset_ids)
        for dataset_id in selected_datasets:
            if connection.execute("SELECT 1 FROM datasets WHERE id = ?", (dataset_id,)).fetchone() is None:
                raise DatasetNotFoundError(dataset_id)
        if selected_folders:
            placeholders = ",".join("?" for _ in selected_folders)
            selected_datasets.update(row[0] for row in connection.execute(
                f"SELECT id FROM datasets WHERE folder_id IN ({placeholders})",
                tuple(selected_folders),
            ))
        return selected_datasets, selected_folders

    def _folder_path(self, folders: dict[str, tuple[str, str | None]], folder_id: str | None) -> str:
        parts: list[str] = []
        seen: set[str] = set()
        while folder_id is not None and folder_id not in seen:
            seen.add(folder_id)
            name, folder_id = folders[folder_id]
            parts.append(name)
        return "/".join(reversed(parts)).casefold()

    def resolve_selection(
        self, dataset_ids: Iterable[str], folder_ids: Iterable[str]
    ) -> list[StoredDataset]:
        with self._connect() as connection:
            selected, _ = self._selection_ids(connection, dataset_ids, folder_ids)
            if not selected:
                return []
            placeholders = ",".join("?" for _ in selected)
            rows = connection.execute(
                f"SELECT * FROM datasets WHERE id IN ({placeholders})", tuple(selected)
            ).fetchall()
            folders = {row["id"]: (row["name"], row["parent_id"]) for row in connection.execute("SELECT * FROM folders")}
            rows.sort(key=lambda row: (
                self._folder_path(folders, row["folder_id"]),
                row["display_name"].casefold(), row["id"],
            ))
            return [self._dataset_from_row(row) for row in rows]

    def preview_delete(
        self, dataset_ids: Iterable[str], folder_ids: Iterable[str]
    ) -> DeletePreview:
        with self._connect() as connection:
            datasets, folders = self._selection_ids(connection, dataset_ids, folder_ids)
            return DeletePreview(self._revision(connection), len(datasets), len(folders))

    def delete_selection(
        self,
        dataset_ids: Iterable[str],
        folder_ids: Iterable[str],
        *,
        expected_revision: int,
    ) -> DeleteResult:
        with self._connect() as connection:
            if self._revision(connection) != expected_revision:
                raise CatalogConflictError("dataset catalog changed")
            datasets, folders = self._selection_ids(connection, dataset_ids, folder_ids)
            deleted_datasets: list[str] = []
            errors: list[dict[str, str]] = []
            for dataset_id in sorted(datasets):
                row = connection.execute("SELECT stored_name FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
                target = (self.root / row[0]).resolve()
                try:
                    if not self._is_within_root(target):
                        raise PathTraversalError(dataset_id)
                    target.unlink()
                except OSError as exc:
                    errors.append({"id": dataset_id, "detail": str(exc)})
                else:
                    connection.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
                    deleted_datasets.append(dataset_id)
            deleted_folders: list[str] = []
            for folder_id in sorted(folders, key=lambda item: len(self._folder_descendants(connection, item))):
                remaining = connection.execute(
                    "SELECT 1 FROM datasets WHERE folder_id = ? UNION SELECT 1 FROM folders WHERE parent_id = ? LIMIT 1",
                    (folder_id, folder_id),
                ).fetchone()
                if remaining is None:
                    connection.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
                    deleted_folders.append(folder_id)
            if deleted_datasets or deleted_folders:
                self._bump_revision(connection)
            return DeleteResult(deleted_datasets, deleted_folders, errors)

    def delete(self, dataset_id: str) -> None:
        stored_name = _decode_id(dataset_id)
        target = (self.root / stored_name).resolve()
        if not self._is_within_root(target):
            raise PathTraversalError(dataset_id)
        if not target.exists():
            raise DatasetNotFoundError(dataset_id)
        target.unlink()
        with self._connect() as connection:
            connection.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
            self._bump_revision(connection)

    def _reserve_target(self, timestamp: str, sanitized: str) -> Path:
        stem, dot, ext = sanitized.rpartition(".")
        if not dot:
            stem, ext = sanitized, ""
        for counter in range(10_001):
            suffix = "" if counter == 0 else f"_{counter}"
            candidate = f"{stem}{suffix}{'.' + ext if ext else ''}"
            target = self.root / f"{timestamp}_{candidate}"
            if not self._is_within_root(target.resolve()):
                raise PathTraversalError(candidate)
            if not target.exists():
                return target
        raise RuntimeError("too many collisions disambiguating")

    def _is_within_root(self, resolved: Path) -> bool:
        try:
            resolved.relative_to(self._resolved_root)
        except ValueError:
            return False
        return True
