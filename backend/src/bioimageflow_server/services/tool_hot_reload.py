"""Tool source hot-reload watcher.

Watches the tool store directory for ``*.py`` edits, debounces them by
``(package, version)``, calls
:meth:`ToolRegistryService.reload_package`, diffs the pre/post snapshot
for that package, and broadcasts ``tool_reload`` / ``tool_removed`` to
connected GUIs via the :class:`ConnectionManager`.

Reload failures broadcast ``system_error`` so the System Errors panel
can surface them, but do not crash the underlying watchdog observer.

The package installer wraps install/uninstall with
:meth:`suppress` / :meth:`resume` so disk writes during install do not
trigger spurious reloads — the post-install ``resume(emit_batch=True)``
performs the load + index in one consolidated batch.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from watchdog.events import (
    FileSystemEvent,
    PatternMatchingEventHandler,
)
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

if TYPE_CHECKING:
    from bioimageflow_server.services.tool_registry import ToolRegistryService
    from bioimageflow_server.ws.handler import ConnectionManager


logger = logging.getLogger(__name__)

_STOP_POLL_INTERVAL_SECONDS = 0.01


# Editor temp-file noise that watchdog's PatternMatchingEventHandler
# filters out before our handler runs. Defined at module scope so tests
# can reference the same list when sanity-checking the filter contract.
IGNORE_PATTERNS = [
    "*/__pycache__/*",
    "*.pyc",
    "*~",
    "*.swp",
    "*.swx",
    "*___jb_tmp___*",
]


class ToolHotReloadService:
    """Watch the tool store for ``*.py`` edits and broadcast reload events."""

    def __init__(
        self,
        registry: "ToolRegistryService",
        connection_manager: "ConnectionManager",
        debounce_ms: int = 500,
        stop_timeout_s: float = 2.0,
    ) -> None:
        self._registry = registry
        self._cm = connection_manager
        self._debounce_s = debounce_ms / 1000.0
        self._stop_timeout_s = stop_timeout_s
        self._observer: BaseObserver | None = None
        self._handler: PatternMatchingEventHandler | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        # Debounce timers, keyed by (package, version).
        self._timers: dict[tuple[str, str], asyncio.TimerHandle] = {}

        # Suppression state. ``_suppressed`` is a flag (a threading.Event so
        # both the loop thread and watchdog worker can read it cheaply).
        # ``_pending`` collects (pkg, ver) pairs the watcher saw while
        # suppressed; ``_pre_suppress_snapshots`` keeps the registry's
        # snapshot at the moment suppress() was called so resume() can
        # diff against the original baseline rather than against a state
        # that was already mutated by the install path.
        self._suppressed = threading.Event()
        self._pending: set[tuple[str, str]] = set()
        self._pre_suppress_snapshots: dict[tuple[str, str], dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._stopped = False

    # -- public lifecycle ------------------------------------------------

    async def start(self, watch_root: Path | list[Path]) -> None:
        """Start watching one or more roots for ``*.py`` changes."""
        self._loop = asyncio.get_running_loop()
        self._stopped = False

        roots = [watch_root] if isinstance(watch_root, Path) else watch_root
        for root in roots:
            root.mkdir(parents=True, exist_ok=True)

        observer = Observer()
        handler = PatternMatchingEventHandler(
            patterns=["*.py"],
            ignore_patterns=IGNORE_PATTERNS,
            ignore_directories=True,
        )
        handler.on_any_event = self._on_any_event  # type: ignore[assignment]
        for root in roots:
            observer.schedule(handler, str(root), recursive=True)
        observer.start()
        self._observer = observer
        self._handler = handler

    def add_watch_root(self, watch_root: Path) -> None:
        """Add another root to the running observer."""
        if self._observer is None or self._handler is None:
            return
        watch_root.mkdir(parents=True, exist_ok=True)
        self._observer.schedule(self._handler, str(watch_root), recursive=True)

    async def stop(self) -> None:
        """Cancel timers and stop the observer."""
        self._stopped = True
        with self._lock:
            for handle in self._timers.values():
                handle.cancel()
            self._timers.clear()

        observer = self._observer
        self._observer = None
        if observer is None:
            return

        loop = asyncio.get_running_loop()
        done = threading.Event()
        errors: list[BaseException] = []

        def _stop_observer() -> None:
            try:
                observer.stop()
                observer.join(timeout=self._stop_timeout_s)
            except BaseException as exc:  # pragma: no cover - defensive.
                errors.append(exc)
            finally:
                done.set()

        thread = threading.Thread(
            target=_stop_observer,
            name="bioimageflow-hot-reload-stop",
            daemon=True,
        )
        thread.start()

        deadline = loop.time() + self._stop_timeout_s
        while not done.is_set() and loop.time() < deadline:
            await asyncio.sleep(_STOP_POLL_INTERVAL_SECONDS)

        if done.is_set() and errors:
            raise errors[0]
        if not done.is_set():
            logger.warning(
                "Tool hot-reload observer did not stop within %.1fs",
                self._stop_timeout_s,
            )
        self._handler = None

    # -- suppress / resume ----------------------------------------------

    def suppress(self) -> None:
        """Block broadcasts and start accumulating affected pairs.

        Captures the current snapshot for every known package version so
        :meth:`resume` can diff against the pre-suppress baseline rather
        than a state that was already mutated by the operation owning
        the suppression window.
        """
        with self._lock:
            self._suppressed.set()
            # Refresh the pre-suppress baseline with whatever the
            # registry currently knows about. We snapshot lazily — the
            # registry's package list is the source of truth.
            packages = getattr(self._registry, "_packages", {})
            for pkg_name, info in list(packages.items()):
                versions = getattr(info, "installed_versions", []) or []
                for ver in versions:
                    key = (pkg_name, ver)
                    if key not in self._pre_suppress_snapshots:
                        self._pre_suppress_snapshots[key] = self._registry.snapshot(pkg_name, ver)

    def resume(self, emit_batch: bool = True) -> None:
        """Clear the suppression flag.

        With ``emit_batch=True``, every accumulated ``(pkg, ver)`` pair —
        plus every package known to the registry that we have a
        pre-suppress snapshot for — is reloaded once and the diff is
        broadcast. With ``emit_batch=False``, accumulated events are
        dropped silently (used on installer error paths).
        """
        with self._lock:
            self._suppressed.clear()
            pending = self._pending.copy()
            pre = self._pre_suppress_snapshots.copy()
            self._pending.clear()
            self._pre_suppress_snapshots.clear()

        if not emit_batch:
            return

        # Include any package the registry knows about that wasn't
        # already in `pending` — covers fresh installs where watchdog
        # may not have fired by the time `resume` is called. We compare
        # the post-install snapshot against the pre-suppress snapshot
        # (empty for a brand-new package) to surface the new tools.
        packages = getattr(self._registry, "_packages", {})
        for pkg_name, info in list(packages.items()):
            versions = getattr(info, "installed_versions", []) or []
            for ver in versions:
                pending.add((pkg_name, ver))
                pre.setdefault((pkg_name, ver), {})

        if self._loop is None:
            # No event loop available — happens in tests that exercise
            # suppress/resume without an active loop. Nothing to schedule.
            return

        for pair in pending:
            prior = pre.get(pair, {})
            self._loop.call_soon_threadsafe(self._fire_with_prior, pair, prior)

    # -- watchdog callback (worker thread) -------------------------------

    def _on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(os.fsdecode(event.src_path))
        if self._loop is None or self._stopped:
            return
        # Hop to the asyncio loop where the rest of the state lives.
        self._loop.call_soon_threadsafe(asyncio.create_task, self._handle_event(path))

    # -- loop-thread handlers --------------------------------------------

    async def _handle_event(self, path: Path) -> None:
        """Process a single file event — debounce by (pkg, ver)."""
        if self._stopped:
            return
        # Capture the running loop on first event so suppress/resume have
        # a target even if start() was never called (covers unit tests).
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        # Defensive ignore for paths the watchdog filter would drop.
        path_str = str(path)
        if any((token in path_str) for token in ("__pycache__", "___jb_tmp___", ".swp", ".swx")):
            return
        if path_str.endswith(".pyc") or path_str.endswith("~"):
            return

        pair = self._registry.resolve_package_for_path(path)
        if pair is None:
            return

        # If suppressed, accumulate; resume() will reload + broadcast.
        if self._suppressed.is_set():
            with self._lock:
                self._pending.add(pair)
                # Capture snapshot at first event for this pair if we
                # don't already have one (covers the rare race where
                # suppress() ran but the registry didn't yet know about
                # this package).
                if pair not in self._pre_suppress_snapshots:
                    self._pre_suppress_snapshots[pair] = self._registry.snapshot(*pair)
            return

        loop = asyncio.get_running_loop()
        with self._lock:
            existing = self._timers.pop(pair, None)
            if existing is not None:
                existing.cancel()
            handle = loop.call_later(self._debounce_s, self._fire, pair)
            self._timers[pair] = handle

    def _fire(self, pair: tuple[str, str]) -> None:
        """Debounce timer callback (loop thread). Schedule the async fire."""
        with self._lock:
            self._timers.pop(pair, None)
        if self._stopped:
            return
        prior = self._registry.snapshot(*pair)
        asyncio.create_task(self._do_reload(pair, prior))

    def _fire_with_prior(self, pair: tuple[str, str], prior: dict[str, Any]) -> None:
        """Resume()'s scheduled fire — uses the pre-suppress snapshot."""
        if self._stopped:
            return
        asyncio.create_task(self._do_reload(pair, prior))

    async def _do_reload(self, pair: tuple[str, str], prior: dict[str, Any]) -> None:
        """Run reload + diff + broadcast for a single ``(pkg, ver)`` pair."""
        pkg, ver = pair
        try:
            current = await asyncio.get_running_loop().run_in_executor(
                None, self._registry.reload_package, pkg, ver
            )
        except FileNotFoundError as exc:
            logger.info(
                "Tool package %s==%s no longer present on disk; treating as full removal: %s",
                pkg,
                ver,
                exc,
            )
            try:
                self._registry.forget_package(pkg, ver)
            except Exception:
                logger.warning(
                    "forget_package(%s, %s) failed during full-removal handling",
                    pkg,
                    ver,
                    exc_info=True,
                )
            for name in prior:
                await self._cm.broadcast_tool_removed(name)
            return
        except Exception as exc:
            logger.warning(
                "Tool reload failed for %s==%s: %s",
                pkg,
                ver,
                exc,
                exc_info=True,
            )
            await self._cm.broadcast_system_error(
                "tool_reload_failed",
                str(exc),
            )
            return

        # Diff prior vs. current and emit one event per change.
        for name, meta in current.items():
            if prior.get(name) != meta:
                payload = meta.model_dump() if hasattr(meta, "model_dump") else dict(meta)
                await self._cm.broadcast_tool_reload(name, payload)
        for name in prior:
            if name not in current:
                await self._cm.broadcast_tool_removed(name)


__all__ = ["ToolHotReloadService", "IGNORE_PATTERNS"]
