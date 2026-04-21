"""Server-side dataset storage service (v1 §2.4.10).

Owns filesystem I/O for the Dataset Browser. Enforces:

- Filename sanitization (path separators, NUL bytes, Windows reserved names,
  empty stems, UTF-8 byte-length truncation preserving extension).
- Path traversal defence (resolve-then-check against the configured root).
- Streaming writes with atomic target reservation (O_WRONLY | O_CREAT | O_EXCL)
  that clean up on overflow or error.
- Per-upload size cap (the cap is a store-level invariant, not a per-call arg).
- Collision disambiguation (`_N` suffix on the stem while preserving the
  timestamp prefix format).
- Round-trippable dataset ids (`d_<urlsafe_b64(stored_filename, no padding)>`).
"""

from __future__ import annotations

import base64
import mimetypes
import os
import re
from collections.abc import AsyncIterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


# Maximum number of bytes in a POSIX filename on common filesystems (ext4, APFS,
# NTFS with longpath). Truncation operates on the UTF-8 byte length, not char
# count, so that multi-byte stems don't blow past the limit.
_MAX_FILENAME_BYTES = 255

# YYYYMMDDTHHMMSS_<stem>.<ext>
_STORED_NAME_RE = re.compile(r"^(\d{8}T\d{6})_(.+)$")

# Windows reserved names (case-insensitive, matched on the stem without
# extension). Any match is suffixed with `_` so the file can safely live on a
# Windows filesystem — we target cross-platform portability.
_WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *{f"com{i}" for i in range(1, 10)},
    *{f"lpt{i}" for i in range(1, 10)},
}


class DatasetStoreError(Exception):
    """Base class for dataset store errors."""


class FileTooLargeError(DatasetStoreError):
    """Raised when a streaming upload exceeds the configured cap."""


class DatasetNotFoundError(DatasetStoreError):
    """Raised when a `dataset_id` does not map to a stored file."""


class PathTraversalError(DatasetStoreError):
    """Raised when a resolved path would escape `datasets_root`."""


# ---------------------------------------------------------------------------
# Public record types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StoredDataset:
    id: str
    original_filename: str
    path: str  # absolute path on the server
    size: int
    upload_date: str  # ISO 8601 derived from the filename's timestamp prefix
    content_type: str | None


# ---------------------------------------------------------------------------
# Module-level helpers (overridable in tests)
# ---------------------------------------------------------------------------


def _now_compact() -> str:
    """Return the current UTC timestamp as `YYYYMMDDTHHMMSS`."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _encode_id(stored_name: str) -> str:
    raw = stored_name.encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    return f"d_{b64}"


def _decode_id(dataset_id: str) -> str:
    if not dataset_id.startswith("d_"):
        raise DatasetNotFoundError(dataset_id)
    b64 = dataset_id[2:]
    padding = "=" * (-len(b64) % 4)
    try:
        raw = base64.urlsafe_b64decode(b64 + padding)
    except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
        raise DatasetNotFoundError(dataset_id) from exc
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DatasetNotFoundError(dataset_id) from exc


def _sanitize_filename(original: str) -> str:
    """Strip path separators, NUL bytes, and Windows reserved names.

    Raises `ValueError` if the result is empty.
    """
    if "\x00" in original:
        raise ValueError("filename contains NUL byte")

    # Strip any directory components. We use both os.path separators and a
    # literal backslash to handle Windows-style paths that arrive via Content-
    # Disposition headers from Windows clients.
    name = os.path.basename(original.replace("\\", "/"))
    if not name or name in (".", ".."):
        raise ValueError(f"invalid filename: {original!r}")

    stem, dot, ext = name.rpartition(".")
    if not dot:
        # No extension
        stem, ext = name, ""

    if stem.lower() in _WINDOWS_RESERVED:
        stem = f"_{stem}"

    # Truncate by utf-8 bytes while preserving the extension. We leave headroom
    # for the timestamp prefix (16 bytes) and any collision disambiguator
    # (~6 bytes) so the final filename fits in _MAX_FILENAME_BYTES.
    headroom = 16 + 8
    ext_bytes = (f".{ext}" if ext else "").encode("utf-8")
    budget = _MAX_FILENAME_BYTES - headroom - len(ext_bytes)
    stem_bytes = stem.encode("utf-8")
    if len(stem_bytes) > budget:
        truncated = stem_bytes[:budget]
        # Walk back to a utf-8 boundary
        while truncated and (truncated[-1] & 0xC0) == 0x80:
            truncated = truncated[:-1]
        stem = truncated.decode("utf-8", errors="ignore")
        if not stem:
            raise ValueError(f"filename truncation left empty stem: {original!r}")

    return f"{stem}.{ext}" if ext else stem


def _split_stored_name(stored_name: str) -> tuple[str, str]:
    """Return (timestamp, sanitized_filename)."""
    m = _STORED_NAME_RE.match(stored_name)
    if not m:
        raise ValueError(f"unrecognised stored name: {stored_name!r}")
    return m.group(1), m.group(2)


def _original_from_sanitized(sanitized: str) -> str:
    """Recover the 'original' filename after stripping a collision suffix.

    `cells_3.tif` -> `cells.tif`; `cells.tif` -> `cells.tif`; `README_1` ->
    `README`. The sanitized name is what the user sees in the list — we want
    collision disambiguators to be invisible.
    """
    stem, dot, ext = sanitized.rpartition(".")
    if not dot:
        stem, ext = sanitized, ""
    m = re.match(r"^(.*?)_(\d+)$", stem)
    if m:
        stem = m.group(1)
    return f"{stem}.{ext}" if ext else stem


def _timestamp_to_iso(compact: str) -> str:
    """`20260421T143022` -> `2026-04-21T14:30:22Z`."""
    return (
        f"{compact[0:4]}-{compact[4:6]}-{compact[6:8]}T"
        f"{compact[9:11]}:{compact[11:13]}:{compact[13:15]}Z"
    )


# ---------------------------------------------------------------------------
# DatasetStore
# ---------------------------------------------------------------------------


class DatasetStore:
    """Filesystem-backed dataset store.

    Constructed with a root and a per-upload size cap. The cap is a store-level
    invariant so callers don't need to thread it through per request.
    """

    def __init__(self, datasets_root: Path, max_upload_size: int):
        self.root: Path = Path(datasets_root)
        self.max_upload_size: int = max_upload_size
        self.root.mkdir(parents=True, exist_ok=True)
        self._resolved_root = self.root.resolve()

    # ------------------------------------------------------------------ list

    def list(self) -> list[StoredDataset]:
        if not self.root.is_dir():
            return []
        out: list[StoredDataset] = []
        for p in self.root.iterdir():
            if not p.is_file():
                continue
            try:
                timestamp, sanitized = _split_stored_name(p.name)
            except ValueError:
                continue  # not something we stored
            original = _original_from_sanitized(sanitized)
            out.append(
                StoredDataset(
                    id=_encode_id(p.name),
                    original_filename=original,
                    path=str(p.resolve()),
                    size=p.stat().st_size,
                    upload_date=_timestamp_to_iso(timestamp),
                    content_type=mimetypes.guess_type(original, strict=False)[0],
                )
            )
        # Newest first, by the timestamp prefix (not mtime — restores preserve
        # the upload date).
        out.sort(key=lambda d: d.upload_date, reverse=True)
        return out

    # ----------------------------------------------------------------- store

    async def store(
        self, filename: str, stream: AsyncIterable[bytes]
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
                    raise FileTooLargeError(
                        f"upload exceeded cap of {self.max_upload_size} bytes"
                    )
                os.write(fd, chunk)
        except BaseException:
            os.close(fd)
            try:
                target_path.unlink()
            except FileNotFoundError:
                pass
            raise
        else:
            os.close(fd)

        stored_name = target_path.name
        original = _original_from_sanitized(sanitized)
        return StoredDataset(
            id=_encode_id(stored_name),
            original_filename=original,
            path=str(target_path.resolve()),
            size=written,
            upload_date=_timestamp_to_iso(timestamp),
            content_type=mimetypes.guess_type(original, strict=False)[0],
        )

    def _reserve_target(self, timestamp: str, sanitized: str) -> Path:
        """Compute the target path, disambiguating collisions via `_N`.

        Resolve-then-check gate runs before any write: the resolved path must
        be relative to the resolved root. This is atomic with O_EXCL in store().
        """
        stem, dot, ext = sanitized.rpartition(".")
        if not dot:
            stem, ext = sanitized, ""

        n = 0
        while True:
            suffix = "" if n == 0 else f"_{n}"
            candidate_stem = f"{stem}{suffix}"
            candidate_name = f"{candidate_stem}.{ext}" if ext else candidate_stem
            stored_name = f"{timestamp}_{candidate_name}"
            target = self.root / stored_name
            resolved = target.resolve()
            if not self._is_within_root(resolved):
                raise PathTraversalError(candidate_name)
            if not target.exists():
                return target
            n += 1
            if n > 10_000:  # pragma: no cover — paranoia
                raise RuntimeError("too many collisions disambiguating")

    def _is_within_root(self, resolved: Path) -> bool:
        try:
            resolved.relative_to(self._resolved_root)
        except ValueError:
            return False
        return True

    # ---------------------------------------------------------------- delete

    def delete(self, dataset_id: str) -> None:
        stored_name = _decode_id(dataset_id)
        target = self.root / stored_name
        resolved = target.resolve()
        if not self._is_within_root(resolved):
            raise PathTraversalError(dataset_id)
        if not target.exists():
            raise DatasetNotFoundError(dataset_id)
        target.unlink()
