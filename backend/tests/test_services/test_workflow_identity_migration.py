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


def test_source_publication_addresses_the_workflow_uuid(tmp_path: Path) -> None:
    from bioimageflow_server.models.workflow import WorkflowCreate
    from bioimageflow_server.services.tool_registry import ToolRegistryService
    from bioimageflow_server.services.workflow_sources import WorkflowSourceService
    from bioimageflow_server.services.workflow_store import WorkflowStoreService

    store = WorkflowStoreService(tmp_path / "workflows", ToolRegistryService())
    info = store.create_workflow(WorkflowCreate(name="folder/workflow"))
    before = store.read_workflow_document(info.id)
    graph = before.graph.model_copy(update={"display_name": "Applied source graph"})

    result = WorkflowSourceService(lambda: store)._commit_graph_and_sources(
        store, info.id, graph, [], authoring_source=None,
    )

    after = store.read_workflow_document(info.id)
    assert after.graph == result.graph == graph
    assert after.workflow_id == info.id
    assert store.relative_path_for_workflow(info.id) == "folder/workflow"
    assert not (store.root_dir / info.id).exists()


def test_source_publication_refuses_external_move_before_creating_source_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bioimageflow_server.models.workflow import WorkflowCreate
    from bioimageflow_server.services.tool_registry import ToolRegistryService
    from bioimageflow_server.services.workflow_artifacts import OwnedWorkflowSources
    from bioimageflow_server.services.workflow_sources import WorkflowSourceConflict, WorkflowSourceService
    from bioimageflow_server.services.workflow_store import WorkflowStoreService

    store = WorkflowStoreService(tmp_path / "workflows", ToolRegistryService())
    info = store.create_workflow(WorkflowCreate(name="original"))
    graph = store.read_workflow_document(info.id).graph
    original = store.workflow_dir(info.id)
    moved = original.with_name("external-move")

    def moved_stage(owned, records):
        temporary = owned.root / ".staged-source"
        temporary.write_bytes(b"source")
        final = owned.root / "new-source" / "module.json"
        original.rename(moved)
        return [(temporary, final)]

    monkeypatch.setattr(OwnedWorkflowSources, "stage", moved_stage)
    with pytest.raises(WorkflowSourceConflict, match="moved"):
        WorkflowSourceService(lambda: store)._commit_graph_and_sources(
            store, info.id, graph, [], authoring_source=None,
        )
    assert not original.exists()
    assert not (moved / "tools/new-source").exists()
    assert store.read_workflow_document(info.id).graph == graph


def test_result_download_filename_uses_relative_path_without_leaking_uuid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil

    from bioimageflow_server.models.workflow import WorkflowCreate
    from bioimageflow_server.services.tool_registry import ToolRegistryService
    from bioimageflow_server.services.workflow_archive import safe_workflow_export_stem
    from bioimageflow_server.services.workflow_exports import WorkflowExportService
    from bioimageflow_server.services.workflow_store import WorkflowStoreService

    store = WorkflowStoreService(tmp_path / "workflows", ToolRegistryService())
    info = store.create_workflow(WorkflowCreate(name="folder/workflow"))

    def export(_storage, *, destination, **_kwargs):
        destination.mkdir(parents=True)
        output = destination / "result.txt"
        output.write_text("retained result")
        return [output]

    monkeypatch.setattr("bioimageflow_server.services.workflow_exports.export_outputs", export)
    prepared = WorkflowExportService(store).prepare_latest_results(info.id)
    try:
        assert prepared.filename == f"{safe_workflow_export_stem(info.relative_path)}-latest-results.zip"
        assert info.id not in prepared.filename
        assert prepared.path.is_file()
    finally:
        shutil.rmtree(prepared.cleanup_root)


@pytest.mark.parametrize("generation", [1, 3])
def test_legacy_local_execution_is_normalized_without_guessing_reused_ownership(
    tmp_path: Path, generation: int,
) -> None:
    path, raw = _execution(tmp_path)
    raw.update(schema_version=1, backend="wetlands", actions={"obsolete": "old wire shape"})
    raw.pop("diagnostics")
    path.write_text(json.dumps(raw))
    original = path.read_bytes()
    identity = str(uuid4())

    [(target, payload, kind)] = workflow_identity_reference_artifacts(
        tmp_path, {"Analysis/nuclei": (identity, generation)},
    )

    assert target == path and kind == "execution_registry"
    assert payload["schema_version"] == 2
    assert payload["revision"] == raw["revision"]
    assert payload["draft_revision"] == raw["draft_revision"]
    assert payload["backend_metadata"]["storage_path"] == "/captured/storage"
    assert payload["workflow_id"] == (identity if generation == 1 else None)
    if generation == 3:
        assert payload["backend_metadata"]["workflow_identity_resolution"]["legacy_path"] == "Analysis/nuclei"
    assert path.read_bytes() == original
    validate_identity_reference_payload(kind, payload)


def test_active_legacy_local_execution_blocks_confirmed_identity_migration(tmp_path: Path) -> None:
    path, raw = _execution(tmp_path, state="running")
    raw.update(schema_version=1, backend="direct")
    path.write_text(json.dumps(raw))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="blocked by active execution retained-run"):
        workflow_identity_reference_artifacts(tmp_path, {"Analysis/nuclei": (str(uuid4()), 1)})
    assert path.read_bytes() == before


def test_legacy_distributed_history_remains_outside_local_migration(tmp_path: Path) -> None:
    path, raw = _execution(tmp_path, state="running")
    raw.update(schema_version=1)
    path.write_text(json.dumps(raw))
    before = path.read_bytes()
    assert workflow_identity_reference_artifacts(tmp_path, {"Analysis/nuclei": (str(uuid4()), 1)}) == []
    assert path.read_bytes() == before


@pytest.mark.parametrize("has_current_workflow", [True, False])
def test_missing_execution_and_agent_owners_become_unresolved_in_reference_only_confirmed_plan(
    tmp_path: Path, has_current_workflow: bool,
) -> None:
    from bioimageflow_server.models.workflow import WorkflowCreate
    from bioimageflow_server.services.execution_registry import ExecutionRegistry
    from bioimageflow_server.services.tool_registry import ToolRegistryService
    from bioimageflow_server.services.workflow_store import WorkflowStoreService

    store = WorkflowStoreService(tmp_path / "workflows", ToolRegistryService())
    current = store.create_workflow(WorkflowCreate(name="current")) if has_current_workflow else None
    path, raw = _execution(tmp_path)
    before = path.read_bytes()
    agent_path = tmp_path / ".bioimageflow" / "agent-state.json"
    agent_raw = {"api_base_url": "http://test/api/v1", "active_workflow_id": "deleted/workflow",
                 "identity_generation": 4, "current_draft_revision": 7}
    agent_path.write_text(json.dumps(agent_raw))
    agent_before = agent_path.read_bytes()
    store.configure_identity_migration_artifacts(
        lambda identities: workflow_identity_reference_artifacts(tmp_path, identities), {},
    )
    status = store.workflow_format_status()
    assert status.pending_plan_id is not None
    assert path.read_bytes() == before
    assert agent_path.read_bytes() == agent_before
    if current is not None:
        assert store.get_workflow(current.id).info.id == current.id

    result = store.apply_workflow_format_migrations(status.pending_plan_id)

    assert result.pending_plan_id is None
    history = ExecutionRegistry(tmp_path).get("retained-run")
    assert history.workflow_id is None
    assert history.revision == raw["revision"]
    assert history.backend_metadata["storage_path"] == "/captured/storage"
    assert history.backend_metadata["workflow_identity_resolution"]["legacy_path"] == "Analysis/nuclei"
    agent = json.loads(agent_path.read_text())
    assert agent["active_workflow_id"] is None
    assert agent["current_draft_revision"] == 7
    assert agent["workflow_identity_resolution"]["legacy_path"] == "deleted/workflow"
    backups = list((tmp_path / ".bioimageflow" / "backups" / "workflow-format").glob("**/retained-run.json"))
    assert len(backups) == 1 and backups[0].read_bytes() == before


def test_agent_generation_mismatch_retains_unresolved_context(tmp_path: Path) -> None:
    path = tmp_path / ".bioimageflow" / "agent-state.json"
    path.parent.mkdir()
    raw = {"api_base_url": "http://test/api/v1", "active_workflow_id": "Analysis/nuclei",
           "identity_generation": 1, "current_draft_revision": 9}
    path.write_text(json.dumps(raw))
    [(_target, payload, kind)] = workflow_identity_reference_artifacts(
        tmp_path, {"Analysis/nuclei": (str(uuid4()), 2)},
    )
    assert payload["active_workflow_id"] is None
    assert payload["current_draft_revision"] == 9
    assert payload["workflow_identity_resolution"]["legacy_path"] == raw["active_workflow_id"]
    assert json.loads(path.read_text()) == raw
    validate_identity_reference_payload(kind, payload)


def test_current_uuid_and_already_unresolved_references_are_not_rewritten(tmp_path: Path) -> None:
    path, raw = _execution(tmp_path)
    raw["workflow_id"] = str(uuid4())
    path.write_text(json.dumps(raw))
    assert workflow_identity_reference_artifacts(tmp_path, {}) == []
    raw["workflow_id"] = None
    path.write_text(json.dumps(raw))
    assert workflow_identity_reference_artifacts(tmp_path, {}) == []
