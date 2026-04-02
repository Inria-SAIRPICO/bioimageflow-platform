"""Shared test fixtures."""

from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()

    # Add a test-only route that requires an int query param (for validation error testing)
    @app.get("/api/v1/test-validation")
    async def _test_validation(value: int) -> dict[str, int]:
        return {"value": value}

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
