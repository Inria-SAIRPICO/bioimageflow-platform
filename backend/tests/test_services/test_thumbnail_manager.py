"""Tests for ThumbnailManager (manager-side thumbnail service).

The manager side does NOT need bioio — that lives in the Wetlands env.
Tests here focus on:
  * cache key derivation (must follow platform_specs_v1 §2.6:
    SHA256(file_path + mtime) — extended with size for distinct sizes)
  * cached retrieval (returns existing PNG bytes)
  * placeholder generation when the source file is missing/unsupported
  * lazy Wetlands launch + queue dispatch (T3)
  * bounded-wait get_or_queue (T4)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bioimageflow_server.services.thumbnail_manager import ThumbnailManager


# ---------------------------------------------------------------------------
# init / cache_path / get_cached / placeholder_png
# ---------------------------------------------------------------------------


def test_init_creates_cache_dir(tmp_path: Path) -> None:
    cache_dir = tmp_path / "thumbs"
    assert not cache_dir.exists()
    ThumbnailManager(cache_dir=cache_dir)
    assert cache_dir.is_dir()


def test_cache_path_changes_with_size(tmp_path: Path) -> None:
    src = tmp_path / "image.tif"
    src.write_bytes(b"x")
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")

    p128 = mgr.cache_path(src, 128)
    p256 = mgr.cache_path(src, 256)
    assert p128 != p256
    assert p128.suffix == ".png"


def test_cache_path_changes_with_mtime(tmp_path: Path) -> None:
    """Spec: cache key invalidates when the file changes (mtime-based)."""
    import os

    src = tmp_path / "image.tif"
    src.write_bytes(b"x")
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")

    p1 = mgr.cache_path(src, 128)
    # Bump mtime to a known later value
    new_mtime = src.stat().st_mtime + 10
    os.utime(src, (new_mtime, new_mtime))
    p2 = mgr.cache_path(src, 128)
    assert p1 != p2


def test_cache_path_stable_for_same_input(tmp_path: Path) -> None:
    src = tmp_path / "image.tif"
    src.write_bytes(b"x")
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")

    assert mgr.cache_path(src, 128) == mgr.cache_path(src, 128)


def test_get_cached_returns_bytes_when_present(tmp_path: Path) -> None:
    src = tmp_path / "image.tif"
    src.write_bytes(b"x")
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")

    payload = b"\x89PNG\r\n\x1a\nfake-png-payload"
    mgr.cache_path(src, 128).write_bytes(payload)
    assert mgr.get_cached(src, 128) == payload


def test_get_cached_returns_none_when_absent(tmp_path: Path) -> None:
    src = tmp_path / "image.tif"
    src.write_bytes(b"x")
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")
    assert mgr.get_cached(src, 128) is None


def test_placeholder_png_returns_valid_png(tmp_path: Path) -> None:
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")
    data = mgr.placeholder_png(64)
    assert data.startswith(b"\x89PNG")


def test_placeholder_png_cached(tmp_path: Path) -> None:
    """Repeated calls return the same bytes object (cheap)."""
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")
    a = mgr.placeholder_png(64)
    b = mgr.placeholder_png(64)
    assert a == b


def test_placeholder_png_size_distinct(tmp_path: Path) -> None:
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")
    small = mgr.placeholder_png(32)
    large = mgr.placeholder_png(128)
    # Cheap heuristic: different sizes produce different byte counts
    assert small != large


# ---------------------------------------------------------------------------
# Synchronous facade for the endpoint: missing-file fast path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_or_queue_returns_placeholder_for_missing_file(tmp_path: Path) -> None:
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")
    bytes_ = await mgr.get_or_queue(tmp_path / "does-not-exist.tif", 128)
    assert bytes_.startswith(b"\x89PNG")
    # The placeholder for missing files matches placeholder_png()
    assert bytes_ == mgr.placeholder_png(128)


@pytest.mark.anyio
async def test_get_or_queue_returns_cached_immediately(tmp_path: Path) -> None:
    """If the cache file exists, no Wetlands env is touched — proven by
    constructing a manager with a sentinel that would explode if the
    launch path ran.
    """
    src = tmp_path / "image.tif"
    src.write_bytes(b"x")
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")

    payload = b"\x89PNG\r\n\x1a\ncached"
    mgr.cache_path(src, 128).write_bytes(payload)

    def _explode() -> None:  # pragma: no cover - must not be called
        raise AssertionError("_launch was called for a cached thumbnail")

    mgr._launch = _explode  # type: ignore[method-assign]
    result = await mgr.get_or_queue(src, 128, wait_timeout=0.0)
    assert result == payload


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
