"""Agent workspace preparation and constrained bridge operations."""

from __future__ import annotations

import json
import re
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4


_WORKFLOW_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_PLATFORM_REFERENCE_IGNORE = shutil.ignore_patterns(
    ".git",
    ".bioimageflow-agent",
    ".bioimageflow",
    ".worktrees",
    ".venv",
    "bioimageflow",
    "external",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
)


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

    def prepare_context(self, active_context: dict[str, Any] | None = None) -> dict[str, str]:
        agent_root = self._workflows_root / ".bioimageflow-agent"
        reference = agent_root / "platform-reference"
        agent_root.mkdir(parents=True, exist_ok=True)
        self._refresh_platform_reference(reference)
        context = {
            "workflows_root": str(self._workflows_root),
            "platform_reference": str(reference),
            "context_file": str(agent_root / "context.json"),
        }
        context_file_payload = dict(context)
        if active_context is not None:
            context_file_payload.update(
                {
                    "active_context": active_context,
                    "instructions": (
                        "Edit only workflows and workflow-local tools. Use the platform APIs for "
                        "drafts, validation, package approval requests, and execution. The copied "
                        "platform reference is read-only context, not an edit target."
                    ),
                }
            )
        (agent_root / "context.json").write_text(
            json.dumps(context_file_payload, indent=2, sort_keys=True) + "\n",
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

    def list_package_install_requests(self) -> list[AgentPackageInstallRequest]:
        return list(self._requests.values())

    def reject_package_install(self, request_id: str) -> None:
        self._require_request(request_id)
        del self._requests[request_id]

    async def install_requested_package(self, request_id: str) -> None:
        request = self._require_request(request_id)
        if not request.approved:
            raise AgentPackageApprovalRequiredError("Package install requires approval")
        if self._package_installer is None:
            raise RuntimeError("Package installer not configured")
        await self._package_installer.install(request.package_name, version=request.version)
        self._requests.pop(request_id, None)

    async def approve_package_install(self, request_id: str) -> None:
        request = self._require_request(request_id)
        self._requests[request_id] = AgentPackageInstallRequest(
            id=request.id,
            package_name=request.package_name,
            version=request.version,
            approved=True,
        )
        try:
            await self.install_requested_package(request_id)
        except Exception:
            self._requests[request_id] = request
            raise

    def _refresh_platform_reference(self, reference: Path) -> None:
        if reference.exists():
            self._make_writable(reference)
            shutil.rmtree(reference)
        shutil.copytree(
            self._platform_repo_root,
            reference,
            symlinks=False,
            ignore=self._ignore_reference_entries,
        )
        self._make_readonly(reference)

    def _resolve_workflow_tool_path(self, workflow_name: str, relative_path: str) -> Path:
        if not _WORKFLOW_NAME_RE.match(workflow_name):
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

    def _ignore_reference_entries(self, src: str, names: list[str]) -> set[str]:
        ignored = set(_PLATFORM_REFERENCE_IGNORE(src, names))
        src_path = Path(src).resolve()
        try:
            relative = self._workflows_root.relative_to(src_path)
        except ValueError:
            return ignored
        if relative.parts:
            ignored.add(relative.parts[0])
        return ignored

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
