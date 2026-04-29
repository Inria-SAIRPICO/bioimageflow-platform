"""ThumbnailManager service.

Manager-side counterpart to ``_external/thumbnail_generator.py``. Owns
the lifecycle of a Wetlands env (``bioio`` + ``pillow`` + bioio
readers) and dispatches thumbnail generation to it via fire-and-forget
``execute()`` calls.

The shape mirrors Galaxy's ``ThumbnailManager`` (env + queue) plus the
on-disk cache layer required by ``platform_specs_v1 §2.6``.

Task split:
  * T2 — cache key, cached retrieval, placeholder, ``get_or_queue``
    fast paths (cached / missing source).
  * T3 — Wetlands env lazy launch + ``queue_generate`` dispatch.
  * T4 — ``get_or_queue`` bounded wait that polls the cache file.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bioimageflow_server.ws.handler import ConnectionManager


_logger = logging.getLogger(__name__)


# Polling resolution for ``get_or_queue`` bounded wait. 50 ms is a fine
# balance: bioio renders are typically 100 ms – 2 s, and the event loop
# sees at most ~20 wake-ups per request.
_POLL_INTERVAL_SECONDS = 0.05


class ThumbnailManager:
    """Generate and cache image thumbnails via a Wetlands env.

    Cheap to construct: the conda env is created lazily on the first
    ``queue_generate`` call. ``get_cached`` / ``placeholder_png`` work
    without ever touching Wetlands.
    """

    def __init__(
        self,
        cache_dir: Path,
        env_path: str | None = None,
        connection_manager: ConnectionManager | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._env_path = env_path
        self._connection_manager = connection_manager
        self._env: Any | None = None
        self._lock = asyncio.Lock()
        self._placeholder_cache: dict[int, bytes] = {}

    # ------------------------------------------------------------------
    # Cache layer
    # ------------------------------------------------------------------

    def cache_path(self, file_path: str | Path, size: int) -> Path:
        """Return the on-disk cache path for ``file_path`` at ``size``.

        Key matches the ``platform_specs_v1`` recipe — SHA-256 of
        ``file_path + mtime + size`` — so the cache invalidates when the
        source changes. ``size`` is included so 128 px and 256 px don't
        clobber each other.
        """
        path = Path(file_path)
        try:
            absolute = str(path.resolve())
        except OSError:
            absolute = str(path)
        try:
            mtime = str(os.path.getmtime(path))
        except (FileNotFoundError, OSError):
            mtime = ""
        digest = hashlib.sha256(
            f"{absolute}|{mtime}|{size}".encode("utf-8")
        ).hexdigest()
        return self.cache_dir / f"{digest}.png"

    def get_cached(self, file_path: str | Path, size: int) -> bytes | None:
        path = self.cache_path(file_path, size)
        if path.is_file():
            try:
                return path.read_bytes()
            except OSError as exc:
                _logger.warning("failed to read cached thumbnail %s: %r", path, exc)
                return None
        return None

    # ------------------------------------------------------------------
    # Placeholder
    # ------------------------------------------------------------------

    def placeholder_png(self, size: int) -> bytes:
        """Return a small PNG used when the source file is unsupported,
        missing, or still being generated. Cached per size.
        """
        cached = self._placeholder_cache.get(size)
        if cached is not None:
            return cached
        data = _build_placeholder_png(size)
        self._placeholder_cache[size] = data
        return data

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def get_or_queue(
        self,
        file_path: str | Path,
        size: int,
        wait_timeout: float = 0.0,
    ) -> bytes:
        """Return PNG bytes for ``file_path`` at ``size``.

        Behaviour:
          * Cache hit → return immediately.
          * Source missing/not a file → return ``placeholder_png(size)``.
          * Otherwise → queue generation, poll the cache file up to
            ``wait_timeout`` seconds; if it appears, return its bytes,
            else return ``placeholder_png(size)`` so the frontend can
            retry.
        """
        cached = self.get_cached(file_path, size)
        if cached is not None:
            return cached

        path = Path(file_path)
        if not path.is_file():
            return self.placeholder_png(size)

        # T3 / T4 — wired in subsequent commits.
        await self.queue_generate(path, size)

        if wait_timeout > 0:
            cache_file = self.cache_path(path, size)
            deadline = time.monotonic() + wait_timeout
            while time.monotonic() < deadline:
                if cache_file.is_file():
                    try:
                        return cache_file.read_bytes()
                    except OSError:
                        break
                await asyncio.sleep(_POLL_INTERVAL_SECONDS)

        return self.placeholder_png(size)

    async def queue_generate(self, file_path: str | Path, size: int) -> None:
        """Dispatch a generation task into the Wetlands env (T3)."""
        # Wired in T3.
        return None

    async def shutdown(self) -> None:
        """Best-effort env shutdown. Idempotent."""
        return None

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    def _launch(self) -> None:
        """Synchronously create + launch the Wetlands env (T3)."""
        return None


# ---------------------------------------------------------------------------
# Placeholder generation
# ---------------------------------------------------------------------------


def _build_placeholder_png(size: int) -> bytes:
    try:
        from PIL import Image, ImageDraw

        image = Image.new("RGBA", (size, size), (245, 245, 245, 255))
        draw = ImageDraw.Draw(image)
        draw.line(
            (size * 0.25, size * 0.25, size * 0.75, size * 0.75),
            fill=(150, 150, 150, 255),
            width=max(1, size // 16),
        )
        draw.line(
            (size * 0.75, size * 0.25, size * 0.25, size * 0.75),
            fill=(150, 150, 150, 255),
            width=max(1, size // 16),
        )
        buf = BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:  # noqa: BLE001
        # Fallback: 1x1 transparent PNG. Hard-coded to avoid a runtime
        # dependency on Pillow at import time.
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\x0bIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
