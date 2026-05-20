"""Tests for agent workspace preparation and bridge write constraints."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from bioimageflow_server.services.agent_workspace import (
    AgentBridgePermissionError,
    AgentPackageApprovalRequiredError,
    AgentWorkspaceService,
)


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_prepares_repo_reference_as_readonly_copy_not_symlink(tmp_path: Path) -> None:
    workflows_root = tmp_path / "workflows"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "pyproject.toml").write_text("[project]\nname='bif'\n", encoding="utf-8")

    service = AgentWorkspaceService(
        workflows_root=workflows_root,
        platform_repo_root=repo_root,
    )

    context = service.prepare_context()

    reference = Path(context["platform_reference"])
    copied_file = reference / "pyproject.toml"
    assert reference.exists()
    assert not reference.is_symlink()
    assert copied_file.read_text(encoding="utf-8") == "[project]\nname='bif'\n"
    assert not (copied_file.stat().st_mode & 0o222)

    copied_file.chmod(0o644)
    copied_file.write_text("changed\n", encoding="utf-8")
    assert (repo_root / "pyproject.toml").read_text(encoding="utf-8") == (
        "[project]\nname='bif'\n"
    )


def test_context_file_is_written_under_workflows_root(tmp_path: Path) -> None:
    workflows_root = tmp_path / "workflows"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    service = AgentWorkspaceService(
        workflows_root=workflows_root,
        platform_repo_root=repo_root,
    )

    context = service.prepare_context()

    context_path = workflows_root / ".bioimageflow-agent" / "context.json"
    assert context_path.is_file()
    assert json.loads(context_path.read_text(encoding="utf-8")) == context


def test_bridge_rejects_writes_outside_workflows_tools(tmp_path: Path) -> None:
    workflows_root = tmp_path / "workflows"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    service = AgentWorkspaceService(
        workflows_root=workflows_root,
        platform_repo_root=repo_root,
    )

    service.write_workflow_tool_file("wf", "tools/my_tool.py", "class MyTool: pass\n")
    assert (workflows_root / "wf" / "tools" / "my_tool.py").is_file()

    with pytest.raises(AgentBridgePermissionError):
        service.write_workflow_tool_file("wf", "../outside.py", "")

    with pytest.raises(AgentBridgePermissionError):
        service.write_workflow_tool_file("wf", "workflow.json", "{}")


async def test_package_install_request_requires_explicit_approval(tmp_path: Path) -> None:
    installer = AsyncMock()
    service = AgentWorkspaceService(
        workflows_root=tmp_path / "workflows",
        platform_repo_root=tmp_path,
        package_installer=installer,
    )

    request = service.request_package_install("cellpose", version="1.0")

    with pytest.raises(AgentPackageApprovalRequiredError):
        await service.install_requested_package(request.id)
    installer.install.assert_not_awaited()

    await service.approve_package_install(request.id)

    installer.install.assert_awaited_once_with("cellpose", version="1.0")
