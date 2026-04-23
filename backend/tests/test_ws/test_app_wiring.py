"""Tests for ConnectionManager wiring inside create_app (WS plan Task 5)."""

from __future__ import annotations

import asyncio
import logging

import pytest
from fastapi.testclient import TestClient


def test_ws_route_mounted_when_manager_provided() -> None:
    from bioimageflow_server.app import create_app
    from bioimageflow_server.models.tools import AppConfig
    from bioimageflow_server.ws.handler import ConnectionManager

    manager = ConnectionManager()
    app = create_app(AppConfig(connection_manager=manager))
    ws_routes = [
        r for r in app.routes if getattr(r, "path", None) == "/ws"
    ]
    assert len(ws_routes) == 1


def test_ws_route_absent_when_no_manager() -> None:
    from bioimageflow_server.app import create_app

    app = create_app()
    ws_routes = [
        r for r in app.routes if getattr(r, "path", None) == "/ws"
    ]
    assert ws_routes == []


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
    app = create_app(AppConfig(connection_manager=manager))
    node_logger = logging.getLogger("bioimageflow.node")
    initial_handlers = set(node_logger.handlers)

    with TestClient(app):
        # Inside lifespan: loop is bound and a WS log handler is attached.
        assert manager._loop is not None
        added = set(node_logger.handlers) - initial_handlers
        assert len(added) == 1

    # After shutdown: loop cleared and handler removed.
    assert manager._loop is None
    assert set(node_logger.handlers) == initial_handlers


def test_integration_subscribe_ack_roundtrip() -> None:
    """End-to-end: create app with manager, connect, send subscribe_logs, receive ack."""
    from bioimageflow_server.app import create_app
    from bioimageflow_server.models.tools import AppConfig
    from bioimageflow_server.ws.handler import ConnectionManager

    manager = ConnectionManager()
    app = create_app(AppConfig(connection_manager=manager))

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "subscribe_logs", "message_id": "m1"})
            msg = ws.receive_json()
            assert msg == {"type": "ack", "ref": "m1"}
