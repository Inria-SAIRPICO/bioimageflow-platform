from __future__ import annotations

from pathlib import Path

from bioimageflow_server.logging_config import default_log_config_path, resolve_log_config_path


def test_default_log_config_path_points_to_packaged_yaml() -> None:
    path = Path(default_log_config_path())

    assert path.name == "logging.yaml"
    assert path.is_file()
    assert "bioimageflow_server" in path.read_text(encoding="utf-8")


def test_resolve_log_config_path_accepts_override() -> None:
    assert resolve_log_config_path("/tmp/logging.yaml") == "/tmp/logging.yaml"
