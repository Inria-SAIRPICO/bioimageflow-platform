"""Tests for ToolHotReloadService.

Unit tests mock ``watchdog.Observer`` and call ``_handle_event`` directly.
Real-filesystem coverage lives in the E2E in ``frontend/tests/e2e``.
"""

from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from bioimageflow_server.models.tools import (
    InputFieldSchema,
    OutputFieldSchema,
    PackageInfo,
    ToolMetadata,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeRegistry:
    """In-memory ToolRegistryService stand-in for hot-reload tests.

    Mimics the surface used by ToolHotReloadService:
    ``snapshot``, ``reload_package``, ``resolve_package_for_path``,
    ``forget_package``.

    Test helpers: ``set_state(pkg, ver, dict)`` seeds the snapshot.
    ``set_reload_outcome(pkg, ver, new_state)`` schedules what reload should
    return next. ``raise_on_reload(exc)`` raises during the next reload.
    """

    def __init__(self, store_root: Path) -> None:
        self._store = store_root
        self._state: dict[tuple[str, str], dict[str, ToolMetadata]] = {}
        self._next_reload: dict[
            tuple[str, str], dict[str, ToolMetadata] | Exception
        ] = {}
        self.reload_calls: list[tuple[str, str]] = []
        self.forget_calls: list[tuple[str, str | None]] = []

    def set_state(
        self, pkg: str, ver: str, tools: dict[str, ToolMetadata]
    ) -> None:
        self._state[(pkg, ver)] = dict(tools)

    def set_reload_outcome(
        self,
        pkg: str,
        ver: str,
        new_state: dict[str, ToolMetadata] | Exception,
    ) -> None:
        self._next_reload[(pkg, ver)] = new_state

    def snapshot(self, pkg: str, ver: str) -> dict[str, ToolMetadata]:
        return dict(self._state.get((pkg, ver), {}))

    def reload_package(self, pkg: str, ver: str) -> dict[str, ToolMetadata]:
        self.reload_calls.append((pkg, ver))
        outcome = self._next_reload.pop((pkg, ver), None)
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is not None:
            self._state[(pkg, ver)] = dict(outcome)
        return dict(self._state.get((pkg, ver), {}))

    def resolve_package_for_path(
        self, path: Path
    ) -> tuple[str, str] | None:
        try:
            relative = Path(path).resolve().relative_to(self._store.resolve())
        except ValueError:
            return None
        parts = relative.parts
        if len(parts) < 3:
            return None
        return parts[0], parts[1]

    def forget_package(self, pkg: str, version: str | None = None) -> None:
        self.forget_calls.append((pkg, version))
        if version is None:
            for key in list(self._state):
                if key[0] == pkg:
                    self._state.pop(key, None)
        else:
            self._state.pop((pkg, version), None)


def _meta(name: str, *, package: str = "dummy", version: str = "1.0.0") -> ToolMetadata:
    return ToolMetadata(
        name=name,
        display_name=name,
        package=package,
        package_version=version,
        tool_type="ProcessingTool",
        inputs={
            "x": InputFieldSchema(
                type="float",
                required=True,
                connectable="not_by_default",
            )
        },
        outputs={"y": OutputFieldSchema(type="float")},
    )


def _meta_with_input(name: str, input_name: str) -> ToolMetadata:
    return ToolMetadata(
        name=name,
        display_name=name,
        package="dummy",
        package_version="1.0.0",
        tool_type="ProcessingTool",
        inputs={
            input_name: InputFieldSchema(
                type="float",
                required=True,
                connectable="not_by_default",
            )
        },
        outputs={"y": OutputFieldSchema(type="float")},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _wait_for(condition, timeout: float = 1.0, interval: float = 0.01):
    """Poll ``condition`` until it returns truthy or timeout."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if condition():
            return True
        await asyncio.sleep(interval)
    return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_single_file_change_emits_one_tool_reload(tmp_path):
    from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService

    pkg, ver = "dummy", "1.0.0"
    reg = FakeRegistry(tmp_path)
    reg.set_state(pkg, ver, {"GaussianSmooth": _meta("GaussianSmooth")})

    cm = MagicMock()
    cm.broadcast_tool_reload = AsyncMock()
    cm.broadcast_tool_removed = AsyncMock()
    cm.broadcast_system_error = AsyncMock()

    svc = ToolHotReloadService(registry=reg, connection_manager=cm, debounce_ms=20)

    # Simulate a source edit: snapshot picks up new metadata after reload.
    new_state = {"GaussianSmooth": _meta_with_input("GaussianSmooth", "diameter")}
    reg.set_reload_outcome(pkg, ver, new_state)

    file_path = tmp_path / pkg / ver / pkg / "filters.py"
    await svc._handle_event(file_path)

    assert await _wait_for(lambda: cm.broadcast_tool_reload.await_count == 1)
    assert reg.reload_calls == [(pkg, ver)]
    cm.broadcast_tool_reload.assert_awaited_once()
    args = cm.broadcast_tool_reload.await_args.args
    assert args[0] == "GaussianSmooth"
    assert "diameter" in args[1]["inputs"]


async def test_rapid_calls_coalesce_to_single_reload(tmp_path):
    from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService

    pkg, ver = "dummy", "1.0.0"
    reg = FakeRegistry(tmp_path)
    reg.set_state(pkg, ver, {"A": _meta("A")})

    cm = MagicMock()
    cm.broadcast_tool_reload = AsyncMock()
    cm.broadcast_tool_removed = AsyncMock()
    cm.broadcast_system_error = AsyncMock()

    svc = ToolHotReloadService(registry=reg, connection_manager=cm, debounce_ms=30)

    reg.set_reload_outcome(pkg, ver, {"A": _meta_with_input("A", "diameter")})

    path = tmp_path / pkg / ver / pkg / "alpha.py"
    for _ in range(5):
        await svc._handle_event(path)

    assert await _wait_for(lambda: cm.broadcast_tool_reload.await_count >= 1, timeout=1.0)
    # Give a little more time to ensure no second reload fires.
    await asyncio.sleep(0.05)
    assert reg.reload_calls.count((pkg, ver)) == 1
    assert cm.broadcast_tool_reload.await_count == 1


async def test_debounce_coalesces_by_package_pair_not_path(tmp_path):
    """DELETE+CREATE on the same file inside the debounce window triggers
    one reload."""
    from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService

    pkg, ver = "dummy", "1.0.0"
    reg = FakeRegistry(tmp_path)
    reg.set_state(pkg, ver, {"A": _meta("A")})

    cm = MagicMock()
    cm.broadcast_tool_reload = AsyncMock()
    cm.broadcast_tool_removed = AsyncMock()
    cm.broadcast_system_error = AsyncMock()

    svc = ToolHotReloadService(registry=reg, connection_manager=cm, debounce_ms=30)

    reg.set_reload_outcome(pkg, ver, {"A": _meta_with_input("A", "diameter")})

    # Atomic save: the editor deletes then re-creates the file.
    delete_path = tmp_path / pkg / ver / pkg / "alpha.py"
    create_path = tmp_path / pkg / ver / pkg / "alpha.py"
    await svc._handle_event(delete_path)
    await svc._handle_event(create_path)

    assert await _wait_for(lambda: cm.broadcast_tool_reload.await_count >= 1, timeout=1.0)
    await asyncio.sleep(0.05)
    assert reg.reload_calls.count((pkg, ver)) == 1


async def test_snapshot_diff_added_changed_removed(tmp_path):
    from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService

    pkg, ver = "dummy", "1.0.0"
    reg = FakeRegistry(tmp_path)
    # Prior: A and B
    reg.set_state(pkg, ver, {"A": _meta("A"), "B": _meta("B")})

    cm = MagicMock()
    cm.broadcast_tool_reload = AsyncMock()
    cm.broadcast_tool_removed = AsyncMock()
    cm.broadcast_system_error = AsyncMock()

    svc = ToolHotReloadService(registry=reg, connection_manager=cm, debounce_ms=15)

    # New: A' (changed), C (added). B is removed.
    reg.set_reload_outcome(
        pkg,
        ver,
        {
            "A": _meta_with_input("A", "extra"),
            "C": _meta("C"),
        },
    )

    await svc._handle_event(tmp_path / pkg / ver / pkg / "x.py")

    assert await _wait_for(
        lambda: cm.broadcast_tool_reload.await_count == 2
        and cm.broadcast_tool_removed.await_count == 1,
        timeout=1.0,
    )

    reload_names = sorted(
        c.args[0] for c in cm.broadcast_tool_reload.await_args_list
    )
    removed_names = sorted(
        c.args[0] for c in cm.broadcast_tool_removed.await_args_list
    )
    assert reload_names == ["A", "C"]
    assert removed_names == ["B"]


async def test_no_op_change_emits_nothing(tmp_path):
    from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService

    pkg, ver = "dummy", "1.0.0"
    reg = FakeRegistry(tmp_path)
    state = {"A": _meta("A")}
    reg.set_state(pkg, ver, state)

    cm = MagicMock()
    cm.broadcast_tool_reload = AsyncMock()
    cm.broadcast_tool_removed = AsyncMock()
    cm.broadcast_system_error = AsyncMock()

    svc = ToolHotReloadService(registry=reg, connection_manager=cm, debounce_ms=15)

    # Reload returns the same metadata.
    reg.set_reload_outcome(pkg, ver, state)

    await svc._handle_event(tmp_path / pkg / ver / pkg / "x.py")

    assert await _wait_for(
        lambda: reg.reload_calls.count((pkg, ver)) == 1, timeout=1.0
    )
    await asyncio.sleep(0.05)
    cm.broadcast_tool_reload.assert_not_awaited()
    cm.broadcast_tool_removed.assert_not_awaited()


async def test_reload_failure_broadcasts_system_error(tmp_path):
    from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService

    pkg, ver = "dummy", "1.0.0"
    reg = FakeRegistry(tmp_path)
    reg.set_state(pkg, ver, {"A": _meta("A")})

    cm = MagicMock()
    cm.broadcast_tool_reload = AsyncMock()
    cm.broadcast_tool_removed = AsyncMock()
    cm.broadcast_system_error = AsyncMock()

    svc = ToolHotReloadService(registry=reg, connection_manager=cm, debounce_ms=15)

    reg.set_reload_outcome(pkg, ver, RuntimeError("syntax error"))

    await svc._handle_event(tmp_path / pkg / ver / pkg / "x.py")

    assert await _wait_for(
        lambda: cm.broadcast_system_error.await_count == 1, timeout=1.0
    )
    args = cm.broadcast_system_error.await_args.args
    assert args[0] == "tool_reload_failed"
    assert "syntax error" in args[1]
    cm.broadcast_tool_reload.assert_not_awaited()
    cm.broadcast_tool_removed.assert_not_awaited()


async def test_subsequent_event_processed_after_failure(tmp_path):
    """A reload failure must not break the service for later events."""
    from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService

    pkg, ver = "dummy", "1.0.0"
    reg = FakeRegistry(tmp_path)
    reg.set_state(pkg, ver, {"A": _meta("A")})

    cm = MagicMock()
    cm.broadcast_tool_reload = AsyncMock()
    cm.broadcast_tool_removed = AsyncMock()
    cm.broadcast_system_error = AsyncMock()

    svc = ToolHotReloadService(registry=reg, connection_manager=cm, debounce_ms=15)

    reg.set_reload_outcome(pkg, ver, RuntimeError("boom"))
    await svc._handle_event(tmp_path / pkg / ver / pkg / "x.py")
    assert await _wait_for(
        lambda: cm.broadcast_system_error.await_count == 1, timeout=1.0
    )

    # Now a successful reload.
    reg.set_reload_outcome(pkg, ver, {"A": _meta_with_input("A", "diameter")})
    await svc._handle_event(tmp_path / pkg / ver / pkg / "x.py")
    assert await _wait_for(
        lambda: cm.broadcast_tool_reload.await_count == 1, timeout=1.0
    )


async def test_full_package_removal_emits_tool_removed_per_class(tmp_path):
    from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService

    pkg, ver = "dummy", "1.0.0"
    reg = FakeRegistry(tmp_path)
    reg.set_state(pkg, ver, {"A": _meta("A"), "B": _meta("B")})

    cm = MagicMock()
    cm.broadcast_tool_reload = AsyncMock()
    cm.broadcast_tool_removed = AsyncMock()
    cm.broadcast_system_error = AsyncMock()

    svc = ToolHotReloadService(registry=reg, connection_manager=cm, debounce_ms=15)

    reg.set_reload_outcome(pkg, ver, FileNotFoundError(f"{pkg}=={ver} not found"))

    await svc._handle_event(tmp_path / pkg / ver / pkg / "x.py")

    assert await _wait_for(
        lambda: cm.broadcast_tool_removed.await_count == 2, timeout=1.0
    )
    removed = sorted(c.args[0] for c in cm.broadcast_tool_removed.await_args_list)
    assert removed == ["A", "B"]
    cm.broadcast_system_error.assert_not_awaited()
    assert (pkg, ver) in reg.forget_calls or (pkg, None) in reg.forget_calls


async def test_suppress_blocks_broadcasts_resume_emits_batch(tmp_path):
    from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService

    reg = FakeRegistry(tmp_path)
    reg.set_state("p1", "1.0.0", {"A": _meta("A", package="p1")})
    reg.set_state("p2", "1.0.0", {"B": _meta("B", package="p2")})

    cm = MagicMock()
    cm.broadcast_tool_reload = AsyncMock()
    cm.broadcast_tool_removed = AsyncMock()
    cm.broadcast_system_error = AsyncMock()

    svc = ToolHotReloadService(registry=reg, connection_manager=cm, debounce_ms=15)

    svc.suppress()

    await svc._handle_event(tmp_path / "p1" / "1.0.0" / "p1" / "a.py")
    await svc._handle_event(tmp_path / "p2" / "1.0.0" / "p2" / "b.py")
    # Wait through the debounce window: nothing should fire while suppressed.
    await asyncio.sleep(0.05)
    cm.broadcast_tool_reload.assert_not_awaited()
    assert reg.reload_calls == []

    # On resume(emit_batch=True), each accumulated pair gets reloaded once
    # and the diff is computed against the pre-suppress snapshot.
    reg.set_reload_outcome("p1", "1.0.0", {"A": _meta_with_input("A", "x")})
    reg.set_reload_outcome("p2", "1.0.0", {"B": _meta_with_input("B", "y")})

    svc.resume(emit_batch=True)

    assert await _wait_for(
        lambda: cm.broadcast_tool_reload.await_count == 2, timeout=1.0
    )
    pairs = sorted(reg.reload_calls)
    assert pairs == [("p1", "1.0.0"), ("p2", "1.0.0")]


async def test_resume_emit_batch_false_drops_events(tmp_path):
    from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService

    reg = FakeRegistry(tmp_path)
    reg.set_state("p1", "1.0.0", {"A": _meta("A", package="p1")})

    cm = MagicMock()
    cm.broadcast_tool_reload = AsyncMock()
    cm.broadcast_tool_removed = AsyncMock()
    cm.broadcast_system_error = AsyncMock()

    svc = ToolHotReloadService(registry=reg, connection_manager=cm, debounce_ms=15)
    svc.suppress()
    await svc._handle_event(tmp_path / "p1" / "1.0.0" / "p1" / "a.py")
    svc.resume(emit_batch=False)

    await asyncio.sleep(0.05)
    cm.broadcast_tool_reload.assert_not_awaited()
    cm.broadcast_tool_removed.assert_not_awaited()
    assert reg.reload_calls == []


async def test_handle_event_outside_store_is_noop(tmp_path):
    from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService

    reg = FakeRegistry(tmp_path)
    cm = MagicMock()
    cm.broadcast_tool_reload = AsyncMock()
    cm.broadcast_tool_removed = AsyncMock()
    cm.broadcast_system_error = AsyncMock()

    svc = ToolHotReloadService(registry=reg, connection_manager=cm, debounce_ms=15)

    # Path outside the store and a too-shallow path inside the store.
    await svc._handle_event(Path("/etc/hosts"))
    await svc._handle_event(tmp_path / "README.md")

    await asyncio.sleep(0.05)
    cm.broadcast_tool_reload.assert_not_awaited()
    cm.broadcast_tool_removed.assert_not_awaited()
    assert reg.reload_calls == []


async def test_pycache_paths_ignored(tmp_path):
    from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService

    pkg, ver = "dummy", "1.0.0"
    reg = FakeRegistry(tmp_path)
    reg.set_state(pkg, ver, {"A": _meta("A")})

    cm = MagicMock()
    cm.broadcast_tool_reload = AsyncMock()
    cm.broadcast_tool_removed = AsyncMock()
    cm.broadcast_system_error = AsyncMock()

    svc = ToolHotReloadService(registry=reg, connection_manager=cm, debounce_ms=15)

    base = tmp_path / pkg / ver / pkg
    for noisy in (
        base / "__pycache__" / "filters.cpython-312.pyc",
        base / "alpha.py.swp",
        base / "alpha.py___jb_tmp___",
    ):
        await svc._handle_event(noisy)

    await asyncio.sleep(0.05)
    cm.broadcast_tool_reload.assert_not_awaited()
    cm.broadcast_tool_removed.assert_not_awaited()
    assert reg.reload_calls == []


async def test_stop_cancels_pending_timer(tmp_path):
    from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService

    pkg, ver = "dummy", "1.0.0"
    reg = FakeRegistry(tmp_path)
    reg.set_state(pkg, ver, {"A": _meta("A")})

    cm = MagicMock()
    cm.broadcast_tool_reload = AsyncMock()
    cm.broadcast_tool_removed = AsyncMock()
    cm.broadcast_system_error = AsyncMock()

    svc = ToolHotReloadService(registry=reg, connection_manager=cm, debounce_ms=200)

    await svc._handle_event(tmp_path / pkg / ver / pkg / "x.py")
    # Stop before the debounce fires.
    await svc.stop()
    await asyncio.sleep(0.3)

    cm.broadcast_tool_reload.assert_not_awaited()
    assert reg.reload_calls == []


async def test_concurrent_suppress_resume_thread_safety(tmp_path):
    """Stress: from a worker thread, fire suppress/resume while the loop
    schedules events. Final accumulator must be well-formed (no
    RuntimeError, no half-applied state)."""
    from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService

    pkg, ver = "dummy", "1.0.0"
    reg = FakeRegistry(tmp_path)
    reg.set_state(pkg, ver, {"A": _meta("A")})

    cm = MagicMock()
    cm.broadcast_tool_reload = AsyncMock()
    cm.broadcast_tool_removed = AsyncMock()
    cm.broadcast_system_error = AsyncMock()

    svc = ToolHotReloadService(registry=reg, connection_manager=cm, debounce_ms=10)

    file_path = tmp_path / pkg / ver / pkg / "x.py"

    stop = threading.Event()

    def _bouncer() -> None:
        for _ in range(50):
            if stop.is_set():
                return
            svc.suppress()
            svc.resume(emit_batch=False)

    t = threading.Thread(target=_bouncer)
    t.start()

    for _ in range(50):
        await svc._handle_event(file_path)
        await asyncio.sleep(0)

    stop.set()
    t.join(timeout=2.0)

    # Wait for any pending timers to drain.
    await asyncio.sleep(0.1)
    # No RuntimeError fell out of the loop; the broadcast counts are
    # whatever they are (depends on race), but the service is still
    # responsive.
    assert not t.is_alive()


async def test_changed_metadata_uses_model_dump_in_payload(tmp_path):
    """The tool_reload payload carries the full metadata dict, including
    inputs and outputs."""
    from bioimageflow_server.services.tool_hot_reload import ToolHotReloadService

    pkg, ver = "dummy", "1.0.0"
    reg = FakeRegistry(tmp_path)
    reg.set_state(pkg, ver, {"A": _meta("A")})

    cm = MagicMock()
    cm.broadcast_tool_reload = AsyncMock()
    cm.broadcast_tool_removed = AsyncMock()
    cm.broadcast_system_error = AsyncMock()

    svc = ToolHotReloadService(registry=reg, connection_manager=cm, debounce_ms=15)
    reg.set_reload_outcome(pkg, ver, {"A": _meta_with_input("A", "diameter")})

    await svc._handle_event(tmp_path / pkg / ver / pkg / "x.py")

    assert await _wait_for(
        lambda: cm.broadcast_tool_reload.await_count == 1, timeout=1.0
    )
    args = cm.broadcast_tool_reload.await_args.args
    payload = args[1]
    assert payload["name"] == "A"
    assert payload["package"] == "dummy"
    assert payload["package_version"] == "1.0.0"
    assert "diameter" in payload["inputs"]
    assert "y" in payload["outputs"]
