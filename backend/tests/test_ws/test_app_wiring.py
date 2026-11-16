"""Tests for ConnectionManager wiring inside create_app (WS plan Task 5)."""

from __future__ import annotations

import logging

import pytest

from fastapi.testclient import TestClient


def test_ws_route_mounted_by_default() -> None:
    from bioimageflow_server.app import create_app

    app = create_app()
    ws_routes = [
        r for r in app.routes if getattr(r, "path", None) == "/ws"
    ]
    assert len(ws_routes) == 1


def test_ws_route_uses_provided_manager() -> None:
    from bioimageflow_server.app import create_app
    from bioimageflow_server.models.tools import AppConfig
    from bioimageflow_server.ws.handler import ConnectionManager

    manager = ConnectionManager()
    app = create_app(AppConfig(connection_manager=manager))
    ws_routes = [
        r for r in app.routes if getattr(r, "path", None) == "/ws"
    ]
    assert len(ws_routes) == 1


def test_app_state_exposes_default_connection_manager() -> None:
    from bioimageflow_server.app import create_app
    from bioimageflow_server.ws.handler import ConnectionManager

    app = create_app()
    assert isinstance(app.state.connection_manager, ConnectionManager)


def test_app_state_exposes_connection_manager() -> None:
    from bioimageflow_server.app import create_app
    from bioimageflow_server.models.tools import AppConfig
    from bioimageflow_server.ws.handler import ConnectionManager

    manager = ConnectionManager()
    app = create_app(AppConfig(connection_manager=manager))
    assert app.state.connection_manager is manager


def test_models_package_reexports_ws_messages() -> None:
    from bioimageflow_server import models

    # Presence of key ws message symbols on the models package.
    for name in (
        "AckMessage",
        "ProgressMessage",
        "NodeStateMessage",
        "LogMessage",
        "StatusSnapshotMessage",
        "SubscribeLogsMessage",
        "ServerMessage",
        "ClientMessage",
    ):
        assert hasattr(models, name), f"models.{name} missing"
        assert name in models.__all__, f"{name} not in models.__all__"


def test_ws_package_reexports_core_symbols() -> None:
    from bioimageflow_server import ws

    for name in ("ConnectionManager", "register_ws", "WebSocketLogHandler", "attach_ws_log_handler"):
        assert hasattr(ws, name), f"ws.{name} missing"


def test_lifespan_sets_and_clears_loop_and_handler() -> None:
    """On startup: loop is bound + log handler is attached; on shutdown: both cleared."""
    from bioimageflow_server.app import create_app
    from bioimageflow_server.models.tools import AppConfig
    from bioimageflow_server.ws.handler import ConnectionManager

    manager = ConnectionManager()
    app = create_app(
        AppConfig(connection_manager=manager, disable_hot_reload=True)
    )
    bioimageflow_logger = logging.getLogger("bioimageflow")
    initial_handlers = set(bioimageflow_logger.handlers)

    with TestClient(app):
        # Inside lifespan: loop is bound and a WS log handler is attached.
        assert manager._loop is not None
        added = set(bioimageflow_logger.handlers) - initial_handlers
        assert len(added) == 1

    # After shutdown: loop cleared and handler removed.
    assert manager._loop is None
    assert set(bioimageflow_logger.handlers) == initial_handlers


def test_integration_subscribe_ack_roundtrip() -> None:
    """End-to-end: create app with manager, connect, send subscribe_logs, receive ack."""
    from bioimageflow_server.app import create_app
    from bioimageflow_server.models.tools import AppConfig
    from bioimageflow_server.ws.handler import ConnectionManager

    manager = ConnectionManager()
    app = create_app(
        AppConfig(connection_manager=manager, disable_hot_reload=True)
    )

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            snapshot = ws.receive_json()
            assert snapshot["type"] == "status_snapshot"
            ws.send_json({"type": "subscribe_logs", "message_id": "m1"})
            msg = ws.receive_json()
            assert msg == {"type": "ack", "ref": "m1"}


def test_execution_manager_uses_connection_manager_as_event_bus() -> None:
    """When a ConnectionManager is supplied, the auto-built ExecutionManager
    should use it as its ExecutionEventBus so progress / node_state /
    execution_complete events flow over the WebSocket. The default app also
    creates a ConnectionManager so production launchers do not silently drop
    terminal execution events.
    """
    from bioimageflow_server.app import create_app
    from bioimageflow_server.models.tools import AppConfig
    from bioimageflow_server.ws.handler import ConnectionManager

    manager = ConnectionManager()
    app_with_ws = create_app(AppConfig(connection_manager=manager))
    # Resolve the ExecutionManager that the graph router will receive.
    from bioimageflow_server.routers.graph import (
        get_execution_manager as graph_get_execution_manager,
    )

    em_with_ws = app_with_ws.dependency_overrides[graph_get_execution_manager]()
    assert em_with_ws.event_bus is manager

    app_default = create_app()
    em_default = app_default.dependency_overrides[graph_get_execution_manager]()
    assert em_default.event_bus is app_default.state.connection_manager


@pytest.mark.anyio
async def test_workflow_event_owner_uses_request_store_after_live_workspace_switch(tmp_path, monkeypatch) -> None:
    import httpx
    from bioimageflow_server.app import create_app
    from bioimageflow_server.models.settings import Settings
    from bioimageflow_server.models.tools import AppConfig
    from bioimageflow_server.services.tool_registry import ToolRegistryService
    from bioimageflow_server.ws.handler import ConnectionManager

    settings = Settings(deployment_mode="desktop", workspace_path=str(tmp_path / "a"))
    manager = ConnectionManager()
    pending, published = [], []
    monkeypatch.setattr(manager, "_schedule", lambda coroutine, _kind: pending.append(coroutine))
    monkeypatch.setattr(manager, "_enqueue_all", published.append)
    publish = manager.publish_workflow_tree_changed

    def switch_before_publish(**payload):
        settings.workspace_path = str(tmp_path / "b")
        publish(**payload)

    monkeypatch.setattr(manager, "publish_workflow_tree_changed", switch_before_publish)
    app = create_app(AppConfig(settings=settings, connection_manager=manager,
                               tool_registry=ToolRegistryService(), disable_hot_reload=True))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/workflows", json={"name": "created-in-a"},
                                     headers={"X-BioImageFlow-Workspace": str(tmp_path / "a")})
    assert response.status_code == 201, response.text
    [delivery] = pending
    await delivery
    assert published[0]["workspace_path"] == str((tmp_path / "a").resolve())
    assert published[0]["workflow_id"] == response.json()["id"]
    assert (tmp_path / "a" / "workflows" / "created-in-a" / "workflow.json").is_file()
    assert not (tmp_path / "b" / "workflows").exists()
