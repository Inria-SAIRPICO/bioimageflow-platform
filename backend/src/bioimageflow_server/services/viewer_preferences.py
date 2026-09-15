"""Atomic versioned local output favorites, independent of application settings."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path
from uuid import UUID

from bioimageflow_server.models.viewer_preferences import (
    OutputPreferenceKey,
    PersistentOutputPreferenceKey,
    SessionOutputPreferenceKey,
    ViewerFavorite,
    ViewerPreferencesSnapshot,
)
from bioimageflow_server.services.filesystem_durability import fsync_directory


class ViewerPreferencesRevisionConflict(ValueError):
    def __init__(self, expected: int, current: int) -> None:
        self.expected = expected
        self.current = current
        super().__init__(
            f"Viewer preferences revision is {current}, not expected {expected}"
        )


class ViewerPreferenceTargetConflict(ValueError):
    """The favorite changed since the caller captured its target."""


_WORKSPACE_IDENTITY_LOCK = threading.RLock()


def ensure_workspace_identity(workspace_dir: Path) -> UUID:
    """Return the durable UUID authority for one local workspace."""

    with _WORKSPACE_IDENTITY_LOCK:
        path = workspace_dir / ".bioimageflow" / "workspace.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if (
                not isinstance(raw, dict)
                or set(raw) != {"version", "id"}
                or raw["version"] != 1
            ):
                raise ValueError(f"Invalid workspace identity: {path}")
            return UUID(str(raw["id"]))
        from uuid import uuid4

        workspace_id = uuid4()
        _atomic_json(path, {"version": 1, "id": str(workspace_id)})
        return workspace_id


class ViewerPreferenceStore:
    """Per-user favorite authority with monotonic compare-and-swap revision."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.forget_journal_path = path.with_name("viewer-preferences-forget.json")
        self._lock = threading.RLock()

    def snapshot(self) -> ViewerPreferencesSnapshot:
        with self._lock:
            return self._read()

    def set(
        self,
        key: OutputPreferenceKey,
        environment_id: UUID,
        *,
        expected_revision: int,
    ) -> ViewerPreferencesSnapshot:
        with self._lock:
            current = self._require_revision(expected_revision)
            favorites = [favorite for favorite in current.favorites if favorite.key != key]
            favorites.append(ViewerFavorite(key=key, environment_id=environment_id))
            return self._commit(current, favorites)

    def unset(
        self,
        key: OutputPreferenceKey,
        *,
        expected_environment_id: UUID,
        expected_revision: int,
    ) -> ViewerPreferencesSnapshot:
        with self._lock:
            current = self._require_revision(expected_revision)
            favorite = next((item for item in current.favorites if item.key == key), None)
            if favorite is None or favorite.environment_id != expected_environment_id:
                raise ViewerPreferenceTargetConflict(
                    "Favorite target no longer matches the captured environment"
                )
            return self._commit(
                current, [item for item in current.favorites if item.key != key]
            )

    def toggle(
        self,
        key: OutputPreferenceKey,
        environment_id: UUID,
        *,
        expected_revision: int,
    ) -> ViewerPreferencesSnapshot:
        with self._lock:
            current = self._require_revision(expected_revision)
            favorite = next((item for item in current.favorites if item.key == key), None)
            favorites = [item for item in current.favorites if item.key != key]
            if favorite is None or favorite.environment_id != environment_id:
                favorites.append(ViewerFavorite(key=key, environment_id=environment_id))
            return self._commit(current, favorites)

    def favorite_for(self, key: OutputPreferenceKey) -> UUID | None:
        snapshot = self.snapshot()
        favorite = next((item for item in snapshot.favorites if item.key == key), None)
        return favorite.environment_id if favorite is not None else None

    def clear_environment(self, environment_id: UUID) -> ViewerPreferencesSnapshot:
        with self._lock:
            current = self._read()
            favorites = [
                item for item in current.favorites if item.environment_id != environment_id
            ]
            return current if len(favorites) == len(current.favorites) else self._commit(current, favorites)

    def prepare_environment_forget(
        self, environment_id: UUID, *, registry_revision: int
    ) -> None:
        """Journal the cross-store target before either authority changes."""

        with self._lock:
            if self.forget_journal_path.exists():
                raise RuntimeError("A viewer environment forget must recover first")
            current = self._read()
            favorites = [
                item for item in current.favorites if item.environment_id != environment_id
            ]
            target = ViewerPreferencesSnapshot(
                revision=current.revision + (favorites != current.favorites),
                favorites=favorites,
            )
            payload = {
                "version": 1,
                "environment_id": str(environment_id),
                "registry_revision": registry_revision,
                "source_preferences_revision": current.revision,
                "target": target.model_dump(mode="json"),
                "target_digest": snapshot_digest(target),
            }
            _atomic_json(self.forget_journal_path, payload)

    def apply_prepared_environment_forget(self) -> UUID | None:
        with self._lock:
            journal = self._read_forget_journal()
            if journal is None:
                return None
            target = ViewerPreferencesSnapshot.model_validate(journal["target"])
            if snapshot_digest(target) != journal["target_digest"]:
                raise ValueError("Viewer preference forget journal digest mismatch")
            current = self._read()
            if current != target:
                if current.revision != journal["source_preferences_revision"]:
                    raise ViewerPreferencesRevisionConflict(
                        journal["source_preferences_revision"], current.revision
                    )
                _atomic_json(self.path, target.model_dump(mode="json"))
            return UUID(journal["environment_id"])

    def pending_environment_forget(self) -> dict[str, object] | None:
        with self._lock:
            return self._read_forget_journal()

    def complete_environment_forget(self) -> None:
        with self._lock:
            try:
                self.forget_journal_path.unlink()
            except FileNotFoundError:
                return
            fsync_directory(self.forget_journal_path.parent)

    def _read_forget_journal(self) -> dict[str, object] | None:
        if not self.forget_journal_path.is_file():
            return None
        raw = json.loads(self.forget_journal_path.read_text(encoding="utf-8"))
        fields = {
            "version",
            "environment_id",
            "registry_revision",
            "source_preferences_revision",
            "target",
            "target_digest",
        }
        if not isinstance(raw, dict) or set(raw) != fields or raw.get("version") != 1:
            raise ValueError("Invalid viewer preference forget journal")
        UUID(str(raw["environment_id"]))
        if not isinstance(raw["registry_revision"], int) or not isinstance(
            raw["source_preferences_revision"], int
        ):
            raise ValueError("Invalid viewer preference forget revisions")
        if not isinstance(raw["target"], dict) or not isinstance(
            raw["target_digest"], str
        ):
            raise ValueError("Invalid viewer preference forget target")
        return raw

    def clear_workflow_generation(
        self, workspace_id: UUID, workflow_id: str, identity_generation: int
    ) -> ViewerPreferencesSnapshot:
        with self._lock:
            current = self._read()
            favorites = [
                item
                for item in current.favorites
                if not (
                    isinstance(item.key, PersistentOutputPreferenceKey)
                    and item.key.workspace_id == workspace_id
                    and item.key.workflow_id == workflow_id
                    and item.key.identity_generation == identity_generation
                )
            ]
            return current if len(favorites) == len(current.favorites) else self._commit(current, favorites)

    def move_workflow_generation(
        self,
        workspace_id: UUID,
        source_workflow_id: str,
        source_generation: int,
        destination_workflow_id: str,
        destination_generation: int,
    ) -> ViewerPreferencesSnapshot:
        with self._lock:
            current = self._read()
            favorites: list[ViewerFavorite] = []
            for favorite in current.favorites:
                key = favorite.key
                if (
                    isinstance(key, PersistentOutputPreferenceKey)
                    and key.workspace_id == workspace_id
                    and key.workflow_id == source_workflow_id
                    and key.identity_generation == source_generation
                ):
                    key = key.model_copy(
                        update={
                            "workflow_id": destination_workflow_id,
                            "identity_generation": destination_generation,
                        }
                    )
                    favorite = favorite.model_copy(update={"key": key})
                favorites.append(favorite)
            return current if favorites == current.favorites else self._commit(current, favorites)

    def discard_session(
        self, workspace_id: UUID, session_id: str
    ) -> ViewerPreferencesSnapshot:
        with self._lock:
            current = self._read()
            favorites = [
                item
                for item in current.favorites
                if not (
                    isinstance(item.key, SessionOutputPreferenceKey)
                    and item.key.workspace_id == workspace_id
                    and item.key.session_id == session_id
                )
            ]
            return current if len(favorites) == len(current.favorites) else self._commit(current, favorites)

    def apply_session(
        self,
        workspace_id: UUID,
        session_id: str,
        *,
        workflow_id: str,
        identity_generation: int,
        parent_node_path: tuple[str, ...],
        surviving_outputs: set[tuple[tuple[str, ...], str]],
    ) -> ViewerPreferencesSnapshot:
        """Move surviving private favorites to an accepted parent instance."""

        with self._lock:
            current = self._read()
            retained = {
                favorite.key: favorite
                for favorite in current.favorites
                if not (
                    isinstance(favorite.key, SessionOutputPreferenceKey)
                    and favorite.key.workspace_id == workspace_id
                    and favorite.key.session_id == session_id
                )
            }
            for favorite in current.favorites:
                key = favorite.key
                if not (
                    isinstance(key, SessionOutputPreferenceKey)
                    and key.workspace_id == workspace_id
                    and key.session_id == session_id
                ):
                    continue
                structural = (key.node_path, key.output_key)
                if structural not in surviving_outputs:
                    continue
                persistent = PersistentOutputPreferenceKey(
                    workspace_id=workspace_id,
                    workflow_id=workflow_id,
                    identity_generation=identity_generation,
                    node_path=(*parent_node_path, *key.node_path),
                    output_key=key.output_key,
                )
                retained[persistent] = ViewerFavorite(
                    key=persistent,
                    environment_id=favorite.environment_id,
                )
            favorites = list(retained.values())
            return current if favorites == current.favorites else self._commit(current, favorites)

    def apply_session_to_session(
        self,
        workspace_id: UUID,
        session_id: str,
        *,
        parent_session_id: str,
        parent_node_path: tuple[str, ...],
        surviving_outputs: set[tuple[tuple[str, ...], str]],
    ) -> ViewerPreferencesSnapshot:
        """Move surviving child favorites into an accepted parent session."""

        with self._lock:
            current = self._read()
            retained = {
                favorite.key: favorite
                for favorite in current.favorites
                if not (
                    isinstance(favorite.key, SessionOutputPreferenceKey)
                    and favorite.key.workspace_id == workspace_id
                    and favorite.key.session_id == session_id
                )
            }
            for favorite in current.favorites:
                key = favorite.key
                if not (
                    isinstance(key, SessionOutputPreferenceKey)
                    and key.workspace_id == workspace_id
                    and key.session_id == session_id
                ):
                    continue
                if (key.node_path, key.output_key) not in surviving_outputs:
                    continue
                parent_key = SessionOutputPreferenceKey(
                    workspace_id=workspace_id,
                    session_id=parent_session_id,
                    node_path=(*parent_node_path, *key.node_path),
                    output_key=key.output_key,
                )
                retained[parent_key] = ViewerFavorite(
                    key=parent_key,
                    environment_id=favorite.environment_id,
                )
            favorites = list(retained.values())
            return current if favorites == current.favorites else self._commit(current, favorites)

    def _require_revision(self, expected: int) -> ViewerPreferencesSnapshot:
        current = self._read()
        if current.revision != expected:
            raise ViewerPreferencesRevisionConflict(expected, current.revision)
        return current

    def _read(self) -> ViewerPreferencesSnapshot:
        if not self.path.is_file():
            return ViewerPreferencesSnapshot(revision=0)
        return ViewerPreferencesSnapshot.model_validate_json(
            self.path.read_text(encoding="utf-8")
        )

    def _commit(
        self,
        current: ViewerPreferencesSnapshot,
        favorites: list[ViewerFavorite],
    ) -> ViewerPreferencesSnapshot:
        candidate = ViewerPreferencesSnapshot(
            revision=current.revision + 1,
            favorites=sorted(
                favorites,
                key=lambda item: json.dumps(
                    item.key.model_dump(mode="json"), sort_keys=True
                ),
            ),
        )
        _atomic_json(self.path, candidate.model_dump(mode="json"))
        return candidate


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def snapshot_digest(snapshot: ViewerPreferencesSnapshot) -> str:
    return hashlib.sha256(
        json.dumps(snapshot.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
