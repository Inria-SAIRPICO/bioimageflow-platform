"""Tests for agent bridge routes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from bioimageflow_server.app import create_app
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.agent_workspace import AgentWorkspaceService


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_agent_bridge_write_rejects_outside_tools(tmp_path: Path) -> None:
    workflows_root = tmp_path / "workflows"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    service = AgentWorkspaceService(
        workflows_root=workflows_root,
        platform_repo_root=repo_root,
    )
    app = create_app(
        config=AppConfig(
            agent_workspace_service=service,
            workflow_root=workflows_root,
            disable_hot_reload=True,
        )
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/v1/agent-bridge/workflows/wf/tools",
            json={"path": "../platform.py", "content": ""},
        )

    assert response.status_code == 403
    assert response.json()["error"] == "agent_write_forbidden"


async def test_agent_bridge_package_install_requires_approval(tmp_path: Path) -> None:
    installer = AsyncMock()
    service = AgentWorkspaceService(
        workflows_root=tmp_path / "workflows",
        platform_repo_root=tmp_path,
        package_installer=installer,
    )
    app = create_app(
        config=AppConfig(
            agent_workspace_service=service,
            package_installer=installer,
            disable_hot_reload=True,
        )
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        requested = await client.post(
            "/api/v1/agent-bridge/package-install-requests",
            json={"package_name": "cellpose", "version": "1.0"},
        )
        assert requested.status_code == 202
        installer.install.assert_not_awaited()

        approved = await client.post(
            "/api/v1/agent-bridge/package-install-requests/"
            f"{requested.json()['id']}/approve"
        )

    assert approved.status_code == 200
    assert approved.json() == {"status": "installed"}
    installer.install.assert_awaited_once_with("cellpose", version="1.0")


async def test_agent_bridge_is_gated_when_openhands_unavailable(tmp_path: Path) -> None:
    service = AgentWorkspaceService(
        workflows_root=tmp_path / "workflows",
        platform_repo_root=tmp_path,
    )
    app = create_app(
        config=AppConfig(
            settings=Settings(deployment_mode="desktop", openhands_enabled=False),
            agent_workspace_service=service,
            workflow_root=tmp_path / "workflows",
            disable_hot_reload=True,
        )
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        context = await client.get("/api/v1/agent-bridge/context")
        write = await client.put(
            "/api/v1/agent-bridge/workflows/wf/tools",
            json={"path": "tools/a.py", "content": ""},
        )
        package = await client.post(
            "/api/v1/agent-bridge/package-install-requests",
            json={"package_name": "cellpose"},
        )

    assert context.status_code == 403
    assert write.status_code == 403
    assert package.status_code == 403
