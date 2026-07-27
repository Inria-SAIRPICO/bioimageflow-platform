"""Portable filesystem durability helpers."""

from __future__ import annotations

import os
from pathlib import Path


# Python's Windows file APIs cannot open directory handles with ``os.open``.
# POSIX platforms support the open + fsync sequence used to persist directory
# entries after an atomic replace.
_CAN_FSYNC_DIRECTORIES = os.name != "nt"
_FILE_FSYNC_FLAGS = os.O_RDWR if os.name == "nt" else os.O_RDONLY


def fsync_file(path: Path) -> None:
    """Flush an existing file through a descriptor valid on this platform."""

    # Windows rejects fsync on a read-only CRT descriptor with EBADF. Opening
    # the application-owned persistence file read/write gives FlushFileBuffers
    # the access it requires without modifying the file.
    descriptor = os.open(path, _FILE_FSYNC_FLAGS)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def fsync_directory(path: Path) -> None:
    """Flush directory entries where the operating system supports it.

    File contents are flushed separately before this helper is called.
    Windows has no portable Python equivalent for POSIX directory ``fsync``;
    attempting ``os.open`` on the directory raises ``PermissionError``.
    """

    if not _CAN_FSYNC_DIRECTORIES:
        return

    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
