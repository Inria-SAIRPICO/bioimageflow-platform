"""Manual lifecycle controls for tool Wetlands environments."""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import Any, Callable

import anyio.to_thread as anyio_to_thread
from bioimageflow import EnvironmentRecipeState
from bioimageflow_core.environment import GENERAL_ENV, EnvironmentSpec

from bioimageflow_server.services.environment_logging import log_environment_operation_event
from bioimageflow_server.services.tool_registry import ToolRegistryService

logger = logging.getLogger(__name__)


class ToolEnvironmentService:
    def __init__(
        self,
        *,
        registry: ToolRegistryService,
        catalog: Any = None,
        connection_manager: Any = None,
        wetlands_manager: Any = None,
        managed_environment_manager: Any = None,
        protected_environment_names: Callable[[], set[str]] | None = None,
    ) -> None:
        self._registry = registry
        self._catalog = catalog
        self._connection_manager = connection_manager
        self._wetlands = wetlands_manager
        self._managed_environments = managed_environment_manager
        self._protected_environment_names = protected_environment_names
        self._standard_refresh_task: asyncio.Task[None] | None = None
        self._processing_environment_lock = threading.RLock()

    @property
    def processing_environment_lock(self) -> Any:
        """Coordinate automatic startup preparation with execution submission."""
        return self._processing_environment_lock

    @property
    def _manager(self) -> Any:
        if self._wetlands is None:
            with self.processing_environment_lock:
                if self._wetlands is None:
                    from bioimageflow.env_manager import WetlandsEnvManager

                    self._wetlands = WetlandsEnvManager()
        return self._wetlands

    @property
    def manager(self) -> Any:
        """Return the shared Wetlands manager used by manual and automatic runs."""
        return self._manager

    async def start(self, env_name: str) -> str:
        return await anyio_to_thread.run_sync(self._mutate_environment, env_name, "start")

    async def recreate(self, env_name: str) -> str:
        return await anyio_to_thread.run_sync(self._mutate_environment, env_name, "recreate")

    async def stop(self, env_name: str) -> str:
        return await anyio_to_thread.run_sync(self._mutate_environment, env_name, "stop")

    def _mutate_environment(self, env_name: str, action: str) -> str:
        with self.processing_environment_lock:
            # Read authority only after queued automatic preparation completes.
            # Policy refusal precedes the operational failure/status boundary.
            tools, spec = self._resolve_environment(env_name)
            self._require_processing_replacement_allowed(env_name)
            try:
                if action == "stop":
                    self._manager.stop(env_name)
                    if self._manager.is_running(env_name):
                        raise RuntimeError(f"Environment {env_name!r} shutdown remains pending")
                    status = "stopped"
                elif action == "recreate":
                    self._set_status(tools, "updating")
                    self._publish(env_name, "updating")
                    self._manager.recreate(
                        spec, on_provision_event=self._log_provision_event,
                        on_removal_event=self._log_provision_event,
                    )
                    status = "running"
                else:
                    state = self._manager.inspect_environment(spec)
                    if state is EnvironmentRecipeState.CURRENT:
                        status = "running" if self._manager.is_running(env_name) else "ready"
                    else:
                        status = "updating" if state is EnvironmentRecipeState.STALE else "creating"
                    self._set_status(tools, status)
                    self._publish(env_name, status)
                    self._manager.get_or_create(
                        spec, replace_existing=state is EnvironmentRecipeState.STALE,
                        on_provision_event=self._log_provision_event,
                        on_removal_event=self._log_provision_event,
                    )
                    status = "running"
            except Exception:
                self._set_status(tools, "failed")
                self._publish(env_name, "failed")
                raise
            self._set_status(tools, status)
            self._publish(env_name, status)
            return status

    def start_standard_environment_refresh(self) -> None:
        """Warm an already-existing stale general processing environment."""

        if self._standard_refresh_task is not None and not self._standard_refresh_task.done():
            return
        self._standard_refresh_task = asyncio.create_task(
            self._refresh_standard_environment(),
            name="bioimageflow-general-refresh",
        )

    async def close(self) -> None:
        task = self._standard_refresh_task
        try:
            if task is not None:
                try:
                    # A thread-backed public mutation must finish before its
                    # pool owner can be shut down; cancelling its awaiter is
                    # not an operation-completion fence.
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    if not task.done():
                        raise
                self._standard_refresh_task = None
        finally:
            # Shutdown owns only an already-created processing manager.
            # Its public close fence keeps uncertain pools/grants for retry.
            if self._wetlands is not None and (task is None or task.done()):
                await anyio_to_thread.run_sync(self._wetlands.shutdown_all)

    async def _refresh_standard_environment(self) -> None:
        env_name = GENERAL_ENV.name
        try:
            await anyio_to_thread.run_sync(self._refresh_standard_environment_sync)
        except asyncio.CancelledError:
            raise
        except Exception:
            tools = self._tools_for_environment(env_name)
            self._set_status(tools, "failed")
            self._publish(env_name, "failed")
            logger.exception("Failed to refresh the bioimageflow-general environment")

    def _refresh_standard_environment_sync(self) -> None:
        # Acquire and release in the worker thread; never hold this guard on
        # the event loop while awaiting an offloaded manager operation.
        with self.processing_environment_lock:
            self._require_processing_replacement_allowed(GENERAL_ENV.name)
            if self._manager.inspect_environment(GENERAL_ENV) is not EnvironmentRecipeState.STALE:
                return
            tools = self._tools_for_environment(GENERAL_ENV.name)
            self._set_status(tools, "updating")
            self._publish(GENERAL_ENV.name, "updating")
            self._manager.admit_runtime(
                GENERAL_ENV, provision=True, replace_stale=True,
                on_provision_event=self._log_provision_event,
                on_removal_event=self._log_provision_event,
            )
            self._set_status(tools, "ready")
            self._publish(GENERAL_ENV.name, "ready")

    def _tools_for_environment(self, env_name: str) -> list[Any]:
        return [
            tool for tool in self._registry.list_tools()
            if tool.environment and tool.environment.get("name") == env_name
        ]

    def _resolve_environment(self, env_name: str) -> tuple[list[Any], EnvironmentSpec]:
        tools = self._tools_for_environment(env_name)
        if not tools:
            raise ValueError(f"Use a declared environment name; unknown environment {env_name!r}")
        specs = [self._environment_spec(tool) for tool in tools]
        spec = specs[0]
        if spec is None or any(candidate != spec for candidate in specs[1:]):
            raise ValueError(f"Conflicting declarations for environment {env_name!r}")
        return tools, spec

    def location(self, env_name: str) -> str | None:
        """Return the managed location for an environment, including before creation."""
        manager = self._managed_environments
        if manager is None:
            # Construct the BioImageFlow wrapper first so it configures the
            # process-wide Wetlands root before the public manager is requested.
            _ = self.manager
            from bioimageflow.env_manager import get_shared_environment_manager

            manager = self._managed_environments = get_shared_environment_manager()
        info = next(
            (
                candidate
                for candidate in manager.managed_environments()
                if candidate.name == env_name
            ),
            None,
        )
        if info is not None:
            return str(Path(info.path).expanduser().resolve())
        return str((Path(manager.environments_root) / env_name).expanduser().resolve())

    def _environment_spec(self, tool: Any) -> EnvironmentSpec | None:
        if not tool.environment:
            return None
        name = str(tool.environment.get("name") or "")
        dependencies = tool.environment.get("dependencies") or {}
        if not name:
            return None
        return EnvironmentSpec(
            name=name, dependencies=dependencies,
            allow_flexible_versions=tool.environment.get("allow_flexible_versions", False),
        )

    def can_replace_processing_environment(self, env_spec: Any) -> bool:
        name = getattr(env_spec, "name", None)
        return isinstance(name, str) and bool(name) and not self._is_protected(name)

    def _is_protected(self, env_name: str) -> bool:
        protected = {"napari", "codeserver", "thumbnail"}
        if self._protected_environment_names is not None:
            protected.update(self._protected_environment_names())
        return env_name in protected

    def _require_processing_replacement_allowed(self, env_name: str) -> None:
        if self._is_protected(env_name):
            raise PermissionError(
                f"Environment '{env_name}' is owned by another platform lifecycle"
            )

    def _set_status(self, tools: list[Any], status: str) -> None:
        for package_name in {tool.package for tool in tools}:
            package = self._registry.get_package(package_name)
            if package is not None:
                package.environment_status = status
            if self._catalog is not None and hasattr(self._catalog, "update_environment_status"):
                self._catalog.update_environment_status(package_name, status)

    def _publish(self, env_name: str, status: str) -> None:
        if self._connection_manager is None:
            return
        publish = getattr(self._connection_manager, "publish_environment_status", None)
        if callable(publish):
            publish(env_name, status)

    @staticmethod
    def _log_provision_event(event: Any) -> None:
        environment = getattr(event, "environment", None)
        owner = f"Environment {environment}" if isinstance(environment, str) else "Environment"
        log_environment_operation_event(event, owner=owner)
