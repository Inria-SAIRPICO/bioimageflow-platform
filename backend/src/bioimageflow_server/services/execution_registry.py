"""Durable per-workspace execution snapshot registry."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from bioimageflow_server.models.execution_runtime import ExecutionPage, ExecutionSnapshot, utc_now
from bioimageflow_server.services.filesystem_durability import fsync_directory, fsync_file


class ExecutionNotFoundError(LookupError):
    pass


class ExecutionRevisionConflict(RuntimeError):
    pass


def _safe_execution_id(value: str) -> str:
    if (
        not value
        or len(value) > 128
        or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in value)
    ):
        raise ValueError("execution_id contains unsafe characters")
    return value


class ExecutionRegistry:
    """Persist one atomically replaced JSON snapshot per execution."""

    def __init__(self, workspace_root: Path) -> None:
        self.root = workspace_root / ".bioimageflow" / "executions"
        self._lock = threading.RLock()

    def _path(self, execution_id: str) -> Path:
        return self.root / f"{_safe_execution_id(execution_id)}.json"

    def get(self, execution_id: str) -> ExecutionSnapshot:
        path = self._path(execution_id)
        with self._lock:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise ExecutionNotFoundError(execution_id) from exc
        return ExecutionSnapshot.model_validate(payload)

    def save(
        self,
        snapshot: ExecutionSnapshot,
        *,
        expected_revision: int | None = None,
    ) -> ExecutionSnapshot:
        """Increment and durably replace a snapshot with optional CAS semantics."""

        path = self._path(snapshot.execution_id)
        with self._lock:
            current: ExecutionSnapshot | None = None
            if path.exists():
                current = ExecutionSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
            current_revision = current.revision if current is not None else -1
            if expected_revision is not None and current_revision != expected_revision:
                raise ExecutionRevisionConflict(
                    f"Expected revision {expected_revision}, found {current_revision}"
                )
            persisted = snapshot.model_copy(
                update={
                    "revision": current_revision + 1,
                    "updated_at": utc_now(),
                }
            )
            self._atomic_write(path, persisted.model_dump(mode="json"))
            return persisted

    def list(
        self,
        *,
        workflow_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> ExecutionPage:
        if offset < 0 or not 1 <= limit <= 200:
            raise ValueError("offset must be non-negative and limit must be in [1, 200]")
        with self._lock:
            snapshots: list[ExecutionSnapshot] = []
            if not self.root.exists():
                return ExecutionPage(items=[], total=0, offset=offset, limit=limit)
            for path in self.root.glob("*.json"):
                if path.is_symlink() or not path.is_file():
                    continue
                snapshots.append(ExecutionSnapshot.model_validate_json(path.read_text("utf-8")))
        if workflow_id is not None:
            snapshots = [item for item in snapshots if item.workflow_id == workflow_id]
        snapshots.sort(key=lambda item: (item.created_at, item.execution_id), reverse=True)
        return ExecutionPage(
            items=snapshots[offset : offset + limit],
            total=len(snapshots),
            offset=offset,
            limit=limit,
        )

    def non_terminal(self) -> list[ExecutionSnapshot]:
        with self._lock:
            if not self.root.exists():
                return []
            snapshots = [
                ExecutionSnapshot.model_validate_json(path.read_text("utf-8"))
                for path in self.root.glob("*.json")
                if path.is_file() and not path.is_symlink()
            ]
        return [item for item in snapshots if not item.terminal]

    def _atomic_write(self, destination: Path, payload: dict[str, object]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.stem}.",
            suffix=".tmp",
            dir=self.root,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
            fsync_file(destination)
            fsync_directory(self.root)
        finally:
            if temporary.exists():
                temporary.unlink()
