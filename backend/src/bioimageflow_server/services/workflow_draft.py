"""Live workflow draft persistence for agent-visible unsaved state."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.validation import NodeStatus, ValidationResult
from bioimageflow_server.models.workflow_draft import (
    DraftWriter,
    WorkflowDraftResponse,
)
from bioimageflow_server.services.graph_validator import validate_graph
from bioimageflow_server.services.session_manager import SessionManager
from bioimageflow_server.services.workflow_store import WorkflowStoreService


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _json_dump_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


class WorkflowDraftRevisionConflict(ValueError):
    """Raised when a draft write uses a stale expected revision."""

    def __init__(
        self,
        *,
        expected_revision: int,
        current: WorkflowDraftResponse,
    ) -> None:
        self.expected_revision = expected_revision
        self.current = current
        super().__init__(
            f"Draft revision conflict: expected {expected_revision}, "
            f"current is {current.draft_revision}"
        )


class WorkflowDraftService:
    """Manage live drafts under workflow-local ``.bioimageflow`` folders."""

    def __init__(
        self,
        workflow_store_provider: Callable[[], WorkflowStoreService],
        *,
        dev_mode_provider: Callable[[], bool] | None = None,
        settings_provider: Callable[[], Any | None] | None = None,
        server_boot_id: str | None = None,
    ) -> None:
        self._workflow_store_provider = workflow_store_provider
        self._dev_mode_provider = dev_mode_provider or (lambda: True)
        self._settings_provider = settings_provider or (lambda: None)
        self.server_boot_id = server_boot_id or uuid.uuid4().hex
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def get_draft(
        self,
        workflow_id: str,
        *,
        api_base_url: str | None = None,
    ) -> WorkflowDraftResponse:
        store = self._store()
        draft_path = self._draft_path(store, workflow_id)
        if draft_path.exists():
            draft = WorkflowDraftResponse.model_validate(
                json.loads(draft_path.read_text(encoding="utf-8"))
            )
        else:
            draft = self._synthesized_draft(store, workflow_id)
        self.write_agent_context(
            store,
            workflow_id=workflow_id,
            draft=draft,
            api_base_url=api_base_url,
        )
        return draft

    def put_draft(
        self,
        workflow_id: str,
        *,
        graph: GraphState,
        expected_revision: int,
        updated_by: DraftWriter = "frontend",
        should_validate: bool = True,
        api_base_url: str | None = None,
    ) -> WorkflowDraftResponse:
        with self._lock_for(workflow_id):
            store = self._store()
            current = self._read_or_synthesize(store, workflow_id)
            if expected_revision != current.draft_revision:
                raise WorkflowDraftRevisionConflict(
                    expected_revision=expected_revision,
                    current=current,
                )
            saved_revision = self._saved_revision(store, workflow_id)
            validation = (
                self._validate(store, workflow_id, graph)
                if should_validate
                else self._default_validation(graph)
            )
            dirty = self._graph_differs_from_saved(store, workflow_id, graph)
            draft = WorkflowDraftResponse(
                workflow_id=workflow_id,
                base_saved_revision=current.base_saved_revision if dirty else saved_revision,
                draft_revision=current.draft_revision + 1,
                updated_at=_utc_now(),
                updated_by=updated_by,
                dirty_against_saved=dirty,
                graph=graph,
                validation=validation,
            )
            _json_dump_atomic(
                self._draft_path(store, workflow_id),
                draft.model_dump(mode="json"),
            )
            self.write_agent_context(
                store,
                workflow_id=workflow_id,
                draft=draft,
                api_base_url=api_base_url,
            )
            return draft

    def _lock_for(self, workflow_id: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(workflow_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[workflow_id] = lock
            return lock

    def write_agent_context(
        self,
        store: WorkflowStoreService,
        *,
        workflow_id: str,
        draft: WorkflowDraftResponse,
        api_base_url: str | None = None,
    ) -> None:
        workspace_meta = store.workspace_dir / ".bioimageflow"
        workspace_meta.mkdir(parents=True, exist_ok=True)
        api_url = (api_base_url or "http://127.0.0.1:8000/api/v1").rstrip("/")
        context = {
            "agent_state_version": 1,
            "generated_at": _utc_now(),
            "server_boot_id": self.server_boot_id,
            "server_pid": os.getpid(),
            "api_base_url": api_url,
            "health_url": f"{api_url}/health",
            "active_workflow_id": workflow_id,
            "current_draft_revision": draft.draft_revision,
            "workspace_path": str(store.workspace_dir),
            "workflows_root": str(store.root_dir),
            "active_draft_path": str(self._draft_path(store, workflow_id)),
            "recommended_commands": [
                "bioimageflow-agent status",
                "bioimageflow-agent get-graph",
                "bioimageflow-agent validate",
                "bioimageflow-agent list-tools",
            ],
        }
        _json_dump_atomic(workspace_meta / "agent-state.json", context)
        (workspace_meta / "AGENTS.md").write_text(
            self._agent_instructions("Codex"),
            encoding="utf-8",
        )
        (workspace_meta / "CLAUDE.md").write_text(
            self._agent_instructions("Claude Code"),
            encoding="utf-8",
        )

    def _store(self) -> WorkflowStoreService:
        return self._workflow_store_provider()

    def _draft_path(self, store: WorkflowStoreService, workflow_id: str) -> Path:
        return store.workflow_dir(workflow_id) / ".bioimageflow" / "draft.json"

    def _read_or_synthesize(
        self,
        store: WorkflowStoreService,
        workflow_id: str,
    ) -> WorkflowDraftResponse:
        draft_path = self._draft_path(store, workflow_id)
        if draft_path.exists():
            return WorkflowDraftResponse.model_validate(
                json.loads(draft_path.read_text(encoding="utf-8"))
            )
        return self._synthesized_draft(store, workflow_id)

    def _synthesized_draft(
        self,
        store: WorkflowStoreService,
        workflow_id: str,
    ) -> WorkflowDraftResponse:
        workflow = store.get_workflow(workflow_id)
        return WorkflowDraftResponse(
            workflow_id=workflow_id,
            base_saved_revision=self._saved_revision(store, workflow_id),
            draft_revision=0,
            updated_at=workflow.info.last_modified,
            updated_by="system",
            dirty_against_saved=False,
            graph=workflow.graph,
            validation=self._validate(store, workflow_id, workflow.graph),
        )

    def _saved_revision(self, store: WorkflowStoreService, workflow_id: str) -> str:
        path = store.workflow_dir(workflow_id) / "workflow.json"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return f"sha256:{digest}"

    def _validate(
        self,
        store: WorkflowStoreService,
        workflow_id: str,
        graph: GraphState,
    ) -> ValidationResult:
        # Deliberately isolated: draft validation must not replace the active
        # frontend graph session used by /graph and parameter patching.
        session_manager = SessionManager()
        return validate_graph(
            graph,
            store.tool_registry,
            session_manager,
            storage_path=store.get_storage_path(workflow_id),
            dev_mode=self._dev_mode_provider(),
            settings=self._settings_provider(),
        )

    @staticmethod
    def _default_validation(graph: GraphState) -> ValidationResult:
        return ValidationResult(
            valid=True,
            node_statuses={
                node.id: NodeStatus(
                    node_id=node.id,
                    status="unexecuted",
                    cached=False,
                )
                for node in graph.nodes
            },
            errors=[],
        )

    def _graph_differs_from_saved(
        self,
        store: WorkflowStoreService,
        workflow_id: str,
        graph: GraphState,
    ) -> bool:
        try:
            saved = store.get_workflow(workflow_id).graph
        except FileNotFoundError:
            return True
        return saved.model_dump(mode="json") != graph.model_dump(mode="json")

    @staticmethod
    def _agent_instructions(agent_name: str) -> str:
        return (
            f"# BioImageFlow Agent Instructions for {agent_name}\n\n"
            "This workspace is managed by BioImageFlow. Read "
            "`.bioimageflow/agent-state.json` to find the active workflow, "
            "API base URL, and live draft path.\n\n"
            "Use BioImageFlow API or `bioimageflow-agent` commands for workflow "
            "changes. Do not hand-edit `workflow.json` derived sections. The "
            "live unsaved graph is stored in the workflow-local draft file.\n"
        )
