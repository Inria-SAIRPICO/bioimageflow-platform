"""Agent workspace preparation and constrained bridge operations."""

from __future__ import annotations

import json
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


class AgentBridgePermissionError(PermissionError):
    """Raised when an agent bridge write targets a forbidden path."""


class AgentPackageApprovalRequiredError(PermissionError):
    """Raised when a package install request has not been approved."""


class AgentPackageRequestNotFoundError(KeyError):
    """Raised when an approval request id is unknown."""


@dataclass(frozen=True)
class AgentPackageInstallRequest:
    """Package install request awaiting explicit user approval."""

    id: str
    package_name: str
    version: str | None
    approved: bool = False


class AgentWorkspaceService:
    """Prepares the agent-visible workspace and enforces write boundaries."""

    def __init__(
        self,
        *,
        workflows_root: Path,
        platform_repo_root: Path,
        package_installer: object | None = None,
    ) -> None:
        self._workflows_root = workflows_root.expanduser().resolve()
        self._platform_repo_root = platform_repo_root.expanduser().resolve()
        self._package_installer = package_installer
        self._requests: dict[str, AgentPackageInstallRequest] = {}

    @property
    def workflows_root(self) -> Path:
        return self._workflows_root

    def prepare_context(self) -> dict[str, str]:
        agent_root = self._workflows_root / ".bioimageflow-agent"
        reference = agent_root / "platform-reference"
        agent_root.mkdir(parents=True, exist_ok=True)
        self._refresh_platform_reference(reference)
        context = {
            "workflows_root": str(self._workflows_root),
            "platform_reference": str(reference),
            "context_file": str(agent_root / "context.json"),
        }
        (agent_root / "context.json").write_text(
            json.dumps(context, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return context

    def write_workflow_tool_file(
        self,
        workflow_name: str,
        relative_path: str,
        content: str,
    ) -> Path:
        target = self._resolve_workflow_tool_path(workflow_name, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def request_package_install(
        self,
        package_name: str,
        *,
        version: str | None = None,
    ) -> AgentPackageInstallRequest:
        request = AgentPackageInstallRequest(
            id=uuid4().hex,
            package_name=package_name,
            version=version,
            approved=False,
        )
        self._requests[request.id] = request
        return request

    async def install_requested_package(self, request_id: str) -> None:
        request = self._require_request(request_id)
        if not request.approved:
            raise AgentPackageApprovalRequiredError("Package install requires approval")
        if self._package_installer is None:
            raise RuntimeError("Package installer not configured")
        await self._package_installer.install(request.package_name, version=request.version)

    async def approve_package_install(self, request_id: str) -> None:
        request = self._require_request(request_id)
        self._requests[request_id] = AgentPackageInstallRequest(
            id=request.id,
            package_name=request.package_name,
            version=request.version,
            approved=True,
        )
        await self.install_requested_package(request_id)

    def _refresh_platform_reference(self, reference: Path) -> None:
        if reference.exists():
            self._make_writable(reference)
            shutil.rmtree(reference)
        ignore = shutil.ignore_patterns(
            ".git",
            ".venv",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
        )
        shutil.copytree(self._platform_repo_root, reference, symlinks=False, ignore=ignore)
        self._make_readonly(reference)

    def _resolve_workflow_tool_path(self, workflow_name: str, relative_path: str) -> Path:
        if not workflow_name or "/" in workflow_name or "\\" in workflow_name:
            raise AgentBridgePermissionError("Invalid workflow name")
        if Path(relative_path).is_absolute():
            raise AgentBridgePermissionError("Agent writes must be relative")
        target = (self._workflows_root / workflow_name / relative_path).resolve()
        tools_root = (self._workflows_root / workflow_name / "tools").resolve()
        try:
            target.relative_to(tools_root)
        except ValueError as exc:
            raise AgentBridgePermissionError(
                "Agent writes are limited to workflow-local tools"
            ) from exc
        return target

    def _require_request(self, request_id: str) -> AgentPackageInstallRequest:
        try:
            return self._requests[request_id]
        except KeyError as exc:
            raise AgentPackageRequestNotFoundError(request_id) from exc

    def _make_readonly(self, root: Path) -> None:
        for path in [root, *root.rglob("*")]:
            mode = path.stat().st_mode
            if path.is_dir():
                path.chmod(mode & ~0o222 | stat.S_IXUSR)
            else:
                path.chmod(mode & ~0o222)

    def _make_writable(self, root: Path) -> None:
        for path in [root, *root.rglob("*")]:
            mode = path.stat().st_mode
            path.chmod(mode | stat.S_IWUSR)
