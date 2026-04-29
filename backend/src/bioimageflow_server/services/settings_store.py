"""Filesystem-backed Settings store with atomic writes.

Persists user preferences to ``<path>`` (default: ``~/.bioimageflow/settings.json``).
Wraps the Pydantic ``Settings`` model with a ``settings_version`` envelope so
future schema migrations can be detected without breaking older clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from bioimageflow_server.models.settings import Settings


logger = logging.getLogger(__name__)

CURRENT_SETTINGS_VERSION = 1


class SettingsStore:
    """Async, filesystem-backed Settings holder with atomic writes."""

    def __init__(
        self,
        path: Path,
        *,
        deployment_mode: Literal["desktop", "webapp"] = "desktop",
    ) -> None:
        self.path = path
        self._deployment_mode: Literal["desktop", "webapp"] = deployment_mode
        self._current: Settings | None = None
        self._lock = asyncio.Lock()

    # --- Public API ------------------------------------------------------

    async def load(self) -> Settings:
        """Read the settings file from disk; seed defaults if missing.

        On any I/O or parse error, log a warning and fall back to in-memory
        defaults without overwriting the user's file. ``settings_version > 1``
        is treated the same way (defaults in memory; user's file untouched)
        so a downgrade run preserves the newer config for the next upgrade.
        """
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as exc:
            logger.warning(
                "Could not create settings parent directory %s: %s; using defaults",
                self.path.parent,
                exc,
            )
            self._current = self._default_settings()
            return self._current

        if not self.path.exists():
            self._current = self._default_settings()
            try:
                self._write_atomic(self._current)
            except OSError as exc:
                logger.warning("Could not seed settings file: %s", exc)
            return self._current

        try:
            raw = self.path.read_text()
        except OSError as exc:
            logger.warning("Could not read settings file %s: %s", self.path, exc)
            self._current = self._default_settings()
            return self._current

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Settings file %s is not valid JSON (%s); using defaults",
                self.path,
                exc,
            )
            self._current = self._default_settings()
            return self._current

        if not isinstance(data, dict):
            logger.warning(
                "Settings file %s did not contain an object; using defaults",
                self.path,
            )
            self._current = self._default_settings()
            return self._current

        version = data.get("settings_version", CURRENT_SETTINGS_VERSION)
        if not isinstance(version, int) or version > CURRENT_SETTINGS_VERSION:
            logger.warning(
                "Settings file %s has unsupported settings_version=%r; using defaults "
                "(file left unchanged)",
                self.path,
                version,
            )
            self._current = self._default_settings()
            return self._current

        # Strip envelope + unknown keys before validation so a downgrade
        # from a future schema doesn't crash on `extra="forbid"`.
        payload = {
            k: v
            for k, v in data.items()
            if k != "settings_version" and k in Settings.model_fields
        }
        # Ensure deployment_mode is present (it's required on the model).
        payload.setdefault("deployment_mode", self._deployment_mode)

        try:
            self._current = Settings.model_validate(payload)
        except ValidationError as exc:
            logger.warning(
                "Settings file %s failed validation (%s); using defaults",
                self.path,
                exc,
            )
            self._current = self._default_settings()
        return self._current

    def get(self) -> Settings:
        """Return the in-memory snapshot. Call :meth:`load` first."""
        if self._current is None:
            raise RuntimeError("SettingsStore.load() must be awaited before get()")
        return self._current

    async def patch(self, changes: dict[str, Any]) -> Settings:
        """Validate ``changes`` against current state, persist, and return."""
        async with self._lock:
            if self._current is None:
                raise RuntimeError("SettingsStore.load() must be awaited before patch()")
            # NOTE: ``model_copy(update=changes)`` does NOT run validators in
            # Pydantic v2. Use ``model_validate`` over the merged dict so
            # extra="forbid" and custom validators apply.
            merged = {**self._current.model_dump(), **changes}
            candidate = Settings.model_validate(merged)
            self._write_atomic(candidate)
            self._current = candidate
            return self._current

    async def flush(self) -> None:
        """No-op in v1 (writes are synchronous inside :meth:`patch`).

        Reserved for future write-behind support; lifespan hooks call this
        on shutdown.
        """
        return None

    def resolved_tool_store_path(self) -> Path:
        """Return ``tool_store_path`` with ``~`` expanded and made absolute."""
        return Path(self.get().tool_store_path).expanduser().resolve()

    def resolved_output_data_folder(self) -> Path:
        """Return ``output_data_folder`` with ``~`` expanded and made absolute."""
        return Path(self.get().output_data_folder).expanduser().resolve()

    # --- Internals -------------------------------------------------------

    def _default_settings(self) -> Settings:
        return Settings(deployment_mode=self._deployment_mode)

    def _write_atomic(self, settings: Settings) -> None:
        """Write ``settings`` atomically: temp file then ``os.replace``."""
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        envelope: dict[str, Any] = {"settings_version": CURRENT_SETTINGS_VERSION}
        envelope.update(settings.model_dump())
        payload = json.dumps(envelope, indent=2)
        try:
            with open(tmp, "w") as fh:
                fh.write(payload)
            os.replace(tmp, self.path)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
