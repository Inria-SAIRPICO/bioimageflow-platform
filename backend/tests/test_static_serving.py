"""Tests for production static file serving and SPA fallback."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    """Create a temporary directory mimicking frontend/dist/."""
    index = tmp_path / "index.html"
    index.write_text("<!DOCTYPE html><html><body>SPA</body></html>")

    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('app');")
    (assets / "style.css").write_text("body { margin: 0; }")

    return tmp_path


@pytest.fixture
async def static_client(static_dir: Path):
    """HTTP client backed by a FastAPI app with static_dir configured."""
    config = AppConfig(static_dir=static_dir)
    app = create_app(config=config)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---- SPA fallback tests ----


@pytest.mark.anyio
async def test_spa_fallback_root(static_client: httpx.AsyncClient, static_dir: Path):
    """GET / returns index.html content."""
    resp = await static_client.get("/")
    assert resp.status_code == 200
    assert "SPA" in resp.text


@pytest.mark.anyio
async def test_spa_fallback_nested_path(static_client: httpx.AsyncClient):
    """GET /some/nested/path returns index.html (SPA fallback)."""
    resp = await static_client.get("/some/nested/path")
    assert resp.status_code == 200
    assert "SPA" in resp.text


# ---- Static asset tests ----


@pytest.mark.anyio
async def test_static_asset_js(static_client: httpx.AsyncClient):
    """GET /assets/app.js returns the JS file."""
    resp = await static_client.get("/assets/app.js")
    assert resp.status_code == 200
    assert "console.log" in resp.text


@pytest.mark.anyio
async def test_static_asset_css(static_client: httpx.AsyncClient):
    """GET /assets/style.css returns the CSS file."""
    resp = await static_client.get("/assets/style.css")
    assert resp.status_code == 200
    assert "margin" in resp.text


@pytest.mark.anyio
async def test_static_asset_missing(static_client: httpx.AsyncClient):
    """GET /assets/nonexistent.js returns 404 from StaticFiles."""
    resp = await static_client.get("/assets/nonexistent.js")
    assert resp.status_code == 404


# ---- API routes still work ----


@pytest.mark.anyio
async def test_api_health_not_caught_by_fallback(static_client: httpx.AsyncClient):
    """GET /api/v1/health still returns the health endpoint, not index.html."""
    resp = await static_client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


# ---- No static_dir configured ----


@pytest.mark.anyio
async def test_no_static_dir_no_fallback():
    """When static_dir is not set, there is no SPA fallback route."""
    config = AppConfig()  # no static_dir
    app = create_app(config=config)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/random/path")
        # Should get 404 since no catch-all is registered
        assert resp.status_code == 404


# ---- AppConfig field ----


def test_appconfig_static_dir_default():
    """AppConfig.static_dir defaults to None."""
    config = AppConfig()
    assert config.static_dir is None


def test_appconfig_static_dir_set(tmp_path: Path):
    """AppConfig.static_dir can be set to a Path."""
    config = AppConfig(static_dir=tmp_path)
    assert config.static_dir == tmp_path
