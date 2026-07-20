"""Shared test fixtures."""

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from bioimageflow_server.app import create_app


class _OfflinePyPIVersionService:
    """Keep repository-owned app tests deterministic and network-free."""

    async def get_versions(self, _package_name: str) -> list[str]:
        return []

    async def get_latest_stable(self, package_name: str) -> str:
        raise AssertionError(
            f"Test must inject a PyPI service before resolving {package_name!r}"
        )

    async def aclose(self) -> None:
        pass


def pytest_addoption(parser: pytest.Parser) -> None:
    """Keep external package certification explicit and opt-in."""

    parser.addoption(
        "--run-external",
        action="store_true",
        default=False,
        help="run external package and service certification tests",
    )

    parser.addoption(
        "--run-common-tools",
        action="store_true",
        default=False,
        help="alias for --run-external retained for common-tools certification",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Classify broad test boundaries and gate external certification."""

    integration_paths = {
        "tests/test_app_config_wiring.py",
        "tests/test_static_serving.py",
        "tests/test_ws/test_app_wiring.py",
    }
    serial_paths = {
        "tests/test_desktop.py",
        "tests/test_logging_config.py",
        "tests/test_ws/test_logging_bridge.py",
    }
    serial_tests = {
        "test_publish_logs_future_exceptions",
        "test_publish_without_loop_drops_silently",
    }

    for item in items:
        relative_path = item.path.relative_to(config.rootpath).as_posix()
        if (
            relative_path.startswith("tests/test_integration/")
            or relative_path.startswith("tests/test_routers/")
            or relative_path in integration_paths
        ):
            item.add_marker("integration")
        if relative_path in serial_paths or item.name in serial_tests:
            item.add_marker("serial")

    if config.getoption("--run-external") or config.getoption("--run-common-tools"):
        return

    skip = pytest.mark.skip(reason="external certification requires --run-external")
    for item in items:
        if item.get_closest_marker("external") is not None:
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

    if request.node.get_closest_marker("external") is not None:
        return

    home = tmp_path / "bioimageflow-home"
    tool_store = home / "tool_packages"
    wetlands = home / "wetlands"
    tool_store.mkdir(parents=True)
    wetlands.mkdir(parents=True)
    monkeypatch.setenv("BIOIMAGEFLOW_HOME", str(home))
    monkeypatch.setenv("BIOIMAGEFLOW_TOOL_STORE", str(tool_store))
    monkeypatch.setenv("BIOIMAGEFLOW_WETLANDS", str(wetlands))
    monkeypatch.setattr(
        "bioimageflow_server.app.ensure_agent_workspace_context",
        lambda _workspace: None,
    )
    monkeypatch.setattr(
        "bioimageflow_server.app.PyPIVersionService",
        _OfflinePyPIVersionService,
    )


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
