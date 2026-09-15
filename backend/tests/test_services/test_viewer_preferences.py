from __future__ import annotations

import json
from uuid import uuid4

import pytest

from bioimageflow_server.models.viewer_preferences import (
    PersistentOutputPreferenceKey,
    SessionOutputPreferenceKey,
)
from bioimageflow_server.services.viewer_preferences import (
    ViewerPreferenceStore,
    ViewerPreferencesRevisionConflict,
    ViewerPreferenceTargetConflict,
    ensure_workspace_identity,
)


def test_workspace_identity_and_favorites_are_durable_and_separate(tmp_path) -> None:
    workspace_id = ensure_workspace_identity(tmp_path / "workspace")
    assert ensure_workspace_identity(tmp_path / "workspace") == workspace_id
    raw_identity = json.loads(
        (tmp_path / "workspace/.bioimageflow/workspace.json").read_text()
    )
    assert raw_identity == {"id": str(workspace_id), "version": 1}

    store = ViewerPreferenceStore(tmp_path / "user/viewer-preferences.json")
    key = PersistentOutputPreferenceKey(
        workspace_id=workspace_id,
        workflow_id="analysis",
        identity_generation=3,
        node_path=("segment",),
        output_key="mask",
    )
    first, second = uuid4(), uuid4()
    assert store.set(key, first, expected_revision=0).revision == 1
    replaced = store.set(key, second, expected_revision=1)
    assert replaced.revision == 2
    assert replaced.favorites[0].environment_id == second

    with pytest.raises(ViewerPreferencesRevisionConflict):
        store.set(key, first, expected_revision=1)
    with pytest.raises(ViewerPreferenceTargetConflict):
        store.unset(key, expected_environment_id=first, expected_revision=2)
    assert store.unset(
        key, expected_environment_id=second, expected_revision=2
    ).favorites == []


def test_move_delete_and_session_lifecycle_use_structural_identity(tmp_path) -> None:
    workspace_id = uuid4()
    environment_id = uuid4()
    store = ViewerPreferenceStore(tmp_path / "viewer-preferences.json")
    persistent = PersistentOutputPreferenceKey(
        workspace_id=workspace_id,
        workflow_id="old",
        identity_generation=4,
        node_path=("child", "segment"),
        output_key="mask",
    )
    store.set(persistent, environment_id, expected_revision=0)
    moved = store.move_workflow_generation(
        workspace_id,
        "old",
        4,
        "new",
        9,
    )
    moved_key = moved.favorites[0].key
    assert isinstance(moved_key, PersistentOutputPreferenceKey)
    assert (moved_key.workflow_id, moved_key.identity_generation) == ("new", 9)
    assert store.clear_workflow_generation(workspace_id, "new", 8) == moved
    assert store.clear_workflow_generation(workspace_id, "new", 9).favorites == []

    session_id = str(uuid4())
    session_key = SessionOutputPreferenceKey(
        workspace_id=workspace_id,
        session_id=session_id,
        node_path=("measure",),
        output_key="table",
    )
    store.set(session_key, environment_id, expected_revision=3)
    applied = store.apply_session(
        workspace_id,
        session_id,
        workflow_id="root",
        identity_generation=2,
        parent_node_path=("nested",),
        surviving_outputs={(("measure",), "table")},
    )
    applied_key = applied.favorites[0].key
    assert isinstance(applied_key, PersistentOutputPreferenceKey)
    assert applied_key.node_path == ("nested", "measure")
    assert applied_key.output_key == "table"


def test_environment_forget_journal_is_forward_recoverable(tmp_path) -> None:
    environment_id = uuid4()
    store = ViewerPreferenceStore(tmp_path / "viewer-preferences.json")
    key = PersistentOutputPreferenceKey(
        workspace_id=uuid4(),
        workflow_id="analysis",
        identity_generation=1,
        node_path=("n1",),
        output_key="image",
    )
    store.set(key, environment_id, expected_revision=0)
    store.prepare_environment_forget(environment_id, registry_revision=7)

    restarted = ViewerPreferenceStore(store.path)
    assert restarted.apply_prepared_environment_forget() == environment_id
    assert restarted.snapshot().favorites == []
    restarted.complete_environment_forget()
    assert restarted.pending_environment_forget() is None
