"""Tests for the datasets router (Task 3)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig

pytestmark = pytest.mark.anyio


async def _client(cfg: AppConfig) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(config=cfg)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    cfg = AppConfig(datasets_root=tmp_path / "datasets", max_upload_size=1_000_000)
    async for c in _client(cfg):
        yield c


@pytest.fixture
async def small_cap_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    """Client with a tiny upload cap to trigger 413s."""
    cfg = AppConfig(datasets_root=tmp_path / "datasets", max_upload_size=20)
    async for c in _client(cfg):
        yield c


# ---------------------------------------------------------------------------
# GET /api/v1/datasets
# ---------------------------------------------------------------------------


async def test_list_empty(client: httpx.AsyncClient):
    r = await client.get("/api/v1/datasets")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_after_upload(client: httpx.AsyncClient):
    await client.post(
        "/api/v1/datasets/upload",
        files={"files": ("cells.tif", b"hello world", "image/tiff")},
    )
    r = await client.get("/api/v1/datasets")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    entry = data[0]
    assert entry["original_filename"] == "cells.tif"
    assert entry["size"] == 11
    assert entry["content_type"] == "image/tiff"
    assert entry["id"].startswith("d_")
    assert entry["upload_date"].endswith("Z")
    assert entry["path"].endswith("cells.tif")


async def test_list_when_root_missing(tmp_path: Path):
    """GET /datasets works even when datasets_root doesn't exist yet."""
    # DatasetStore mkdirs on construction; even if the user manually removes
    # the directory after startup, list() must not crash.
    cfg = AppConfig(datasets_root=tmp_path / "nope", max_upload_size=1_000)
    async for c in _client(cfg):
        r = await c.get("/api/v1/datasets")
        assert r.status_code == 200
        assert r.json() == []


# ---------------------------------------------------------------------------
# POST /api/v1/datasets/upload
# ---------------------------------------------------------------------------


async def test_upload_single_file(client: httpx.AsyncClient):
    r = await client.post(
        "/api/v1/datasets/upload",
        files={"files": ("sample.tif", b"image bytes", "image/tiff")},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["uploaded"]) == 1
    assert body["errors"] == []
    uploaded = body["uploaded"][0]
    assert uploaded["original_filename"] == "sample.tif"
    assert uploaded["size"] == 11
    assert uploaded["path"].endswith("sample.tif")


async def test_upload_multi_file(client: httpx.AsyncClient):
    r = await client.post(
        "/api/v1/datasets/upload",
        files=[
            ("files", ("a.tif", b"AAA", "image/tiff")),
            ("files", ("b.png", b"BBBB", "image/png")),
        ],
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["uploaded"]) == 2
    names = {u["original_filename"] for u in body["uploaded"]}
    assert names == {"a.tif", "b.png"}


async def test_upload_oversize_mid_stream(small_cap_client: httpx.AsyncClient):
    r = await small_cap_client.post(
        "/api/v1/datasets/upload",
        files={"files": ("big.bin", b"x" * 50, "application/octet-stream")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["uploaded"] == []
    assert len(body["errors"]) == 1
    err = body["errors"][0]
    assert err["filename"] == "big.bin"
    assert err["error"] == "file_too_large"


async def test_upload_path_traversal(client: httpx.AsyncClient):
    """Traversal is sanitized (stripped), not rejected — file lands in root with basename."""
    r = await client.post(
        "/api/v1/datasets/upload",
        files={"files": ("../../etc/passwd", b"nope", "application/octet-stream")},
    )
    # Sanitization strips directory components; the file is stored as "passwd".
    assert r.status_code == 200
    body = r.json()
    assert len(body["uploaded"]) == 1
    assert body["uploaded"][0]["original_filename"] == "passwd"


async def test_upload_partial_success(small_cap_client: httpx.AsyncClient):
    """One file under cap, one over — partial success with one error."""
    r = await small_cap_client.post(
        "/api/v1/datasets/upload",
        files=[
            ("files", ("ok.bin", b"tiny", "application/octet-stream")),
            ("files", ("big.bin", b"x" * 50, "application/octet-stream")),
        ],
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["uploaded"]) == 1
    assert body["uploaded"][0]["original_filename"] == "ok.bin"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["filename"] == "big.bin"


async def test_upload_dos_guard_rejects_huge_content_length(
    small_cap_client: httpx.AsyncClient,
):
    """Upload where declared Content-Length > cap * MAX_FILES is rejected up-front."""
    # cap=20 bytes per file, so guard trips at 20 * 32 = 640. Send body > that.
    r = await small_cap_client.post(
        "/api/v1/datasets/upload",
        content=b"x" * 2000,
    )
    assert r.status_code == 413
    body = r.json()
    assert body["error"] == "file_too_large"


async def test_upload_multi_file_total_over_per_file_cap(
    tmp_path: Path,
):
    """3 files each ~10KB under a per-file cap of 20KB all succeed (total > cap)."""
    cfg = AppConfig(datasets_root=tmp_path / "d", max_upload_size=20_000)
    async for c in _client(cfg):
        blob = b"x" * 10_000
        r = await c.post(
            "/api/v1/datasets/upload",
            files=[
                ("files", ("a.bin", blob, "application/octet-stream")),
                ("files", ("b.bin", blob, "application/octet-stream")),
                ("files", ("c.bin", blob, "application/octet-stream")),
            ],
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["uploaded"]) == 3
        assert body["errors"] == []


# ---------------------------------------------------------------------------
# DELETE /api/v1/datasets/{id}
# ---------------------------------------------------------------------------


async def test_delete_success(client: httpx.AsyncClient):
    up = await client.post(
        "/api/v1/datasets/upload",
        files={"files": ("gone.tif", b"bye", "image/tiff")},
    )
    dataset_id = up.json()["uploaded"][0]["id"]
    r = await client.delete(f"/api/v1/datasets/{dataset_id}")
    assert r.status_code == 204

    listing = await client.get("/api/v1/datasets")
    assert listing.json() == []


async def test_delete_unknown_returns_404(client: httpx.AsyncClient):
    r = await client.delete("/api/v1/datasets/d_bogus")
    assert r.status_code == 404
    body = r.json()
    assert body["error"] == "not_found"


async def test_delete_traversal_id_returns_400(client: httpx.AsyncClient):
    import base64

    evil = (
        base64.urlsafe_b64encode(b"../../../etc/passwd").rstrip(b"=").decode("ascii")
    )
    r = await client.delete(f"/api/v1/datasets/d_{evil}")
    # Traversal raises PathTraversalError -> 400 path_traversal
    assert r.status_code == 400
    assert r.json()["error"] == "path_traversal"


# ---------------------------------------------------------------------------
# OpenAPI tag
# ---------------------------------------------------------------------------


async def test_openapi_has_datasets_tag(client: httpx.AsyncClient):
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    tags = set()
    for path_item in schema["paths"].values():
        for op in path_item.values():
            for t in op.get("tags", []):
                tags.add(t)
    assert "datasets" in tags
