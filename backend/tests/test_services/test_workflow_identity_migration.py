"""Identity migration changes mutable attribution without changing run authority."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from bioimageflow_server.models.execution_runtime import ExecutionSnapshot
from bioimageflow_server.models.viewer_preferences import (
    PersistentOutputPreferenceKey,
    SessionOutputPreferenceKey,
    ViewerFavorite,
    ViewerPreferencesSnapshot,
)
from bioimageflow_server.services.execution_runtime import _execution_actions
from bioimageflow_server.services.workflow_identity_migration import (
    validate_identity_reference_payload,
    workflow_identity_reference_artifacts,
)


def _execution(workspace: Path, *, state: str = "succeeded") -> tuple[Path, dict]:
    path = workspace / ".bioimageflow" / "executions" / "retained-run.json"
    path.parent.mkdir(parents=True)
    snapshot = ExecutionSnapshot(
        execution_id="retained-run", workflow_id="Analysis/nuclei", revision=9,
        draft_revision=4, backend="managed_remote", target_id="cluster", state=state,
        backend_metadata={"storage_path": "/captured/storage", "run_id": "immutable-run"},
    )
    raw = snapshot.model_dump(mode="json")
    path.write_text(json.dumps(raw))
    return path, raw


def test_execution_attribution_preserves_revision_and_captured_storage(tmp_path: Path) -> None:
    path, before = _execution(tmp_path)
    original_bytes = path.read_bytes()
    identity = str(uuid4())

    targets = workflow_identity_reference_artifacts(tmp_path, {"Analysis/nuclei": (identity, 1)})

    assert targets == [(path, {**before, "workflow_id": identity}, "execution_registry")]
    assert path.read_bytes() == original_bytes
    validate_identity_reference_payload(targets[0][2], targets[0][1])


def test_reused_path_history_remains_explicitly_unresolved(tmp_path: Path) -> None:
    path, before = _execution(tmp_path)
    targets = workflow_identity_reference_artifacts(tmp_path, {"Analysis/nuclei": (str(uuid4()), 3)})
    assert len(targets) == 1
    target_path, payload, _kind = targets[0]
    assert target_path == path
    assert payload["workflow_id"] is None
    assert payload["revision"] == before["revision"]
    assert payload["backend_metadata"]["storage_path"] == "/captured/storage"
    assert payload["backend_metadata"]["workflow_identity_resolution"]["legacy_path"] == "Analysis/nuclei"
    snapshot = ExecutionSnapshot.model_validate(payload)
    actions = _execution_actions(snapshot, {})
    assert not actions.retry.available
    assert not actions.recompute.available
    assert "unresolved" in actions.retry.reason


def test_active_execution_blocks_identity_rewrite(tmp_path: Path) -> None:
    path, _before = _execution(tmp_path, state="running")
    original = path.read_bytes()
    with pytest.raises(ValueError, match="blocked by active execution"):
        workflow_identity_reference_artifacts(tmp_path, {"Analysis/nuclei": (str(uuid4()), 1)})
    assert path.read_bytes() == original


def test_favorites_remap_only_exact_workspace_and_incarnation(tmp_path: Path) -> None:
    workspace_id, other_workspace, environment_id = uuid4(), uuid4(), uuid4()
    metadata = tmp_path / ".bioimageflow"
    metadata.mkdir()
    (metadata / "workspace.json").write_text(json.dumps({"version": 1, "id": str(workspace_id)}))
    preferences = tmp_path / "settings" / "viewer-preferences.json"
    preferences.parent.mkdir()
    exact = PersistentOutputPreferenceKey(
        workspace_id=workspace_id, workflow_id="Analysis/nuclei", identity_generation=2,
        node_path=("node",), output_key="image",
    )
    keys = [exact, exact.model_copy(update={"identity_generation": 1}),
            exact.model_copy(update={"workspace_id": other_workspace}),
            SessionOutputPreferenceKey(workspace_id=workspace_id, session_id="private", node_path=("node",), output_key="image")]
    snapshot = ViewerPreferencesSnapshot(
        revision=8, favorites=[ViewerFavorite(key=key, environment_id=environment_id) for key in keys],
    )
    before = snapshot.model_dump(mode="json")
    preferences.write_text(json.dumps(before))
    identity = str(uuid4())

    targets = workflow_identity_reference_artifacts(
        tmp_path, {"Analysis/nuclei": (identity, 2)}, viewer_preferences_path=preferences,
    )

    assert len(targets) == 1
    path, payload, kind = targets[0]
    assert path == preferences and kind == "viewer_preferences"
    assert payload["revision"] == 8
    assert payload["favorites"][0]["key"] == {**before["favorites"][0]["key"], "workflow_id": identity}
    assert payload["favorites"][1:] == before["favorites"][1:]
    assert json.loads(preferences.read_text()) == before
    validate_identity_reference_payload(kind, payload)


def test_identity_reference_kinds_are_explicitly_admitted() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        validate_identity_reference_payload("arbitrary_file", {})


@pytest.mark.parametrize("generation", [1, 3])
def test_agent_context_migration_preserves_only_unambiguous_ownership(tmp_path: Path, generation: int) -> None:
    path = tmp_path / ".bioimageflow" / "agent-state.json"
    path.parent.mkdir()
    raw = {"api_base_url": "http://test/api/v1", "active_workflow_id": "Analysis/nuclei", "current_draft_revision": 8}
    path.write_text(json.dumps(raw))
    identity = str(uuid4())

    [(target, payload, kind)] = workflow_identity_reference_artifacts(tmp_path, {"Analysis/nuclei": (identity, generation)})

    assert target == path and kind == "agent_context"
    assert payload["current_draft_revision"] == 8
    assert payload["active_workflow_id"] == (identity if generation == 1 else None)
    assert json.loads(path.read_text()) == raw
    validate_identity_reference_payload(kind, payload)
