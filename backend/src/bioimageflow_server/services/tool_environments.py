"""Manual lifecycle controls for tool Wetlands environments."""

from __future__ import annotations

from pathlib import Path
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
        connection_manager: Any = None,
        wetlands_manager: Any = None,
    ) -> None:
        self._registry = registry
        self._catalog = catalog
        self._connection_manager = connection_manager
        self._wetlands = wetlands_manager

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
        self._set_status(tools, "creating")
        self._publish(env_name, "creating")
        await anyio_to_thread.run_sync(self._manager.get_or_create, spec)
        self._set_status(tools, "running")
        self._publish(env_name, "running")
        return "running"

    async def recreate(self, env_name: str) -> str:
        tools = self._tools_for_environment(env_name)
        spec = next((self._environment_spec(tool) for tool in tools), None)
        if spec is None:
            self._publish(env_name, "stopped")
            return "stopped"
        self._set_status(tools, "creating")
        self._publish(env_name, "creating")
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

    async def stop(self, env_name: str) -> str:
        tools = self._tools_for_environment(env_name)
        await anyio_to_thread.run_sync(self._stop_wetlands_environment, env_name)
        self._set_status(tools, "stopped")
        self._publish(env_name, "stopped")
        return "stopped"

    async def delete(
        self,
        env_name: str,
        *,
        expected_path: str,
        expected_existing_hash: str,
    ) -> str:
        tools = self._tools_for_environment(env_name)
        if not tools:
            raise FileNotFoundError(
                f"Environment '{env_name}' is not associated with a registered tool"
            )
        await anyio_to_thread.run_sync(
            self._delete_wetlands_environment,
            env_name,
            expected_path,
            expected_existing_hash,
        )
        self._set_status(tools, "stopped")
        self._publish(env_name, "stopped")
        return "deleted"

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
        manager = getattr(self._manager, "_manager", None)
        managed_environments = getattr(manager, "managed_environments", None)
        if callable(managed_environments):
            info = next(
                (candidate for candidate in managed_environments() if candidate.name == env_name),
                None,
            )
            if info is not None:
                return str(Path(info.path).expanduser().resolve())
        environments_root = getattr(manager, "environments_root", None)
        if environments_root is None:
            return None
        return str((Path(environments_root) / env_name).expanduser().resolve())

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

    def _publish(self, env_name: str, status: str) -> None:
        if self._connection_manager is None:
            return
        publish = getattr(self._connection_manager, "publish_environment_status", None)
        if callable(publish):
            publish(env_name, status)

    def _stop_wetlands_environment(self, env_name: str) -> None:
        stop = getattr(self._manager, "stop", None)
        if not callable(stop):
            raise RuntimeError("Wetlands environment manager does not support stop()")
        stop(env_name)

    def _recreate_wetlands_environment(self, spec: EnvironmentSpec) -> None:
        wetlands = self._manager
        manager = getattr(wetlands, "_manager", None)
        provision = getattr(manager, "provision", None)
        to_wetlands_spec = getattr(wetlands, "_to_wetlands_spec", None)
        if not callable(provision) or not callable(to_wetlands_spec):
            raise RuntimeError("Wetlands environment manager does not support replacement")

        self._stop_wetlands_environment(spec.name)
        operation = provision(
            spec.name,
            to_wetlands_spec(spec),
            replace_existing=True,
        )
        wait_for = getattr(operation, "wait_for", None)
        if not callable(wait_for):
            raise RuntimeError("Wetlands provisioning operation does not support wait_for()")
        wait_for()
        wetlands.get_or_create(spec)

    def _delete_wetlands_environment(
        self,
        env_name: str,
        expected_path: str,
        expected_existing_hash: str,
    ) -> None:
        wetlands = self._manager
        manager = getattr(wetlands, "_manager", None)
        managed_environments = getattr(manager, "managed_environments", None)
        remove = getattr(manager, "remove", None)
        if not callable(managed_environments) or not callable(remove):
            raise RuntimeError("Wetlands environment manager does not support managed removal")

        info = next(
            (candidate for candidate in managed_environments() if candidate.name == env_name),
            None,
        )
        if info is None:
            raise FileNotFoundError(f"Managed environment '{env_name}' does not exist")
        if Path(expected_path).expanduser().resolve() != Path(info.path).expanduser().resolve():
            raise PermissionError(
                "Environment deletion was refused because the recovery path no longer "
                "matches the default managed environment path."
            )
        if not info.ready:
            raise PermissionError(
                "Environment deletion was refused because Wetlands metadata is unavailable."
            )
        if info.recipe_hash != expected_existing_hash:
            raise PermissionError(
                "Environment deletion was refused because the environment recipe changed. "
                "Retry the run to refresh the recovery details."
            )

        self._stop_wetlands_environment(env_name)
        operation = remove(env_name)
        wait_for = getattr(operation, "wait_for", None)
        if not callable(wait_for):
            raise RuntimeError("Wetlands removal operation does not support wait_for()")
        wait_for()
