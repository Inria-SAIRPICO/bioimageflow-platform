"""Atomic v2 persistence and trusted loading for managed-cluster profiles."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from bioimageflow_server.models.execution_profiles import (
    DistributedExecutionProfile,
    ExecutionProfileCreate,
)


class ExecutionProfileNotFoundError(KeyError):
    pass


class ExecutionProfileConflictError(RuntimeError):
    pass


class ExecutionProfileInUseError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedClusterConfig:
    path: Path
    digest: str
    cluster: Any


def load_cluster_config(
    path: Path | str,
    *,
    expected_digest: str | None = None,
) -> LoadedClusterConfig:
    """Execute one trusted script and require its top-level ``cluster`` value."""

    cluster_api = importlib.import_module("bioimageflow.cluster")

    expanded = Path(path).expanduser()
    if expanded.is_symlink():
        raise ValueError("Cluster configuration must not be a symlink (symbolic link)")
    resolved = expanded.resolve(strict=True)
    before = expanded.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or resolved.suffix != ".py":
        raise ValueError("Cluster configuration must be a regular Python file")
    descriptor = os.open(resolved, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(descriptor)
        content = bytearray()
        while chunk := os.read(descriptor, 1024 * 1024):
            content.extend(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    final = expanded.stat(follow_symlinks=False)
    identities = {
        (item.st_dev, item.st_ino, item.st_mode, item.st_size, item.st_mtime_ns)
        for item in (before, opened, after, final)
    }
    if len(identities) != 1:
        raise ValueError("Cluster configuration changed while it was loaded")
    exact_bytes = bytes(content)
    digest = f"sha256:{hashlib.sha256(exact_bytes).hexdigest()}"
    if expected_digest is not None and digest != expected_digest:
        raise ValueError(
            "Cluster configuration digest changed; save the profile again before use"
        )
    module_name = f"_bioimageflow_cluster_{uuid4().hex}"
    values: dict[str, Any] = {
        "__builtins__": __builtins__,
        "__file__": str(resolved),
        "__name__": module_name,
        "__package__": None,
    }
    exec(compile(exact_bytes, str(resolved), "exec"), values, values)
    cluster = values.get("cluster")
    if type(cluster) is not cluster_api.RemoteCluster:
        raise ValueError(
            "Cluster configuration must define top-level cluster as an exact RemoteCluster"
        )
    return LoadedClusterConfig(path=resolved, digest=digest, cluster=cluster)


class _ProfileEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profiles_version: Literal[2] = 2
    profiles: list[DistributedExecutionProfile] = Field(default_factory=list)


class ExecutionProfileStore:
    """Application-wide v2 profile store with per-profile revision CAS."""

    def __init__(self, path: Path, *, editable: bool = True) -> None:
        self.path = path
        self.editable = editable
        self._profiles: dict[str, DistributedExecutionProfile] | None = None
        self._lock = asyncio.Lock()
        self._reference_checker: Callable[[str], bool] = lambda _profile_id: False

    def set_reference_checker(self, checker: Callable[[str], bool]) -> None:
        self._reference_checker = checker

    async def load(self) -> list[DistributedExecutionProfile]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._profiles = {}
            self._write_atomic()
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Execution profile store must contain an object")
        if raw.get("profiles_version") != 2:
            # v1 contained obsolete executable/transport contracts. It is intentionally
            # discarded rather than imported, archived, or interpreted.
            self._profiles = {}
            self._write_atomic()
            return []
        envelope = _ProfileEnvelope.model_validate(raw)
        self._profiles = {profile.id: profile for profile in envelope.profiles}
        if len(self._profiles) != len(envelope.profiles):
            raise ValueError("Execution profile IDs must be unique")
        return self.list()

    def list(self) -> list[DistributedExecutionProfile]:
        return sorted(
            self._require_loaded().values(),
            key=lambda item: (item.name.casefold(), item.id),
        )

    def get(self, profile_id: str) -> DistributedExecutionProfile:
        try:
            return self._require_loaded()[profile_id]
        except KeyError as exc:
            raise ExecutionProfileNotFoundError(profile_id) from exc

    async def create(self, fields: ExecutionProfileCreate) -> DistributedExecutionProfile:
        loaded = await asyncio.to_thread(load_cluster_config, Path(fields.config_path))
        async with self._lock:
            values = fields.model_dump(mode="python")
            values["config_path"] = str(loaded.path)
            profile = DistributedExecutionProfile(
                **values,
                id=f"profile_{uuid4().hex}",
                revision=1,
                config_digest=loaded.digest,
                cluster_host=loaded.cluster.host,
                cluster_root=str(loaded.cluster.root),
            )
            profiles = {**self._require_loaded(), profile.id: profile}
            self._write_atomic(profiles)
            self._profiles = profiles
            return profile

    async def update(
        self,
        profile_id: str,
        expected_revision: int,
        fields: ExecutionProfileCreate,
    ) -> DistributedExecutionProfile:
        loaded = await asyncio.to_thread(load_cluster_config, Path(fields.config_path))
        async with self._lock:
            current = self.get(profile_id)
            if current.revision != expected_revision:
                raise ExecutionProfileConflictError(
                    f"Profile revision {current.revision} does not match {expected_revision}"
                )
            values = fields.model_dump(mode="python")
            values["config_path"] = str(loaded.path)
            updated = DistributedExecutionProfile(
                **values,
                id=profile_id,
                revision=current.revision + 1,
                config_digest=loaded.digest,
                cluster_host=loaded.cluster.host,
                cluster_root=str(loaded.cluster.root),
            )
            profiles = {**self._require_loaded(), profile_id: updated}
            self._write_atomic(profiles)
            self._profiles = profiles
            return updated

    async def delete(self, profile_id: str, expected_revision: int) -> None:
        async with self._lock:
            current = self.get(profile_id)
            if current.revision != expected_revision:
                raise ExecutionProfileConflictError(
                    f"Profile revision {current.revision} does not match {expected_revision}"
                )
            if self._reference_checker(profile_id):
                raise ExecutionProfileInUseError(
                    "Execution profile is referenced by a non-terminal execution"
                )
            profiles = dict(self._require_loaded())
            del profiles[profile_id]
            self._write_atomic(profiles)
            self._profiles = profiles

    async def flush(self) -> None:
        return None

    def _require_loaded(self) -> dict[str, DistributedExecutionProfile]:
        if self._profiles is None:
            raise RuntimeError("ExecutionProfileStore.load() must be awaited first")
        return self._profiles

    def _write_atomic(
        self,
        profiles: dict[str, DistributedExecutionProfile] | None = None,
    ) -> None:
        selected = self._require_loaded() if profiles is None else profiles
        envelope: dict[str, Any] = {
            "profiles_version": 2,
            "profiles": [
                profile.model_dump(mode="json")
                for profile in sorted(selected.values(), key=lambda item: item.id)
            ],
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()
