"""Application version for installed distributions and launcher source archives."""

import importlib.metadata
from pathlib import Path
import tomllib


def get_application_version() -> str:
    try:
        return importlib.metadata.version("bioimageflow-server")
    except importlib.metadata.PackageNotFoundError:
        # Module entrypoints run verified sources without installing the app.
        try:
            project = tomllib.loads(
                (Path(__file__).resolve().parents[2] / "pyproject.toml").read_text()
            ).get("project", {})
            if isinstance(project, dict):
                version = project.get("version")
                if project.get("name") == "bioimageflow-server" and isinstance(version, str) and version:
                    return version
        except (OSError, ValueError):
            pass
        return "0.0.0-dev"
