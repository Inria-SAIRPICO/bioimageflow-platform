from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pandas as pd
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.services.fiji_launcher import (
    FijiInstallationError,
    FijiLaunchError,
    FijiLauncher,
    FijiNotConfiguredError,
)


pytestmark = pytest.mark.anyio

_RESULT_IDENTITY = {
    "run_id": "run_0123456789abcdef0123456789abcdef",
    "node_key": "n1",
    "result_key": "rk_" + "a" * 64,
    "record_id": "rec_0123456789abcdef0123456789abcdef",
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _launcher() -> MagicMock:
    launcher = MagicMock(spec=FijiLauncher)
    launcher.open = MagicMock(return_value=None)
    return launcher


async def _post(app, payload: dict[str, object]) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post("/api/v1/fiji/open", json=payload)


async def test_open_resolves_workflow_result_cell(tmp_path: Path) -> None:
    image = tmp_path / "outputs" / "mask.tif"
    image.parent.mkdir()
    image.write_bytes(b"tif")
    result_store = MagicMock()
    result_store.load_result_dataframe.return_value = pd.DataFrame(
        {"mask": [str(image)]}
    )
    workflow_store = MagicMock()
    workflow_store.get_storage_path.return_value = tmp_path
    launcher = _launcher()
    app = create_app(
        AppConfig(
            settings=Settings(deployment_mode="desktop", fiji_path=str(tmp_path)),
            result_store=result_store,
            workflow_store=workflow_store,
            fiji_launcher=launcher,
        )
    )

    response = await _post(
        app,
        {
            "node_id": "n1",
            "row": 0,
            "col": "mask",
            "workflow_name": "analysis",
            "result_identity": _RESULT_IDENTITY,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    launcher.open.assert_called_once_with(image)


async def test_open_rejects_webapp_mode(tmp_path: Path) -> None:
    launcher = _launcher()
    app = create_app(
        AppConfig(
            settings=Settings(deployment_mode="webapp"),
            deployment_mode="webapp",
            storage_path=tmp_path,
            workflow_root=tmp_path / "workflows",
            fiji_launcher=launcher,
        )
    )

    response = await _post(app, {"node_id": "n1", "row": 0, "col": "mask"})

    assert response.status_code == 403
    assert response.json()["error"] == "fiji_unavailable"
    launcher.open.assert_not_called()


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (FijiNotConfiguredError("configure Fiji"), 409, "fiji_not_configured"),
        (FijiInstallationError("Fiji moved"), 409, "fiji_configuration_invalid"),
        (FijiLaunchError("launch denied"), 503, "fiji_launch_failed"),
    ],
)
async def test_open_returns_structured_fiji_errors(
    tmp_path: Path, error: Exception, status: int, code: str
) -> None:
    image = tmp_path / "mask.tif"
    image.write_bytes(b"tif")
    result_store = MagicMock()
    result_store.load_result_dataframe.return_value = pd.DataFrame({"mask": [str(image)]})
    launcher = _launcher()
    launcher.open.side_effect = error
    app = create_app(
        AppConfig(
            settings=Settings(deployment_mode="desktop", fiji_path=str(tmp_path)),
            result_store=result_store,
            fiji_launcher=launcher,
        )
    )

    response = await _post(
        app,
        {
            "node_id": "n1",
            "row": 0,
            "col": "mask",
            "result_identity": _RESULT_IDENTITY,
        },
    )

    assert response.status_code == status
    assert response.json()["error"] == code


async def test_open_requires_complete_result_identity() -> None:
    app = create_app(AppConfig(fiji_launcher=_launcher()))

    response = await _post(app, {"node_id": "n1", "row": 0})

    assert response.status_code == 422


async def test_fiji_route_is_in_openapi() -> None:
    app = create_app(AppConfig(fiji_launcher=_launcher()))
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/openapi.json")

    assert "/api/v1/fiji/open" in response.json()["paths"]
