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
from unittest import mock
import asyncio

import pytest
from wetlands import EnvironmentSpec

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
    cm = mock.MagicMock()
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache", connection_manager=cm)

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


def test_get_cached_logs_corrupt_cache_read_to_ws(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "image.tif"
    src.write_bytes(b"x")
    cm = mock.MagicMock()
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache", connection_manager=cm)
    cache_file = mgr.cache_path(src, 128)
    cache_file.write_bytes(b"bad")

    original_read_bytes = Path.read_bytes

    def _raise_for_cache(path: Path) -> bytes:
        if path == cache_file:
            raise OSError("cannot read")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", _raise_for_cache)
    assert mgr.get_cached(src, 128) is None
    cm.publish_log.assert_called()
    assert "failed to read cached thumbnail" in cm.publish_log.call_args.args[1]


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


# ---------------------------------------------------------------------------
# Wetlands launch + queue (T3)
# ---------------------------------------------------------------------------


class _StubExecution:
    def __init__(self, *, gate: asyncio.Event | None = None) -> None:
        self.gate = gate
        self.cancelled = False

    def __await__(self):
        async def wait() -> None:
            if self.gate is not None:
                await self.gate.wait()

        return wait().__await__()

    def cancel(self) -> bool:
        self.cancelled = True
        if self.gate is not None:
            self.gate.set()
        return True


def _stub_pool(*, execution: _StubExecution | None = None) -> mock.MagicMock:
    pool = mock.MagicMock()
    pool.submit_path.return_value = execution or _StubExecution()
    return pool


@pytest.mark.anyio
async def test_queue_generate_lazily_calls_launch(tmp_path: Path) -> None:
    src = tmp_path / "image.tif"
    src.write_bytes(b"x")
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")

    pool = _stub_pool()
    launched: list[bool] = []

    def fake_launch() -> None:
        launched.append(True)
        mgr._env = mock.MagicMock()
        mgr._pool = pool

    mgr._launch = fake_launch  # type: ignore[method-assign]
    await mgr.queue_generate(src, 128)
    assert launched == [True]
    pool.submit_path.assert_called_once()


@pytest.mark.anyio
async def test_queue_generate_publishes_backend_lifecycle_logs(tmp_path: Path) -> None:
    src = tmp_path / "image.tif"
    src.write_bytes(b"x")
    cm = mock.MagicMock()
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache", connection_manager=cm)

    pool = _stub_pool()

    def fake_launch() -> None:
        mgr._env = mock.MagicMock()
        mgr._pool = pool

    mgr._launch = fake_launch  # type: ignore[method-assign]
    await mgr.queue_generate(src, 128)
    await asyncio.sleep(0)

    messages = [call.args[1] for call in cm.publish_log.call_args_list]
    assert any("Launching thumbnail environment" in message for message in messages)
    assert any("Queued thumbnail generation" in message for message in messages)


@pytest.mark.anyio
async def test_queue_generate_passes_correct_args(tmp_path: Path) -> None:
    src = tmp_path / "image.tif"
    src.write_bytes(b"fake-tiff")
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")

    pool = _stub_pool()
    mgr._env = mock.MagicMock()
    mgr._pool = pool

    await mgr.queue_generate(src, 128)

    args, kwargs = pool.submit_path.call_args
    assert "thumbnail_generator" in str(args[0])
    assert args[1] == "create_thumbnail"
    submitted = kwargs["args"]
    assert submitted[0] == str(src)
    assert submitted[1] == "tif"  # extension without dot
    assert submitted[2] == str(mgr.cache_path(src, 128))
    assert submitted[3] == (128, 128)


@pytest.mark.anyio
async def test_queue_generate_skips_when_cached(tmp_path: Path) -> None:
    src = tmp_path / "image.tif"
    src.write_bytes(b"x")
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")
    mgr.cache_path(src, 128).write_bytes(b"already-cached")

    pool = _stub_pool()
    mgr._env = mock.MagicMock()
    mgr._pool = pool

    await mgr.queue_generate(src, 128)
    pool.submit_path.assert_not_called()


@pytest.mark.anyio
async def test_queue_generate_skips_when_source_missing(tmp_path: Path) -> None:
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")

    pool = _stub_pool()
    mgr._env = mock.MagicMock()
    mgr._pool = pool

    def _explode() -> None:  # pragma: no cover
        raise AssertionError("_launch must not run for a missing source")

    mgr._launch = _explode  # type: ignore[method-assign]

    await mgr.queue_generate(tmp_path / "missing.tif", 128)
    pool.submit_path.assert_not_called()


@pytest.mark.anyio
async def test_queue_generate_reuses_env_across_calls(tmp_path: Path) -> None:
    src1 = tmp_path / "a.tif"
    src1.write_bytes(b"x")
    src2 = tmp_path / "b.tif"
    src2.write_bytes(b"y")
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")

    pool = _stub_pool()
    launches: list[bool] = []

    def fake_launch() -> None:
        launches.append(True)
        mgr._env = mock.MagicMock()
        mgr._pool = pool

    mgr._launch = fake_launch  # type: ignore[method-assign]

    await mgr.queue_generate(src1, 128)
    await mgr.queue_generate(src2, 128)

    assert len(launches) == 1
    assert pool.submit_path.call_count == 2


@pytest.mark.anyio
async def test_concurrent_queue_generate_same_cache_uses_one_render(
    tmp_path: Path,
) -> None:
    src = tmp_path / "image.tif"
    src.write_bytes(b"x")
    cm = mock.MagicMock()
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache", connection_manager=cm)

    release = asyncio.Event()
    execution = _StubExecution(gate=release)
    pool = _stub_pool(execution=execution)
    mgr._env = mock.MagicMock()
    mgr._pool = pool

    await asyncio.gather(
        mgr.queue_generate(src, 128),
        mgr.queue_generate(src, 128),
    )
    release.set()
    await asyncio.sleep(0)

    assert pool.submit_path.call_count == 1
    completion_logs = [
        call.args[1]
        for call in cm.publish_log.call_args_list
        if "Thumbnail generation completed" in call.args[1]
    ]
    assert len(completion_logs) == 1


@pytest.mark.anyio
async def test_queue_generate_handles_extension_with_no_dot(tmp_path: Path) -> None:
    """Files with no extension produce extension="" — bioio side handles it
    (Galaxy fallback creates a symlink with the dataset's logical
    extension, which is empty here)."""
    src = tmp_path / "datafile_no_extension"
    src.write_bytes(b"x")
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")
    pool = _stub_pool()
    mgr._env = mock.MagicMock()
    mgr._pool = pool

    await mgr.queue_generate(src, 128)
    _, kwargs = pool.submit_path.call_args
    assert kwargs["args"][1] == ""


# ---------------------------------------------------------------------------
# get_or_queue bounded wait (T4)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_or_queue_bounded_wait_returns_real_when_ready(tmp_path: Path) -> None:
    """When the cache file is written by the (mocked) generator before the
    timeout, get_or_queue returns the real bytes."""
    src = tmp_path / "image.tif"
    src.write_bytes(b"x")
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")
    cache_file = mgr.cache_path(src, 128)
    real_png = b"\x89PNG\r\n\x1a\nrendered"

    pool = _stub_pool()

    def write_cache(*_a: object, **_kw: object) -> _StubExecution:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(real_png)
        return _StubExecution()

    pool.submit_path.side_effect = write_cache
    mgr._env = mock.MagicMock()
    mgr._pool = pool

    result = await mgr.get_or_queue(src, 128, wait_timeout=1.0)
    assert result == real_png


@pytest.mark.anyio
async def test_get_or_queue_returns_placeholder_on_timeout(tmp_path: Path) -> None:
    src = tmp_path / "image.tif"
    src.write_bytes(b"x")
    mgr = ThumbnailManager(cache_dir=tmp_path / "cache")

    pool = _stub_pool()  # never writes the cache file
    mgr._env = mock.MagicMock()
    mgr._pool = pool

    result = await mgr.get_or_queue(src, 128, wait_timeout=0.1)
    assert result == mgr.placeholder_png(128)
    pool.submit_path.assert_called_once()


def test_launch_provisions_environment_and_starts_worker_pool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bioimageflow_server.services import thumbnail_manager as module

    pool = mock.MagicMock()
    environment = mock.MagicMock()
    environment.start.return_value = pool
    operation = mock.MagicMock()
    operation.wait_for.return_value = environment
    manager = mock.MagicMock()
    manager.provision.return_value = operation
    monkeypatch.setattr(
        "bioimageflow.env_manager.get_shared_environment_manager",
        lambda: manager,
    )
    thumbnails = ThumbnailManager(cache_dir=tmp_path / "cache")

    thumbnails._launch()

    manager.provision.assert_called_once_with(
        "thumbnail",
        EnvironmentSpec(python="3.12.*", pypi=module._THUMBNAIL_ENV_PIP),
        replace_existing=True,
    )
    operation.listen.assert_called_once()
    operation.wait_for.assert_called_once_with()
    environment.start.assert_called_once_with(workers=8)
    assert thumbnails._pool is pool


@pytest.mark.anyio
async def test_shutdown_cancels_pending_generation_and_closes_pool(tmp_path: Path) -> None:
    source = tmp_path / "image.tif"
    source.write_bytes(b"x")
    gate = asyncio.Event()
    execution = _StubExecution(gate=gate)
    pool = _stub_pool(execution=execution)
    thumbnails = ThumbnailManager(cache_dir=tmp_path / "cache")
    thumbnails._env = mock.MagicMock()
    thumbnails._pool = pool
    await thumbnails.queue_generate(source, 128)

    await thumbnails.shutdown()

    assert execution.cancelled is True
    pool.close.assert_called_once_with()
    assert thumbnails._pending_generations == {}
    assert thumbnails._pool is None


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
