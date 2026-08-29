"""Durable per-workspace execution snapshot registry."""

from __future__ import annotations

import json
import hashlib
import os
import tempfile
import threading
import re
from collections.abc import Callable
from pathlib import Path

from bioimageflow_server.models.execution_runtime import ExecutionPage, ExecutionSnapshot, utc_now
from bioimageflow_server.services.filesystem_durability import fsync_directory, fsync_file


class ExecutionNotFoundError(LookupError):
    pass


class ExecutionRevisionConflict(RuntimeError):
    pass


class RetryPlanNotFoundError(LookupError):
    pass


class RetryPlanConflictError(RuntimeError):
    pass


_RETRY_DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")


def _safe_execution_id(value: str) -> str:
    if (
        not value
        or len(value) > 128
        or any(
            character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for character in value
        )
    ):
        raise ValueError("execution_id contains unsafe characters")
    return value


class ExecutionRegistry:
    """Persist one atomically replaced JSON snapshot per execution."""

    def __init__(self, workspace_root: Path | Callable[[], Path]) -> None:
        self._workspace_provider = (
            workspace_root if callable(workspace_root) else lambda: workspace_root
        )
        self._execution_roots: dict[str, Path] = {}
        self._lock = threading.RLock()

    @property
    def root(self) -> Path:
        return self._workspace_provider() / ".bioimageflow" / "executions"

    def _bind_root(self, execution_id: str, root: Path | None = None) -> Path:
        safe_id = _safe_execution_id(execution_id)
        selected = self.root if root is None else root
        return self._execution_roots.setdefault(safe_id, selected)

    def _execution_root(self, execution_id: str) -> Path:
        safe_id = _safe_execution_id(execution_id)
        return self._execution_roots.get(safe_id, self.root)

    def _path(self, execution_id: str, *, bind: bool = False) -> Path:
        safe_id = _safe_execution_id(execution_id)
        root = self._bind_root(safe_id) if bind else self._execution_root(safe_id)
        return root / f"{safe_id}.json"

    def _retry_plan_path(self, execution_id: str, digest: str) -> Path:
        match = _RETRY_DIGEST.fullmatch(digest)
        if match is None:
            raise ValueError("retry plan digest is invalid")
        return self._execution_root(execution_id) / "retry_plans" / f"{match.group(1)}.json"

    def _cleanup_plan_path(self, execution_id: str, digest: str) -> Path:
        match = _RETRY_DIGEST.fullmatch(digest)
        if match is None:
            raise ValueError("cleanup plan digest is invalid")
        return self._execution_root(execution_id) / "cleanup_plans" / f"{match.group(1)}.json"

    @staticmethod
    def _decode_snapshot(payload: object) -> ExecutionSnapshot | None:
        if not isinstance(payload, dict):
            raise ValueError("Execution snapshot must contain an object")
        if payload.get("schema_version") == 2:
            return ExecutionSnapshot.model_validate(payload)
        if payload.get("schema_version") != 1:
            raise ValueError("Unsupported execution snapshot schema")
        if payload.get("backend") not in {"direct", "wetlands"}:
            # Legacy distributed records depend on removed executable profiles and
            # transports. They are deliberately excluded without touching local runs.
            return None
        migrated = dict(payload)
        migrated["schema_version"] = 2
        migrated.pop("actions", None)
        migrated.setdefault("diagnostics", [])
        return ExecutionSnapshot.model_validate(migrated)

    @classmethod
    def _read_snapshot(cls, path: Path) -> ExecutionSnapshot | None:
        return cls._decode_snapshot(json.loads(path.read_text(encoding="utf-8")))

    def migrate(self) -> tuple[int, int]:
        """Preserve v1 local history and erase obsolete distributed state."""

        if not self.root.exists():
            return 0, 0
        migrated = 0
        removed_ids: set[str] = set()
        with self._lock:
            for path in sorted(self.root.glob("*.json")):
                if not path.is_file() or path.is_symlink():
                    continue
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict) or payload.get("schema_version") != 1:
                    continue
                execution_id = payload.get("execution_id")
                if payload.get("backend") in {"direct", "wetlands"}:
                    snapshot = self._decode_snapshot(payload)
                    assert snapshot is not None
                    self._atomic_write(path, snapshot.model_dump(mode="json"))
                    migrated += 1
                    continue
                path.unlink()
                fsync_directory(path.parent)
                if isinstance(execution_id, str):
                    removed_ids.add(execution_id)
            for directory in (self.root / "retry_plans", self.root / "cleanup_plans"):
                if not directory.exists():
                    continue
                for path in directory.glob("*.json"):
                    try:
                        envelope = json.loads(path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        continue
                    plan = envelope.get("plan") if isinstance(envelope, dict) else None
                    owner = (
                        envelope.get("execution_id")
                        if isinstance(envelope, dict)
                        else None
                    )
                    parent = plan.get("parent_run_id") if isinstance(plan, dict) else None
                    if owner in removed_ids or parent in removed_ids:
                        path.unlink()
                        fsync_directory(path.parent)
        return migrated, len(removed_ids)

    def get(self, execution_id: str) -> ExecutionSnapshot:
        path = self._path(execution_id)
        with self._lock:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise ExecutionNotFoundError(execution_id) from exc
        snapshot = self._decode_snapshot(payload)
        if snapshot is None:
            raise ExecutionNotFoundError(execution_id)
        self._bind_root(execution_id, path.parent)
        return snapshot

    def save(
        self,
        snapshot: ExecutionSnapshot,
        *,
        expected_revision: int | None = None,
    ) -> ExecutionSnapshot:
        """Increment and durably replace a snapshot with optional CAS semantics."""

        path = self._path(snapshot.execution_id, bind=True)
        with self._lock:
            current: ExecutionSnapshot | None = None
            if path.exists():
                current = self._read_snapshot(path)
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
                snapshot = self._read_snapshot(path)
                if snapshot is not None:
                    self._bind_root(snapshot.execution_id, path.parent)
                    snapshots.append(snapshot)
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
            snapshots = []
            for path in self.root.glob("*.json"):
                if not path.is_file() or path.is_symlink():
                    continue
                snapshot = self._read_snapshot(path)
                if snapshot is not None:
                    self._bind_root(snapshot.execution_id, path.parent)
                    snapshots.append(snapshot)
        return [item for item in snapshots if not item.terminal]

    def save_retry_plan(self, payload: dict[str, object]) -> None:
        """Durably retain one exact immutable retry plan before confirmation."""

        digest = payload.get("digest")
        parent_run_id = payload.get("parent_run_id")
        if not isinstance(digest, str) or not isinstance(parent_run_id, str):
            raise ValueError("retry plan payload is incomplete")
        self._bind_root(parent_run_id)
        path = self._retry_plan_path(parent_run_id, digest)
        envelope = {
            "schema": "bioimageflow.platform.retry-confirmation.v1",
            "state": "planned",
            "plan": payload,
            "error": None,
        }
        with self._lock:
            if path.exists():
                current = json.loads(path.read_text(encoding="utf-8"))
                if current.get("plan") != payload:
                    raise RetryPlanConflictError("retry plan digest is already retained")
                return
            self._atomic_write(path, envelope)

    def save_cleanup_plan(self, execution_id: str, payload: dict[str, object]) -> str:
        digest = "sha256:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        envelope = {
            "schema": "bioimageflow.platform.cluster-cleanup-confirmation.v1",
            "execution_id": execution_id,
            "plan": payload,
        }
        with self._lock:
            self._bind_root(execution_id)
            self._atomic_write(self._cleanup_plan_path(execution_id, digest), envelope)
        return digest

    def get_cleanup_plan(self, execution_id: str, digest: str) -> dict[str, object]:
        with self._lock:
            try:
                envelope = json.loads(
                    self._cleanup_plan_path(execution_id, digest).read_text(encoding="utf-8")
                )
            except FileNotFoundError as exc:
                raise ExecutionNotFoundError("cleanup plan") from exc
        if envelope.get("execution_id") != execution_id or not isinstance(
            envelope.get("plan"), dict
        ):
            raise ExecutionNotFoundError("cleanup plan")
        return envelope["plan"]

    def get_retry_plan(self, parent_execution_id: str, digest: str) -> dict[str, object]:
        path = self._retry_plan_path(parent_execution_id, digest)
        with self._lock:
            try:
                envelope = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise RetryPlanNotFoundError(digest) from exc
        payload = envelope.get("plan")
        if not isinstance(payload, dict):
            raise RetryPlanConflictError("retained retry plan envelope is invalid")
        if payload.get("parent_run_id") != parent_execution_id:
            raise RetryPlanNotFoundError(digest)
        return payload

    def retry_plan_state(self, parent_execution_id: str, digest: str) -> str:
        path = self._retry_plan_path(parent_execution_id, digest)
        with self._lock:
            try:
                envelope = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise RetryPlanNotFoundError(digest) from exc
        plan = envelope.get("plan")
        state = envelope.get("state")
        if (
            not isinstance(plan, dict)
            or plan.get("parent_run_id") != parent_execution_id
            or not isinstance(state, str)
        ):
            raise RetryPlanConflictError("retained retry plan envelope is invalid")
        return state

    def confirm_retry_plan(self, parent_execution_id: str, digest: str) -> dict[str, object]:
        """Durably record confirmation before any child allocation or submission."""

        path = self._retry_plan_path(parent_execution_id, digest)
        with self._lock:
            try:
                envelope = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise RetryPlanNotFoundError(digest) from exc
            plan = envelope.get("plan")
            if not isinstance(plan, dict) or plan.get("parent_run_id") != parent_execution_id:
                raise RetryPlanNotFoundError(digest)
            if envelope.get("state") == "planned":
                envelope["state"] = "confirmed"
                self._atomic_write(path, envelope)
            elif envelope.get("state") not in {"confirmed", "started"}:
                raise RetryPlanConflictError("retry plan confirmation cannot be resumed")
        return plan

    def mark_retry_started(self, parent_execution_id: str, digest: str) -> None:
        path = self._retry_plan_path(parent_execution_id, digest)
        with self._lock:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            plan = envelope.get("plan")
            if not isinstance(plan, dict) or plan.get("parent_run_id") != parent_execution_id:
                raise RetryPlanNotFoundError(digest)
            if envelope.get("state") == "started":
                return
            if envelope.get("state") != "confirmed":
                raise RetryPlanConflictError("retry plan was not confirmed")
            envelope["state"] = "started"
            self._atomic_write(path, envelope)

    def mark_retry_uncertain(self, parent_execution_id: str, digest: str) -> None:
        """Stop replaying start while preserving exact-child reconnection."""

        path = self._retry_plan_path(parent_execution_id, digest)
        with self._lock:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            plan = envelope.get("plan")
            if not isinstance(plan, dict) or plan.get("parent_run_id") != parent_execution_id:
                raise RetryPlanNotFoundError(digest)
            if envelope.get("state") == "uncertain":
                return
            if envelope.get("state") != "confirmed":
                raise RetryPlanConflictError("retry plan was not confirmed")
            envelope["state"] = "uncertain"
            self._atomic_write(path, envelope)

    def mark_retry_absent(self, parent_execution_id: str, digest: str) -> None:
        """Permit replay only after the exact child is definitively absent."""

        path = self._retry_plan_path(parent_execution_id, digest)
        with self._lock:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            plan = envelope.get("plan")
            if not isinstance(plan, dict) or plan.get("parent_run_id") != parent_execution_id:
                raise RetryPlanNotFoundError(digest)
            if envelope.get("state") != "uncertain":
                raise RetryPlanConflictError("retry plan is not awaiting exact-child recovery")
            envelope["state"] = "confirmed"
            self._atomic_write(path, envelope)

    def mark_retry_failed(
        self,
        parent_execution_id: str,
        digest: str,
        *,
        error: dict[str, object],
    ) -> None:
        path = self._retry_plan_path(parent_execution_id, digest)
        with self._lock:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            plan = envelope.get("plan")
            if not isinstance(plan, dict) or plan.get("parent_run_id") != parent_execution_id:
                raise RetryPlanNotFoundError(digest)
            envelope.update(state="failed", error=error)
            self._atomic_write(path, envelope)

    def confirmed_retry_plans(self) -> list[tuple[str, str]]:
        current_root = self.root
        directory = current_root / "retry_plans"
        if not directory.exists():
            return []
        confirmed: list[tuple[str, str]] = []
        with self._lock:
            for path in sorted(directory.glob("*.json")):
                envelope = json.loads(path.read_text(encoding="utf-8"))
                if envelope.get("state") not in {"confirmed", "uncertain"}:
                    continue
                plan = envelope.get("plan")
                if not isinstance(plan, dict):
                    raise RetryPlanConflictError("retained retry plan envelope is invalid")
                parent = plan.get("parent_run_id")
                digest = plan.get("digest")
                if not isinstance(parent, str) or not isinstance(digest, str):
                    raise RetryPlanConflictError("retained retry plan is incomplete")
                self._bind_root(parent, current_root)
                confirmed.append((parent, digest))
        return confirmed

    def _atomic_write(self, destination: Path, payload: dict[str, object]) -> None:
        parent_existed = destination.parent.exists()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not parent_existed:
            fsync_directory(destination.parent.parent)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.stem}.",
            suffix=".tmp",
            dir=destination.parent,
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
            fsync_directory(destination.parent)
        finally:
            if temporary.exists():
                temporary.unlink()
