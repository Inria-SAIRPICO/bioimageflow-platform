"""Persistent registry and package-only inventory for local napari environments."""

from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import inspect
import json
import logging
import os
import shutil
import subprocess
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID, uuid4

from pydantic import ValidationError
from wetlands import (
    EnvironmentManager,
    EnvironmentSpec,
    ManagedEnvironmentState,
    Operation,
    OperationCanceled,
    OperationEvent,
)

from bioimageflow.env_manager import get_shared_environment_manager

from bioimageflow_server.models.napari_environments import (
    NapariEnvironment,
    NapariEnvironmentOperation,
    NapariEnvironmentOperationError,
    NapariEnvironmentInventory,
    NapariEnvironmentList,
    NapariFilenamePreview,
    NapariFilenameRule,
    NapariFilenameRuleCreate,
    NapariLaunchContext,
    NapariManagedEnvironmentCopy,
    NapariManagedEnvironmentCreate,
    NapariManagedMetadata,
    NapariManagedOperationMutation,
    NapariManagedRecipe,
)
from bioimageflow_server.services.environment_logging import log_environment_operation_event
from bioimageflow_server.services.operation_failures import (
    normalize_operation_text,
    operation_failure_detail,
)
from bioimageflow_server.services.settings_store import SettingsRevisionConflict, SettingsStore
from bioimageflow_server.services.viewer_preferences import ViewerPreferenceStore

if TYPE_CHECKING:
    from bioimageflow_server.services.napari_launcher import NapariLauncherPool


PROBE_TIMEOUT_SECONDS = 15.0
PROBE_OUTPUT_LIMIT = 1024 * 1024
_logger = logging.getLogger(__name__)

_PROBE_SCRIPT = r"""
import hashlib
import importlib.metadata as metadata
import json
import re
import sys

def canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()

packages = {}
for distribution in metadata.distributions():
    name = distribution.metadata.get("Name")
    if name:
        packages[canonical(name)] = distribution.version
ordered = [{"name": name, "version": packages[name]} for name in sorted(packages)]
payload = {
    "python_version": sys.version.split()[0],
    "napari_version": packages.get("napari"),
    "distributions": ordered,
}
for candidate in ("pyqt6", "pyqt5", "pyside6", "pyside2"):
    if candidate in packages:
        payload["qt_distribution"] = candidate
        payload["qt_version"] = packages[candidate]
        break
for candidate in ("bioimageflow-server", "bioimageflow"):
    if candidate in packages:
        payload["bridge_distribution"] = candidate
        payload["bridge_version"] = packages[candidate]
        break
payload["fingerprint"] = hashlib.sha256(
    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
"""


class NapariEnvironmentError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


ProbeRunner = Callable[[Sequence[str], dict[str, str], float, int], str]
EnvironmentManagerProvider = Callable[[], EnvironmentManager]
# Called again during restart recovery when finalization may have crossed a crash boundary.
# Integrations must therefore journal or otherwise implement this hook idempotently.
EnvironmentReferenceCleanup = Callable[[UUID], Any]


def _bounded_run(
    argv: Sequence[str], env: dict[str, str], timeout: float, output_limit: int
) -> str:
    try:
        process = subprocess.Popen(  # noqa: S603 - argv is resolved server-side
            list(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    except OSError as exc:
        raise NapariEnvironmentError("napari_probe_failed", str(exc)) from exc

    exceeded = threading.Event()
    captured: list[bytearray] = [bytearray(), bytearray()]

    def read_bounded(index: int) -> None:
        stream = process.stdout if index == 0 else process.stderr
        assert stream is not None
        while chunk := stream.read(65536):
            remaining = output_limit + 1 - len(captured[index])
            if remaining > 0:
                captured[index].extend(chunk[:remaining])
            if len(captured[index]) > output_limit:
                exceeded.set()
                try:
                    process.kill()
                except OSError:
                    pass
                return

    readers = [
        threading.Thread(target=read_bounded, args=(index,), daemon=True) for index in (0, 1)
    ]
    for reader in readers:
        reader.start()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        for reader in readers:
            reader.join(timeout=1)
        assert process.stdout is not None and process.stderr is not None
        process.stdout.close()
        process.stderr.close()
        raise NapariEnvironmentError(
            "napari_probe_timeout", f"environment probe exceeded {timeout:g} seconds"
        ) from exc
    for reader in readers:
        reader.join(timeout=1)
    assert process.stdout is not None and process.stderr is not None
    process.stdout.close()
    process.stderr.close()
    if exceeded.is_set():
        raise NapariEnvironmentError(
            "napari_probe_output_limit",
            f"environment probe exceeded the {output_limit}-byte output limit",
        )
    output = bytes(captured[0]).decode("utf-8", errors="replace")
    error = bytes(captured[1]).decode("utf-8", errors="replace").strip()
    if process.returncode != 0:
        raise NapariEnvironmentError(
            "napari_probe_failed", error or f"probe exited with status {process.returncode}"
        )
    return output


def _canonical_path(path: Path) -> str:
    return os.path.normcase(str(path.resolve(strict=True)))


def _launch_path(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def _interpreter_fingerprint(path: Path) -> str:
    stat = path.stat()
    material = (
        f"{_canonical_path(path)}\0{stat.st_dev}\0{stat.st_ino}\0{stat.st_size}\0{stat.st_mtime_ns}"
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _validate_pattern(pattern: str) -> str:
    value = pattern.strip()
    if not value:
        raise NapariEnvironmentError("invalid_filename_pattern", "filename pattern is empty")
    if "/" in value or "\\" in value:
        raise NapariEnvironmentError(
            "invalid_filename_pattern", "filename patterns cannot contain path separators"
        )
    if "**" in value:
        raise NapariEnvironmentError(
            "invalid_filename_pattern", "recursive ** patterns are not supported"
        )
    index = 0
    while index < len(value):
        if value[index] == "]":
            raise NapariEnvironmentError("invalid_filename_pattern", "unmatched ] in pattern")
        if value[index] != "[":
            index += 1
            continue
        closing = value.find("]", index + 1)
        if closing < 0 or closing == index + 1:
            raise NapariEnvironmentError("invalid_filename_pattern", "malformed character class")
        content = value[index + 1 : closing]
        if content == "!" or "[" in content:
            raise NapariEnvironmentError("invalid_filename_pattern", "malformed character class")
        index = closing + 1
    return value


def canonicalize_rule_value(value: str, mode: str) -> str:
    if mode == "pattern":
        return _validate_pattern(value)
    extension = value.strip()
    if extension.startswith("."):
        extension = extension[1:]
    if (
        not extension
        or any(character in extension for character in "*?[]/\\")
        or any(character.isspace() for character in extension)
    ):
        raise NapariEnvironmentError(
            "invalid_filename_extension", "extension must be a literal suffix such as .ome.tif"
        )
    return _validate_pattern(f"*.{extension}")


class NapariEnvironmentService:
    """Own registry invariants while persisting through the application settings store."""

    def __init__(
        self,
        store: SettingsStore,
        *,
        managed_singleton_roots: Sequence[Path] = (),
        conda_executable: str | None = None,
        probe_runner: ProbeRunner = _bounded_run,
        preference_store: ViewerPreferenceStore | None = None,
        environment_manager_provider: EnvironmentManagerProvider = get_shared_environment_manager,
        reference_cleanup: EnvironmentReferenceCleanup | None = None,
    ) -> None:
        self.store = store
        self.managed_singleton_roots = tuple(managed_singleton_roots)
        self.conda_executable = conda_executable
        self.probe_runner = probe_runner
        self.preference_store = preference_store
        self.environment_manager_provider = environment_manager_provider
        self.reference_cleanup = reference_cleanup
        self._launcher_pool: NapariLauncherPool | None = None
        self._wetlands_operations: dict[UUID, Operation[Any]] = {}
        self._operation_tasks: dict[UUID, asyncio.Task[None]] = {}
        self._environment_locks: dict[UUID, asyncio.Lock] = {}
        self._cancellation_requested: set[UUID] = set()

    def set_launcher_pool(self, launcher_pool: NapariLauncherPool) -> None:
        """Bind viewer lifecycle coordination after the app constructs the pool."""
        self._launcher_pool = launcher_pool

    def snapshot(self) -> NapariEnvironmentList:
        settings = self.store.get()
        environments = sorted(
            (self._with_current_interpreter_state(item) for item in settings.napari_environments),
            key=lambda item: item.registration_order,
        )
        return NapariEnvironmentList(
            revision=settings.napari_registry_revision,
            environments=environments,
            default_environment_id=settings.napari_default_environment_id,
            filename_rules=settings.napari_filename_rules,
            operations=settings.napari_environment_operations,
        )

    async def create_managed(
        self, request: NapariManagedEnvironmentCreate
    ) -> NapariManagedOperationMutation:
        return await self._begin_new_managed(
            name=request.name,
            recipe=request.recipe.resolved(),
            kind="create",
            expected_revision=request.expected_revision,
        )

    async def copy_managed(
        self, source_id: UUID, request: NapariManagedEnvironmentCopy
    ) -> NapariManagedOperationMutation:
        source = self._get(source_id)
        if (
            source.ownership != "managed"
            or source.managed is None
            or source.managed.recipe.source != "managed"
        ):
            raise NapariEnvironmentError(
                "napari_managed_copy_forbidden",
                "only recipe-created managed environments can be copied",
            )
        if source.state not in {"ready", "drifted"}:
            raise NapariEnvironmentError(
                "napari_managed_copy_unavailable", "the source environment is not ready"
            )
        recipe_data = source.managed.recipe.model_dump()
        changed_matrix = any(value is not None for value in (request.python, request.napari, request.qt))
        if request.python is not None:
            recipe_data["python"] = request.python
        if request.napari is not None:
            recipe_data["napari"] = request.napari
        if request.qt is not None:
            recipe_data["qt"] = request.qt
        if request.requested_packages is not None:
            recipe_data["requested_packages"] = request.requested_packages
        if changed_matrix:
            recipe_data["preset"] = "advanced"
        recipe = NapariManagedRecipe.model_validate(recipe_data)
        return await self._begin_new_managed(
            name=request.name,
            recipe=recipe,
            kind="copy",
            expected_revision=request.expected_revision,
        )

    async def retry_managed(
        self, environment_id: UUID, *, expected_revision: int
    ) -> NapariManagedOperationMutation:
        environment = self._get(environment_id)
        if (
            environment.ownership != "managed"
            or environment.managed is None
            or environment.managed.recipe.source != "managed"
        ):
            raise NapariEnvironmentError(
                "napari_managed_retry_forbidden",
                "only recipe-created managed environments can be retried",
            )
        if environment.state not in {"failed", "cancelled", "setup_needed"}:
            raise NapariEnvironmentError(
                "napari_managed_retry_unavailable",
                f"environment state {environment.state!r} cannot be retried",
            )
        latest = next(
            (
                operation
                for operation in reversed(self.store.get().napari_environment_operations)
                if operation.environment_id == environment_id
            ),
            None,
        )
        if latest is not None and latest.kind == "remove":
            raise NapariEnvironmentError(
                "napari_managed_retry_unavailable",
                "a failed deletion must be retried through managed DELETE",
            )
        self._require_no_active_operation(environment_id)
        operation = self._new_operation(environment_id, "retry", "Retry queued")
        updated = environment.model_copy(
            update={"state": "creating", "last_error": None, "inventory": None}
        )
        settings = self.store.get()
        await self._patch(
            expected_revision,
            {
                "napari_environments": [
                    updated if item.id == environment_id else item
                    for item in settings.napari_environments
                ],
                "napari_environment_operations": self._append_operation(
                    settings.napari_environment_operations, operation
                ),
            },
        )
        info = next(
            (
                item
                for item in self.environment_manager_provider().managed_environments()
                if item.name == environment.managed.wetlands_name
            ),
            None,
        )
        if info is not None and info.state is ManagedEnvironmentState.READY:
            self._operation_tasks[operation.id] = asyncio.create_task(
                self._recover_ready_environment(updated, operation),
                name=f"napari-recover-{environment_id}",
            )
        else:
            await self._start_provisioning(updated, operation)
        return self.managed_operation(environment_id, operation.id)

    async def remove_managed(
        self, environment_id: UUID, *, expected_revision: int
    ) -> NapariManagedOperationMutation:
        environment = self._get(environment_id)
        if (
            environment.ownership != "managed"
            or environment.managed is None
            or environment.managed.recipe.source != "managed"
        ):
            raise NapariEnvironmentError(
                "napari_managed_delete_forbidden",
                "only platform-created managed installations can be deleted; forget this entry instead",
            )
        self._require_no_active_operation(environment_id)
        operation = self._new_operation(
            environment_id, "remove", "Removal queued", state="removing"
        )
        updated = environment.model_copy(update={"state": "removing", "last_error": None})
        settings = self.store.get()
        await self._patch(
            expected_revision,
            {
                "napari_environments": [
                    updated if item.id == environment_id else item
                    for item in settings.napari_environments
                ],
                "napari_environment_operations": self._append_operation(
                    settings.napari_environment_operations, operation
                ),
            },
        )
        self._operation_tasks[operation.id] = asyncio.create_task(
            self._complete_removal(updated, operation),
            name=f"napari-remove-{environment_id}",
        )
        return self.managed_operation(environment_id, operation.id)

    def managed_operation(
        self, environment_id: UUID, operation_id: UUID
    ) -> NapariManagedOperationMutation:
        settings = self.store.get()
        operation = next(
            (
                item
                for item in settings.napari_environment_operations
                if item.id == operation_id and item.environment_id == environment_id
            ),
            None,
        )
        if operation is None:
            raise NapariEnvironmentError(
                "napari_operation_not_found", f"napari operation {operation_id} was not found"
            )
        environment = next(
            (item for item in settings.napari_environments if item.id == environment_id), None
        )
        return NapariManagedOperationMutation(
            revision=settings.napari_registry_revision,
            environment=environment,
            operation=operation,
        )

    async def cancel_managed_operation(
        self, environment_id: UUID, operation_id: UUID
    ) -> NapariManagedOperationMutation:
        mutation = self.managed_operation(environment_id, operation_id)
        if mutation.operation.state in {"completed", "failed", "cancelled"}:
            return mutation
        wetlands_operation = self._wetlands_operations.get(operation_id)
        if wetlands_operation is None:
            if operation_id in self._operation_tasks:
                self._cancellation_requested.add(operation_id)
                await self._update_operation(
                    operation_id,
                    message="Cancellation requested; waiting for the current step",
                )
                return self.managed_operation(environment_id, operation_id)
            raise NapariEnvironmentError(
                "napari_operation_not_live",
                "the operation did not survive process restart; reconcile or retry it",
            )
        if not wetlands_operation.cancel():
            return self.managed_operation(environment_id, operation_id)
        await self._update_operation(
            operation_id,
            message="Cancellation requested; waiting for cleanup",
        )
        return self.managed_operation(environment_id, operation_id)

    async def reconcile_managed_operations(self) -> None:
        """Reconcile persisted non-terminal operations without claiming live progress."""
        manager = self.environment_manager_provider()
        infos = {item.name: item for item in manager.managed_environments()}
        for operation in list(self.store.get().napari_environment_operations):
            if operation.state in {"completed", "failed", "cancelled"}:
                continue
            environment = next(
                (
                    item
                    for item in self.store.get().napari_environments
                    if item.id == operation.environment_id
                ),
                None,
            )
            if environment is None or environment.managed is None:
                await self._finish_operation_without_environment(
                    operation,
                    state="failed",
                    code="napari_operation_restart_unknown",
                    detail="operation ownership could not be recovered after restart",
                )
                continue
            info = infos.get(environment.managed.wetlands_name)
            if operation.kind == "remove" and info is None:
                await self._finalize_removed(environment, operation)
            elif (
                operation.kind != "remove"
                and info is not None
                and info.state is ManagedEnvironmentState.READY
            ):
                await self._recover_ready_environment(environment, operation)
            else:
                await self._finish_environment_operation(
                    environment,
                    operation,
                    environment_state="failed",
                    operation_state="failed",
                    code="napari_operation_interrupted",
                    detail="live progress did not survive process restart; retry is required",
                )

    async def close(self) -> None:
        """Request cancellation and await owned background operation tasks."""
        for operation in list(self._wetlands_operations.values()):
            operation.cancel()
        self._cancellation_requested.update(self._operation_tasks)
        tasks = list(self._operation_tasks.values())
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _begin_new_managed(
        self,
        *,
        name: str,
        recipe: NapariManagedRecipe,
        kind: Literal["create", "copy"],
        expected_revision: int,
    ) -> NapariManagedOperationMutation:
        settings = self.store.get()
        self._require_unique_name(name, settings.napari_environments)
        environment_id = uuid4()
        wetlands_name = f"napari-{environment_id.hex}"
        operation = self._new_operation(environment_id, kind, "Creation queued")
        environment = NapariEnvironment(
            id=environment_id,
            registration_order=max(
                (item.registration_order for item in settings.napari_environments), default=-1
            )
            + 1,
            name=name,
            ownership="managed",
            kind="conda",
            root=f"managed-pending:{wetlands_name}",
            interpreter="",
            interpreter_identity="",
            interpreter_fingerprint="",
            launch=NapariLaunchContext(strategy="wetlands-managed"),
            managed=NapariManagedMetadata(
                wetlands_name=wetlands_name,
                installation_generation=None,
                recipe=recipe,
            ),
            state="creating",
        )
        changes: dict[str, Any] = {
            "napari_environments": [*settings.napari_environments, environment],
            "napari_environment_operations": self._append_operation(
                settings.napari_environment_operations, operation
            ),
        }
        await self._patch(expected_revision, changes)
        await self._start_provisioning(environment, operation)
        return self.managed_operation(environment.id, operation.id)

    async def adopt_managed_singleton(self) -> None:
        settings = self.store.get()
        for root in self.managed_singleton_roots:
            try:
                resolved = self._resolve_installation(root)
            except NapariEnvironmentError:
                continue
            canonical_root = _canonical_path(resolved[0])
            if any(
                item.root.casefold() == canonical_root.casefold()
                for item in settings.napari_environments
            ):
                return
            name = "Default napari"
            suffix = 2
            existing_names = {item.name.casefold() for item in settings.napari_environments}
            while name.casefold() in existing_names:
                name = f"Default napari ({suffix})"
                suffix += 1
            environment = self._new_environment(
                name, *resolved, ownership="managed", wetlands_name="napari"
            )
            environments = [*settings.napari_environments, environment]
            await self._patch(
                settings.napari_registry_revision,
                {
                    "napari_environments": environments,
                    "napari_default_environment_id": settings.napari_default_environment_id
                    or environment.id,
                },
            )
            return

    async def _start_provisioning(
        self, environment: NapariEnvironment, platform_operation: NapariEnvironmentOperation
    ) -> None:
        assert environment.managed is not None
        manager = self.environment_manager_provider()
        try:
            wetlands_operation = manager.provision(
                environment.managed.wetlands_name,
                self._environment_spec(environment.managed.recipe),
                replace_existing=False,
            )
        except Exception as exc:  # noqa: BLE001 - converted to durable typed failure
            await self._finish_environment_operation(
                environment,
                platform_operation,
                environment_state="failed",
                operation_state="failed",
                code="napari_provision_failed",
                detail=operation_failure_detail(exc) or str(exc) or type(exc).__name__,
            )
            return
        self._wetlands_operations[platform_operation.id] = wetlands_operation
        await self._update_operation(
            platform_operation.id,
            environment_id=environment.id,
            state="resolving",
            progress=5,
            message="Resolving managed environment recipe",
            wetlands_operation_id=wetlands_operation.id,
        )
        loop = asyncio.get_running_loop()

        def receive(event: OperationEvent) -> None:
            loop.call_soon_threadsafe(
                lambda: asyncio.create_task(
                    self._record_wetlands_event(platform_operation.id, event)
                )
            )

        wetlands_operation.listen(receive)
        self._operation_tasks[platform_operation.id] = asyncio.create_task(
            self._complete_provisioning(environment, platform_operation, wetlands_operation),
            name=f"napari-provision-{environment.id}",
        )

    async def _complete_provisioning(
        self,
        environment: NapariEnvironment,
        platform_operation: NapariEnvironmentOperation,
        wetlands_operation: Operation[Any],
    ) -> None:
        lock = self._environment_locks.setdefault(environment.id, asyncio.Lock())
        async with lock:
            try:
                managed = await asyncio.to_thread(wetlands_operation.wait_for)
                resolved = self.environment_manager_provider().environment(
                    environment.managed.wetlands_name  # type: ignore[union-attr]
                )
                if Path(managed.path).resolve() != Path(resolved.path).resolve():
                    raise NapariEnvironmentError(
                        "napari_managed_generation_mismatch",
                        "provisioned environment does not match the published generation",
                    )
                await self._publish_validating_environment(environment, resolved)
                validating = self._get(environment.id)
                inventory = await asyncio.to_thread(self._probe_inventory, validating)
                ready = validating.model_copy(
                    update={"inventory": inventory, "state": "ready", "last_error": None}
                )
                await self._finish_environment_operation(
                    ready,
                    platform_operation,
                    environment_state="ready",
                    operation_state="completed",
                    detail="Managed napari environment is ready",
                )
            except OperationCanceled:
                await self._bind_observed_generation(environment.id)
                await self._finish_environment_operation(
                    self._get(environment.id),
                    platform_operation,
                    environment_state="cancelled",
                    operation_state="cancelled",
                    detail="Managed environment creation was cancelled",
                )
            except Exception as exc:  # noqa: BLE001 - persisted operational failure
                await self._bind_observed_generation(environment.id)
                await self._finish_environment_operation(
                    self._get(environment.id),
                    platform_operation,
                    environment_state="failed",
                    operation_state="failed",
                    code=(
                        exc.code
                        if isinstance(exc, NapariEnvironmentError)
                        else "napari_provision_failed"
                    ),
                    detail=(
                        exc.detail
                        if isinstance(exc, NapariEnvironmentError)
                        else operation_failure_detail(exc) or str(exc) or type(exc).__name__
                    ),
                )
            finally:
                self._wetlands_operations.pop(platform_operation.id, None)
                self._operation_tasks.pop(platform_operation.id, None)

    async def _publish_validating_environment(
        self, environment: NapariEnvironment, managed: Any
    ) -> None:
        root, kind, interpreter = self._resolve_managed_installation(Path(managed.path))
        try:
            generation = UUID(str(managed.generation_id))
        except (TypeError, ValueError) as exc:
            raise NapariEnvironmentError(
                "napari_managed_generation_invalid",
                "Wetlands published an invalid managed generation identity",
            ) from exc
        assert environment.managed is not None
        metadata = environment.managed.model_copy(
            update={"installation_generation": generation}
        )
        validating = environment.model_copy(
            update={
                "root": _canonical_path(root),
                "kind": kind,
                "interpreter": _launch_path(interpreter),
                "interpreter_identity": _canonical_path(interpreter),
                "interpreter_fingerprint": _interpreter_fingerprint(interpreter),
                "launch": self._launch_context(root, kind, interpreter, ownership="managed"),
                "managed": metadata,
                "state": "creating",
                "last_error": None,
            }
        )
        await self._replace_environment_internal(validating)
        await self._update_operation(
            environment_id=environment.id,
            operation_id=self._active_operation(environment.id).id,
            state="validating",
            progress=85,
            message="Validating installed distributions",
            wetlands_operation_id=None,
        )

    async def _complete_removal(
        self, environment: NapariEnvironment, platform_operation: NapariEnvironmentOperation
    ) -> None:
        lock = self._environment_locks.setdefault(environment.id, asyncio.Lock())
        async with lock:
            installation_removed = False
            try:
                if self._launcher_pool is None:
                    raise NapariEnvironmentError(
                        "napari_launcher_coordination_unavailable",
                        "napari launcher coordination is not configured",
                    )
                await self._launcher_pool.shutdown(environment.id)
                if platform_operation.id in self._cancellation_requested:
                    await self._finish_environment_operation(
                        environment,
                        platform_operation,
                        environment_state="ready",
                        operation_state="cancelled",
                        detail="Managed environment removal was cancelled",
                    )
                    return
                manager = self.environment_manager_provider()
                self._verify_owned_generation(environment, manager)
                assert environment.managed is not None
                wetlands_operation = manager.remove(environment.managed.wetlands_name)
                self._wetlands_operations[platform_operation.id] = wetlands_operation
                await self._update_operation(
                    operation_id=platform_operation.id,
                    environment_id=environment.id,
                    wetlands_operation_id=wetlands_operation.id,
                    message="Removing managed installation",
                    progress=25,
                )
                loop = asyncio.get_running_loop()

                def receive(event: OperationEvent) -> None:
                    loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(
                            self._record_wetlands_event(platform_operation.id, event)
                        )
                    )

                wetlands_operation.listen(receive)
                await asyncio.to_thread(wetlands_operation.wait_for)
                installation_removed = True
                await self._finalize_removed(environment, platform_operation)
            except OperationCanceled:
                await self._finish_environment_operation(
                    environment,
                    platform_operation,
                    environment_state="cancelled",
                    operation_state="cancelled",
                    detail="Managed environment removal was cancelled",
                )
            except Exception as exc:  # noqa: BLE001 - persisted operational failure
                if installation_removed:
                    detail = (
                        "managed installation was removed, but registry/reference cleanup "
                        f"is pending: {str(exc) or type(exc).__name__}"
                    )
                    try:
                        await self._update_operation(
                            platform_operation.id,
                            environment_id=environment.id,
                            state="removing",
                            message=detail,
                            error=NapariEnvironmentOperationError(
                                code="napari_remove_finalization_pending", detail=detail
                            ),
                        )
                    except Exception:  # noqa: BLE001 - original durable intent remains recoverable
                        _logger.exception("Could not record pending napari removal finalization")
                else:
                    await self._finish_environment_operation(
                        environment,
                        platform_operation,
                        environment_state="failed",
                        operation_state="failed",
                        code=(
                            exc.code
                            if isinstance(exc, NapariEnvironmentError)
                            else "napari_remove_failed"
                        ),
                        detail=(
                            exc.detail
                            if isinstance(exc, NapariEnvironmentError)
                            else operation_failure_detail(exc) or str(exc) or type(exc).__name__
                        ),
                    )
            finally:
                self._wetlands_operations.pop(platform_operation.id, None)
                self._operation_tasks.pop(platform_operation.id, None)
                self._cancellation_requested.discard(platform_operation.id)

    async def _recover_ready_environment(
        self, environment: NapariEnvironment, operation: NapariEnvironmentOperation
    ) -> None:
        try:
            managed = self.environment_manager_provider().environment(
                environment.managed.wetlands_name  # type: ignore[union-attr]
            )
            await self._publish_validating_environment(environment, managed)
            validating = self._get(environment.id)
            inventory = await asyncio.to_thread(self._probe_inventory, validating)
            ready = validating.model_copy(
                update={"inventory": inventory, "state": "ready", "last_error": None}
            )
            await self._finish_environment_operation(
                ready,
                operation,
                environment_state="ready",
                operation_state="completed",
                detail="Recovered and validated completed managed environment",
            )
        except Exception as exc:  # noqa: BLE001
            await self._finish_environment_operation(
                self._get(environment.id),
                operation,
                environment_state="failed",
                operation_state="failed",
                code="napari_restart_validation_failed",
                detail=str(exc) or type(exc).__name__,
            )
        finally:
            self._operation_tasks.pop(operation.id, None)

    async def _finalize_removed(
        self, environment: NapariEnvironment, operation: NapariEnvironmentOperation
    ) -> None:
        if self.reference_cleanup is not None:
            result = self.reference_cleanup(environment.id)
            if inspect.isawaitable(result):
                await result

        def mutation(settings: Any) -> dict[str, Any]:
            completed = self._operation_update(
                settings.napari_environment_operations,
                operation.id,
                state="completed",
                progress=100,
                message="Managed installation removed",
                error=None,
            )
            return {
                "napari_environments": [
                    item for item in settings.napari_environments if item.id != environment.id
                ],
                "napari_filename_rules": [
                    rule
                    for rule in settings.napari_filename_rules
                    if rule.environment_id != environment.id
                ],
                "napari_default_environment_id": (
                    None
                    if settings.napari_default_environment_id == environment.id
                    else settings.napari_default_environment_id
                ),
                "napari_environment_operations": completed,
            }

        await self.store.mutate_napari_registry(mutation)

    def _verify_owned_generation(
        self, environment: NapariEnvironment, manager: EnvironmentManager
    ) -> None:
        assert environment.managed is not None
        if environment.managed.installation_generation is None:
            raise NapariEnvironmentError(
                "napari_managed_ownership_unverified",
                "managed generation identity is unavailable; deletion is unsafe",
            )
        info = next(
            (
                item
                for item in manager.managed_environments()
                if item.name == environment.managed.wetlands_name
            ),
            None,
        )
        if info is None:
            raise NapariEnvironmentError(
                "napari_managed_generation_missing", "owned Wetlands environment is missing"
            )
        if (
            Path(info.path).resolve() != Path(environment.root).resolve()
            or info.generation_id != str(environment.managed.installation_generation)
        ):
            raise NapariEnvironmentError(
                "napari_managed_generation_mismatch",
                "Wetlands name, path, or generation no longer matches the owned registry entry",
            )

    async def _bind_observed_generation(self, environment_id: UUID) -> None:
        environment = self._get(environment_id)
        assert environment.managed is not None
        info = next(
            (
                item
                for item in self.environment_manager_provider().managed_environments()
                if item.name == environment.managed.wetlands_name and item.generation_id is not None
            ),
            None,
        )
        if info is None:
            return
        try:
            generation = UUID(info.generation_id)
            root, kind, interpreter = self._resolve_managed_installation(info.path)
        except (ValueError, NapariEnvironmentError):
            return
        bound = environment.model_copy(
            update={
                "root": _canonical_path(root),
                "kind": kind,
                "interpreter": _launch_path(interpreter),
                "interpreter_identity": _canonical_path(interpreter),
                "interpreter_fingerprint": _interpreter_fingerprint(interpreter),
                "launch": self._launch_context(root, kind, interpreter, ownership="managed"),
                "managed": environment.managed.model_copy(
                    update={"installation_generation": generation}
                ),
            }
        )
        await self._replace_environment_internal(bound)

    async def _record_wetlands_event(
        self, platform_operation_id: UUID, event: OperationEvent
    ) -> None:
        environment = getattr(event, "environment", None) or "napari"
        log_environment_operation_event(event, owner=f"Napari environment {environment}")
        operation = next(
            (
                item
                for item in self.store.get().napari_environment_operations
                if item.id == platform_operation_id
            ),
            None,
        )
        if operation is None or operation.state in {"completed", "failed", "cancelled"}:
            return
        if operation.kind == "remove":
            state = "removing"
            base_progress = 25
        else:
            state = "installing"
            base_progress = 10
        progress = base_progress
        if event.current is not None and event.maximum:
            progress = base_progress + round(
                (event.current / event.maximum) * (70 if operation.kind != "remove" else 60)
            )
        await self._update_operation(
            operation_id=platform_operation_id,
            environment_id=operation.environment_id,
            state=state,
            progress=min(progress, 80),
            message=normalize_operation_text(event.message),
            wetlands_operation_id=event.operation_id,
        )

    async def register(self, name: str, path: str, *, expected_revision: int) -> NapariEnvironment:
        root, kind, interpreter = self._resolve_installation(Path(path))
        settings = self.store.get()
        self._require_unique_name(name, settings.napari_environments)
        canonical_root = _canonical_path(root)
        if any(
            item.root.casefold() == canonical_root.casefold()
            for item in settings.napari_environments
        ):
            raise NapariEnvironmentError(
                "napari_environment_duplicate", "this Python environment is already registered"
            )
        environment = self._new_environment(name, root, kind, interpreter, ownership="external")
        changes: dict[str, Any] = {
            "napari_environments": [*settings.napari_environments, environment]
        }
        if settings.napari_default_environment_id is None:
            changes["napari_default_environment_id"] = environment.id
        await self._patch(expected_revision, changes)
        return environment

    async def update(
        self,
        environment_id: UUID,
        *,
        name: str | None = None,
        path: str | None = None,
        expected_revision: int,
    ) -> NapariEnvironment:
        settings = self.store.get()
        current = self._get(environment_id)
        candidate = current.model_copy(deep=True)
        if name is not None:
            self._require_unique_name(name, settings.napari_environments, exclude=environment_id)
            candidate.name = name.strip()
        if path is not None:
            if current.ownership != "external":
                raise NapariEnvironmentError(
                    "napari_managed_locate_forbidden", "managed environments cannot be relocated"
                )
            root, kind, interpreter = self._resolve_installation(Path(path))
            canonical_root = _canonical_path(root)
            if any(
                item.id != environment_id and item.root.casefold() == canonical_root.casefold()
                for item in settings.napari_environments
            ):
                raise NapariEnvironmentError(
                    "napari_environment_duplicate", "this Python environment is already registered"
                )
            candidate.root = _canonical_path(root)
            candidate.kind = kind
            candidate.interpreter = _launch_path(interpreter)
            candidate.interpreter_identity = _canonical_path(interpreter)
            candidate.interpreter_fingerprint = _interpreter_fingerprint(interpreter)
            candidate.launch = self._launch_context(root, kind, interpreter, ownership="external")
            candidate.inventory = None
            candidate.state = "ready"
            candidate.last_error = None
        environments = [
            candidate if item.id == environment_id else item
            for item in settings.napari_environments
        ]
        await self._patch(expected_revision, {"napari_environments": environments})
        return candidate

    async def forget(
        self, environment_id: UUID, *, expected_revision: int
    ) -> NapariEnvironmentList:
        settings = self.store.get()
        environment = self._get(environment_id)
        if settings.napari_registry_revision != expected_revision:
            raise NapariEnvironmentError(
                "napari_registry_revision_conflict",
                f"expected registry revision {expected_revision}, current is "
                f"{settings.napari_registry_revision}",
            )
        if (
            environment.managed is not None
            and environment.managed.recipe.source == "managed"
        ):
            raise NapariEnvironmentError(
                "napari_managed_forget_forbidden",
                "platform-created installations must use managed deletion",
            )
        self._require_no_active_operation(environment_id)
        environments = [item for item in settings.napari_environments if item.id != environment_id]
        rules = [
            rule for rule in settings.napari_filename_rules if rule.environment_id != environment_id
        ]
        changes = {
                "napari_environments": environments,
                "napari_filename_rules": rules,
                "napari_default_environment_id": (
                    None
                    if settings.napari_default_environment_id == environment_id
                    else settings.napari_default_environment_id
                ),
            }
        if self.preference_store is not None:
            self.preference_store.prepare_environment_forget(
                environment_id, registry_revision=expected_revision
            )
            self.preference_store.apply_prepared_environment_forget()
        try:
            await self._patch(expected_revision, changes)
        except Exception:
            # The durable journal intentionally remains for startup or retry
            # forward recovery; it is never rolled back to dangling state.
            raise
        if self.preference_store is not None:
            self.preference_store.complete_environment_forget()
        return self.snapshot()

    async def recover_pending_environment_forget(self) -> None:
        """Forward-complete a crash-interrupted registry/preference cleanup."""

        if self.preference_store is None:
            return
        journal = self.preference_store.pending_environment_forget()
        if journal is None:
            return
        environment_id = self.preference_store.apply_prepared_environment_forget()
        assert environment_id is not None
        settings = self.store.get()
        if any(item.id == environment_id for item in settings.napari_environments):
            environments = [
                item for item in settings.napari_environments if item.id != environment_id
            ]
            rules = [
                rule
                for rule in settings.napari_filename_rules
                if rule.environment_id != environment_id
            ]
            await self._patch(
                settings.napari_registry_revision,
                {
                    "napari_environments": environments,
                    "napari_filename_rules": rules,
                    "napari_default_environment_id": (
                        None
                        if settings.napari_default_environment_id == environment_id
                        else settings.napari_default_environment_id
                    ),
                },
            )
        self.preference_store.complete_environment_forget()

    async def set_default(
        self, environment_id: UUID | None, *, expected_revision: int
    ) -> NapariEnvironmentList:
        if environment_id is not None:
            self._get(environment_id)
        await self._patch(expected_revision, {"napari_default_environment_id": environment_id})
        return self.snapshot()

    async def probe(self, environment_id: UUID, *, expected_revision: int) -> NapariEnvironment:
        current = self._with_current_interpreter_state(self._get(environment_id))
        if current.state in {"missing", "replaced"}:
            await self._replace_environment(current, expected_revision=expected_revision)
            raise NapariEnvironmentError(
                f"napari_environment_{current.state}", current.last_error or current.state
            )
        argv = self._probe_argv(current)
        try:
            output = self.probe_runner(
                argv, self._probe_environment(), PROBE_TIMEOUT_SECONDS, PROBE_OUTPUT_LIMIT
            )
            raw = json.loads(output)
            inventory = NapariEnvironmentInventory(**raw, probed_at=datetime.now(UTC))
        except NapariEnvironmentError as exc:
            failed = current.model_copy(update={"state": "probe_failed", "last_error": exc.detail})
            await self._replace_environment(failed, expected_revision=expected_revision)
            raise
        except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
            failed = current.model_copy(
                update={"state": "probe_failed", "last_error": "probe returned invalid inventory"}
            )
            await self._replace_environment(failed, expected_revision=expected_revision)
            raise NapariEnvironmentError(
                "napari_probe_invalid", "probe returned invalid inventory"
            ) from exc
        drifted = (
            current.inventory is not None and current.inventory.fingerprint != inventory.fingerprint
        )
        updated = current.model_copy(
            update={
                "inventory": inventory,
                "state": "drifted" if drifted else "ready",
                "last_error": "installed distribution inventory changed" if drifted else None,
            }
        )
        await self._replace_environment(updated, expected_revision=expected_revision)
        return updated

    async def add_rule(self, request: NapariFilenameRuleCreate) -> NapariFilenameRule:
        self._get(request.environment_id)
        settings = self.store.get()
        pattern = canonicalize_rule_value(request.value, request.mode)
        self._require_unique_pattern(pattern, settings.napari_filename_rules)
        rule = NapariFilenameRule(
            id=uuid4(),
            pattern=pattern,
            environment_id=request.environment_id,
            enabled=request.enabled,
            reader_id=request.reader_id,
        )
        await self._patch(
            request.expected_revision,
            {"napari_filename_rules": [*settings.napari_filename_rules, rule]},
        )
        return rule

    async def replace_rules(
        self, rules: list[NapariFilenameRule], *, expected_revision: int
    ) -> NapariEnvironmentList:
        known = {item.id for item in self.store.get().napari_environments}
        seen: set[str] = set()
        normalized: list[NapariFilenameRule] = []
        for rule in rules:
            if rule.environment_id not in known:
                raise NapariEnvironmentError(
                    "napari_environment_not_found", "filename rule environment is not registered"
                )
            pattern = _validate_pattern(rule.pattern)
            folded = pattern.casefold()
            if folded in seen:
                raise NapariEnvironmentError(
                    "duplicate_filename_pattern", "filename rule pattern is duplicated"
                )
            seen.add(folded)
            normalized.append(rule.model_copy(update={"pattern": pattern}))
        await self._patch(expected_revision, {"napari_filename_rules": normalized})
        return self.snapshot()

    def preview(self, filename: str) -> NapariFilenamePreview:
        basename = PurePath(filename.rstrip("/\\")).name
        matching = [
            rule.id
            for rule in self.store.get().napari_filename_rules
            if rule.enabled and fnmatch.fnmatchcase(basename.casefold(), rule.pattern.casefold())
        ]
        return NapariFilenamePreview(
            filename=basename,
            matching_rule_ids=matching,
            winner_rule_id=matching[0] if matching else None,
        )

    async def _replace_environment(
        self, replacement: NapariEnvironment, *, expected_revision: int
    ) -> None:
        settings = self.store.get()
        await self._patch(
            expected_revision,
            {
                "napari_environments": [
                    replacement if item.id == replacement.id else item
                    for item in settings.napari_environments
                ]
            },
        )

    @staticmethod
    def _environment_spec(recipe: NapariManagedRecipe) -> EnvironmentSpec:
        if recipe.source != "managed":
            raise NapariEnvironmentError(
                "napari_managed_recipe_missing", "adopted environments have no install recipe"
            )
        assert recipe.python is not None and recipe.napari is not None and recipe.qt is not None
        return EnvironmentSpec(
            # The durable recipe uses PEP 440 (``==3.12.*``), while Pixi's
            # dependency table accepts a Conda version specifier without the
            # equality operator. Recipe validation already proves that the
            # constraint selects exactly Python 3.12.
            python="3.12.*",
            conda=(),
            pypi=(
                f"napari=={recipe.napari}",
                recipe.qt,
                *recipe.requested_packages,
            ),
            channels=tuple(recipe.channels),
        )

    def _probe_inventory(self, environment: NapariEnvironment) -> NapariEnvironmentInventory:
        output = self.probe_runner(
            self._probe_argv(environment),
            self._probe_environment(),
            PROBE_TIMEOUT_SECONDS,
            PROBE_OUTPUT_LIMIT,
        )
        try:
            raw = json.loads(output)
            return NapariEnvironmentInventory(**raw, probed_at=datetime.now(UTC))
        except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
            raise NapariEnvironmentError(
                "napari_probe_invalid", "probe returned invalid inventory"
            ) from exc

    @staticmethod
    def _new_operation(
        environment_id: UUID,
        kind: Literal["create", "copy", "retry", "remove"],
        message: str,
        *,
        state: Literal[
            "pending", "resolving", "installing", "validating", "removing"
        ] = "pending",
    ) -> NapariEnvironmentOperation:
        return NapariEnvironmentOperation(
            id=uuid4(),
            environment_id=environment_id,
            kind=kind,
            state=state,
            progress=0,
            message=message,
        )

    @staticmethod
    def _append_operation(
        operations: list[NapariEnvironmentOperation], operation: NapariEnvironmentOperation
    ) -> list[NapariEnvironmentOperation]:
        combined = [*operations, operation]
        if len(combined) <= 200:
            return combined
        terminal = {"completed", "failed", "cancelled"}
        for index, existing in enumerate(combined):
            if existing.state in terminal:
                return [*combined[:index], *combined[index + 1 :]]
        return combined

    @staticmethod
    def _operation_update(
        operations: list[NapariEnvironmentOperation],
        operation_id: UUID,
        **changes: Any,
    ) -> list[NapariEnvironmentOperation]:
        found = False
        updated: list[NapariEnvironmentOperation] = []
        for operation in operations:
            if operation.id != operation_id:
                updated.append(operation)
                continue
            found = True
            updated.append(
                NapariEnvironmentOperation.model_validate(
                    {
                        **operation.model_dump(),
                        **changes,
                        "updated_at": datetime.now(UTC),
                    }
                )
            )
        if not found:
            raise NapariEnvironmentError(
                "napari_operation_not_found", f"napari operation {operation_id} was not found"
            )
        return updated

    def _active_operation(self, environment_id: UUID) -> NapariEnvironmentOperation:
        for operation in reversed(self.store.get().napari_environment_operations):
            if operation.environment_id == environment_id and operation.state not in {
                "completed",
                "failed",
                "cancelled",
            }:
                return operation
        raise NapariEnvironmentError(
            "napari_operation_not_found", "environment has no active mutation"
        )

    def _require_no_active_operation(self, environment_id: UUID) -> None:
        if any(
            operation.environment_id == environment_id
            and operation.state not in {"completed", "failed", "cancelled"}
            for operation in self.store.get().napari_environment_operations
        ):
            raise NapariEnvironmentError(
                "napari_environment_mutation_active",
                "this environment already has an active mutation",
            )

    async def _update_operation(
        self,
        operation_id: UUID,
        *,
        environment_id: UUID | None = None,
        state: str | None = None,
        progress: int | None = None,
        message: str | None = None,
        error: NapariEnvironmentOperationError | None | object = ...,
        wetlands_operation_id: str | None | object = ...,
    ) -> None:
        def mutation(settings: Any) -> dict[str, Any]:
            current = next(
                (
                    item
                    for item in settings.napari_environment_operations
                    if item.id == operation_id
                ),
                None,
            )
            if current is None:
                return {}
            if environment_id is not None and current.environment_id != environment_id:
                return {}
            if current.state in {"completed", "failed", "cancelled"}:
                return {}
            changes: dict[str, Any] = {}
            if state is not None:
                changes["state"] = state
            if progress is not None:
                changes["progress"] = progress
            if message is not None:
                changes["message"] = message
            if error is not ...:
                changes["error"] = error
            if wetlands_operation_id is not ...:
                changes["wetlands_operation_id"] = wetlands_operation_id
            if not changes:
                return {}
            return {
                "napari_environment_operations": self._operation_update(
                    settings.napari_environment_operations, operation_id, **changes
                )
            }

        await self.store.mutate_napari_registry(mutation)

    async def _replace_environment_internal(self, replacement: NapariEnvironment) -> None:
        def mutation(settings: Any) -> dict[str, Any]:
            return {
                "napari_environments": [
                    replacement if item.id == replacement.id else item
                    for item in settings.napari_environments
                ]
            }

        await self.store.mutate_napari_registry(mutation)

    async def _finish_environment_operation(
        self,
        environment: NapariEnvironment,
        operation: NapariEnvironmentOperation,
        *,
        environment_state: str,
        operation_state: str,
        detail: str,
        code: str | None = None,
    ) -> None:
        error = (
            NapariEnvironmentOperationError(code=code, detail=detail)
            if code is not None
            else None
        )

        def mutation(settings: Any) -> dict[str, Any]:
            current = next(
                (item for item in settings.napari_environments if item.id == environment.id),
                None,
            )
            environments = settings.napari_environments
            if current is not None:
                runtime_fields = {
                    "root": environment.root,
                    "kind": environment.kind,
                    "interpreter": environment.interpreter,
                    "interpreter_identity": environment.interpreter_identity,
                    "interpreter_fingerprint": environment.interpreter_fingerprint,
                    "launch": environment.launch,
                    "managed": environment.managed,
                    "inventory": environment.inventory,
                    "state": environment_state,
                    "last_error": detail if error is not None else None,
                }
                replacement = current.model_copy(update=runtime_fields)
                environments = [
                    replacement if item.id == environment.id else item
                    for item in settings.napari_environments
                ]
            return {
                "napari_environments": environments,
                "napari_environment_operations": self._operation_update(
                    settings.napari_environment_operations,
                    operation.id,
                    state=operation_state,
                    progress=100 if operation_state == "completed" else operation.progress,
                    message=detail,
                    error=error,
                ),
            }

        await self.store.mutate_napari_registry(mutation)

    async def _finish_operation_without_environment(
        self,
        operation: NapariEnvironmentOperation,
        *,
        state: Literal["failed", "cancelled"],
        code: str,
        detail: str,
    ) -> None:
        def mutation(settings: Any) -> dict[str, Any]:
            return {
                "napari_environment_operations": self._operation_update(
                    settings.napari_environment_operations,
                    operation.id,
                    state=state,
                    message=detail,
                    error=NapariEnvironmentOperationError(code=code, detail=detail),
                )
            }

        await self.store.mutate_napari_registry(mutation)

    async def _patch(self, expected_revision: int, changes: dict[str, Any]) -> None:
        try:
            await self.store.patch_napari_registry(expected_revision, changes)
        except SettingsRevisionConflict as exc:
            raise NapariEnvironmentError("napari_registry_revision_conflict", str(exc)) from exc

    def _get(self, environment_id: UUID) -> NapariEnvironment:
        for environment in self.store.get().napari_environments:
            if environment.id == environment_id:
                return environment
        raise NapariEnvironmentError(
            "napari_environment_not_found", f"napari environment {environment_id} is not registered"
        )

    def _new_environment(
        self,
        name: str,
        root: Path,
        kind: Literal["conda", "venv"],
        interpreter: Path,
        *,
        ownership: Literal["external", "managed"],
        wetlands_name: str | None = None,
    ) -> NapariEnvironment:
        settings = self.store.get()
        managed = None
        if ownership == "managed":
            assert wetlands_name is not None
            managed = NapariManagedMetadata(
                wetlands_name=wetlands_name,
                installation_generation=uuid4(),
                recipe=NapariManagedRecipe(source="adopted"),
            )
        return NapariEnvironment(
            id=uuid4(),
            registration_order=max(
                (item.registration_order for item in settings.napari_environments), default=-1
            )
            + 1,
            name=name.strip(),
            ownership=ownership,
            kind=kind,
            root=_canonical_path(root),
            interpreter=_launch_path(interpreter),
            interpreter_identity=_canonical_path(interpreter),
            interpreter_fingerprint=_interpreter_fingerprint(interpreter),
            launch=self._launch_context(root, kind, interpreter, ownership=ownership),
            managed=managed,
        )

    def _resolve_installation(self, selected: Path) -> tuple[Path, Literal["conda", "venv"], Path]:
        selected = Path(os.path.abspath(selected.expanduser()))
        if selected.is_dir():
            root = selected
            candidates = [
                root / "bin" / "python",
                root / "bin" / "python3",
                root / "Scripts" / "python.exe",
                root / ".pixi" / "envs" / "default" / "bin" / "python",
                root / ".pixi" / "envs" / "default" / "bin" / "python3",
                root / ".pixi" / "envs" / "default" / "Scripts" / "python.exe",
            ]
            interpreter = next((candidate for candidate in candidates if candidate.is_file()), None)
            if interpreter is not None and ".pixi" in interpreter.parts:
                root = interpreter.parent.parent
        else:
            interpreter = selected if selected.is_file() else None
            root = selected.parent.parent
        if interpreter is None:
            raise NapariEnvironmentError(
                "napari_interpreter_not_found", "selected environment has no Python interpreter"
            )
        if not os.access(interpreter, os.X_OK):
            raise NapariEnvironmentError(
                "napari_interpreter_not_executable", "selected Python interpreter is not executable"
            )
        if (root / "conda-meta").is_dir():
            kind = "conda"
        elif (root / "pyvenv.cfg").is_file():
            kind = "venv"
        else:
            raise NapariEnvironmentError(
                "napari_environment_kind_unsupported",
                "selected interpreter is not in a Conda environment or Python virtual environment",
            )
        return root, kind, interpreter

    def _resolve_managed_installation(
        self, project_path: Path
    ) -> tuple[Path, Literal["conda"], Path]:
        """Resolve a Wetlands project while preserving its public owned path."""
        project = Path(os.path.abspath(project_path.expanduser()))
        if not project.is_dir():
            raise NapariEnvironmentError(
                "napari_managed_path_missing", "Wetlands managed environment path is missing"
            )
        prefix = project / ".pixi" / "envs" / "default"
        interpreter = next(
            (
                candidate
                for candidate in (
                    prefix / "bin" / "python",
                    prefix / "bin" / "python3",
                    prefix / "Scripts" / "python.exe",
                )
                if candidate.is_file()
            ),
            None,
        )
        if interpreter is None:
            raise NapariEnvironmentError(
                "napari_interpreter_not_found",
                "Wetlands managed environment has no Python interpreter",
            )
        if not (prefix / "conda-meta").is_dir():
            raise NapariEnvironmentError(
                "napari_environment_kind_unsupported",
                "Wetlands managed environment has no Conda prefix",
            )
        if not os.access(interpreter, os.X_OK):
            raise NapariEnvironmentError(
                "napari_interpreter_not_executable",
                "Wetlands managed Python interpreter is not executable",
            )
        return project, "conda", interpreter

    def _with_current_interpreter_state(self, environment: NapariEnvironment) -> NapariEnvironment:
        if environment.state in {
            "setup_needed",
            "creating",
            "failed",
            "cancelled",
            "removing",
        }:
            return environment
        interpreter = Path(environment.interpreter)
        if not interpreter.is_file():
            return environment.model_copy(
                update={"state": "missing", "last_error": "registered interpreter is missing"}
            )
        try:
            fingerprint = _interpreter_fingerprint(interpreter)
        except OSError:
            return environment.model_copy(
                update={"state": "missing", "last_error": "registered interpreter is unavailable"}
            )
        if fingerprint != environment.interpreter_fingerprint:
            return environment.model_copy(
                update={"state": "replaced", "last_error": "registered interpreter was replaced"}
            )
        return environment

    def _probe_argv(self, environment: NapariEnvironment) -> list[str]:
        return [*environment.launch.argv_prefix, "-I", "-s", "-c", _PROBE_SCRIPT]

    def _launch_context(
        self,
        root: Path,
        kind: Literal["conda", "venv"],
        interpreter: Path,
        *,
        ownership: Literal["external", "managed"],
    ) -> NapariLaunchContext:
        if ownership == "managed":
            return NapariLaunchContext(
                strategy="wetlands-managed", argv_prefix=[_launch_path(interpreter)]
            )
        if kind == "venv":
            return NapariLaunchContext(
                strategy="interpreter", argv_prefix=[_launch_path(interpreter)]
            )
        conda = self.conda_executable or shutil.which("conda")
        if conda is None:
            raise NapariEnvironmentError(
                "napari_conda_unavailable",
                "Conda launch context could not be resolved for this environment",
            )
        resolved_conda = _canonical_path(Path(conda))
        return NapariLaunchContext(
            strategy="conda-run",
            argv_prefix=[
                resolved_conda,
                "run",
                "--no-capture-output",
                "-p",
                _canonical_path(root),
                "python",
            ],
            conda_executable=resolved_conda,
        )

    @staticmethod
    def _probe_environment() -> dict[str, str]:
        keep = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL"}
        environment = {key: value for key, value in os.environ.items() if key in keep}
        environment["PYTHONNOUSERSITE"] = "1"
        environment["PYTHONHASHSEED"] = "0"
        return environment

    @staticmethod
    def _require_unique_name(
        name: str, environments: list[NapariEnvironment], *, exclude: UUID | None = None
    ) -> None:
        normalized = name.strip().casefold()
        if not normalized:
            raise NapariEnvironmentError("invalid_environment_name", "environment name is empty")
        if any(item.id != exclude and item.name.casefold() == normalized for item in environments):
            raise NapariEnvironmentError(
                "duplicate_environment_name", "environment names must be unique ignoring case"
            )

    @staticmethod
    def _require_unique_pattern(pattern: str, rules: list[NapariFilenameRule]) -> None:
        if any(rule.pattern.casefold() == pattern.casefold() for rule in rules):
            raise NapariEnvironmentError(
                "duplicate_filename_pattern", "filename rule pattern is already registered"
            )
