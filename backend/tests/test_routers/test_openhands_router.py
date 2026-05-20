"""Tests for the OpenHands router and app wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.openhands import OpenHandsContext, OpenHandsStatus
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.openhands import OpenHandsLaunchError, OpenHandsService


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _fake_service(*, available: bool = True) -> MagicMock:
    service = MagicMock(spec=OpenHandsService)
    service.status = MagicMock(
        return_value=OpenHandsStatus(
            available=available,
            running=False,
            pid=None,
            url=None,
        )
    )
    service.launch = AsyncMock(
        return_value=OpenHandsStatus(
            available=available,
            running=True,
            pid=777,
            url="http://127.0.0.1:3000",
        )
    )
    service.shutdown = AsyncMock(
        return_value=OpenHandsStatus(
            available=available,
            running=False,
            pid=None,
            url=None,
        )
    )
    service.context = MagicMock(
        return_value=OpenHandsContext(
            available=available,
            reason=None if available else "disabled",
            deployment_mode="desktop",
            unsafe_webapp_features_enabled=False,
            runtime="process",
            host="127.0.0.1",
            port=3000,
            url="http://127.0.0.1:3000",
            workspace="/tmp/openhands",
            process_acknowledged=False,
        )
    )
    return service


@pytest.fixture
async def client_with_service() -> AsyncIterator[tuple[httpx.AsyncClient, MagicMock]]:
    service = _fake_service()
    app = create_app(config=AppConfig(openhands_service=service))  # type: ignore[arg-type]
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, service


async def test_status_launch_false_does_not_launch(client_with_service) -> None:
    client, service = client_with_service

    response = await client.get("/api/v1/openhands/status?launch=false")

    assert response.status_code == 200
    assert response.json()["running"] is False
    service.status.assert_called_once()
    service.launch.assert_not_awaited()


async def test_status_launch_true_launches(client_with_service) -> None:
    client, service = client_with_service

    response = await client.get("/api/v1/openhands/status?launch=true")

    assert response.status_code == 200
    assert response.json()["running"] is True
    service.launch.assert_awaited_once()


async def test_launch_returns_status(client_with_service) -> None:
    client, service = client_with_service

    response = await client.post("/api/v1/openhands/launch")

    assert response.status_code == 200
    assert response.json()["pid"] == 777
    service.launch.assert_awaited_once()


async def test_launch_unavailable_returns_403() -> None:
    service = _fake_service(available=False)
    service.launch.side_effect = OpenHandsLaunchError("disabled")
    app = create_app(config=AppConfig(openhands_service=service))  # type: ignore[arg-type]
    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/v1/openhands/launch")

    assert response.status_code == 403
    assert response.json()["error"] == "openhands_unavailable"


async def test_shutdown_returns_status(client_with_service) -> None:
    client, service = client_with_service

    response = await client.post("/api/v1/openhands/shutdown")

    assert response.status_code == 200
    assert response.json()["running"] is False
    service.shutdown.assert_awaited_once()


async def test_context_returns_effective_configuration(client_with_service) -> None:
    client, service = client_with_service

    response = await client.get("/api/v1/openhands/context")

    assert response.status_code == 200
    assert response.json()["available"] is True
    assert response.json()["runtime"] == "process"
    service.context.assert_called_once()


def test_router_mounted_at_api_v1_openhands_prefix() -> None:
    app = create_app(config=AppConfig(openhands_service=_fake_service()))  # type: ignore[arg-type]
    paths = {route.path for route in app.routes}  # type: ignore[attr-defined]

    assert "/api/v1/openhands/status" in paths
    assert "/api/v1/openhands/launch" in paths
    assert "/api/v1/openhands/shutdown" in paths
    assert "/api/v1/openhands/context" in paths


def test_create_app_constructs_default_openhands_service_from_settings(tmp_path: Path) -> None:
    settings = Settings(
        deployment_mode="desktop",
        openhands_workspace=str(tmp_path),
    )
    app = create_app(config=AppConfig(settings=settings))

    service = app.state.openhands_service

    assert isinstance(service, OpenHandsService)
    assert service.context().workspace == str(tmp_path)


def test_create_app_defaults_openhands_workspace_to_workflow_root(tmp_path: Path) -> None:
    workflow_root = tmp_path / "workflows"
    app = create_app(
        config=AppConfig(
            settings=Settings(deployment_mode="desktop"),
            workflow_root=workflow_root,
            disable_hot_reload=True,
        )
    )

    service = app.state.openhands_service

    assert isinstance(service, OpenHandsService)
    assert service.context().workspace == str(workflow_root.resolve())


def test_webapp_without_unsafe_features_is_not_available(tmp_path: Path) -> None:
    app = create_app(
        config=AppConfig(
            settings=Settings(
                deployment_mode="webapp",
                openhands_workspace=str(tmp_path),
            ),
            deployment_mode="webapp",
        )
    )

    service = app.state.openhands_service

    assert service.context().available is False
    assert service.context().reason == "unsafe_webapp_features_disabled"
