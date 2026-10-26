"""Own shared thumbnail setup, background rendering, and a fingerprinted PNG cache.

Request cancellation only withdraws a waiter; the service owns setup and render
lifetimes until completion or explicit shutdown.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import logging
import time
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

from wetlands import EnvironmentSpec, ExecutionTask, ManagedEnvironment, WorkerPool

from bioimageflow_server.services.environment_logging import log_environment_operation_event

if TYPE_CHECKING:
    from bioimageflow_server.ws.handler import ConnectionManager


_logger = logging.getLogger(__name__)


_MAX_FAILURES = 256
_WORKERS = 2


@dataclass
class _Generation:
    started: asyncio.Future[None]
    task: asyncio.Task[None] | None = None
    execution: ExecutionTask[Any] | None = None
    submission: asyncio.Task[ExecutionTask[Any]] | None = None


# Absolute path to the subprocess-side helper. Wetlands' ``execute``
# imports it by path (the helper isn't on the env's PYTHONPATH).
_GENERATOR_MODULE_NAME: str = str(
    (Path(__file__).parent.parent / "_external" / "thumbnail_generator.py").resolve()
)


# Pip dependencies for the ``thumbnail`` Wetlands env. Mirrors Galaxy's
# reader stack plus ome-zarr / ome-tiff support. TIFF glob support is
# intentionally omitted because this service accepts only concrete files.
_THUMBNAIL_ENV_PIP: tuple[str, ...] = (
    "bioio==3.4.0",
    "pillow==11.1.0",
    "numpy",
    "bioio-ome-zarr",
    "bioio-ome-tiff",
    "bioio-imageio",
    "bioio-tifffile",
)


class ThumbnailManager:
    """Generate and cache image thumbnails via a Wetlands env.

    Cheap to construct: the conda env is created lazily on the first
    ``queue_generate`` call. ``get_cached`` / ``placeholder_png`` work
    without ever touching Wetlands.
    """

    def __init__(
        self,
        cache_dir: Path,
        connection_manager: ConnectionManager | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._connection_manager = connection_manager
        self._env: ManagedEnvironment | None = None
        self._pool: WorkerPool | None = None
        self._startup_task: asyncio.Task[None] | None = None
        self._operation: Any = None
        self.environment_state = "idle"
        self._closed = False
        self._pending_generations: dict[Path, _Generation] = {}
        self._failures: OrderedDict[Path, str] = OrderedDict()
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
            stat = path.stat()
            mtime = f"{stat.st_mtime_ns}:{stat.st_size}"
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
                self._failures[path] = str(exc)
                while len(self._failures) > _MAX_FAILURES:
                    self._failures.popitem(last=False)
                _logger.warning("failed to read cached thumbnail %s: %r", path, exc)
                self._publish_log(
                    "WARNING",
                    f"failed to read cached thumbnail {path}: {exc!r}",
                )
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
            ``wait_timeout`` seconds; join the job without canceling it on
            timeout, then return cached bytes or a status placeholder.
        """
        cached = self.get_cached(file_path, size)
        if cached is not None:
            return cached

        path = Path(file_path)
        if not path.is_file():
            return self.placeholder_png(size)

        job = self._schedule_generation(path, size)
        if job is not None and job.task is not None and wait_timeout > 0:
            try:
                await asyncio.wait_for(asyncio.shield(job.task), wait_timeout)
            except TimeoutError:
                pass
        return self.get_cached(path, size) or self.placeholder_png(size)

    def status(self, file_path: str | Path, size: int) -> str:
        """Report actual work state; a placeholder alone cannot establish failure."""
        if self.get_cached(file_path, size) is not None:
            return "ready"
        path = Path(file_path)
        key = self.cache_path(path, size)
        if key in self._failures or self.environment_state == "failed":
            return "failed"
        if self._closed or not path.is_file():
            return "unavailable"
        return "pending"

    def _schedule_generation(self, path: Path, size: int) -> _Generation | None:
        key = self.cache_path(path, size)
        if self._closed or not path.is_file() or key.is_file() or key in self._failures:
            return None
        existing = self._pending_generations.get(key)
        if existing is not None:
            return existing
        # Reserve before the first await, including while the environment starts.
        job = _Generation(started=asyncio.get_running_loop().create_future())
        self._pending_generations[key] = job
        job.task = asyncio.create_task(self._generate(job, path, key, size))
        return job

    async def queue_generate(self, file_path: str | Path, size: int) -> None:
        """Join the shared startup/submission without owning its cancellation."""
        job = self._schedule_generation(Path(file_path), size)
        if job is not None:
            await asyncio.shield(job.started)

    async def _ensure_environment(self) -> None:
        if self._pool is not None:
            return
        if self._startup_task is None:
            self.environment_state = "starting"
            self._publish_log("INFO", "Launching thumbnail environment")
            self._startup_task = asyncio.create_task(asyncio.to_thread(self._launch))
        try:
            await asyncio.shield(self._startup_task)
        except Exception:
            self.environment_state = "failed"
            raise
        if self._pool is not None:
            self.environment_state = "ready"

    async def _generate(self, job: _Generation, source: Path, key: Path, size: int) -> None:
        try:
            await self._ensure_environment()
            if self._closed or key.is_file():
                return
            pool = self._pool
            if pool is None:
                raise RuntimeError("Thumbnail environment did not provide a worker pool")
            self._publish_log("INFO", f"Queued thumbnail generation for {source}")
            job.submission = asyncio.create_task(asyncio.to_thread(
                pool.submit_path, _GENERATOR_MODULE_NAME, "create_thumbnail",
                args=(str(source), source.suffix.lstrip("."), str(key), (size, size)),
            ))
            job.execution = await asyncio.shield(job.submission)
            if not job.started.done():
                job.started.set_result(None)
            await job.execution
            if not key.is_file():
                raise RuntimeError("Renderer completed without publishing a thumbnail")
            if key != self.cache_path(source, size):
                # An external file changed while rendering; never publish that
                # image under its previous fingerprint.
                key.unlink(missing_ok=True)
                return
            self._publish_log("INFO", f"Thumbnail generation completed for {source}")
        except asyncio.CancelledError:
            if job.execution is None and job.submission is not None:
                # A thread submission cannot be canceled by dropping its awaiter.
                # Join it before retiring its eventual worker task and pool.
                job.execution = await job.submission
            if job.execution is not None:
                job.execution.cancel()
            raise
        except Exception as exc:  # noqa: BLE001
            self._failures[key] = str(exc)
            while len(self._failures) > _MAX_FAILURES:
                self._failures.popitem(last=False)
            self._publish_log("ERROR", f"Thumbnail generation failed for {source}: {exc}")
        finally:
            if not job.started.done():
                job.started.set_result(None)
            if self._pending_generations.get(key) is job:
                self._pending_generations.pop(key, None)

    async def shutdown(self) -> None:
        """Retire this owner, join startup, cancel renders, then close its pool."""
        self._closed = True
        if self._operation is not None:
            self._operation.cancel()
        jobs = list(self._pending_generations.values())
        tasks = [job.task for job in jobs if job.task is not None]
        for job in jobs:
            if not job.started.done():
                job.started.set_result(None)
            if job.execution is not None:
                job.execution.cancel()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self._startup_task is not None:
            await asyncio.gather(self._startup_task, return_exceptions=True)
        self._pending_generations.clear()
        pool, self._pool = self._pool, None
        self._env = None
        if pool is not None:
            await asyncio.to_thread(pool.close)

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    def _launch(self) -> None:
        """Create or load the Wetlands env and launch its workers.

        Synchronous; called via ``asyncio.to_thread`` from
        ``queue_generate`` so the event loop stays responsive while the
        Conda solve runs.
        """
        if self._env is not None:
            return

        try:
            from bioimageflow.env_manager import get_shared_environment_manager

            em = get_shared_environment_manager()
            self._publish_log("INFO", "Provisioning thumbnail environment")
            operation = em.provision(
                "thumbnail",
                EnvironmentSpec(python="3.12.*", pypi=_THUMBNAIL_ENV_PIP),
                replace_existing=True,
                on_mutation_started=self._mark_installing,
            )
            self._operation = operation
            if self._closed:
                operation.cancel()
            operation.listen(
                lambda event: log_environment_operation_event(event, owner="Thumbnail environment")
            )
            env = operation.wait_for()
            if self._closed:
                return
            pool = env.start(workers=_WORKERS)
            self._env = env
            self._pool = pool
            self.environment_state = "ready"
            self._publish_log("INFO", "Thumbnail environment running")
        except Exception:  # noqa: BLE001
            if self._closed:
                return
            self.environment_state = "failed"
            _logger.exception("thumbnail Wetlands env failed to launch")
            self._publish_log(
                "ERROR",
                "thumbnail Wetlands env failed to launch",
            )
            self._env = None
            self._pool = None
            raise
        finally:
            self._operation = None

    def _mark_installing(self) -> None:
        self.environment_state = "installing"
        self._publish_log("INFO", "Preparing thumbnail support. First-time setup may take several minutes.")

    def _publish_log(self, level: str, message: str) -> None:
        cm = self._connection_manager
        if cm is None or not hasattr(cm, "publish_log"):
            return
        try:
            cm.publish_log(level, message, None, time.time())
        except Exception as exc:  # noqa: BLE001
            _logger.warning("thumbnail log broadcast failed: %r", exc)


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
