"""Tests for portable filesystem durability helpers."""

from pathlib import Path
from unittest.mock import MagicMock


def test_fsync_file_uses_platform_descriptor_flags(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from bioimageflow_server.services import filesystem_durability

    path = tmp_path / "state.json"
    mock_open = MagicMock(return_value=42)
    mock_fsync = MagicMock()
    mock_close = MagicMock()
    monkeypatch.setattr(filesystem_durability.os, "open", mock_open)
    monkeypatch.setattr(filesystem_durability.os, "fsync", mock_fsync)
    monkeypatch.setattr(filesystem_durability.os, "close", mock_close)

    filesystem_durability.fsync_file(path)

    mock_open.assert_called_once_with(path, filesystem_durability._FILE_FSYNC_FLAGS)
    mock_fsync.assert_called_once_with(42)
    mock_close.assert_called_once_with(42)


def test_fsync_directory_is_noop_when_platform_cannot_open_directories(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from bioimageflow_server.services import filesystem_durability

    mock_open = MagicMock()
    monkeypatch.setattr(filesystem_durability, "_CAN_FSYNC_DIRECTORIES", False)
    monkeypatch.setattr(filesystem_durability.os, "open", mock_open)

    filesystem_durability.fsync_directory(tmp_path)

    mock_open.assert_not_called()


def test_fsync_directory_flushes_and_closes_supported_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from bioimageflow_server.services import filesystem_durability

    monkeypatch.setattr(filesystem_durability, "_CAN_FSYNC_DIRECTORIES", True)
    mock_open = MagicMock(return_value=42)
    mock_fsync = MagicMock()
    mock_close = MagicMock()
    monkeypatch.setattr(filesystem_durability.os, "open", mock_open)
    monkeypatch.setattr(filesystem_durability.os, "fsync", mock_fsync)
    monkeypatch.setattr(filesystem_durability.os, "close", mock_close)

    filesystem_durability.fsync_directory(tmp_path)

    mock_open.assert_called_once_with(tmp_path, filesystem_durability.os.O_RDONLY)
    mock_fsync.assert_called_once_with(42)
    mock_close.assert_called_once_with(42)


def test_fsync_directory_closes_descriptor_when_flush_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pytest

    from bioimageflow_server.services import filesystem_durability

    monkeypatch.setattr(filesystem_durability, "_CAN_FSYNC_DIRECTORIES", True)
    monkeypatch.setattr(filesystem_durability.os, "open", MagicMock(return_value=42))
    monkeypatch.setattr(
        filesystem_durability.os,
        "fsync",
        MagicMock(side_effect=OSError("flush failed")),
    )
    mock_close = MagicMock()
    monkeypatch.setattr(filesystem_durability.os, "close", mock_close)

    with pytest.raises(OSError, match="flush failed"):
        filesystem_durability.fsync_directory(tmp_path)

    mock_close.assert_called_once_with(42)
