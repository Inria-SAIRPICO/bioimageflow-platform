"""Manual lifecycle controls for tool Wetlands environments."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ContextManager, cast

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
        wetlands = self._manager
        envs = getattr(wetlands, "_envs", None)
        if isinstance(envs, dict):
            env = envs.pop(env_name, None)
            if env is not None and hasattr(env, "exit"):
                env.exit()
        hashes = getattr(wetlands, "_env_hashes", None)
        if isinstance(hashes, dict):
            hashes.pop(env_name, None)
        configs = getattr(wetlands, "_launch_configs", None)
        if isinstance(configs, dict):
            configs.pop(env_name, None)

    def _delete_wetlands_environment(
        self,
        env_name: str,
        expected_path: str,
        expected_existing_hash: str,
    ) -> None:
        wetlands = self._manager
        lock = getattr(wetlands, "_lock", None)
        if lock is not None and hasattr(lock, "__enter__") and hasattr(lock, "__exit__"):
            context_lock = cast(ContextManager[None], lock)
            with context_lock:
                self._delete_wetlands_environment_locked(
                    wetlands, env_name, expected_path, expected_existing_hash
                )
            return
        self._delete_wetlands_environment_locked(
            wetlands, env_name, expected_path, expected_existing_hash
        )

    def _delete_wetlands_environment_locked(
        self,
        wetlands: Any,
        env_name: str,
        expected_path: str,
        expected_existing_hash: str,
    ) -> None:
        self._validate_recovery_context(
            wetlands,
            env_name,
            expected_path=expected_path,
            expected_existing_hash=expected_existing_hash,
        )
        envs = getattr(wetlands, "_envs", None)
        env = envs.get(env_name) if isinstance(envs, dict) else None
        if env is None:
            manager = getattr(wetlands, "_manager", None)
            load = getattr(manager, "load", None)
            if not callable(load):
                raise RuntimeError("Wetlands environment manager does not support load()")
            env = load(env_name)

        delete = getattr(env, "delete", None)
        if not callable(delete):
            raise RuntimeError(f"Environment '{env_name}' does not support deletion")
        delete()

        if isinstance(envs, dict):
            envs.pop(env_name, None)
        hashes = getattr(wetlands, "_env_hashes", None)
        if isinstance(hashes, dict):
            hashes.pop(env_name, None)
        configs = getattr(wetlands, "_launch_configs", None)
        if isinstance(configs, dict):
            configs.pop(env_name, None)

    def _validate_recovery_context(
        self,
        wetlands: Any,
        env_name: str,
        *,
        expected_path: str,
        expected_existing_hash: str,
    ) -> None:
        manager = getattr(wetlands, "_manager", None)
        settings_manager = getattr(manager, "settings_manager", None)
        default_path_for_name = getattr(settings_manager, "get_environment_path_from_name", None)
        if not callable(default_path_for_name):
            raise RuntimeError("Wetlands environment manager cannot resolve environment paths")

        default_path_value = default_path_for_name(env_name)
        if not isinstance(default_path_value, (str, Path)):
            raise RuntimeError("Wetlands environment manager returned an invalid path")
        default_path = Path(default_path_value)
        if Path(expected_path).expanduser().resolve() != default_path.expanduser().resolve():
            raise PermissionError(
                "Environment deletion was refused because the recovery path no longer "
                "matches the default managed environment path."
            )

        from wetlands._internal.environment_metadata import read_environment_metadata

        metadata, reason = read_environment_metadata(
            default_path,
            use_pixi=bool(getattr(settings_manager, "use_pixi", True)),
        )
        if metadata is None:
            raise PermissionError(
                "Environment deletion was refused because Wetlands metadata is "
                f"{reason or 'unavailable'}."
            )
        if metadata.get("recipe_hash") != expected_existing_hash:
            raise PermissionError(
                "Environment deletion was refused because the environment recipe changed. "
                "Retry the run to refresh the recovery details."
            )
