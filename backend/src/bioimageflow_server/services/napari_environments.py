"""Persistent registry and package-only inventory for local napari environments."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import ValidationError

from bioimageflow_server.models.napari_environments import (
    NapariEnvironment,
    NapariEnvironmentInventory,
    NapariEnvironmentList,
    NapariFilenamePreview,
    NapariFilenameRule,
    NapariFilenameRuleCreate,
    NapariLaunchContext,
    NapariManagedMetadata,
    NapariManagedRecipe,
)
from bioimageflow_server.services.settings_store import SettingsRevisionConflict, SettingsStore
from bioimageflow_server.services.viewer_preferences import ViewerPreferenceStore


PROBE_TIMEOUT_SECONDS = 15.0
PROBE_OUTPUT_LIMIT = 1024 * 1024

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
    ) -> None:
        self.store = store
        self.managed_singleton_roots = tuple(managed_singleton_roots)
        self.conda_executable = conda_executable
        self.probe_runner = probe_runner
        self.preference_store = preference_store

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
        )

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
        self._get(environment_id)
        if settings.napari_registry_revision != expected_revision:
            raise NapariEnvironmentError(
                "napari_registry_revision_conflict",
                f"expected registry revision {expected_revision}, current is "
                f"{settings.napari_registry_revision}",
            )
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
        kind: str,
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

    def _with_current_interpreter_state(self, environment: NapariEnvironment) -> NapariEnvironment:
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
