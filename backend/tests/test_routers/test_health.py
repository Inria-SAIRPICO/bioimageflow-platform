"""Tests for the health endpoint."""

import httpx
import pytest

from bioimageflow_server import version

pytestmark = pytest.mark.anyio


async def test_health_returns_200(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


async def test_health_returns_expected_payload(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_source_release_reports_its_version_without_distribution_metadata(tmp_path, monkeypatch):
    def missing_distribution(_name):
        raise version.importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(version.importlib.metadata, "version", missing_distribution)
    monkeypatch.setattr(version, "__file__", str(tmp_path / "src/bioimageflow_server/version.py"))
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "bioimageflow-server"\nversion = "0.1.30"\n')
    assert version.get_application_version() == "0.1.30"
    project.write_text('[project]\nname = "another-project"\nversion = "9.9.9"\n')
    assert version.get_application_version() == "0.0.0-dev"
    project.write_text('invalid TOML !')
    assert version.get_application_version() == "0.0.0-dev"
    project.unlink()
    assert version.get_application_version() == "0.0.0-dev"
