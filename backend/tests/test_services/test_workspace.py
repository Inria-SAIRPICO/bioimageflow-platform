"""Tests for workspace path resolution."""

from pathlib import Path

import pytest

from bioimageflow_server.models.settings import Settings
from bioimageflow_server.services.workspace import (
    WorkspacePermissionError,
    WorkspaceService,
)


def test_desktop_workspace_uses_configured_path(tmp_path: Path) -> None:
    service = WorkspaceService(
        settings=Settings(deployment_mode="desktop"),
        deployment_mode="desktop",
        workspace_path=tmp_path / "workspace",
    )

    info = service.info()

    assert info.workspace_path == str(tmp_path / "workspace")
    assert info.workflows_root == str(tmp_path / "workspace" / "workflows")
    assert info.tools_root == str(tmp_path / "workspace" / "tools")
    assert info.outputs_root == str(tmp_path / "workspace" / "outputs")
    assert info.user_editable is True


def test_webapp_workspace_is_scoped_to_user(tmp_path: Path) -> None:
    service = WorkspaceService(
        settings=Settings(deployment_mode="webapp"),
        deployment_mode="webapp",
        workspaces_root=tmp_path / "users",
        user_id="user1",
    )

    assert service.workspace_path() == tmp_path / "users" / "user1" / "workspace"
    assert service.info().user_editable is False


def test_webapp_workspace_cannot_be_changed_by_user(tmp_path: Path) -> None:
    service = WorkspaceService(
        settings=Settings(deployment_mode="webapp"),
        deployment_mode="webapp",
        workspaces_root=tmp_path / "users",
        user_id="user1",
    )

    with pytest.raises(WorkspacePermissionError):
        service.update_workspace_path(str(tmp_path / "other"))
