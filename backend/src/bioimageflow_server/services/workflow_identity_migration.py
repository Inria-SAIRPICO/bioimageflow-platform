"""Prepare mutable workflow references for the confirmed identity migration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from bioimageflow_server.models.execution_runtime import ExecutionSnapshot
from bioimageflow_server.models.viewer_preferences import ViewerPreferencesSnapshot

IdentityMigrationMap = dict[str, tuple[str, int]]
IdentityMigrationArtifact = tuple[Path, dict[str, Any], str]


def workflow_identity_reference_artifacts(
    workspace_dir: Path,
    identities: IdentityMigrationMap,
    *,
    viewer_preferences_path: Path | None = None,
) -> list[IdentityMigrationArtifact]:
    """Capture proposed replacements without writing or changing CAS revisions.

    Execution history without an incarnation can only be attributed when the
    legacy path has never been reused. Older ambiguous history stays accessible
    by execution ID rather than being attached to an unrelated current workflow.
    Immutable library result records and captured runtime storage are untouched.
    """

    artifacts: list[IdentityMigrationArtifact] = []
    agent_path = workspace_dir / ".bioimageflow" / "agent-state.json"
    if agent_path.is_file():
        raw_agent = _read_object(agent_path)
        identity = identities.get(str(raw_agent.get("active_workflow_id")))
        if identity is not None:
            generation = raw_agent.get("identity_generation")
            if generation == identity[1] or (generation is None and identity[1] in (0, 1)):
                agent = {**raw_agent, "active_workflow_id": identity[0], "identity_generation": identity[1]}
            else:
                agent = {
                    **raw_agent,
                    "active_workflow_id": None,
                    "workflow_identity_resolution": {
                        "legacy_path": raw_agent["active_workflow_id"],
                        "reason": "Select an active workflow by UUID to resolve legacy ownership",
                    },
                }
            artifacts.append((agent_path, agent, "agent_context"))
    root = workspace_dir / ".bioimageflow" / "executions"
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                continue
            raw = _read_object(path)
            # Legacy execution-format migration remains its own contract.
            if raw.get("schema_version") != 2:
                continue
            snapshot = ExecutionSnapshot.model_validate(raw)
            identity = identities.get(str(raw.get("workflow_id")))
            if identity is None:
                continue
            if not snapshot.terminal:
                raise ValueError(
                    "Workflow identity migration is blocked by active execution "
                    f"{snapshot.execution_id}"
                )
            if identity[1] in (0, 1):
                payload = {**raw, "workflow_id": identity[0]}
            else:
                payload = {
                    **raw,
                    "workflow_id": None,
                    "backend_metadata": {
                        **raw.get("backend_metadata", {}),
                        "workflow_identity_resolution": {
                            "legacy_path": raw["workflow_id"],
                            "reason": "Legacy execution has no incarnation for a reused path",
                        },
                    },
                }
            if payload != raw:
                artifacts.append((path, payload, "execution_registry"))

    identity_path = workspace_dir / ".bioimageflow" / "workspace.json"
    if (
        viewer_preferences_path is not None
        and viewer_preferences_path.is_file()
        and identity_path.is_file()
    ):
        workspace = _read_object(identity_path)
        if workspace.get("version") != 1:
            raise ValueError("Invalid workspace identity during workflow migration")
        workspace_id = str(UUID(str(workspace.get("id"))))
        raw = _read_object(viewer_preferences_path)
        ViewerPreferencesSnapshot.model_validate(raw)
        favorites: list[dict[str, Any]] = []
        for favorite in raw["favorites"]:
            key = favorite["key"]
            identity = identities.get(str(key.get("workflow_id")))
            if (
                key.get("kind") == "persistent"
                and key.get("workspace_id") == workspace_id
                and identity is not None
                and key.get("identity_generation") == identity[1]
            ):
                favorite = {**favorite, "key": {**key, "workflow_id": identity[0]}}
            favorites.append(favorite)
        payload = {**raw, "favorites": favorites}
        if payload != raw:
            artifacts.append((viewer_preferences_path, payload, "viewer_preferences"))
    return artifacts


def validate_identity_reference_payload(kind: str, payload: dict[str, Any]) -> None:
    """Validate only the explicitly admitted mutable reference authorities."""

    if kind == "execution_registry":
        ExecutionSnapshot.model_validate(payload)
    elif kind == "viewer_preferences":
        ViewerPreferencesSnapshot.model_validate(payload)
    elif kind == "agent_context":
        from bioimageflow_server.agent_mcp import AgentState

        AgentState.model_validate(payload)
    else:
        raise ValueError(f"Unsupported workflow identity reference kind: {kind}")


def _read_object(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError(f"Workflow identity reference is a symlink: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Workflow identity reference must contain an object: {path}")
    return payload
