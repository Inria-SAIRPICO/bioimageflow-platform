"""Tests for the napari router and create_app wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import logging
import pandas as pd
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.napari import NapariStatus
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.result_store import DATAFRAME_RECORD_DIR_ATTR
from bioimageflow_server.services.napari_launcher import (
    NapariLauncher,
    NapariLaunchError,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _fake_launcher(*, status: NapariStatus | None = None) -> MagicMock:
    """A MagicMock standing in for NapariLauncher.

    ``open()`` and ``shutdown()`` are AsyncMocks; ``status()`` is sync.
    """
    launcher = MagicMock(spec=NapariLauncher)
    launcher.open = AsyncMock(return_value=None)
    launcher.shutdown = AsyncMock(return_value=None)
    launcher.status = MagicMock(
        return_value=status or NapariStatus(running=False)
    )
    return launcher


@pytest.fixture
async def client_with_launcher() -> AsyncIterator[tuple[httpx.AsyncClient, MagicMock]]:
    launcher = _fake_launcher()
    config = AppConfig(napari_launcher=launcher)  # type: ignore[arg-type]
    app = create_app(config=config)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, launcher


# ---------------------------------------------------------------------------
# POST /napari/open
# ---------------------------------------------------------------------------


async def test_open_returns_200_for_valid_paths(
    client_with_launcher,
) -> None:
    client, launcher = client_with_launcher
    res = await client.post(
        "/api/v1/napari/open",
        json={"paths": ["/tmp/a.tif"], "clear_layers": False},
    )
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    launcher.open.assert_awaited_once_with(["/tmp/a.tif"], False)


async def test_open_router_does_not_pre_validate_paths(
    client_with_launcher,
) -> None:
    """The launcher is the single validation gate; the router just
    forwards. Even a non-existent path goes to the launcher.
    """
    client, launcher = client_with_launcher
    res = await client.post(
        "/api/v1/napari/open",
        json={"paths": ["/nonexistent/x.tif"]},
    )
    assert res.status_code == 200
    launcher.open.assert_awaited_once_with(["/nonexistent/x.tif"], False)


async def test_open_with_clear_layers_passes_flag(
    client_with_launcher,
) -> None:
    client, launcher = client_with_launcher
    res = await client.post(
        "/api/v1/napari/open",
        json={"paths": ["/tmp/a.tif"], "clear_layers": True},
    )
    assert res.status_code == 200
    launcher.open.assert_awaited_once_with(["/tmp/a.tif"], True)


async def test_open_resolves_record_relative_asset_path(tmp_path: Path) -> None:
    record_dir = tmp_path / "records" / "rec_test"
    image_path = record_dir / "assets" / "mask.tif"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"tif")
    df = pd.DataFrame({"mask": ["assets/mask.tif"]})
    df.attrs[DATAFRAME_RECORD_DIR_ATTR] = str(record_dir)
    result_store = MagicMock()
    result_store.get_latest_dataframe.return_value = df
    launcher = _fake_launcher()
    config = AppConfig(
        napari_launcher=launcher,  # type: ignore[arg-type]
        result_store=result_store,
    )
    app = create_app(config=config)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/napari/open",
            json={
                "paths": ["assets/mask.tif"],
                "node_id": "n1",
                "row": 0,
                "col": "mask",
            },
        )
    assert res.status_code == 200
    result_store.get_latest_dataframe.assert_called_once_with("n1", storage_path=None)
    launcher.open.assert_awaited_once_with([str(image_path)], False)


async def test_open_resolves_relative_path_against_workflow_storage(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "outputs" / "mask.tif"
    image_path.parent.mkdir()
    image_path.write_bytes(b"tif")
    result_store = MagicMock()
    result_store.get_latest_dataframe.return_value = pd.DataFrame(
        {"mask": ["outputs/mask.tif"]}
    )
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path
    launcher = _fake_launcher()
    config = AppConfig(
        napari_launcher=launcher,  # type: ignore[arg-type]
        result_store=result_store,
        workflow_store=workflow_store,
    )
    app = create_app(config=config)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/napari/open",
            json={
                "paths": ["outputs/mask.tif"],
                "node_id": "n1",
                "row": 0,
                "col": "mask",
                "workflow_name": "wf_a",
            },
        )
    assert res.status_code == 200
    workflow_store.get_storage_path.assert_called_once_with("wf_a")
    result_store.get_latest_dataframe.assert_called_once_with("n1", storage_path=tmp_path)
    launcher.open.assert_awaited_once_with([str(image_path)], False)


async def test_open_returns_400_when_launcher_raises_filenotfound(
    client_with_launcher, caplog: pytest.LogCaptureFixture,
) -> None:
    client, launcher = client_with_launcher
    launcher.open.side_effect = FileNotFoundError(["/tmp/missing.tif"])
    with caplog.at_level(logging.WARNING, logger="bioimageflow_server.routers.napari"):
        res = await client.post(
            "/api/v1/napari/open",
            json={"paths": ["/tmp/missing.tif"]},
        )
    assert res.status_code == 400
    body = res.json()
    assert body["error"] == "path_not_found"
    assert "missing.tif" in body["detail"]
    assert "Napari open request rejected because paths were not found" in caplog.text


async def test_open_returns_503_on_napari_launch_error(
    client_with_launcher, caplog: pytest.LogCaptureFixture,
) -> None:
    client, launcher = client_with_launcher
    launcher.open.side_effect = NapariLaunchError("solver crashed")
    with caplog.at_level(logging.ERROR, logger="bioimageflow_server.routers.napari"):
        res = await client.post(
            "/api/v1/napari/open",
            json={"paths": ["/tmp/a.tif"]},
        )
    assert res.status_code == 503
    body = res.json()
    assert body["error"] == "napari_launch_failed"
    assert "solver crashed" in body["detail"]
    assert "Napari open request failed while launching or contacting Napari" in caplog.text


async def test_open_with_empty_paths_is_valid(client_with_launcher) -> None:
    client, launcher = client_with_launcher
    res = await client.post(
        "/api/v1/napari/open", json={"paths": []}
    )
    assert res.status_code == 200
    launcher.open.assert_awaited_once_with([], False)


async def test_open_without_body_returns_422(client_with_launcher) -> None:
    client, _ = client_with_launcher
    res = await client.post("/api/v1/napari/open")
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# GET /napari/status
# ---------------------------------------------------------------------------


async def test_status_returns_napari_status_shape_when_not_running(
    client_with_launcher,
) -> None:
    client, _ = client_with_launcher
    res = await client.get("/api/v1/napari/status")
    assert res.status_code == 200
    assert res.json() == {"running": False, "env_path": None, "pid": None}


async def test_status_returns_running_with_pid_when_alive() -> None:
    launcher = _fake_launcher(
        status=NapariStatus(running=True, env_path="/envs/napari", pid=4242)
    )
    config = AppConfig(napari_launcher=launcher)  # type: ignore[arg-type]
    app = create_app(config=config)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        res = await ac.get("/api/v1/napari/status")
    assert res.status_code == 200
    assert res.json() == {
        "running": True,
        "env_path": "/envs/napari",
        "pid": 4242,
    }


async def test_status_does_not_call_open_or_send_command(
    client_with_launcher,
) -> None:
    client, launcher = client_with_launcher
    await client.get("/api/v1/napari/status")
    launcher.open.assert_not_awaited()
    # _send_command would be called via launcher internals; the mock
    # spec-bound launcher does not expose it, but we verify open is
    # never called on a status request.
    assert launcher.status.call_count == 1


# ---------------------------------------------------------------------------
# POST /napari/shutdown
# ---------------------------------------------------------------------------


async def test_shutdown_returns_200(client_with_launcher) -> None:
    client, launcher = client_with_launcher
    res = await client.post("/api/v1/napari/shutdown")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    launcher.shutdown.assert_awaited_once()


async def test_shutdown_is_safe_when_not_running(client_with_launcher) -> None:
    client, launcher = client_with_launcher
    # Default fake status is running=False; shutdown should still 200.
    res = await client.post("/api/v1/napari/shutdown")
    assert res.status_code == 200
    launcher.shutdown.assert_awaited_once()


# ---------------------------------------------------------------------------
# create_app wiring
# ---------------------------------------------------------------------------


def test_router_mounted_at_api_v1_napari_prefix() -> None:
    config = AppConfig(napari_launcher=_fake_launcher())  # type: ignore[arg-type]
    app = create_app(config=config)
    paths = {route.path for route in app.routes}  # type: ignore[attr-defined]
    assert "/api/v1/napari/open" in paths
    assert "/api/v1/napari/status" in paths
    assert "/api/v1/napari/shutdown" in paths


def test_create_app_constructs_default_napari_launcher_from_settings() -> None:
    """When AppConfig.napari_launcher is None, create_app builds one
    from Settings.napari_env_path and stores it on app.state.
    """
    from bioimageflow_server.models.settings import Settings

    settings = Settings(
        deployment_mode="desktop",
        output_data_folder="/tmp/out",
        napari_env_path="/envs/napari",
    )
    config = AppConfig(settings=settings)
    app = create_app(config=config)
    launcher = app.state.napari_launcher
    assert isinstance(launcher, NapariLauncher)
    assert launcher._napari_env_path == "/envs/napari"


def test_create_app_passes_connection_manager_to_default_launcher() -> None:
    """The default-built launcher must receive the WS ConnectionManager
    so it can broadcast environment_status events.
    """
    config = AppConfig()
    app = create_app(config=config)
    launcher = app.state.napari_launcher
    assert isinstance(launcher, NapariLauncher)
    # The connection_manager must be the same one the WS layer uses.
    assert launcher._connection_manager is app.state.connection_manager


def test_create_app_uses_provided_napari_launcher() -> None:
    custom = _fake_launcher()
    config = AppConfig(napari_launcher=custom)  # type: ignore[arg-type]
    app = create_app(config=config)
    assert app.state.napari_launcher is custom


# ---------------------------------------------------------------------------
# Lifespan ordering
# ---------------------------------------------------------------------------


async def test_lifespan_calls_shutdown_before_ws_handler_removal() -> None:
    """The launcher.shutdown() must run before the WS log handler is
    detached so the final environment_status: stopped event reaches
    connected clients. We drive the lifespan directly because
    ASGITransport does not run startup/shutdown events.
    """
    import logging as _logging

    order: list[str] = []
    launcher = _fake_launcher()

    async def _record_shutdown() -> None:
        order.append("napari_shutdown")

    launcher.shutdown.side_effect = _record_shutdown

    config = AppConfig(napari_launcher=launcher)  # type: ignore[arg-type]
    app = create_app(config=config)

    # Wrap removeHandler so we can record when the WS log handler is
    # detached; the first call after lifespan exit corresponds to the
    # napari path's WS log handler removal.
    bioimageflow_logger = _logging.getLogger("bioimageflow")
    real_remove = bioimageflow_logger.removeHandler

    def _record_remove(h: Any) -> None:
        order.append("ws_handler_removed")
        real_remove(h)

    bioimageflow_logger.removeHandler = _record_remove  # type: ignore[assignment]
    try:
        async with app.router.lifespan_context(app):
            pass
    finally:
        bioimageflow_logger.removeHandler = real_remove  # type: ignore[assignment]

    # napari_shutdown must come BEFORE ws_handler_removed.
    assert "napari_shutdown" in order
    assert "ws_handler_removed" in order
    assert order.index("napari_shutdown") < order.index("ws_handler_removed")


async def test_lifespan_completes_when_shutdown_raises() -> None:
    """A raise in launcher.shutdown() must be logged and swallowed so
    the rest of the lifespan cleanup still runs.
    """
    launcher = _fake_launcher()
    launcher.shutdown.side_effect = RuntimeError("boom")

    config = AppConfig(napari_launcher=launcher)  # type: ignore[arg-type]
    app = create_app(config=config)

    # Should NOT raise; the exception is logged, not propagated.
    async with app.router.lifespan_context(app):
        pass
