"""Manual lifecycle controls for tool Wetlands environments."""

from __future__ import annotations

import asyncio
import logging
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

    @property
    def _manager(self) -> Any:
        if self._wetlands is None:
            from bioimageflow.env_manager import WetlandsEnvManager

            self._wetlands = WetlandsEnvManager()
        return self._wetlands

    @property
    def manager(self) -> Any:
        """Return the shared Wetlands manager used by manual and automatic runs."""
        return self._manager

    async def start(self, env_name: str) -> str:
        tools = self._tools_for_environment(env_name)
        if not tools:
            self._publish(env_name, "creating")
            return "creating"
        spec = next((self._environment_spec(tool) for tool in tools), None)
        if spec is None:
            self._publish(env_name, "stopped")
            return "stopped"
        self._require_processing_replacement_allowed(env_name)
        state = await anyio_to_thread.run_sync(self._manager.inspect_environment, spec)
        status = "updating" if state is EnvironmentRecipeState.STALE else "creating"
        self._set_status(tools, status)
        self._publish(env_name, status)
        await anyio_to_thread.run_sync(
            lambda: self._manager.get_or_create(
                spec,
                replace_existing=state is EnvironmentRecipeState.STALE,
                on_provision_event=self._log_provision_event,
            )
        )
        self._set_status(tools, "running")
        self._publish(env_name, "running")
        return "running"

    async def recreate(self, env_name: str) -> str:
        tools = self._tools_for_environment(env_name)
        spec = next((self._environment_spec(tool) for tool in tools), None)
        if spec is None:
            self._publish(env_name, "stopped")
            return "stopped"
        self._require_processing_replacement_allowed(env_name)
        self._set_status(tools, "updating")
        self._publish(env_name, "updating")
        try:
            await anyio_to_thread.run_sync(
                self._recreate_wetlands_environment,
                spec,
            )
        except Exception:
            self._set_status(tools, "failed")
            self._publish(env_name, "failed")
            raise
        self._set_status(tools, "running")
        self._publish(env_name, "running")
        return "running"

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
        self._standard_refresh_task = None
        if task is None:
            return
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _refresh_standard_environment(self) -> None:
        env_name = GENERAL_ENV.name
        try:
            self._require_processing_replacement_allowed(env_name)
            state = await anyio_to_thread.run_sync(
                self._manager.inspect_environment,
                GENERAL_ENV,
            )
            if state is not EnvironmentRecipeState.STALE:
                return
            tools = self._tools_for_environment(env_name)
            self._set_status(tools, "updating")
            self._publish(env_name, "updating")
            await anyio_to_thread.run_sync(
                lambda: self._manager.get_or_create(
                    GENERAL_ENV,
                    replace_existing=True,
                    on_provision_event=self._log_provision_event,
                )
            )
            self._set_status(tools, "running")
            self._publish(env_name, "running")
        except asyncio.CancelledError:
            raise
        except Exception:
            tools = self._tools_for_environment(env_name)
            self._set_status(tools, "failed")
            self._publish(env_name, "failed")
            logger.exception("Failed to refresh the bioimageflow-general environment")

    async def stop(self, env_name: str) -> str:
        tools = self._tools_for_environment(env_name)
        await anyio_to_thread.run_sync(self._stop_wetlands_environment, env_name)
        self._set_status(tools, "stopped")
        self._publish(env_name, "stopped")
        return "stopped"

    def _tools_for_environment(self, env_name: str) -> list[Any]:
        matches = []
        for tool in self._registry.list_tools():
            tool_env_name = None
            if tool.environment:
                tool_env_name = str(tool.environment.get("name") or "")
            if env_name in {tool_env_name, tool.name, tool.package}:
                matches.append(tool)
        return matches

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
        return EnvironmentSpec(name=name, dependencies=dependencies)

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

    def _stop_wetlands_environment(self, env_name: str) -> None:
        self._manager.stop(env_name)

    def _recreate_wetlands_environment(self, spec: EnvironmentSpec) -> None:
        self._stop_wetlands_environment(spec.name)
        self._manager.get_or_create(
            spec,
            replace_existing=True,
            on_provision_event=self._log_provision_event,
        )

    @staticmethod
    def _log_provision_event(event: Any) -> None:
        environment = getattr(event, "environment", None)
        owner = f"Environment {environment}" if isinstance(environment, str) else "Environment"
        log_environment_operation_event(event, owner=owner)
