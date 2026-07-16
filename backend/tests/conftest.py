"""Shared test fixtures."""

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app


def pytest_addoption(parser: pytest.Parser) -> None:
    """Keep external package certification out of the deterministic suite."""

    parser.addoption(
        "--run-common-tools",
        action="store_true",
        default=False,
        help="run tests that certify an installed bioimageflow-common-tools package",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip live common-tools checks unless the caller explicitly opts in."""

    if config.getoption("--run-common-tools"):
        return

    skip = pytest.mark.skip(
        reason="external common-tools certification requires --run-common-tools"
    )
    for item in items:
        if item.get_closest_marker("common_tools") is not None:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Run the supported ASGI test backend once under asyncio by default."""

    return "asyncio"


@pytest.fixture(autouse=True)
def isolated_bioimageflow_runtime(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep deterministic tests out of the developer's persistent runtime state."""

    if request.node.get_closest_marker("common_tools") is not None:
        return

    home = tmp_path / "bioimageflow-home"
    tool_store = home / "tool_packages"
    wetlands = home / "wetlands"
    tool_store.mkdir(parents=True)
    wetlands.mkdir(parents=True)
    monkeypatch.setenv("BIOIMAGEFLOW_HOME", str(home))
    monkeypatch.setenv("BIOIMAGEFLOW_TOOL_STORE", str(tool_store))
    monkeypatch.setenv("BIOIMAGEFLOW_WETLANDS", str(wetlands))


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
