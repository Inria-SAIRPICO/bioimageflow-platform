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

    with pytest.raises(AgentBridgePermissionError):
        service.write_workflow_tool_file("..", "tools/escape.py", "")

    with pytest.raises(AgentBridgePermissionError):
        service.write_workflow_tool_file(".", "tools/escape.py", "")


def test_platform_reference_copy_ignores_nested_workflow_agent_dir(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    workflows_root = repo_root / "workflows"
    recursive_agent = workflows_root / ".bioimageflow-agent" / "platform-reference"
    recursive_agent.mkdir(parents=True)
    (recursive_agent / "should_not_copy.txt").write_text("recursive\n", encoding="utf-8")
    (repo_root / "backend").mkdir()
    (repo_root / "backend" / "app.py").write_text("source\n", encoding="utf-8")
    service = AgentWorkspaceService(
        workflows_root=workflows_root,
        platform_repo_root=repo_root,
    )

    context = service.prepare_context()

    reference = Path(context["platform_reference"])
    assert (reference / "backend" / "app.py").is_file()
    assert not (reference / "workflows" / ".bioimageflow-agent").exists()


def test_platform_reference_copy_ignores_agent_dir_when_workspace_is_repo_root(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    recursive_agent = repo_root / ".bioimageflow-agent" / "platform-reference"
    recursive_agent.mkdir(parents=True)
    (recursive_agent / "should_not_copy.txt").write_text("recursive\n", encoding="utf-8")
    (repo_root / "backend").mkdir()
    (repo_root / "backend" / "app.py").write_text("source\n", encoding="utf-8")
    service = AgentWorkspaceService(
        workflows_root=repo_root,
        platform_repo_root=repo_root,
    )

    context = service.prepare_context()

    reference = Path(context["platform_reference"])
    assert (reference / "backend" / "app.py").is_file()
    assert not (reference / ".bioimageflow-agent").exists()


def test_platform_reference_copy_ignores_heavy_local_runtime_dirs(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "backend").mkdir()
    (repo_root / "backend" / "app.py").write_text("source\n", encoding="utf-8")
    for relative in [
        ".pixi/envs/default/bin/python",
        "wetlands/pixi/workspaces/bioimageflow-general/.pixi/envs/default/bin/python",
        "bif_data/raw.bin",
    ]:
        path = repo_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("heavy\n", encoding="utf-8")
    service = AgentWorkspaceService(
        workflows_root=repo_root / "workflows",
        platform_repo_root=repo_root,
    )

    context = service.prepare_context()

    reference = Path(context["platform_reference"])
    assert (reference / "backend" / "app.py").is_file()
    assert not (reference / ".pixi").exists()
    assert not (reference / "wetlands").exists()
    assert not (reference / "bif_data").exists()


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
    assert service.list_package_install_requests() == []


async def test_package_install_failure_restores_pending_request(tmp_path: Path) -> None:
    installer = AsyncMock()
    installer.install.side_effect = RuntimeError("network down")
    service = AgentWorkspaceService(
        workflows_root=tmp_path / "workflows",
        platform_repo_root=tmp_path,
        package_installer=installer,
    )
    request = service.request_package_install("cellpose")

    with pytest.raises(RuntimeError, match="network down"):
        await service.approve_package_install(request.id)

    assert service.list_package_install_requests() == [request]
