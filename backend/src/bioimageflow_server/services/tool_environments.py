"""Manual lifecycle controls for tool Wetlands environments."""

from __future__ import annotations

from typing import Any

import anyio.to_thread as anyio_to_thread
from bioimageflow_core.environment import EnvironmentSpec

from bioimageflow_server.services.tool_registry import ToolRegistryService


class ToolEnvironmentService:
    def __init__(
        self,
        *,
        registry: ToolRegistryService,
        catalog: Any = None,
        wetlands_manager: Any = None,
    ) -> None:
        self._registry = registry
        self._catalog = catalog
        self._wetlands = wetlands_manager

    @property
    def _manager(self) -> Any:
        if self._wetlands is None:
            from bioimageflow.env_manager import WetlandsEnvManager

            self._wetlands = WetlandsEnvManager()
        return self._wetlands

    async def start(self, env_name: str) -> str:
        tools = self._tools_for_environment(env_name)
        if not tools:
            return "creating"
        self._set_status(tools, "creating")
        spec = self._environment_spec(tools[0])
        if spec is not None:
            await anyio_to_thread.run_sync(self._manager.get_or_create, spec)
        self._set_status(tools, "running")
        return "running"

    async def stop(self, env_name: str) -> str:
        tools = self._tools_for_environment(env_name)
        await anyio_to_thread.run_sync(self._stop_wetlands_environment, env_name)
        self._set_status(tools, "stopped")
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

    def _environment_spec(self, tool: Any) -> EnvironmentSpec | None:
        if not tool.environment:
            return None
        name = str(tool.environment.get("name") or "")
        dependencies = tool.environment.get("dependencies") or {}
        if not name:
            return None
        return EnvironmentSpec(name=name, dependencies=dependencies)

    def _set_status(self, tools: list[Any], status: str) -> None:
        for package_name in {tool.package for tool in tools}:
            package = self._registry.get_package(package_name)
            if package is not None:
                package.environment_status = status
            if self._catalog is not None and hasattr(self._catalog, "update_environment_status"):
                self._catalog.update_environment_status(package_name, status)

    def _stop_wetlands_environment(self, env_name: str) -> None:
        if self._wetlands is None:
            return
        envs = getattr(self._wetlands, "_envs", None)
        if isinstance(envs, dict):
            env = envs.pop(env_name, None)
            if env is not None and hasattr(env, "exit"):
                env.exit()
        hashes = getattr(self._wetlands, "_env_hashes", None)
        if isinstance(hashes, dict):
            hashes.pop(env_name, None)
        configs = getattr(self._wetlands, "_launch_configs", None)
        if isinstance(configs, dict):
            configs.pop(env_name, None)
