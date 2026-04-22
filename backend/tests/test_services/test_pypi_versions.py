"""Tests for PyPIVersionService."""

from __future__ import annotations

import httpx
import pytest

from bioimageflow_server.services.package_installer import (
    PackageNetworkError,
    PackageNotFoundError,
)
from bioimageflow_server.services.pypi_versions import PyPIVersionService

pytestmark = pytest.mark.anyio


def _make_service(handler) -> PyPIVersionService:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return PyPIVersionService(client=client, base_url="https://pypi.org/pypi")


async def test_get_versions_returns_sorted_ascending():
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "releases": {
                    "0.1.1": [{}],
                    "0.1.0": [{}],
                    "0.2.0a1": [{}],
                }
            },
        )

    svc = _make_service(handler)
    try:
        versions = await svc.get_versions("bioimageflow_core")
    finally:
        await svc.aclose()
    assert versions == ["0.1.0", "0.1.1", "0.2.0a1"]


async def test_get_versions_normalizes_name_to_hyphen():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"releases": {"0.1.0": [{}]}})

    svc = _make_service(handler)
    try:
        await svc.get_versions("bioimageflow_core")
    finally:
        await svc.aclose()
    assert seen == ["https://pypi.org/pypi/bioimageflow-core/json"]


async def test_get_versions_404_raises_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    svc = _make_service(handler)
    try:
        with pytest.raises(PackageNotFoundError):
            await svc.get_versions("missing_pkg")
    finally:
        await svc.aclose()


async def test_get_versions_connect_error_raises_network():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    svc = _make_service(handler)
    try:
        with pytest.raises(PackageNetworkError):
            await svc.get_versions("anything")
    finally:
        await svc.aclose()


async def test_get_versions_timeout_raises_network():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    svc = _make_service(handler)
    try:
        with pytest.raises(PackageNetworkError):
            await svc.get_versions("anything")
    finally:
        await svc.aclose()


async def test_get_latest_stable_skips_prereleases():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "releases": {
                    "0.1.0": [{}],
                    "0.1.1": [{}],
                    "0.2.0a1": [{}],
                }
            },
        )

    svc = _make_service(handler)
    try:
        latest = await svc.get_latest_stable("bioimageflow_core")
    finally:
        await svc.aclose()
    assert latest == "0.1.1"


async def test_get_latest_stable_falls_back_to_prerelease_when_no_stable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"releases": {"0.2.0a1": [{}], "0.2.0a2": [{}]}},
        )

    svc = _make_service(handler)
    try:
        latest = await svc.get_latest_stable("pre_only")
    finally:
        await svc.aclose()
    # When no stable release exists, take the newest version overall.
    assert latest == "0.2.0a2"


async def test_get_latest_stable_empty_releases_raises_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"releases": {}})

    svc = _make_service(handler)
    try:
        with pytest.raises(PackageNotFoundError):
            await svc.get_latest_stable("empty_pkg")
    finally:
        await svc.aclose()
