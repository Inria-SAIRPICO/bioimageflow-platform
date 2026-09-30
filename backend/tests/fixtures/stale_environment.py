"""Observable real provisioning fixtures; only the named install fault is injected."""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
from pathlib import Path
from typing import Any

from bioimageflow.env_manager import EnvironmentRecipeState, get_shared_environment_manager
from bioimageflow_core import EnvironmentSpec

from tests.fixtures.stale_worker_numbers import StaleWorkerNumbers


def old_worker_spec() -> EnvironmentSpec:
    return EnvironmentSpec(
        name=StaleWorkerNumbers.environment.name,
        dependencies={"python": ">=3.12,<3.13"},
    )


def pixi_forwarder(root: Path) -> tuple[Path, Path]:
    """Forward to actual Pixi, failing exactly one armed install with exit 77."""
    selected = os.environ.get("BIOIMAGEFLOW_E2E_PIXI") or shutil.which("pixi")
    marker = root / "fail-next-pixi-install"
    executable = root / "pixi-forwarder"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, sys\n"
        f"selected = {selected!r}\n"
        "if selected is None:\n"
        "    from wetlands import EnvironmentManager\n"
        f"    bootstrap = EnvironmentManager({str(root / 'pixi-bootstrap')!r})\n"
        "    try:\n"
        "        selected = str(bootstrap.prepare().wait_for().executable)\n"
        "    finally:\n"
        "        bootstrap.close()\n"
        f"marker = pathlib.Path({str(marker)!r})\n"
        "if sys.argv[1:2] == ['install'] and marker.exists():\n"
        "    marker.unlink()\n"
        "    print('E1 injected Pixi install failure (exit 77)', file=sys.stderr)\n"
        "    sys.exit(77)\n"
        "os.execv(selected, [selected, *sys.argv[1:]])\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable, marker


def inventory() -> list[dict[str, Any]]:
    manager = get_shared_environment_manager()
    return [
        {
            "name": info.name, "generation_id": info.generation_id,
            "recipe_hash": info.recipe_hash, "state": info.state.value,
            "path": str(info.path),
            "worker_pids": [worker.process_id for worker in manager.running_workers(info.name)],
        }
        for info in manager.managed_environments()
    ]


class ObservedProcessingManager:
    """Delegate real managed operations and pause a genuine preparation callback."""

    def __init__(self, manager: Any) -> None:
        self.manager = manager
        self.release = threading.Event()
        self.release.set()
        self.preparations: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.retired_worker_pids: list[int] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self.manager, name)

    def get_or_create(self, spec: Any, *args: Any, **kwargs: Any) -> Any:
        preparation_callback = kwargs.pop("on_preparation", None)
        event_callback = kwargs.pop("on_provision_event", None)

        def preparation(value: Any) -> None:
            self.preparations.append({
                "name": value.name, "action": value.action,
                "requested_recipe_hash": value.requested_recipe_hash,
                "existing_recipe_hash": value.existing_recipe_hash,
                "replace_existing": kwargs.get("replace_existing", False),
            })
            if preparation_callback is not None:
                preparation_callback(value)
            if value.name == StaleWorkerNumbers.environment.name and value.action == "updating":
                if not self.release.wait(60):
                    raise TimeoutError("E1 preparation observer was not released")

        def event(value: Any) -> None:
            self.events.append({
                "operation_id": value.operation_id, "kind": value.kind.value,
                "message": value.message, "stage": value.stage,
            })
            if event_callback is not None:
                event_callback(value)

        return self.manager.get_or_create(
            spec, *args, **kwargs, on_preparation=preparation, on_provision_event=event,
        )

    def seed_stale(self) -> dict[str, Any]:
        spec = old_worker_spec()
        existing = any(item["name"] == spec.name for item in inventory())
        self.manager.get_or_create(spec, max_workers=1, replace_existing=existing)
        assert self.manager.inspect_environment(StaleWorkerNumbers.environment) is EnvironmentRecipeState.STALE
        old = next(item for item in inventory() if item["name"] == spec.name)
        self.retired_worker_pids = old["worker_pids"]
        self.preparations.clear()
        self.events.clear()
        self.release.clear()
        return old

    def evidence(self) -> dict[str, Any]:
        # Make a snapshot while callbacks may append from the execution thread.
        infos = inventory()
        requested = next((
            item["requested_recipe_hash"] for item in reversed(self.preparations)
            if item["name"] == StaleWorkerNumbers.environment.name
        ), None)
        info = next((item for item in infos if item["name"] == StaleWorkerNumbers.environment.name), None)
        state = (
            self.manager.inspect_environment(StaleWorkerNumbers.environment).value
            if requested is None else
            "missing" if info is None or info["state"] != "ready" else
            "current" if info["recipe_hash"] == requested else "stale"
        )
        alive: list[int] = []
        for pid in self.retired_worker_pids:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                continue
            alive.append(pid)
        return json.loads(json.dumps({
            "inventory": infos, "preparations": list(self.preparations),
            "events": list(self.events),
            "recipe_state": state,
            "retired_worker_pids": self.retired_worker_pids,
            "retired_workers_alive": alive,
        }))
