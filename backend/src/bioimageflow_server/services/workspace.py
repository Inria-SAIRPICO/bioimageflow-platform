"""Workspace path resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.workspace import WorkspaceInfo


DEFAULT_DESKTOP_WORKSPACE = Path("~/BioImageFlow/workspace")
DEFAULT_WEBAPP_WORKSPACES_ROOT = Path("/data/users")


class WorkspacePermissionError(PermissionError):
    """Raised when a user attempts to change an admin-managed workspace."""


def normalize_workspace_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return candidate.resolve(strict=False)


class WorkspaceService:
    def __init__(
        self,
        *,
        settings: Settings,
        deployment_mode: Literal["desktop", "webapp"],
        workspace_path: Path | None = None,
        workspaces_root: Path | None = None,
        user_id: str | None = None,
    ) -> None:
        self.settings = settings
        self.deployment_mode = deployment_mode
        self._workspace_path = workspace_path
        self._workspaces_root = workspaces_root
        self.user_id = user_id or "default"

    def workspace_path(self) -> Path:
        if self.deployment_mode == "webapp":
            root = self._workspaces_root or (
                Path(self.settings.workspaces_root)
                if self.settings.workspaces_root
                else DEFAULT_WEBAPP_WORKSPACES_ROOT
            )
            return normalize_workspace_path(root) / self.user_id / "workspace"
        configured = self._workspace_path or (
            Path(self.settings.workspace_path)
            if self.settings.workspace_path
            else DEFAULT_DESKTOP_WORKSPACE
        )
        return normalize_workspace_path(configured)

    def workflows_root(self) -> Path:
        return self.workspace_path() / "workflows"

    def tools_root(self) -> Path:
        return self.workspace_path() / "tools"

    def outputs_root(self) -> Path:
        return self.workspace_path() / "outputs"

    def info(self) -> WorkspaceInfo:
        workspace = self.workspace_path()
        return WorkspaceInfo(
            workspace_path=str(workspace),
            workflows_root=str(workspace / "workflows"),
            tools_root=str(workspace / "tools"),
            outputs_root=str(workspace / "outputs"),
            deployment_mode=self.deployment_mode,
            user_editable=self.deployment_mode == "desktop",
        )

    def update_workspace_path(self, path: str) -> WorkspaceInfo:
        if self.deployment_mode != "desktop":
            raise WorkspacePermissionError("workspace path is admin-managed in webapp mode")
        self._workspace_path = normalize_workspace_path(path)
        return self.info()
