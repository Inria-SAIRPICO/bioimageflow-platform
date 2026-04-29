"""Tests for ThumbnailService."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from bioimageflow_server.services.thumbnail import ThumbnailService


def _png_size(data: bytes) -> tuple[int, int]:
    return Image.open(BytesIO(data)).size


def test_get_thumbnail_returns_png_for_png(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (64, 32), "red").save(source)
    data = ThumbnailService(tmp_path / "thumbs").get_thumbnail(source, size=32)
    assert data.startswith(b"\x89PNG")
    assert _png_size(data) == (32, 32)


def test_get_thumbnail_returns_png_for_jpeg(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    Image.new("RGB", (64, 32), "blue").save(source)
    data = ThumbnailService(tmp_path / "thumbs").get_thumbnail(source, size=48)
    assert data.startswith(b"\x89PNG")
    assert _png_size(data) == (48, 48)


def test_get_thumbnail_cache_hit(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (16, 16), "green").save(source)
    service = ThumbnailService(tmp_path / "thumbs")
    first = service.get_thumbnail(source, size=32)
    source.unlink()
    second = service.get_thumbnail(source, size=32)
    assert second != first


def test_missing_or_unsupported_file_returns_placeholder(tmp_path: Path) -> None:
    service = ThumbnailService(tmp_path / "thumbs")
    missing = service.get_thumbnail(tmp_path / "missing.png", size=32)
    unsupported = service.get_thumbnail(tmp_path / "volume.nii", size=32)
    assert missing.startswith(b"\x89PNG")
    assert unsupported.startswith(b"\x89PNG")
