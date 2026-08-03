"""Atomic versioned persistence for distributed execution profiles."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

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


class _ProfileEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profiles_version: Literal[1] = 1
    profiles: list[DistributedExecutionProfile] = []


class ExecutionProfileStore:
    """Application-wide profile store with per-profile revision CAS."""

    def __init__(self, path: Path, *, editable: bool = True) -> None:
        self.path = path
        self.editable = editable
        self._profiles: dict[str, DistributedExecutionProfile] | None = None
        self._lock = asyncio.Lock()
        self._reference_checker: Callable[[str], bool] = lambda _profile_id: False

    def set_reference_checker(self, checker: Callable[[str], bool]) -> None:
        """Prevent removal while a retained non-terminal run needs a profile."""
        self._reference_checker = checker

    async def load(self) -> list[DistributedExecutionProfile]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._profiles = {}
            self._write_atomic()
            return []
        envelope = _ProfileEnvelope.model_validate_json(self.path.read_text(encoding="utf-8"))
        self._profiles = {profile.id: profile for profile in envelope.profiles}
        if len(self._profiles) != len(envelope.profiles):
            raise ValueError("Execution profile IDs must be unique")
        return self.list()

    def list(self) -> list[DistributedExecutionProfile]:
        profiles = self._require_loaded()
        return sorted(profiles.values(), key=lambda item: (item.name.casefold(), item.id))

    def get(self, profile_id: str) -> DistributedExecutionProfile:
        try:
            return self._require_loaded()[profile_id]
        except KeyError as exc:
            raise ExecutionProfileNotFoundError(profile_id) from exc

    async def create(self, fields: ExecutionProfileCreate) -> DistributedExecutionProfile:
        async with self._lock:
            profile = DistributedExecutionProfile(
                **fields.model_dump(mode="python"),
                id=f"profile_{uuid4().hex}",
                revision=1,
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
        async with self._lock:
            current = self.get(profile_id)
            if current.revision != expected_revision:
                raise ExecutionProfileConflictError(
                    f"Profile revision {current.revision} does not match {expected_revision}"
                )
            updated = DistributedExecutionProfile(
                **fields.model_dump(mode="python"),
                id=profile_id,
                revision=current.revision + 1,
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
        self, profiles: dict[str, DistributedExecutionProfile] | None = None
    ) -> None:
        profiles = self._require_loaded() if profiles is None else profiles
        envelope: dict[str, Any] = {
            "profiles_version": 1,
            "profiles": [
                profile.model_dump(mode="json")
                for profile in sorted(profiles.values(), key=lambda item: item.id)
            ],
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            tmp.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
        finally:
            if tmp.exists():
                tmp.unlink()
